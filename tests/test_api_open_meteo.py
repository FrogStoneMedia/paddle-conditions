"""Tests for Open-Meteo API clients."""

import json
from pathlib import Path

import pytest

from custom_components.paddle_conditions.api.base import APIError
from custom_components.paddle_conditions.api.open_meteo import (
    AQIData,
    OpenMeteoAQIClient,
    OpenMeteoWeatherClient,
    WeatherData,
)

from .conftest import mock_get_error, mock_get_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def weather_response():
    return json.loads((FIXTURES / "open_meteo_weather.json").read_text())


@pytest.fixture
def aqi_response():
    return json.loads((FIXTURES / "open_meteo_aqi.json").read_text())


# --- Weather client tests ---


async def test_fetch_weather_success(mock_session, weather_response):
    mock_session.get = mock_get_json(weather_response)

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
    mock_session.get = mock_get_json(weather_response)

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
    mock_session.get = mock_get_json(thunderstorm_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.has_thunderstorm is True


async def test_fetch_weather_no_thunderstorm(mock_session, weather_response):
    """Non-thunderstorm weather codes should set has_thunderstorm=False."""
    mock_session.get = mock_get_json(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.has_thunderstorm is False


async def test_fetch_weather_hourly_data(mock_session, weather_response):
    """Hourly forecast arrays should be parsed."""
    mock_session.get = mock_get_json(weather_response)

    client = OpenMeteoWeatherClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.hourly_wind == [5.0, 6.2]
    assert data.hourly_temp == [65.0, 66.5]
    assert data.hourly_uv == [0, 0.5]
    assert len(data.hourly_times) == 2


async def test_fetch_weather_api_error(mock_session):
    """HTTP errors should raise APIError."""
    mock_session.get = mock_get_error(500, "Server Error")

    client = OpenMeteoWeatherClient(mock_session)
    client._retries = 0
    with pytest.raises(APIError):
        await client.fetch(latitude=38.637, longitude=-121.227)


# --- AQI client tests ---


async def test_fetch_aqi_success(mock_session, aqi_response):
    mock_session.get = mock_get_json(aqi_response)

    client = OpenMeteoAQIClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)

    assert isinstance(data, AQIData)
    assert data.aqi == 42
    assert data.pm25 == 8.5
    assert data.pm10 == 15.2
    assert data.ozone == 35.0


async def test_fetch_aqi_missing_fields(mock_session):
    """Missing fields should be None, not crash."""
    mock_session.get = mock_get_json({"current": {"us_aqi": 50}})

    client = OpenMeteoAQIClient(mock_session)
    data = await client.fetch(latitude=38.637, longitude=-121.227)
    assert data.aqi == 50
    assert data.pm25 is None


# --- Forecast window and time handling ---


async def test_fetch_weather_requests_forward_utc_window(mock_session, weather_response):
    """Hourly data must start at the current hour and come back in UTC."""
    mock_session.get = mock_get_json(weather_response)

    await OpenMeteoWeatherClient(mock_session).fetch(latitude=38.637, longitude=-121.227)

    params = mock_session.get.call_args.kwargs["params"]
    # forecast_hours sets the hourly window (starting now); forecast_days only sizes the daily sunrise/sunset.
    assert params["forecast_hours"] == 48
    assert params["daily"] == "sunrise,sunset"
    assert params["timezone"] == "GMT"
    hourly = params["hourly"].split(",")
    assert "wind_gusts_10m" in hourly
    assert "precipitation_probability" in hourly


async def test_fetch_weather_includes_todays_daylight_after_utc_midnight(mock_session, weather_response):
    """West of Greenwich the UTC date turns over before sunset (5 PM in California, 2 PM in Hawaii).

    The daily list starts at the current UTC date, so without a past day the spot's
    own afternoon was missing and the cards planned and charted tomorrow as "today".
    """
    mock_session.get = mock_get_json(weather_response)

    await OpenMeteoWeatherClient(mock_session).fetch(latitude=21.2766, longitude=-157.8284)

    params = mock_session.get.call_args.kwargs["params"]
    assert params["past_days"] == 1
    # forecast_hours still starts the hourly series now, past_days only adds a daily row.
    assert params["forecast_hours"] == 48


async def test_fetch_weather_hourly_times_are_utc_aware(mock_session):
    """Offset-free GMT timestamps are returned as explicit UTC ISO strings."""
    response = {
        "current": {"wind_speed_10m": 3.0, "weather_code": 0},
        "hourly": {
            "time": ["2026-10-21T19:00", "2026-10-21T20:00"],
            "wind_speed_10m": [3.0, 4.0],
            "wind_gusts_10m": [6.0, 7.0],
            "temperature_2m": [70.0, 71.0],
            "uv_index": [2.0, 1.0],
            "precipitation_probability": [5, 10],
            "weather_code": [0, 1],
        },
    }
    mock_session.get = mock_get_json(response)

    data = await OpenMeteoWeatherClient(mock_session).fetch(latitude=38.6, longitude=-121.2)

    assert data.hourly_times == ["2026-10-21T19:00:00+00:00", "2026-10-21T20:00:00+00:00"]
    assert data.hourly_gusts == [6.0, 7.0]


async def test_fetch_weather_keeps_missing_hourly_values_as_none(mock_session):
    """Open-Meteo sends null for hours it has no value for; keep it None, don't invent zeros."""
    response = {
        "current": {"wind_speed_10m": 3.0, "weather_code": 0},
        "hourly": {
            "time": ["2026-10-21T19:00"],
            "wind_speed_10m": [None],
            "temperature_2m": [None],
            "uv_index": [None],
            "precipitation_probability": [None],
            "weather_code": [None],
        },
    }
    mock_session.get = mock_get_json(response)

    data = await OpenMeteoWeatherClient(mock_session).fetch(latitude=38.6, longitude=-121.2)

    assert data.hourly_wind == [None]
    assert data.hourly_gusts == [None]
    assert data.hourly_precip == [None]
