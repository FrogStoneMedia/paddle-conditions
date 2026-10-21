"""Tests for Paddle Conditions config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.paddle_conditions.api.base import APIError
from custom_components.paddle_conditions.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_apis")

WEATHER_CLIENT_PATH = "custom_components.paddle_conditions.config_flow.OpenMeteoWeatherClient"
SESSION_PATH = "homeassistant.helpers.aiohttp_client.async_get_clientsession"
FRONTEND_PATH = "custom_components.paddle_conditions.async_register_cards"


@pytest.fixture(autouse=True)
def _mock_frontend():
    """Prevent frontend registration from needing hass.http in tests."""
    with patch(FRONTEND_PATH, return_value=None):
        yield


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
    with patch(SESSION_PATH), patch(WEATHER_CLIENT_PATH) as mock_cls:
        mock_cls.return_value.fetch = AsyncMock()
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
    with patch(SESSION_PATH), patch(WEATHER_CLIENT_PATH) as mock_cls:
        mock_cls.return_value.fetch = AsyncMock()
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
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["activity"] == "sup"
    assert entry.options["update_interval"] == 15
    # Verify weights were normalized to sum to 1.0
    weights = entry.options["weights"]
    # The seven slider weights normalize to 1.0; weights with no slider (streamflow,
    # tide, the CDEC factors) are kept as-is and the scorer renormalizes per location.
    hidden = ("streamflow", "tide", "reservoir_level", "water_quality", "river_stage")
    sliders = {k: v for k, v in weights.items() if k not in hidden}
    assert abs(sum(sliders.values()) - 1.0) < 0.001
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
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    expected = get_profile("sup", "recreational").weights
    assert entry.options["weights"] == expected


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
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Profile should be reset to kayaking's default (flatwater)
    assert entry.options["profile"] == "flatwater"


async def test_location_subentry_weather_api_failure(hass: HomeAssistant):
    """Test that a weather API failure shows cannot_connect error."""
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

    # Submit location with weather API failing
    with patch(SESSION_PATH), patch(WEATHER_CLIENT_PATH) as mock_cls:
        mock_cls.return_value.fetch = AsyncMock(side_effect=APIError("API unreachable"))
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                "name": "Bad Location",
                "latitude": 0.01,
                "longitude": 0.01,
                "water_body_type": "lake",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "location"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_keeps_weights_without_sliders(hass: HomeAssistant):
    """Saving options must not drop the streamflow and tide weights, which have no slider."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "activity": "sup",
            "profile": "recreational",
            "update_interval": 20,
            "weight_wind_speed": 30,
            "weight_wind_gusts": 10,
            "weight_air_quality": 20,
            "weight_temperature": 15,
            "weight_uv_index": 10,
            "weight_visibility": 10,
            "weight_precipitation": 5,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    weights = entry.options["weights"]
    assert weights["streamflow"] == pytest.approx(0.15)
    assert weights["tide"] == pytest.approx(0.10)
    assert weights["wind_speed"] == pytest.approx(0.30)


@pytest.mark.parametrize(("submitted", "stored"), [("k-123", "k-123"), ("", None)])
async def test_options_flow_usgs_api_key(hass: HomeAssistant, submitted, stored):
    """The USGS key is saved when given and left out entirely when blank."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"update_interval": 10, "usgs_api_key": submitted}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options.get("usgs_api_key") == stored


async def test_dropdowns_use_translated_options(hass: HomeAssistant):
    """Option labels come from strings.json, not hard-coded English."""
    import json
    from pathlib import Path

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    selectors = {
        str(key): value.config for key, value in result["data_schema"].schema.items() if hasattr(value, "config")
    }
    strings = json.loads((Path(__file__).parents[1] / "custom_components/paddle_conditions/strings.json").read_text())[
        "selector"
    ]

    for field in ("activity", "profile"):
        config = selectors[field]
        assert config["translation_key"] == field
        assert set(config["options"]) <= set(strings[field]["options"])


async def _options_entry(hass: HomeAssistant, options: dict | None = None):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    entry = result["result"]
    if options:
        hass.config_entries.async_update_entry(entry, options=options)
    return entry


async def test_options_flow_profile_change_loads_profile_weights(hass: HomeAssistant):
    """Picking another profile for the same activity resets weights to that profile's."""
    from custom_components.paddle_conditions.profiles import get_profile

    entry = await _options_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"activity": "sup", "profile": "racing", "update_interval": 10}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["profile"] == "racing"
    assert entry.options["weights"] == get_profile("sup", "racing").weights


async def test_options_form_offers_kayaking_profiles(hass: HomeAssistant):
    entry = await _options_entry(hass, {"activity": "kayaking", "profile": "river"})

    result = await hass.config_entries.options.async_init(entry.entry_id)

    profile = next(v for k, v in result["data_schema"].schema.items() if str(k) == "profile")
    assert profile.config["options"] == ["flatwater", "river", "ocean"]


async def test_options_flow_restores_missing_hidden_weights(hass: HomeAssistant):
    """Stored weights missing streamflow (from the old bug) get the profile's back on save."""
    entry = await _options_entry(hass, {"weights": {"wind_speed": 1.0}})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"update_interval": 10, "weight_wind_speed": 100}
    )

    assert entry.options["weights"]["streamflow"] == pytest.approx(0.15)
