"""Tests for the CDEC client."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from custom_components.paddle_conditions.api.base import APIError
from custom_components.paddle_conditions.api.cdec import (
    CDEC_TZ,
    CDEC_URL,
    CDECClient,
    CDECData,
    CDECReading,
    parse_cdec_date,
)

from .conftest import mock_get_text


def mock_get_json(data):
    """CDEC sends JSON as text/plain, so the client reads text."""
    return mock_get_text(json.dumps(data))


# 14:20 PST
NOW = datetime(2026, 10, 21, 22, 20, tzinfo=UTC)


def _record(sensor: int, value, obs: str, flag: str = " ") -> dict:
    """A record shaped like CDEC's live JSON."""
    return {
        "stationId": "AFO",
        "durCode": "E",
        "SENSOR_NUM": sensor,
        "sensorType": "TEST",
        "date": obs,
        "obsDate": obs,
        "value": value,
        "dataFlag": flag,
        "units": "TEST",
    }


def test_parse_cdec_date_is_pst_all_year():
    # Summer too: CDEC does not observe daylight time.
    assert parse_cdec_date("2026-7-4 9:45") == datetime(2026, 7, 4, 17, 45, tzinfo=UTC)
    assert parse_cdec_date("2026-10-21 14:00") == datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
    assert parse_cdec_date("2026-10-21") == datetime(2026, 10, 21, tzinfo=CDEC_TZ)
    assert parse_cdec_date("2026-13-40 9:00") is None
    assert parse_cdec_date("not a date") is None
    assert parse_cdec_date(None) is None


async def test_fetch_requests_event_and_hourly_through_tomorrow(mock_session):
    mock_session.get = mock_get_json([])

    data = await CDECClient(mock_session).fetch(" afo ", now=NOW)

    assert data == CDECData()
    event, hourly = (call for call in mock_session.get.call_args_list)
    assert event.args[0] == CDEC_URL
    assert event.kwargs["params"] == {
        "Stations": "AFO",
        "SensorNums": "25,20,1,27,61,62,100",
        "dur_code": "E",
        "Start": "2026-10-19",
        "End": "2026-10-22",
    }
    assert hourly.kwargs["params"]["SensorNums"] == "15,6,76,23"
    assert hourly.kwargs["params"]["dur_code"] == "H"


async def test_fetch_picks_newest_real_reading(mock_session):
    mock_session.get = mock_get_json(
        [
            _record(1, 6.32, "2026-10-21 9:45"),
            _record(1, 6.30, "2026-10-21 14:00"),
            _record(1, -9999, "2026-10-21 14:15"),
            _record(1, -9999, "2026-10-21 23:00"),
            _record(25, 61.6, "2026-10-21 14:00"),
            _record(25, 99.0, "2026-10-21 14:15", flag="N"),
            _record(27, 3.1, "2026-10-21 14:00", flag="v"),
            _record(62, "7.2", "2026-10-21 14:00"),
            _record(61, 9.0, "garbage"),
            _record(999, 1.0, "2026-10-21 14:00"),
        ]
    )

    data = await CDECClient(mock_session).fetch("AFO", now=NOW)

    observed = datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
    assert data.river_stage_ft == CDECReading(6.30, observed)
    assert data.water_temp_f == CDECReading(61.6, observed)
    assert data.turbidity_ntu is None
    assert data.ph is None
    assert data.dissolved_oxygen_mg_l is None


async def test_fetch_maps_hourly_reservoir_sensors(mock_session):
    mock_session.get = mock_get_json(
        [
            _record(15, 388386, "2026-10-21 12:00"),
            _record(23, 324, "2026-10-21 12:00"),
            _record(6, 401.34, "2026-10-21 12:00"),
            _record(76, 354, "2026-10-21 12:00"),
        ]
    )

    data = await CDECClient(mock_session).fetch("FOL", now=NOW)

    assert data.storage_af is not None
    assert data.storage_af.value == 388386
    assert data.outflow_cfs is not None
    assert data.outflow_cfs.value == 324
    assert data.elevation_ft is not None
    assert data.inflow_cfs is not None


async def test_fetch_tolerates_non_list_response(mock_session):
    mock_session.get = mock_get_json({"error": "nope"})
    assert await CDECClient(mock_session).fetch("AFO", now=NOW) == CDECData()


def test_merged_with_prefers_nearest_station():
    observed = datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
    near = CDECData(river_stage_ft=CDECReading(6.3, observed))
    far = CDECData(river_stage_ft=CDECReading(9.9, observed), storage_af=CDECReading(1.0, observed))

    merged = near.merged_with(far)

    assert merged.river_stage_ft == CDECReading(6.3, observed)
    assert merged.storage_af == CDECReading(1.0, observed)


async def test_fetch_raises_api_error_on_invalid_json(mock_session):
    mock_session.get = mock_get_text("<html>maintenance</html>")
    with pytest.raises(APIError):
        await CDECClient(mock_session).fetch("AFO", now=NOW)
