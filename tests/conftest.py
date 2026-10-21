"""Shared test fixtures for Paddle Conditions."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import the package up front so patch() targets under it always resolve.
import custom_components.paddle_conditions  # noqa: F401


class MockAsyncContextManager:
    """Wraps a mock response so ``async with session.get(...) as resp:`` works."""

    def __init__(self, response=None, *, side_effect=None):
        self._response = response
        self._side_effect = side_effect

    async def __aenter__(self):
        if self._side_effect is not None:
            raise self._side_effect
        return self._response

    async def __aexit__(self, *args):
        pass


def mock_get_json(data):
    """Create a mock ``session.get`` that returns *data* as JSON via async context manager."""
    resp = MagicMock()
    resp.json = AsyncMock(return_value=data)
    resp.raise_for_status = MagicMock()
    return MagicMock(return_value=MockAsyncContextManager(resp))


def mock_get_text(text):
    """Create a mock ``session.get`` that returns *text* via async context manager."""
    resp = MagicMock()
    resp.text = AsyncMock(return_value=text)
    resp.raise_for_status = MagicMock()
    return MagicMock(return_value=MockAsyncContextManager(resp))


def mock_get_error(status, message, headers=None):
    """Create a mock ``session.get`` whose response raises on ``raise_for_status``."""
    from aiohttp import ClientResponseError

    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=status, message=message, headers=headers
        )
    )
    return MagicMock(return_value=MockAsyncContextManager(resp))


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession."""
    return AsyncMock()


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = "paddle_conditions"
    entry.title = "Paddle Conditions"
    entry.data = {}
    entry.options = {}
    entry.subentries = {}
    entry.runtime_data = {}
    return entry


@pytest.fixture
def mock_subentry():
    """Create a mock location subentry."""
    subentry = MagicMock()
    subentry.subentry_id = "sub_test_001"
    subentry.subentry_type = "location"
    subentry.title = "Lake Natoma"
    subentry.data = {
        "name": "Lake Natoma",
        "latitude": 38.637,
        "longitude": -121.227,
        "water_body_type": "lake",
        "display_order": 0,
        "usgs_station_id": "11446500",
        "noaa_station_id": "",
        "optimal_cfs": None,
    }
    return subentry


# --- Real Home Assistant harness -------------------------------------------
#
# These fixtures run the integration through a real config entry and mock
# HTTP at the shared aiohttp session (aioclient_mock), so tests exercise the
# same code path Home Assistant does.

LAKE_SUBENTRY_ID = "sub_lake"
LAKE_LOCATION = {
    "name": "Lake Natoma",
    "latitude": 38.637,
    "longitude": -121.227,
    "water_body_type": "lake",
    "display_order": 0,
    "usgs_station_id": "11446500",
    "noaa_station_id": "",
    "optimal_cfs": None,
}

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
USGS_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/latest-continuous/items"
NOAA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
PC_DIRECTORY_URL = "https://api.paddleconditions.com/public/spots/directory"
PC_STATIONS_URL = "https://api.paddleconditions.com/public/spot/{slug}/stations"
CDEC_URL = "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet"
NWS_POINTS_URL = re.compile(r"^https://api\.weather\.gov/points/")
NWS_GRID_URL = "https://api.weather.gov/gridpoints/STO/54,72"

PC_DIRECTORY = {
    "states": [
        {
            "state": "California",
            "slug": "california",
            "count": 2,
            "spots": [
                {"name": "Lake Natoma", "slug": "lake-natoma", "type": "lake", "county": "Sacramento"},
                {"name": "Lake Oroville", "slug": "lake-oroville-ca", "type": "reservoir", "county": "Butte"},
            ],
        }
    ],
    "totalSpots": 2,
    "topSpots": [],
}

PC_OROVILLE_STATIONS = {
    "slug": "lake-oroville-ca",
    "name": "Lake Oroville",
    "type": "reservoir",
    "lat": 39.54,
    "lng": -121.47,
    "reservoirCapacityAf": 3537577,
    "damOutflowThresholdCfs": 25000,
    "stations": {
        "usgs": [],
        "noaa": [],
        "cdec": [
            {"id": "ORO", "name": "Oroville Dam", "distanceKm": 0.4, "dataTypes": ["storage"]},
            {"id": "OTB", "name": "Thermalito", "distanceKm": 9.1, "dataTypes": ["temp"]},
        ],
    },
    "stageBaselines": {},
}


