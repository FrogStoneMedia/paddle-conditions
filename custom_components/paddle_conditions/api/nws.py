"""National Weather Service gridpoint forecasts, overlaid on Open-Meteo for US locations.

NWS forecasts handle large lakes better than Open-Meteo's model grid, so the
Paddle Conditions API uses NWS for wind, gusts, direction, temperature and
rain chance where it has them, and Open-Meteo for everything else (UV,
visibility, weather codes, sunrise and sunset). This mirrors that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientSession

from .base import APIError, BaseAPIClient
from .open_meteo import WeatherData

NWS_URL = "https://api.weather.gov"
# NWS asks every client to identify itself.
USER_AGENT = "PaddleConditions-HomeAssistant (github.com/FrogStoneMedia/paddle-conditions)"

_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")
_KMH_TO_MPH = 0.621371


def is_us_location(latitude: float, longitude: float) -> bool:
    """The contiguous US, where NWS gridpoints exist (same box as the API)."""
    return 24 <= latitude <= 50 and -125 <= longitude <= -66


@dataclass(frozen=True)
class NWSHour:
    """One forecast hour. None where NWS has no value for that hour."""

    temp_f: float | None = None
    wind_mph: float | None = None
    gust_mph: float | None = None
    wind_direction: int | None = None
    precip_pct: int | None = None


@dataclass(frozen=True)
class NWSForecast:
    """Hourly NWS forecast keyed by the start of each UTC hour."""

    hours: dict[datetime, NWSHour]


def _duration_hours(raw: str) -> int:
    """'PT1H' -> 1, 'P1DT6H' -> 30, 'PT30M' -> 1."""
    match = _DURATION.match(raw)
    if not match:
        return 1
    days, hours, minutes = (int(part) if part else 0 for part in match.groups())
    return max(1, days * 24 + hours + (1 if minutes else 0))


def _expand(series: Any, convert: Any) -> dict[datetime, Any]:
    """Expand NWS 'start/duration' periods into one value per UTC hour."""
    hourly: dict[datetime, Any] = {}
    for item in (series or {}).get("values") or []:
        value = item.get("value")
        if not isinstance(value, int | float) or isinstance(value, bool):
            continue
        start_raw, _, duration = str(item.get("validTime", "")).partition("/")
        try:
            start = datetime.fromisoformat(start_raw).astimezone(UTC)
        except ValueError:
            continue
        for hour in range(_duration_hours(duration)):
            hourly[start + timedelta(hours=hour)] = convert(value)
    return hourly


def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _kmh_to_mph(kmh: float) -> float:
    return round(kmh * _KMH_TO_MPH, 1)


class NWSClient(BaseAPIClient):
    """Client for api.weather.gov points and gridpoints."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)
        # Grid assignments don't change for a point.
        self._gridpoints: dict[tuple[float, float], str] = {}

    async def _gridpoint_url(self, latitude: float, longitude: float) -> str:
        key = (round(latitude, 4), round(longitude, 4))
        if key not in self._gridpoints:
            data = await self._get_json(f"{NWS_URL}/points/{key[0]},{key[1]}", headers=self._headers)
            url = (data or {}).get("properties", {}).get("forecastGridData")
            if not isinstance(url, str) or not url.startswith(f"{NWS_URL}/gridpoints/"):
                raise APIError(f"NWS has no gridpoint for {key[0]},{key[1]}")
            self._gridpoints[key] = url
        return self._gridpoints[key]

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}

    async def fetch(self, latitude: float, longitude: float) -> NWSForecast:
        """Fetch the hourly gridpoint forecast for a point."""
        data = await self._get_json(await self._gridpoint_url(latitude, longitude), headers=self._headers)
        props = (data or {}).get("properties") or {}
        series = {
            "temp_f": _expand(props.get("temperature"), _c_to_f),
            "wind_mph": _expand(props.get("windSpeed"), _kmh_to_mph),
            "gust_mph": _expand(props.get("windGust"), _kmh_to_mph),
            "wind_direction": _expand(props.get("windDirection"), round),
            "precip_pct": _expand(props.get("probabilityOfPrecipitation"), round),
        }
        times = set().union(*(s.keys() for s in series.values()))
        return NWSForecast(hours={t: NWSHour(**{k: s.get(t) for k, s in series.items()}) for t in times})


def overlay(weather: WeatherData, forecast: NWSForecast, now: datetime) -> WeatherData:
    """Open-Meteo with NWS wind, gusts, direction, temperature and rain chance where NWS has them."""
    if not forecast.hours:
        return weather

    def hour_of(stamp: str) -> NWSHour | None:
        try:
            return forecast.hours.get(datetime.fromisoformat(stamp).astimezone(UTC))
        except ValueError:
            return None

    hours = [hour_of(t) for t in weather.hourly_times]

    def merged(base: list[Any], field: str) -> list[Any]:
        out = list(base)
        for i, hour in enumerate(hours):
            if hour is not None and (value := getattr(hour, field)) is not None:
                out[i] = value
        return out

    # Current conditions: the NWS hour closest to now, as the API does, if it is close.
    closest = min(forecast.hours, key=lambda t: abs(t - now))
    current = forecast.hours[closest] if abs(closest - now) <= timedelta(hours=1) else NWSHour()

    def now_or(field: str, fallback: Any) -> Any:
        value = getattr(current, field)
        return fallback if value is None else value

    return replace(
        weather,
        wind_speed=now_or("wind_mph", weather.wind_speed),
        wind_gusts=now_or("gust_mph", weather.wind_gusts),
        wind_direction=now_or("wind_direction", weather.wind_direction),
        air_temp=now_or("temp_f", weather.air_temp),
        precipitation_probability=now_or("precip_pct", weather.precipitation_probability),
        hourly_wind=merged(weather.hourly_wind, "wind_mph"),
        hourly_gusts=merged(weather.hourly_gusts, "gust_mph"),
        hourly_temp=merged(weather.hourly_temp, "temp_f"),
        hourly_precip=merged(weather.hourly_precip, "precip_pct"),
    )
