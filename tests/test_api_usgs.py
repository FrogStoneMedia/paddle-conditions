"""Tests for USGS API client."""

import json
from pathlib import Path

import pytest

from custom_components.paddle_conditions.api.usgs import USGSClient, USGSData

from .conftest import mock_get_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def usgs_response():
    return json.loads((FIXTURES / "usgs_water_temp.json").read_text())


async def test_fetch_usgs_water_temp(mock_session, usgs_response):
    mock_session.get = mock_get_json(usgs_response)

    client = USGSClient(mock_session)
    data = await client.fetch(site_id="11446500")

    assert isinstance(data, USGSData)
    assert data.water_temp_f is not None
    # 14.72°C = 58.496°F
    assert abs(data.water_temp_f - 58.5) < 0.1


async def test_fetch_usgs_streamflow(mock_session, usgs_response):
    mock_session.get = mock_get_json(usgs_response)

    client = USGSClient(mock_session)
    data = await client.fetch(site_id="11446500")
    assert data.streamflow_cfs == 1250.0


async def test_fetch_usgs_no_data(mock_session):
    mock_session.get = mock_get_json({"value": {"timeSeries": []}})

    client = USGSClient(mock_session)
    data = await client.fetch(site_id="99999999")
    assert data.water_temp_f is None
    assert data.streamflow_cfs is None


async def test_fetch_usgs_malformed_value(mock_session):
    """Non-numeric values should be skipped gracefully."""
    malformed = {
        "value": {
            "timeSeries": [
                {
                    "variable": {"variableCode": [{"value": "00010"}]},
                    "values": [{"value": [{"value": "ICE", "dateTime": "2026-03-10T12:00:00"}]}],
                }
            ]
        }
    }
    mock_session.get = mock_get_json(malformed)

    client = USGSClient(mock_session)
    data = await client.fetch(site_id="11446500")
    assert data.water_temp_f is None
