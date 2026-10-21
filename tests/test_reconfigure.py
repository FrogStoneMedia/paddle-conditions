"""Tests for reconfiguring a location subentry on a loaded entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LAKE_LOCATION, LAKE_SUBENTRY_ID, WEATHER_URL, setup_integration

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")

FLOW_FETCH = "custom_components.paddle_conditions.api.open_meteo.OpenMeteoWeatherClient.fetch"


def _weather_calls(aioclient_mock) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]).startswith(WEATHER_URL))


async def test_reconfigure_updates_location_and_reloads_once(hass: HomeAssistant, config_entry, mock_apis):
    """Editing a location saves it and reloads the entry exactly once."""
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    fetches_after_setup = _weather_calls(mock_apis)

    result = await config_entry.start_subentry_reconfigure_flow(hass, LAKE_SUBENTRY_ID)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_data = {k: v for k, v in LAKE_LOCATION.items() if k != "optimal_cfs"}
    new_data["name"] = "Lake Natoma North"
    with patch(FLOW_FETCH, AsyncMock()):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], new_data)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = config_entry.subentries[LAKE_SUBENTRY_ID]
    assert subentry.title == "Lake Natoma North"
    assert subentry.data["name"] == "Lake Natoma North"
    assert config_entry.state is ConfigEntryState.LOADED
    assert _weather_calls(mock_apis) == fetches_after_setup + 1


async def test_reconfigure_cannot_connect_shows_error(hass: HomeAssistant, config_entry, mock_apis):
    """A coordinate the weather API rejects keeps the form open with an error."""
    from custom_components.paddle_conditions.api.base import APIError

    await setup_integration(hass, config_entry)
    result = await config_entry.start_subentry_reconfigure_flow(hass, LAKE_SUBENTRY_ID)

    new_data = {k: v for k, v in LAKE_LOCATION.items() if k != "optimal_cfs"}
    with patch(FLOW_FETCH, AsyncMock(side_effect=APIError("boom"))):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], new_data)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_unexpected_error_shows_unknown(hass: HomeAssistant, config_entry, mock_apis):
    """A bug in validation surfaces as 'unknown', not as a connection problem."""
    await setup_integration(hass, config_entry)
    result = await config_entry.start_subentry_reconfigure_flow(hass, LAKE_SUBENTRY_ID)

    new_data = {k: v for k, v in LAKE_LOCATION.items() if k != "optimal_cfs"}
    with patch(FLOW_FETCH, AsyncMock(side_effect=RuntimeError("bug"))):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], new_data)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
