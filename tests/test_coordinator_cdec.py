"""California CDEC gauges and curated stage baselines on a real config entry."""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.paddle_conditions.api.cdec import CDEC_TZ

from .conftest import (
    AQI_URL,
    CDEC_URL,
    LAKE_LOCATION,
    LAKE_SUBENTRY_ID,
    PC_STATIONS_URL,
    USGS_URL,
    WEATHER_URL,
    make_weather_payload,
    setup_integration,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")

RESERVOIR = {
    **LAKE_LOCATION,
    "name": "Folsom Lake",
    "usgs_station_id": "",
    "cdec_station_ids": "FOL, AFO",
    "reservoir_capacity_af": 977000,
    "dam_outflow_threshold_cfs": 8000,
    "spot_slug": None,
}
RIVER = {
    **LAKE_LOCATION,
    "name": "American River",
    "water_body_type": "river",
    "usgs_station_id": "",
    "optimal_cfs": 1500,
    "cdec_station_ids": "AFO",
    "spot_slug": "american-river",
}


def _record(sensor: int, value: float, minutes_ago: int = 20) -> dict:
    """A CDEC record observed *minutes_ago* before the frozen clock, stamped in PST like the real thing."""
    observed = (dt_util.utcnow() - timedelta(minutes=minutes_ago)).astimezone(CDEC_TZ)
    stamp = f"{observed.year}-{observed.month}-{observed.day} {observed.hour}:{observed.minute:02d}"
    return {"SENSOR_NUM": sensor, "obsDate": stamp, "date": stamp, "value": value, "dataFlag": " "}


def _cdec_url(station: str) -> re.Pattern[str]:
    return re.compile(re.escape(CDEC_URL) + rf"\?.*Stations={station}(&|$)")


def _serve(
    aioclient_mock, stations: dict[str, list[dict] | Exception], baselines: dict | None = None, baselines_status=200
) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, json={"features": []})
    for station, records in stations.items():
        if isinstance(records, Exception):
            aioclient_mock.get(_cdec_url(station), exc=records)
        else:
            aioclient_mock.get(_cdec_url(station), text=json.dumps(records))
    aioclient_mock.get(
        PC_STATIONS_URL.format(slug="american-river"),
        status=baselines_status,
        json={
            "slug": "american-river",
            "name": "American River",
            "type": "river",
            "lat": 38.6,
            "lng": -121.2,
            "stations": {"usgs": [], "noaa": [], "cdec": [{"id": "AFO"}]},
            "stageBaselines": baselines or {},
        },
    )


def _calls(aioclient_mock, prefix: str) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]).startswith(prefix))


