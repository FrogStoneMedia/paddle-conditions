"""Tests for NOAA API client."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.paddle_conditions.api.noaa import NOAAClient, NOAAData

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def coops_response():
    return json.loads((FIXTURES / "noaa_coops_tides.json").read_text())


def _mock_get(data):
    resp = MagicMock()
    resp.json = AsyncMock(return_value=data)
    resp.raise_for_status = MagicMock()
    return AsyncMock(return_value=resp)


async def test_fetch_tides(mock_session, coops_response):
    mock_session.get = _mock_get(coops_response)

    client = NOAAClient(mock_session)
    data = await client.fetch_tides(station_id="9414290")

    assert isinstance(data, NOAAData)
    assert len(data.tide_predictions) == 4
    assert data.tide_predictions[0].type == "H"
    assert abs(data.tide_predictions[0].height_ft - 4.521) < 0.01


async def test_fetch_tides_empty(mock_session):
    mock_session.get = _mock_get({"predictions": []})

    client = NOAAClient(mock_session)
    data = await client.fetch_tides(station_id="9414290")
    assert data.tide_predictions == []


async def test_fetch_tides_malformed_entry(mock_session):
    """Malformed entries should be skipped, not crash."""
    malformed = {
        "predictions": [
            {"t": "2026-03-10 12:00", "v": "not_a_number", "type": "H"},
            {"t": "2026-03-10 18:00", "v": "4.5", "type": "L"},
        ]
    }
    mock_session.get = _mock_get(malformed)

    client = NOAAClient(mock_session)
    data = await client.fetch_tides(station_id="9414290")
    assert len(data.tide_predictions) == 1


async def test_fetch_tides_http_error(mock_session):
    """HTTP errors should raise APIError."""
    from aiohttp import ClientResponseError

    from custom_components.paddle_conditions.api.base import APIError

    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(request_info=MagicMock(), history=(), status=503, message="Unavailable")
    )
    mock_session.get = AsyncMock(return_value=resp)

    client = NOAAClient(mock_session)
    with pytest.raises(APIError):
        await client.fetch_tides(station_id="9414290")


async def test_fetch_water_temp_success(mock_session):
    water_temp_response = {"data": [{"t": "2026-03-10 12:00", "v": "55.2"}]}
    mock_session.get = _mock_get(water_temp_response)

    client = NOAAClient(mock_session)
    temp = await client.fetch_water_temp(station_id="9414290")
    assert temp is not None
    assert abs(temp - 55.2) < 0.1


async def test_fetch_water_temp_no_data(mock_session):
    mock_session.get = _mock_get({"data": []})

    client = NOAAClient(mock_session)
    temp = await client.fetch_water_temp(station_id="9414290")
    assert temp is None
