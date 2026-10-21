"""Coordinator behaviour on a real config entry: freshness, cache, setup failures, forecast."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.paddle_conditions.cache import PaddleCache, location_fingerprint
from custom_components.paddle_conditions.const import DOMAIN

from .conftest import (
    AQI_URL,
    LAKE_SUBENTRY_ID,
    NOAA_URL,
    USGS_URL,
    WEATHER_URL,
    make_weather_payload,
    setup_integration,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")

SCORE = "sensor.lake_natoma_paddle_score"
FORECAST = "sensor.lake_natoma_3_hour_forecast"


def _serve(aioclient_mock, weather=None, *, weather_exc=None):
    """Register upstream responses; weather can be a payload or an exception."""
    aioclient_mock.clear_requests()
    if weather_exc is not None:
        aioclient_mock.get(WEATHER_URL, exc=weather_exc)
    else:
        aioclient_mock.get(WEATHER_URL, json=weather or make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, json={"features": []})
    aioclient_mock.get(NOAA_URL, json={"data": []})


async def _tick(hass, freezer, minutes: int) -> None:
    # One second past the mark: the coordinator's schedule carries sub-second jitter.
    freezer.tick(timedelta(minutes=minutes, seconds=1))
    async_fire_time_changed(hass)
    # Scheduled refreshes run as entry background tasks.
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_setup_retries_when_weather_is_down_and_nothing_is_cached(
    hass: HomeAssistant, config_entry, aioclient_mock
):
    """No data at all on a fresh install must surface as ConfigEntryNotReady."""
    _serve(aioclient_mock, weather_exc=TimeoutError())

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_short_weather_outage_keeps_last_good_conditions(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    """One failed poll inside the freshness window keeps the last score available."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    good = hass.states.get(SCORE).state

    _serve(aioclient_mock, weather_exc=TimeoutError())
    await _tick(hass, freezer, 10)

    assert hass.states.get(SCORE).state == good


async def test_long_weather_outage_makes_entities_unavailable(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    """Old conditions must not stay on screen as if they were current."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    _serve(aioclient_mock, weather_exc=TimeoutError())
    for _ in range(8):  # 80 minutes of failed 10-minute polls
        await _tick(hass, freezer, 10)

    assert hass.states.get(SCORE).state == STATE_UNAVAILABLE

    _serve(aioclient_mock)
    await config_entry.runtime_data[LAKE_SUBENTRY_ID].async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(SCORE).state != STATE_UNAVAILABLE


async def test_restart_with_weather_down_uses_fresh_cache(
    hass: HomeAssistant, config_entry, aioclient_mock, hass_storage
):
    """A recent cached reading for the same location lets setup succeed offline."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    good = hass.states.get(SCORE).state
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    _serve(aioclient_mock, weather_exc=TimeoutError())
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(SCORE).state == good


async def test_cache_for_a_changed_location_is_ignored(hass: HomeAssistant, config_entry, aioclient_mock):
    """Cached conditions for other coordinates must never be shown for this location."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    subentry = config_entry.subentries[LAKE_SUBENTRY_ID]
    hass.config_entries.async_update_subentry(config_entry, subentry, data={**subentry.data, "latitude": 40.0})
    _serve(aioclient_mock, weather_exc=TimeoutError())
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_cache_is_removed_with_the_entry(
    hass: HomeAssistant, config_entry, aioclient_mock, hass_storage, freezer
):
    """Deleting the integration leaves no per-location cache behind."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    await _tick(hass, freezer, 1)  # let the delayed save land
    key = f"{DOMAIN}.{config_entry.entry_id}.conditions"
    assert key in hass_storage

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert key not in hass_storage


async def test_cache_drops_locations_that_no_longer_exist(hass: HomeAssistant, config_entry):
    """Stale per-location rows are pruned when the cache loads."""
    cache = PaddleCache(hass, config_entry.entry_id)
    await cache.async_load(keep={"gone"})
    cache._locations = {"gone": {"fingerprint": "x", "conditions": {}}, "kept": {"fingerprint": "y", "conditions": {}}}
    await cache.async_load(keep={"kept"})
    assert set(cache._locations) <= {"kept"}


def test_fingerprint_changes_with_location_and_scoring_options():
    base = location_fingerprint({"latitude": 1.0, "longitude": 2.0}, {})
    assert base == location_fingerprint({"longitude": 2.0, "latitude": 1.0}, {})
    assert base != location_fingerprint({"latitude": 1.5, "longitude": 2.0}, {})
    assert base != location_fingerprint({"latitude": 1.0, "longitude": 2.0}, {"profile": "racing"})
    assert base == location_fingerprint({"latitude": 1.0, "longitude": 2.0}, {"update_interval": 30})


async def test_forecast_starts_now_and_scores_rain(hass: HomeAssistant, config_entry, aioclient_mock):
    """Blocks start at the current hour, and a wet block scores below a dry one."""
    payload = make_weather_payload()
    payload["hourly"]["precipitation_probability"] = [0, 0, 0] + [100] * 45
    _serve(aioclient_mock, payload)
    await setup_integration(hass, config_entry)

    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_update_entity(FORECAST, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    blocks = hass.states.get(FORECAST).attributes["blocks"]
    start = dt_util.parse_datetime(blocks[0]["start"])
    assert start is not None and start.tzinfo is not None
    assert abs((start - dt_util.utcnow()).total_seconds()) < 3600
    assert blocks[0]["score"] > blocks[1]["score"]


async def test_forecast_tolerates_missing_hourly_values(hass: HomeAssistant, config_entry, aioclient_mock):
    """Nulls in Open-Meteo's hourly arrays must not break the update."""
    payload = make_weather_payload()
    for key in ("wind_speed_10m", "wind_gusts_10m", "temperature_2m", "uv_index", "precipitation_probability"):
        payload["hourly"][key][0] = None
        payload["hourly"][key][-1] = None
    _serve(aioclient_mock, payload)

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(SCORE).state not in (STATE_UNAVAILABLE, "unknown")


# --- Ported from the MagicMock-based coordinator and setup tests ---------------


async def test_update_interval_option_is_used(hass: HomeAssistant, config_entry, mock_apis):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"update_interval": 30})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.runtime_data[LAKE_SUBENTRY_ID].update_interval == timedelta(minutes=30)


