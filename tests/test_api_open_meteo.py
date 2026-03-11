"""Tests for Open-Meteo API clients."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.paddle_conditions.api.open_meteo import (
    AQIData,
    OpenMeteoAQIClient,
    OpenMeteoWeatherClient,
    WeatherData,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def weather_response():
    return json.loads((FIXTURES / "open_meteo_weather.json").read_text())


@pytest.fixture
def aqi_response():
    return json.loads((FIXTURES / "open_meteo_aqi.json").read_text())


def _mock_get(data):
    """Create a mock session.get that returns JSON data."""
    resp = MagicMock()
    resp.json = AsyncMock(return_value=data)
    resp.raise_for_status = MagicMock()
    return AsyncMock(return_value=resp)


# --- Weather client tests ---


async def test_fetch_weather_success(mock_session, weather_response):
    mock_session.get = _mock_get(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)

    assert isinstance(data, WeatherData)
    assert data.wind_speed == 8.5
    assert data.wind_gusts == 14.2
    assert data.wind_direction == 225
    assert data.air_temp == 72.3
    assert data.uv_index == 5.1
    assert data.precipitation_probability == 10


async def test_fetch_weather_visibility_conversion(mock_session, weather_response):
    """Visibility comes in meters, must be converted to miles."""
    mock_session.get = _mock_get(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    # 24140 meters / 1609.344 ≈ 15 miles
    assert data.visibility is not None
    assert data.visibility > 10


async def test_fetch_weather_thunderstorm_detection(mock_session):
    """Weather code 95/96/99 should set has_thunderstorm=True."""
    thunderstorm_response = {
        "current": {
            "wind_speed_10m": 15.0,
            "wind_gusts_10m": 25.0,
            "wind_direction_10m": 180,
            "temperature_2m": 80.0,
            "uv_index": 3.0,
            "visibility": 8000.0,
            "precipitation_probability": 70,
            "weather_code": 95,
        },
        "hourly": {
            "time": [],
            "wind_speed_10m": [],
            "temperature_2m": [],
            "uv_index": [],
            "weather_code": [],
        },
    }
    mock_session.get = _mock_get(thunderstorm_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.has_thunderstorm is True


async def test_fetch_weather_no_thunderstorm(mock_session, weather_response):
    """Non-thunderstorm weather codes should set has_thunderstorm=False."""
    mock_session.get = _mock_get(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.has_thunderstorm is False


async def test_fetch_weather_hourly_data(mock_session, weather_response):
    """Hourly forecast arrays should be parsed."""
    mock_session.get = _mock_get(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.hourly_wind == [5.0, 6.2]
    assert data.hourly_temp == [65.0, 66.5]
    assert data.hourly_uv == [0, 0.5]
    assert len(data.hourly_times) == 2


async def test_fetch_weather_api_error(mock_session):
    """HTTP errors should raise APIError."""
    from aiohttp import ClientResponseError

    from custom_components.paddle_conditions.api.base import APIError

    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(request_info=MagicMock(), history=(), status=500, message="Server Error")
    )
    mock_session.get = AsyncMock(return_value=resp)

    client = OpenMeteoWeatherClient(mock_session)
    client._retries = 0
    with pytest.raises(APIError):
        await client.fetch(latitude=38.637, longitude=-121.227)


# --- AQI client tests ---


async def test_fetch_aqi_success(mock_session, aqi_response):
    mock_session.get = _mock_get(aqi_response)

    client = OpenMeteoAQIClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)

    assert isinstance(data, AQIData)
    assert data.aqi == 42
    assert data.pm25 == 8.5
    assert data.pm10 == 15.2
    assert data.ozone == 35.0


async def test_fetch_aqi_missing_fields(mock_session):
    """Missing fields should be None, not crash."""
    mock_session.get = _mock_get({"current": {"us_aqi": 50}})

    client = OpenMeteoAQIClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.aqi == 50
    assert data.pm25 is None
