"""Tests for the NWS gridpoint client and the Open-Meteo overlay."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.paddle_conditions.api.base import APIError
from custom_components.paddle_conditions.api.nws import (
    NWS_URL,
    USER_AGENT,
    NWSClient,
    NWSForecast,
    NWSHour,
    is_us_location,
    overlay,
)
from custom_components.paddle_conditions.api.open_meteo import WeatherData

from .conftest import MockAsyncContextManager

GRID_URL = f"{NWS_URL}/gridpoints/STO/54,72"
POINTS = {"properties": {"gridId": "STO", "gridX": 54, "gridY": 72, "forecastGridData": GRID_URL}}
GRID = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [
                {"validTime": "2026-10-21T22:00:00+00:00/PT1H", "value": 20},
                {"validTime": "2026-10-21T23:00:00+00:00/PT1H", "value": None},
            ],
        },
        "windSpeed": {"values": [{"validTime": "2026-10-21T15:00:00-07:00/PT8H", "value": 16.09}]},
        "windGust": {"values": [{"validTime": "2026-10-21T22:00:00+00:00/P1DT2H", "value": 32.19}]},
        "windDirection": {"values": [{"validTime": "2026-10-21T22:00:00+00:00/PT1H", "value": 150.4}]},
        "probabilityOfPrecipitation": {"values": [{"validTime": "2026-10-21T22:00:00+00:00/PT30M", "value": 40}]},
    }
}
H22 = datetime(2026, 10, 21, 22, tzinfo=UTC)
H23 = datetime(2026, 10, 21, 23, tzinfo=UTC)


def _sequence(*payloads):
    responses = []
    for payload in payloads:
        resp = MagicMock()
        resp.json = AsyncMock(return_value=payload)
        resp.raise_for_status = MagicMock()
        responses.append(MockAsyncContextManager(resp))
    return MagicMock(side_effect=responses)


def _weather(**overrides) -> WeatherData:
    base = {
        "wind_speed": 3.0,
        "wind_gusts": 5.0,
        "wind_direction": 10,
        "air_temp": 60.0,
        "uv_index": 4.0,
        "visibility": 10.0,
        "precipitation_probability": 0,
        "condition": "clear_sky",
        "has_thunderstorm": False,
        "hourly_wind": [3.0, 3.0, 3.0],
        "hourly_gusts": [5.0, 5.0, 5.0],
        "hourly_temp": [60.0, 61.0, 62.0],
        "hourly_uv": [4.0, 4.0, 4.0],
        "hourly_times": ["2026-10-21T22:00:00+00:00", "2026-10-21T23:00:00+00:00", "2026-10-22T00:00:00+00:00"],
        "hourly_weather_codes": [0, 0, 0],
        "hourly_precip": [0, 0, 0],
        "hourly_visibility": [10.0, 10.0, 10.0],
    }
    return WeatherData(**{**base, **overrides})


def test_is_us_location():
    assert is_us_location(38.71, -121.16)
    assert not is_us_location(51.5, -0.12)
    assert not is_us_location(21.3, -157.8)  # Hawaii is outside the box, as in the API


async def test_fetch_resolves_gridpoint_once_and_converts_units(mock_session):
    mock_session.get = _sequence(POINTS, GRID, GRID)
    client = NWSClient(mock_session)

    forecast = await client.fetch(38.71, -121.16)
    await client.fetch(38.71, -121.16)

    urls = [call.args[0] for call in mock_session.get.call_args_list]
    assert urls == [f"{NWS_URL}/points/38.71,-121.16", GRID_URL, GRID_URL]
    assert mock_session.get.call_args.kwargs["headers"]["User-Agent"] == USER_AGENT
    assert forecast.hours[H22] == NWSHour(temp_f=68.0, wind_mph=10.0, gust_mph=20.0, wind_direction=150, precip_pct=40)
    # Null temperature is skipped; the 8 h wind period (from 15:00 PDT) and the 26 h gust period reach 23:00.
    assert forecast.hours[H23] == NWSHour(wind_mph=10.0, gust_mph=20.0)
    # P1DT2H from 22:00 covers 26 hours: through 23:00 the next day.
    assert forecast.hours[datetime(2026, 10, 22, 23, tzinfo=UTC)].gust_mph == 20.0
    assert datetime(2026, 10, 23, 0, tzinfo=UTC) not in forecast.hours


async def test_points_without_gridpoint_raise(mock_session):
    mock_session.get = _sequence({"properties": {}})
    with pytest.raises(APIError):
        await NWSClient(mock_session).fetch(38.71, -121.16)


def test_overlay_prefers_nws_and_keeps_open_meteo_elsewhere():
    forecast = NWSForecast(
        hours={
            H22: NWSHour(temp_f=68.0, wind_mph=10.0, gust_mph=20.0, wind_direction=150, precip_pct=40),
            H23: NWSHour(wind_mph=12.0),
        }
    )

    merged = overlay(_weather(), forecast, now=datetime(2026, 10, 21, 22, 20, tzinfo=UTC))

    assert (merged.wind_speed, merged.wind_gusts, merged.wind_direction) == (10.0, 20.0, 150)
    assert (merged.air_temp, merged.precipitation_probability) == (68.0, 40)
    assert merged.hourly_wind == [10.0, 12.0, 3.0]
    # No NWS value: Open-Meteo's stays (the API wrote 0 here).
    assert merged.hourly_temp == [68.0, 61.0, 62.0]
    assert merged.hourly_gusts == [20.0, 5.0, 5.0]
    # Open-Meteo only fields are untouched.
    assert (merged.uv_index, merged.visibility, merged.condition) == (4.0, 10.0, "clear_sky")


def test_overlay_ignores_a_stale_forecast_for_current_conditions():
    forecast = NWSForecast(hours={H22: NWSHour(wind_mph=10.0)})

    merged = overlay(_weather(), forecast, now=datetime(2026, 10, 22, 3, tzinfo=UTC))

    assert merged.wind_speed == 3.0
    assert merged.hourly_wind[0] == 10.0


def test_overlay_with_empty_forecast_is_a_no_op():
    weather = _weather()
    assert overlay(weather, NWSForecast(hours={}), now=H22) is weather
