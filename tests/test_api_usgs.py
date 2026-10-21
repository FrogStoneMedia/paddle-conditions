"""Tests for the USGS Water Data (OGC API) client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.paddle_conditions.api.base import RateLimitedError
from custom_components.paddle_conditions.api.usgs import USGS_URL, USGSClient, USGSData

from .conftest import mock_get_error, mock_get_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def usgs_response():
    return json.loads((FIXTURES / "usgs_latest_continuous.json").read_text())


def _feature(code: str, value, unit: str, time: str = "2026-10-21T19:00:00+00:00") -> dict:
    return {
        "type": "Feature",
        "properties": {"parameter_code": code, "value": value, "unit_of_measure": unit, "time": time},
    }


async def test_fetch_queries_latest_continuous(mock_session, usgs_response):
    mock_session.get = mock_get_json(usgs_response)

    await USGSClient(mock_session).fetch("11447650")

    call = mock_session.get.call_args
    assert call.args[0] == USGS_URL
    assert call.kwargs["params"] == {
        "f": "json",
        "monitoring_location_id": "USGS-11447650",
        "parameter_code": "00010,00060",
    }
    assert "X-Api-Key" not in (call.kwargs.get("headers") or {})


async def test_fetch_sends_api_key_header(mock_session, usgs_response):
    mock_session.get = mock_get_json(usgs_response)

    await USGSClient(mock_session, api_key="abc123").fetch("USGS-11447650")

    call = mock_session.get.call_args
    assert call.kwargs["headers"] == {"X-Api-Key": "abc123"}
    assert call.kwargs["params"]["monitoring_location_id"] == "USGS-11447650"


async def test_fetch_uses_newest_reading_and_converts_units(mock_session, usgs_response):
    """The fixture has two temperature series; the 19:00 reading wins over 18:15."""
    mock_session.get = mock_get_json(usgs_response)

    data = await USGSClient(mock_session).fetch("11447650")

    assert isinstance(data, USGSData)
    assert data.water_temp_f == pytest.approx(16.8 * 9 / 5 + 32)
    assert data.streamflow_cfs == 10700.0


async def test_fahrenheit_readings_are_not_converted(mock_session):
    mock_session.get = mock_get_json({"features": [_feature("00010", "61.5", "degF")]})

    data = await USGSClient(mock_session).fetch("1")

    assert data.water_temp_f == 61.5


@pytest.mark.parametrize("value", [None, "ICE", "", "nan"])
async def test_missing_or_unreadable_values_are_skipped(mock_session, value):
    mock_session.get = mock_get_json({"features": [_feature("00010", value, "degC")]})

    data = await USGSClient(mock_session).fetch("1")

    assert data.water_temp_f is None


async def test_unknown_unit_is_skipped(mock_session):
    mock_session.get = mock_get_json({"features": [_feature("00010", "10", "furlongs")]})

    assert (await USGSClient(mock_session).fetch("1")).water_temp_f is None


async def test_no_features(mock_session):
    mock_session.get = mock_get_json({"features": []})

    data = await USGSClient(mock_session).fetch("99999999")

    assert data == USGSData(water_temp_f=None, streamflow_cfs=None)


async def test_rate_limit_carries_retry_after(mock_session):
    mock_session.get = mock_get_error(429, "Too Many Requests", headers={"Retry-After": "120"})

    with pytest.raises(RateLimitedError) as err:
        await USGSClient(mock_session).fetch("1")

    assert err.value.retry_after == 120.0


async def test_rate_limit_without_retry_after(mock_session):
    mock_session.get = mock_get_error(429, "Too Many Requests")

    with pytest.raises(RateLimitedError) as err:
        await USGSClient(mock_session).fetch("1")

    assert err.value.retry_after is None