async def _tick(hass, freezer, minutes: int) -> None:
    freezer.tick(timedelta(minutes=minutes, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _conditions(config_entry):
    return config_entry.runtime_data[LAKE_SUBENTRY_ID].data


def _baseline_months(sample_count: int = 120) -> dict:
    month = dt_util.utcnow().astimezone(CDEC_TZ).month
    return {
        "AFO": [
            {"month": month, "p10": 2, "p25": 3, "p50": 4, "p75": 6, "p90": 8, "p95": 10, "sampleCount": sample_count}
        ]
    }


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_reservoir_level_and_cdec_readings(hass: HomeAssistant, config_entry, aioclient_mock):
    """Nearest station first: FOL's storage and outflow, AFO fills in water temperature."""
    _serve(
        aioclient_mock,
        {
            "FOL": [_record(15, 586200, minutes_ago=200), _record(23, 3000, minutes_ago=200)],
            "AFO": [_record(25, 61.6), _record(15, 1)],
        },
    )
    await setup_integration(hass, config_entry)

    conditions = _conditions(config_entry)
    assert conditions.reservoir_storage_af == 586200
    assert conditions.reservoir_percent_full == 60.0
    assert conditions.dam_outflow_cfs == 3000
    assert conditions.water_temp == 61.6
    assert conditions.score.factors["reservoir_level"] == 100
    assert not conditions.score.vetoed


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_high_dam_release_vetoes(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock, {"FOL": [_record(23, 9500)], "AFO": []})
    await setup_integration(hass, config_entry)

    score = _conditions(config_entry).score
    assert score.vetoed
    assert score.veto_reason == "High dam release: 9500 CFS exceeds 8000 CFS threshold"


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_one_station_down_keeps_the_others(hass: HomeAssistant, config_entry, aioclient_mock, caplog):
    _serve(aioclient_mock, {"FOL": TimeoutError(), "AFO": [_record(25, 60.0)]})
    await setup_integration(hass, config_entry)

    assert _conditions(config_entry).water_temp == 60.0
    assert "CDEC data" not in caplog.text


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_cdec_down_is_logged_once_and_retried(hass: HomeAssistant, config_entry, aioclient_mock, freezer, caplog):
    _serve(aioclient_mock, {"FOL": TimeoutError(), "AFO": TimeoutError()})
    await setup_integration(hass, config_entry)
    await _tick(hass, freezer, 10)

    assert caplog.text.count("CDEC data for Folsom Lake is unavailable") == 1
    assert _conditions(config_entry).reservoir_storage_af is None
    # Retried on every poll while failing: two stations, and both requests each (one failing doesn't skip the other).
    assert _calls(aioclient_mock, CDEC_URL) == 8


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_cdec_is_polled_every_30_minutes(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    _serve(aioclient_mock, {"FOL": [_record(15, 500000)], "AFO": [_record(25, 60.0)]})
    await setup_integration(hass, config_entry)
    requests_per_poll = _calls(aioclient_mock, CDEC_URL)
    assert requests_per_poll == 4

    await _tick(hass, freezer, 10)
    await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, CDEC_URL) == requests_per_poll
    await _tick(hass, freezer, 10)
    assert _calls(aioclient_mock, CDEC_URL) == 2 * requests_per_poll


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_silent_station_is_rechecked_daily(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    """Spots list gauges that report none of our sensors (Oroville: six of nine); poll those once a day."""
    _serve(aioclient_mock, {"FOL": [_record(15, 500000)], "AFO": []})
    await setup_integration(hass, config_entry)
    assert _calls(aioclient_mock, CDEC_URL) == 4

    await _tick(hass, freezer, 30)
    assert _calls(aioclient_mock, CDEC_URL) == 6  # FOL only

    # A day on, AFO is asked again, and once it reports it is polled with the rest.
    for _ in range(46):  # to 23.5 hours after setup
        await _tick(hass, freezer, 30)
    assert _conditions(config_entry).water_temp is None
    _serve(aioclient_mock, {"FOL": [_record(15, 500000)], "AFO": [_record(25, 60.0)]})
    await _tick(hass, freezer, 30)
    assert _conditions(config_entry).water_temp == 60.0
    _serve(aioclient_mock, {"FOL": [_record(15, 500000)], "AFO": [_record(25, 60.0)]})
    await _tick(hass, freezer, 30)
    assert _calls(aioclient_mock, CDEC_URL) == 4


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_all_stations_silent(hass: HomeAssistant, config_entry, aioclient_mock, freezer, caplog):
    """No CDEC requests between daily checks, and silence isn't reported as an outage."""
    _serve(aioclient_mock, {"FOL": [], "AFO": []})
    await setup_integration(hass, config_entry)
    await _tick(hass, freezer, 30)
    await _tick(hass, freezer, 30)

    assert _calls(aioclient_mock, CDEC_URL) == 4
    assert _conditions(config_entry).reservoir_storage_af is None
    assert "CDEC data" not in caplog.text


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_cdec_readings_expire(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    """A reading reused between polls stops counting once it is six hours old."""
    _serve(aioclient_mock, {"FOL": [_record(15, 500000, minutes_ago=355)], "AFO": []})
    await setup_integration(hass, config_entry)
    assert _conditions(config_entry).reservoir_storage_af == 500000

    _serve(aioclient_mock, {"FOL": TimeoutError(), "AFO": TimeoutError()})
    await _tick(hass, freezer, 10)
    assert _conditions(config_entry).reservoir_storage_af is None


@pytest.mark.parametrize("location_data", [RIVER])
async def test_river_stage_scored_against_curated_baseline(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    _serve(aioclient_mock, {"AFO": [_record(1, 6.0), _record(20, 1500)]}, baselines=_baseline_months())
    await setup_integration(hass, config_entry)

    conditions = _conditions(config_entry)
    assert conditions.river_stage_ft == 6.0
    assert conditions.streamflow_cfs == 1500
    # SUP recreational: lower is better from the median; p75 scores 50.
    assert conditions.score.factors["river_stage"] == 50

    # Baselines are read once a day.
    await _tick(hass, freezer, 60)
    assert _calls(aioclient_mock, PC_STATIONS_URL.format(slug="american-river")) == 1


@pytest.mark.parametrize("location_data", [RIVER])
async def test_dangerous_river_stage_vetoes(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock, {"AFO": [_record(1, 10.5)]}, baselines=_baseline_months())
    await setup_integration(hass, config_entry)

    score = _conditions(config_entry).score
    assert score.vetoed
    assert score.veto_reason == "Dangerous water level"


@pytest.mark.parametrize("location_data", [RIVER])
async def test_thin_baseline_is_not_used(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock, {"AFO": [_record(1, 10.5)]}, baselines=_baseline_months(sample_count=59))
    await setup_integration(hass, config_entry)

    score = _conditions(config_entry).score
    assert not score.vetoed
    assert "river_stage" in score.missing_factors


@pytest.mark.parametrize("location_data", [RIVER])
async def test_baseline_outage_is_retried_hourly(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    # 404 rather than 5xx: the client's 5xx retry sleeps, and the frozen clock never wakes it.
    _serve(aioclient_mock, {"AFO": [_record(1, 6.0)]}, baselines_status=404)
    url = PC_STATIONS_URL.format(slug="american-river")
    await setup_integration(hass, config_entry)
    await _tick(hass, freezer, 30)
    assert _calls(aioclient_mock, url) == 1
    await _tick(hass, freezer, 31)
    assert _calls(aioclient_mock, url) == 2


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_weights_saved_before_cdec_factors_still_score_them(hass: HomeAssistant, config_entry, aioclient_mock):
    """2.0 saved all nine weights; the new factors fall back to the profile's."""
    nine = {
        "wind_speed": 0.3,
        "wind_gusts": 0.1,
        "air_quality": 0.2,
        "temperature": 0.15,
        "uv_index": 0.1,
        "visibility": 0.1,
        "precipitation": 0.05,
        "streamflow": 0.15,
        "tide": 0.1,
    }
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"weights": nine})
    _serve(aioclient_mock, {"FOL": [_record(15, 586200)], "AFO": []})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert "reservoir_level" in _conditions(config_entry).score.factors


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_cdec_sensors(hass: HomeAssistant, config_entry, aioclient_mock):
    from homeassistant.helpers import entity_registry as er

    _serve(aioclient_mock, {"FOL": [_record(15, 586200), _record(23, 3000)], "AFO": [_record(1, 6.25)]})
    await setup_integration(hass, config_entry)

    level = hass.states.get("sensor.folsom_lake_reservoir_level")
    assert level.state == "60.0"
    assert level.attributes["storage_acre_feet"] == 586200
    assert hass.states.get("sensor.folsom_lake_dam_outflow").state == "3000.0"
    # Metric test instance: feet shown as metres.
    assert float(hass.states.get("sensor.folsom_lake_river_stage").state) == pytest.approx(6.25 * 0.3048, abs=0.01)
    registry = er.async_get(hass)
    for key in ("turbidity", "dissolved_oxygen", "ph", "conductivity"):
        entity_id = registry.async_get_entity_id("sensor", "paddle_conditions", f"{LAKE_SUBENTRY_ID}_{key}")
        assert registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_cdec_sensors_off_without_cdec_stations(hass: HomeAssistant, config_entry, mock_apis):
    from homeassistant.helpers import entity_registry as er

    await setup_integration(hass, config_entry)

    registry = er.async_get(hass)
    for key in ("river_stage", "reservoir_level", "dam_outflow"):
        entity_id = registry.async_get_entity_id("sensor", "paddle_conditions", f"{LAKE_SUBENTRY_ID}_{key}")
        assert registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("location_data", [RESERVOIR])
async def test_failed_station_keeps_its_recent_reading(hass: HomeAssistant, config_entry, aioclient_mock, freezer):
    """FOL's high release stays a No-go when FOL times out on the next poll but AFO answers."""
    _serve(aioclient_mock, {"FOL": [_record(23, 9500)], "AFO": [_record(25, 60.0)]})
    await setup_integration(hass, config_entry)
    assert _conditions(config_entry).score.vetoed

    _serve(aioclient_mock, {"FOL": TimeoutError(), "AFO": [_record(25, 61.0)]})
    await _tick(hass, freezer, 30)

    conditions = _conditions(config_entry)
    assert conditions.water_temp == 61.0
    assert conditions.dam_outflow_cfs == 9500
    assert conditions.score.vetoed


@pytest.mark.parametrize("location_data", [{**RIVER, "usgs_station_id": ""}])
async def test_streamflow_sensor_enabled_for_cdec_only_river(hass: HomeAssistant, config_entry, aioclient_mock):
    from homeassistant.helpers import entity_registry as er

    _serve(aioclient_mock, {"AFO": [_record(20, 1500)]})
    await setup_integration(hass, config_entry)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", "paddle_conditions", f"{LAKE_SUBENTRY_ID}_streamflow")
    assert registry.async_get(entity_id).disabled_by is None