async def test_air_quality_outage_degrades_and_logs_once(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer, caplog
):
    """A failing optional source drops its factor and is logged once per outage."""
    _serve(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, exc=TimeoutError())
    aioclient_mock.get(USGS_URL, json={"features": []})

    await setup_integration(hass, config_entry)
    await _tick(hass, freezer, 10)
    await _tick(hass, freezer, 10)

    state = hass.states.get(SCORE)
    assert state.state not in (STATE_UNAVAILABLE, "unknown")
    assert "air_quality" in state.attributes["missing_factors"]
    assert caplog.text.count("Air quality data for Lake Natoma is unavailable") == 1


@pytest.mark.parametrize(
    ("usgs_temp_c", "noaa_temp_f", "expected_f"),
    [(16.0, 55.0, 60.8), (None, 55.0, 55.0)],
    ids=["usgs-preferred", "noaa-fallback"],
)
async def test_water_temperature_source_preference(
    hass: HomeAssistant, config_entry, aioclient_mock, usgs_temp_c, noaa_temp_f, expected_f
):
    subentry = dict(config_entry.subentries[LAKE_SUBENTRY_ID].data)
    features = []
    if usgs_temp_c is not None:
        features.append(
            {
                "properties": {
                    "parameter_code": "00010",
                    "value": str(usgs_temp_c),
                    "unit_of_measure": "degC",
                    "time": dt_util.utcnow().isoformat(),
                }
            }
        )
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, json={"features": features})
    aioclient_mock.get(
        NOAA_URL, json={"data": [{"t": dt_util.utcnow().strftime("%Y-%m-%d %H:%M"), "v": str(noaa_temp_f)}]}
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_subentry(
        config_entry, config_entry.subentries[LAKE_SUBENTRY_ID], data={**subentry, "noaa_station_id": "9414290"}
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The test instance is metric, so HA shows the Fahrenheit native value in Celsius.
    expected_c = (expected_f - 32) * 5 / 9
    assert float(hass.states.get("sensor.lake_natoma_water_temperature").state) == pytest.approx(expected_c, abs=0.1)


async def test_forecast_blocks_use_peak_wind(hass: HomeAssistant, config_entry, aioclient_mock):
    payload = make_weather_payload()
    payload["hourly"]["wind_speed_10m"][:6] = [3.0, 5.0, 11.0, 4.0, 6.0, 14.0]
    _serve(aioclient_mock, payload)
    await setup_integration(hass, config_entry)

    blocks = config_entry.runtime_data[LAKE_SUBENTRY_ID].data.forecast_blocks
    assert len(blocks) == 8
    assert [blocks[0].wind_mph, blocks[1].wind_mph] == [11.0, 14.0]


async def test_empty_hourly_series_produces_no_blocks(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock, make_weather_payload(hours=0))
    await setup_integration(hass, config_entry)

    assert config_entry.runtime_data[LAKE_SUBENTRY_ID].data.forecast_blocks == []


async def test_entry_without_locations_loads_and_unloads(hass: HomeAssistant, mock_apis):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.paddle_conditions.config_flow import PaddleConfigFlow

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        minor_version=PaddleConfigFlow.MINOR_VERSION,
        subentries_data=[
            {"data": {}, "subentry_id": "other", "subentry_type": "something_else", "title": "x", "unique_id": None}
        ],
    )
    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data == {}

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


# --- USGS throttle, API key and rate-limit repair ---------------------------


def _usgs_calls(aioclient_mock) -> list:
    return [call for call in aioclient_mock.mock_calls if str(call[1]).startswith(USGS_URL)]


def _serve_usgs(aioclient_mock, **kwargs) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, **kwargs)


