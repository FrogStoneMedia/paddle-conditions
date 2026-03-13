"""Shared test fixtures for Paddle Conditions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


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


def mock_get_error(status, message):
    """Create a mock ``session.get`` whose response raises on ``raise_for_status``."""
    from aiohttp import ClientResponseError

    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(request_info=MagicMock(), history=(), status=status, message=message)
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
