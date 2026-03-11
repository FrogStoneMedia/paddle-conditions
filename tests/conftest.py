"""Shared test fixtures for Paddle Conditions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


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