def make_weather_payload(hours: int = 48, **current_overrides):
    """Build an Open-Meteo response whose hourly series starts at the current UTC hour."""
    from homeassistant.util import dt as dt_util

    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta

    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    current = {
        "wind_speed_10m": 5.0,
        "wind_gusts_10m": 8.0,
        "wind_direction_10m": 225,
        "temperature_2m": 75.0,
        "uv_index": 3.0,
        "visibility": 24140.0,
        "precipitation_probability": 5,
        "weather_code": 1,
        **current_overrides,
    }
    return {
        "utc_offset_seconds": 0,
        "current": current,
        "hourly": {
            "time": times,
            "wind_speed_10m": [5.0] * hours,
            "wind_gusts_10m": [8.0] * hours,
            "temperature_2m": [75.0] * hours,
            "uv_index": [3.0] * hours,
            "precipitation_probability": [5] * hours,
            "weather_code": [1] * hours,
            "visibility": [24140.0] * hours,
        },
        "daily": {
            "time": [(start + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(3)],
            "sunrise": [(start + timedelta(days=d, hours=-6)).strftime("%Y-%m-%dT%H:%M") for d in range(3)],
            "sunset": [(start + timedelta(days=d, hours=5)).strftime("%Y-%m-%dT%H:%M") for d in range(3)],
        },
    }


def make_aqi_payload(hours: int = 48, aqi: int = 30):
    """Build an Open-Meteo air-quality response with an hourly series from the current UTC hour."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {"current": {"us_aqi": aqi}, "hourly": {"time": times, "us_aqi": [aqi] * hours}}


@pytest.fixture
def location_data():
    """Location subentry data used by config_entry; override per test."""
    return dict(LAKE_LOCATION)


@pytest.fixture
def config_entry(location_data):
    """A Paddle Conditions config entry with one location subentry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.paddle_conditions.config_flow import PaddleConfigFlow
    from custom_components.paddle_conditions.const import DOMAIN

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Paddle Conditions",
        version=PaddleConfigFlow.VERSION,
        minor_version=PaddleConfigFlow.MINOR_VERSION,
        data={},
        options={},
        subentries_data=[
            {
                "data": location_data,
                "subentry_id": LAKE_SUBENTRY_ID,
                "subentry_type": "location",
                "title": location_data["name"],
                "unique_id": None,
            }
        ],
    )


@pytest.fixture
def mock_apis(aioclient_mock):
    """Serve every upstream API from fixtures through the shared session."""
    import json
    from pathlib import Path

    fixtures = Path(__file__).parent / "fixtures"
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, json=make_aqi_payload())
    aioclient_mock.get(USGS_URL, json=json.loads((fixtures / "usgs_latest_continuous.json").read_text()))
    aioclient_mock.get(NOAA_URL, json={"data": []})
    aioclient_mock.get(PC_DIRECTORY_URL, json=PC_DIRECTORY)
    aioclient_mock.get(PC_STATIONS_URL.format(slug="lake-oroville-ca"), json=PC_OROVILLE_STATIONS)
    # CDEC serves JSON as text/plain.
    aioclient_mock.get(CDEC_URL, text="[]")
    # NWS answers but forecasts nothing, so Open-Meteo values stand unless a test serves a forecast.
    aioclient_mock.get(NWS_POINTS_URL, json={"properties": {"forecastGridData": NWS_GRID_URL}})
    aioclient_mock.get(NWS_GRID_URL, json={"properties": {}})
    return aioclient_mock


@pytest.fixture
def mock_frontend():
    """Skip card registration; covered by dedicated frontend tests."""
    from unittest.mock import patch

    with patch("custom_components.paddle_conditions.async_register_cards", return_value=None):
        yield


async def setup_integration(hass, entry) -> None:
    """Add the entry to hass and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
