"""NWS overlay on a real config entry (Lake Natoma is in the contiguous US)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    AQI_URL,
    LAKE_LOCATION,
    LAKE_SUBENTRY_ID,
    NWS_GRID_URL,
    NWS_POINTS_URL,
    USGS_URL,
    WEATHER_URL,
    make_weather_payload,
    setup_integration,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")


def _grid(wind_kmh: float = 32.19, temp_c: float = 25.0) -> dict:
    """An NWS gridpoint payload covering the six hours around the frozen clock."""
    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    period = f"{start.isoformat()}/PT6H"
    return {
        "properties": {
            "temperature": {"values": [{"validTime": period, "value": temp_c}]},
            "windSpeed": {"values": [{"validTime": period, "value": wind_kmh}]},
        }
    }


def _serve(aioclient_mock, grid: dict | None = None, *, grid_status: int = 200) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, json={"features": []})
    aioclient_mock.get(NWS_POINTS_URL, json={"properties": {"forecastGridData": NWS_GRID_URL}})
    aioclient_mock.get(NWS_GRID_URL, status=grid_status, json=grid or _grid())


def _calls(aioclient_mock, url: str) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == url)


async def _tick(hass, freezer, minutes: int) -> None:
    freezer.tick(timedelta(minutes=minutes, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _conditions(config_entry):
    return config_entry.runtime_data[LAKE_SUBENTRY_ID].data


async def test_nws_overrides_wind_and_temperature(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    conditions = _conditions(config_entry)
    assert conditions.wind_speed == 20.0  # 32.19 km/h
    assert conditions.air_temp == 77.0
    assert conditions.hourly_wind[0] == 20.0
    # UV and conditions still come from Open-Meteo.
    assert conditions.uv_index == make_weather_payload()["current"]["uv_index"]


async def test_nws_is_polled_hourly_and_resolved_once(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    for _ in range(5):
        await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, NWS_GRID_URL) == 1

    await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, NWS_GRID_URL) == 2
    assert sum(1 for call in aioclient_mock.mock_calls if "/points/" in str(call[1])) == 1


async def test_nws_outage_falls_back_to_open_meteo(hass: HomeAssistant, config_entry, aioclient_mock, freezer, caplog):
    # 404 rather than 5xx: the client's 5xx retry sleeps, and the frozen clock never wakes it.
    _serve(aioclient_mock, grid_status=404)
    await setup_integration(hass, config_entry)

    assert _conditions(config_entry).wind_speed == make_weather_payload()["current"]["wind_speed_10m"]
    assert "NWS data for Lake Natoma is unavailable" in caplog.text
    # Retried after 15 minutes, not on every poll.
    await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, NWS_GRID_URL) == 1
    await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, NWS_GRID_URL) == 2


@pytest.mark.parametrize("location_data", [{**LAKE_LOCATION, "latitude": 51.5, "longitude": -0.12}])
async def test_outside_the_us_uses_open_meteo_only(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    assert not any("weather.gov" in str(call[1]) for call in aioclient_mock.mock_calls)