def _flow(observed_minutes_ago: int = 15, value: str = "1500") -> dict:
    """A USGS latest-continuous payload whose observation time is relative to the frozen clock."""
    observed = (dt_util.utcnow() - timedelta(minutes=observed_minutes_ago)).isoformat()
    return {
        "features": [
            {"properties": {"parameter_code": "00060", "value": value, "unit_of_measure": "ft^3/s", "time": observed}}
        ]
    }


async def test_usgs_is_polled_hourly_without_a_key(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    """USGS updates every 15 min and keyless quota is small: fetch at most hourly."""
    _serve_usgs(aioclient_mock, json=_flow())
    await setup_integration(hass, config_entry)
    for _ in range(5):
        await _tick(hass, freezer, 10)
    assert len(_usgs_calls(aioclient_mock)) == 1

    await _tick(hass, freezer, 10)
    assert len(_usgs_calls(aioclient_mock)) == 2


async def test_usgs_key_is_sent_and_allows_15_minute_polling(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"usgs_api_key": "k-123"})
    _serve_usgs(aioclient_mock, json=_flow())
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 10)
    await _tick(hass, freezer, 10)

    calls = _usgs_calls(aioclient_mock)
    assert len(calls) == 2
    assert calls[0][3]["X-Api-Key"] == "k-123"


async def test_usgs_rate_limit_raises_repair_and_keeps_last_reading(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    from homeassistant.helpers import issue_registry as ir

    _serve_usgs(aioclient_mock, json=_flow())
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data[LAKE_SUBENTRY_ID]
    assert coordinator.data.streamflow_cfs == 1500.0

    _serve_usgs(aioclient_mock, status=429, headers={"Retry-After": "7200"})
    await _tick(hass, freezer, 61)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "usgs_rate_limited")
    assert issue is not None and issue.translation_key == "usgs_rate_limited"
    assert coordinator.data.streamflow_cfs == 1500.0  # last reading, still under 2 h old

    # Retry-After is honoured: no new USGS call before it expires.
    await _tick(hass, freezer, 61)
    assert len(_usgs_calls(aioclient_mock)) == 1

    _serve_usgs(aioclient_mock, json=_flow())
    await _tick(hass, freezer, 61)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "usgs_rate_limited") is None


async def test_reading_expires_by_observation_time(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    """A reading older than six hours is dropped, even if USGS keeps serving it."""
    _serve_usgs(aioclient_mock, json=_flow())
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data[LAKE_SUBENTRY_ID]
    assert coordinator.data.streamflow_cfs == 1500.0

    _serve_usgs(aioclient_mock, exc=TimeoutError())
    for _ in range(7):
        await _tick(hass, freezer, 61)

    assert coordinator.data.streamflow_cfs is None


async def test_stale_gauge_is_not_reported_as_current(hass: HomeAssistant, config_entry, aioclient_mock):
    """A gauge that stopped reporting a week ago returns HTTP 200 with its last value; ignore it."""
    _serve_usgs(aioclient_mock, json=_flow(observed_minutes_ago=7 * 24 * 60))
    await setup_integration(hass, config_entry)

    assert config_entry.runtime_data[LAKE_SUBENTRY_ID].data.streamflow_cfs is None


async def test_usgs_rate_limit_is_honoured_during_a_weather_outage(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    from homeassistant.helpers import issue_registry as ir

    _serve_usgs(aioclient_mock, json=_flow())
    await setup_integration(hass, config_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(WEATHER_URL, exc=TimeoutError())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, status=429, headers={"Retry-After": "7200"})
    await _tick(hass, freezer, 61)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "usgs_rate_limited") is not None

    await _tick(hass, freezer, 61)
    assert len(_usgs_calls(aioclient_mock)) == 1


async def test_repair_stays_while_any_location_is_rate_limited(hass: HomeAssistant, aioclient_mock, freezer):
    """One location answering must not clear the repair while another is still limited."""
    from homeassistant.helpers import issue_registry as ir
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.paddle_conditions.config_flow import PaddleConfigFlow

    from .conftest import LAKE_LOCATION

    def loc(sid: str, station: str) -> dict:
        data = {**LAKE_LOCATION, "name": sid, "usgs_station_id": station}
        return {"data": data, "subentry_id": sid, "subentry_type": "location", "title": sid, "unique_id": None}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        minor_version=PaddleConfigFlow.MINOR_VERSION,
        subentries_data=[loc("a", "111"), loc("b", "222")],
    )
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(f"{USGS_URL}?f=json&monitoring_location_id=USGS-111&parameter_code=00010,00060", status=429)
    aioclient_mock.get(f"{USGS_URL}?f=json&monitoring_location_id=USGS-222&parameter_code=00010,00060", json=_flow())

    await setup_integration(hass, entry)

    assert ir.async_get(hass).async_get_issue(DOMAIN, "usgs_rate_limited") is not None


