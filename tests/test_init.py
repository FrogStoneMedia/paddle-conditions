"""Tests for __init__.py entry setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.paddle_conditions import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.paddle_conditions.const import SUBENTRY_TYPE_LOCATION


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


async def test_async_setup_entry_creates_coordinators(mock_hass, mock_config_entry, mock_subentry):
    """Setup creates a coordinator per location subentry."""
    mock_subentry.subentry_type = SUBENTRY_TYPE_LOCATION
    mock_config_entry.subentries = {"sub_001": mock_subentry}
    mock_config_entry.async_on_unload = MagicMock()

    with (
        patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"),
        patch("custom_components.paddle_conditions.PaddleCoordinator.async_config_entry_first_refresh"),
    ):
        result = await async_setup_entry(mock_hass, mock_config_entry)

    assert result is True
    assert "sub_001" in mock_config_entry.runtime_data
    mock_hass.config_entries.async_forward_entry_setups.assert_called_once()
    # Verify update listener registered (coordinator also registers async_shutdown)
    assert mock_config_entry.async_on_unload.call_count >= 2


async def test_async_setup_entry_skips_non_location_subentries(mock_hass, mock_config_entry, mock_subentry):
    """Non-location subentries are ignored."""
    mock_subentry.subentry_type = "something_else"
    mock_config_entry.subentries = {"sub_001": mock_subentry}
    mock_config_entry.async_on_unload = MagicMock()

    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        result = await async_setup_entry(mock_hass, mock_config_entry)

    assert result is True
    assert "sub_001" not in mock_config_entry.runtime_data


async def test_async_setup_entry_no_subentries(mock_hass, mock_config_entry):
    """Entry with no subentries still sets up successfully."""
    mock_config_entry.subentries = {}
    mock_config_entry.async_on_unload = MagicMock()

    result = await async_setup_entry(mock_hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.runtime_data == {}


async def test_async_unload_entry(mock_hass, mock_config_entry):
    """Unload forwards to platform unload."""
    result = await async_unload_entry(mock_hass, mock_config_entry)

    assert result is True
    mock_hass.config_entries.async_unload_platforms.assert_called_once()
