"""Open-Meteo API clients for weather and air quality data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession

from .base import BaseAPIClient

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
METERS_PER_MILE = 1609.344

THUNDERSTORM_CODES = {95, 96, 99}

WEATHER_CODE_TEXT = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
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
    condition_text: str | None
    has_thunderstorm: bool
    hourly_wind: list[float]
    hourly_temp: list[float]
    hourly_uv: list[float]
    hourly_times: list[str]
    hourly_weather_codes: list[int]


@dataclass(frozen=True)
class AQIData:
    """Parsed air quality data from Open-Meteo."""

    aqi: int | None
    pm25: float | None
    pm10: float | None
    ozone: float | None


class OpenMeteoWeatherClient(BaseAPIClient):
    """Client for Open-Meteo Weather API."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)

    async def fetch(self, latitude: float, longitude: float) -> WeatherData:
        """Fetch current weather and hourly forecast."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
            "temperature_2m,uv_index,visibility,"
            "precipitation_probability,weather_code",
            "hourly": "wind_speed_10m,temperature_2m,uv_index,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 2,
        }
        data = await self._get_json(WEATHER_URL, params=params)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> WeatherData:
        current = data.get("current", {})
        hourly = data.get("hourly", {})

        visibility_m = current.get("visibility")
        visibility_mi = (visibility_m / METERS_PER_MILE) if visibility_m is not None else None

        weather_code = current.get("weather_code")
        condition = WEATHER_CODE_TEXT.get(weather_code) if weather_code is not None else None

        return WeatherData(
            wind_speed=current.get("wind_speed_10m"),
            wind_gusts=current.get("wind_gusts_10m"),
            wind_direction=current.get("wind_direction_10m"),
            air_temp=current.get("temperature_2m"),
            uv_index=current.get("uv_index"),
            visibility=visibility_mi,
            precipitation_probability=current.get("precipitation_probability"),
            condition_text=condition,
            has_thunderstorm=(weather_code in THUNDERSTORM_CODES if weather_code is not None else False),
            hourly_wind=hourly.get("wind_speed_10m", []),
            hourly_temp=hourly.get("temperature_2m", []),
            hourly_uv=hourly.get("uv_index", []),
            hourly_times=hourly.get("time", []),
            hourly_weather_codes=hourly.get("weather_code", []),
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
        }
        data = await self._get_json(AQI_URL, params=params)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> AQIData:
        current = data.get("current", {})
        return AQIData(
            aqi=current.get("us_aqi"),
            pm25=current.get("pm2_5"),
            pm10=current.get("pm10"),
            ozone=current.get("ozone"),
        )
