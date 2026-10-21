"""Tests for the get_dashboard_yaml action."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paddle_conditions.config_flow import PaddleConfigFlow
from custom_components.paddle_conditions.const import DOMAIN

from .conftest import LAKE_LOCATION, setup_integration

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_apis", "mock_frontend")


def _location(subentry_id: str, name: str, order: int) -> dict:
    return {
        "data": {**LAKE_LOCATION, "name": name, "display_order": order},
        "subentry_id": subentry_id,
        "subentry_type": "location",
        "title": name,
        "unique_id": None,
    }


async def _call(hass: HomeAssistant) -> dict:
    return await hass.services.async_call(DOMAIN, "get_dashboard_yaml", {}, blocking=True, return_response=True)


async def test_action_is_registered_without_any_entry(hass: HomeAssistant):
    """Actions belong to async_setup, so they exist even before an entry loads."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "get_dashboard_yaml")


async def test_action_without_locations_raises_translated_error(hass: HomeAssistant):
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass)

    assert err.value.translation_key == "no_locations"


async def test_dashboard_uses_real_entity_ids_in_display_order(hass: HomeAssistant):
    """Cards follow display_order and reference the registry's entity IDs, even after a rename."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        minor_version=PaddleConfigFlow.MINOR_VERSION,
        subentries_data=[_location("sub_b", "Folsom Lake", 2), _location("sub_a", "Lake Natoma", 1)],
    )
    await setup_integration(hass, entry)

    registry = er.async_get(hass)
    natoma = registry.async_get_entity_id("sensor", DOMAIN, "sub_a_score")
    registry.async_update_entity(natoma, new_entity_id="sensor.my_home_lake_score")

    response = await _call(hass)

    cards = response["views"][0]["cards"]
    assert cards[0] == {
        "type": "custom:paddle-spots-card",
        "entities": ["sensor.my_home_lake_score", "sensor.folsom_lake_paddle_score"],
    }
    assert [c["entity"] for c in cards[1:]] == ["sensor.my_home_lake_score", "sensor.folsom_lake_paddle_score"]


async def test_single_location_has_no_spots_card(hass: HomeAssistant, config_entry):
    await setup_integration(hass, config_entry)

    cards = (await _call(hass))["views"][0]["cards"]

    assert cards == [{"type": "custom:paddle-score-card", "entity": "sensor.lake_natoma_paddle_score"}]