async def test_removal_after_unload_leaves_no_cache(hass: HomeAssistant, config_entry, aioclient_mock, hass_storage):
    """Removing straight after an update (save still pending) must not leave a cache behind."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)  # Delayed save is pending, not written.

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert f"{DOMAIN}.{config_entry.entry_id}.conditions" not in hass_storage


async def test_forecast_blocks_score_air_quality_and_visibility(hass: HomeAssistant, config_entry, aioclient_mock):
    """Blocks score hourly AQI and visibility like the current score does, so they agree."""
    from .conftest import make_aqi_payload

    weather = make_weather_payload()
    weather["hourly"]["visibility"][3:6] = [400.0, 400.0, 400.0]  # Fog in the second block.
    aqi = make_aqi_payload()
    aqi["hourly"]["us_aqi"][6:9] = [180, 180, 180]  # Smoke in the third block.
    aioclient_mock.get(WEATHER_URL, json=weather)
    aioclient_mock.get(AQI_URL, json=aqi)
    aioclient_mock.get(USGS_URL, json={"features": []})
    await setup_integration(hass, config_entry)

    blocks = config_entry.runtime_data[LAKE_SUBENTRY_ID].data.forecast_blocks
    assert blocks[0].aqi == 30
    assert blocks[1].visibility_mi == pytest.approx(400 / 1609.344, abs=0.05)  # rounded to 0.1 mi
    assert blocks[2].aqi == 180
    assert blocks[1].score < blocks[0].score
    assert blocks[2].score < blocks[0].score


async def test_location_added_during_a_reload_is_not_lost(hass: HomeAssistant, config_entry, mock_apis):
    """HA only notifies listeners registered at that moment; a location added mid-reload must still load."""
    from homeassistant.config_entries import ConfigSubentry

    from .conftest import LAKE_LOCATION

    await setup_integration(hass, config_entry)

    def add(sid: str) -> None:
        hass.config_entries.async_add_subentry(
            config_entry,
            ConfigSubentry(
                data={**LAKE_LOCATION, "name": sid},
                subentry_type="location",
                title=sid,
                unique_id=None,
                subentry_id=sid,
            ),
        )

    add("first")  # Triggers a reload...
    await asyncio.sleep(0)
    add("second")  # ...and this lands while the entry is unloaded.
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert set(config_entry.runtime_data) == {LAKE_SUBENTRY_ID, "first", "second"}


async def test_location_edited_during_setup_is_applied(hass: HomeAssistant, config_entry, aioclient_mock):
    """HA edits subentries in place; an edit that lands while setup awaits I/O must still reload."""
    from unittest.mock import patch

    from custom_components.paddle_conditions.coordinator import PaddleCoordinator

    _serve(aioclient_mock)
    config_entry.add_to_hass(hass)
    original = PaddleCoordinator.async_config_entry_first_refresh

    async def refresh_then_edit(self):
        await original(self)
        if self.latitude == LAKE_LOCATION_LAT:  # Only during the first setup.
            sub = config_entry.subentries[LAKE_SUBENTRY_ID]
            hass.config_entries.async_update_subentry(config_entry, sub, data={**sub.data, "latitude": 40.0})

    with patch.object(PaddleCoordinator, "async_config_entry_first_refresh", refresh_then_edit):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.runtime_data[LAKE_SUBENTRY_ID].latitude == 40.0


LAKE_LOCATION_LAT = 38.637
