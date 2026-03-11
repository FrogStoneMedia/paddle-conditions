"""Tests for Paddle Conditions config flow."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.paddle_conditions.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_config_flow_creates_entry(hass: HomeAssistant):
    """Test that the config flow creates an entry with no user input needed."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Paddle Conditions"


async def test_config_flow_single_instance(hass: HomeAssistant):
    """Only one instance of the integration should be allowed."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    # Second attempt should abort
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_location_subentry_flow_with_preset(hass: HomeAssistant):
    """Test adding a location via preset selection."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    # Start subentry flow — first step is preset selection
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select a preset
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"preset": "lake_natoma"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "location"

    # Confirm pre-filled location details
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "name": "Lake Natoma",
            "latitude": 38.636,
            "longitude": -121.185,
            "water_body_type": "lake",
            "display_order": 0,
            "usgs_station_id": "11446220",
            "noaa_station_id": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lake Natoma"


async def test_location_subentry_flow_custom(hass: HomeAssistant):
    """Test adding a custom location without a preset."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "location"),
        context={"source": config_entries.SOURCE_USER},
    )

    # Select custom location
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"preset": "custom"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "location"

    # Enter location details manually
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "name": "American River",
            "latitude": 38.63,
            "longitude": -121.22,
            "water_body_type": "river",
            "display_order": 1,
            "usgs_station_id": "11446500",
            "noaa_station_id": "",
            "optimal_cfs": 2000,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "American River"


async def test_options_flow(hass: HomeAssistant):
    """Test the options flow for global settings."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    # Open options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "activity": "sup",
            "profile": "recreational",
            "update_interval": 15,
            "weight_wind_speed": 30,
            "weight_wind_gusts": 10,
            "weight_air_quality": 20,
            "weight_temperature": 15,
            "weight_uv_index": 10,
            "weight_visibility": 10,
            "weight_precipitation": 5,
            "cloud_sync_url": "",
            "cloud_sync_token": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["activity"] == "sup"
    assert entry.options["update_interval"] == 15
    # Verify weights were normalized to sum to 1.0
    weights = entry.options["weights"]
    assert abs(sum(weights.values()) - 1.0) < 0.001
    assert abs(weights["wind_speed"] - 0.30) < 0.01


async def test_options_flow_all_zero_weights_fallback(hass: HomeAssistant):
    """All-zero weights should fall back to profile defaults."""
    from custom_components.paddle_conditions.profiles import get_profile

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "activity": "sup",
            "profile": "recreational",
            "update_interval": 10,
            "weight_wind_speed": 0,
            "weight_wind_gusts": 0,
            "weight_air_quality": 0,
            "weight_temperature": 0,
            "weight_uv_index": 0,
            "weight_visibility": 0,
            "weight_precipitation": 0,
            "cloud_sync_url": "",
            "cloud_sync_token": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    expected = get_profile("sup", "recreational").weights
    assert entry.options["weights"] == expected


async def test_options_flow_cloud_sync_fields(hass: HomeAssistant):
    """Test that cloud sync URL and token are saved in options."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "activity": "sup",
            "profile": "recreational",
            "update_interval": 10,
            "weight_wind_speed": 30,
            "weight_wind_gusts": 10,
            "weight_air_quality": 20,
            "weight_temperature": 15,
            "weight_uv_index": 10,
            "weight_visibility": 10,
            "weight_precipitation": 5,
            "cloud_sync_url": "https://sync.paddleconditions.com",
            "cloud_sync_token": "my-secret-token",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["cloud_sync_url"] == "https://sync.paddleconditions.com"
    assert entry.options["cloud_sync_token"] == "my-secret-token"


async def test_options_flow_activity_change_resets_profile(hass: HomeAssistant):
    """Changing activity should reset profile to activity's default."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    # Set initial options to SUP recreational
    hass.config_entries.async_update_entry(
        entry,
        options={
            "activity": "sup",
            "profile": "recreational",
        },
    )

    # Now switch to kayaking
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "activity": "kayaking",
            "profile": "recreational",  # user still has old profile selected
            "update_interval": 10,
            "weight_wind_speed": 30,
            "weight_wind_gusts": 10,
            "weight_air_quality": 20,
            "weight_temperature": 15,
            "weight_uv_index": 10,
            "weight_visibility": 10,
            "weight_precipitation": 5,
            "cloud_sync_url": "",
            "cloud_sync_token": "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Profile should be reset to kayaking's default (flatwater)
    assert entry.options["profile"] == "flatwater"
