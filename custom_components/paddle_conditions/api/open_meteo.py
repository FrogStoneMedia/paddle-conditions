"""Open-Meteo API clients for weather and air quality data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientSession

from .base import BaseAPIClient

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
METERS_PER_MILE = 1609.344

FORECAST_HOURS = 48

THUNDERSTORM_CODES = {95, 96, 99}

# WMO weather interpretation codes -> stable keys (translated in strings.json).
WEATHER_CODE_CONDITIONS = {
    0: "clear_sky",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing_rime_fog",
    51: "light_drizzle",
    53: "moderate_drizzle",
    55: "dense_drizzle",
    56: "light_freezing_drizzle",
    57: "dense_freezing_drizzle",
    61: "slight_rain",
    63: "moderate_rain",
    65: "heavy_rain",
    66: "light_freezing_rain",
    67: "heavy_freezing_rain",
    71: "slight_snow",
    73: "moderate_snow",
    75: "heavy_snow",
    77: "snow_grains",
    80: "slight_rain_showers",
    81: "moderate_rain_showers",
    82: "violent_rain_showers",
    85: "slight_snow_showers",
    86: "heavy_snow_showers",
    95: "thunderstorm",
    96: "thunderstorm_with_slight_hail",
    99: "thunderstorm_with_heavy_hail",
}


@dataclass(frozen=True)
class WeatherData:
    """Parsed weather data from Open-Meteo."""

    wind_speed: float | None
    wind_gusts: float | None
    wind_direction: int | None
    air_temp: float | None
    uv_index: float | None
    visibility: float | None
    precipitation_probability: int | None
    condition: str | None  # Key from WEATHER_CODE_CONDITIONS
    has_thunderstorm: bool
    hourly_wind: list[float | None]
    hourly_gusts: list[float | None]
    hourly_temp: list[float | None]
    hourly_uv: list[float | None]
    hourly_times: list[str]
    hourly_weather_codes: list[int | None]
    hourly_precip: list[int | None]
    hourly_visibility: list[float | None]  # miles
    # (sunrise, sunset) per day at this location, UTC ISO 8601.
    daylight: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class AQIData:
    """Parsed air quality data from Open-Meteo."""

    aqi: int | None
    pm25: float | None
    pm10: float | None
    ozone: float | None
    # Hourly US AQI keyed by the same UTC ISO timestamps as the weather series.
    hourly_aqi: dict[str, int | None] = field(default_factory=dict)


class OpenMeteoWeatherClient(BaseAPIClient):
    """Client for Open-Meteo Weather API."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)

    async def fetch(self, latitude: float, longitude: float) -> WeatherData:
        """Fetch current weather and the next 48 hours, starting at the current hour, in UTC."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
            "temperature_2m,uv_index,visibility,"
            "precipitation_probability,weather_code",
            "hourly": (
                "wind_speed_10m,wind_gusts_10m,temperature_2m,uv_index,precipitation_probability,weather_code,visibility"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            # forecast_hours starts the series at the current hour; forecast_days
            # starts it at local midnight, which put past hours in the forecast.
            "daily": "sunrise,sunset",
            # Days are UTC dates, which turn over before sunset west of Greenwich;
            # a past day keeps this afternoon's daylight in the list.
            "past_days": 1,
            "forecast_days": 3,
            "forecast_hours": FORECAST_HOURS,
            "timezone": "GMT",
        }
        data = await self._get_json(WEATHER_URL, params=params)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> WeatherData:
        current = data.get("current", {})
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})
        times = hourly.get("time", [])
        count = len(times)

        def series(key: str) -> list[Any]:
            """Return an hourly series aligned to the time axis, padding gaps with None."""
            values = list(hourly.get(key) or [])[:count]
            return values + [None] * (count - len(values))

        visibility_m = current.get("visibility")
        visibility_mi = (visibility_m / METERS_PER_MILE) if visibility_m is not None else None

        weather_code = current.get("weather_code")
        condition = WEATHER_CODE_CONDITIONS.get(weather_code) if weather_code is not None else None

        return WeatherData(
            wind_speed=current.get("wind_speed_10m"),
            wind_gusts=current.get("wind_gusts_10m"),
            wind_direction=current.get("wind_direction_10m"),
            air_temp=current.get("temperature_2m"),
            uv_index=current.get("uv_index"),
            visibility=visibility_mi,
            precipitation_probability=current.get("precipitation_probability"),
            condition=condition,
            has_thunderstorm=(weather_code in THUNDERSTORM_CODES if weather_code is not None else False),
            hourly_wind=series("wind_speed_10m"),
            hourly_gusts=series("wind_gusts_10m"),
            hourly_temp=series("temperature_2m"),
            hourly_uv=series("uv_index"),
            # Requested in GMT, so the offset-free timestamps are UTC.
            hourly_times=[f"{t}:00+00:00" for t in times],
            hourly_weather_codes=series("weather_code"),
            hourly_precip=series("precipitation_probability"),
            hourly_visibility=[None if v is None else v / METERS_PER_MILE for v in series("visibility")],
            daylight=[
                (f"{rise}:00+00:00", f"{down}:00+00:00")
                for rise, down in zip(daily.get("sunrise") or [], daily.get("sunset") or [], strict=False)
                if rise and down
            ],
        )


class OpenMeteoAQIClient(BaseAPIClient):
    """Client for Open-Meteo Air Quality API."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)

    async def fetch(self, latitude: float, longitude: float) -> AQIData:
        """Fetch current air quality data."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi,pm2_5,pm10,ozone",
            "hourly": "us_aqi",
            "forecast_hours": FORECAST_HOURS,
            "timezone": "GMT",
        }
        data = await self._get_json(AQI_URL, params=params)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> AQIData:
        current = data.get("current", {})
        hourly = data.get("hourly", {})
        return AQIData(
            aqi=current.get("us_aqi"),
            pm25=current.get("pm2_5"),
            pm10=current.get("pm10"),
            ozone=current.get("ozone"),
            hourly_aqi=dict(
                zip((f"{t}:00+00:00" for t in hourly.get("time", [])), hourly.get("us_aqi", []), strict=False)
            ),
        )
