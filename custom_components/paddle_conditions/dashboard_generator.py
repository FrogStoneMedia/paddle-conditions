"""Generate a Lovelace dashboard config for configured paddle locations."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_DISPLAY_ORDER, DOMAIN, SUBENTRY_TYPE_LOCATION


def generate_dashboard(hass: HomeAssistant, subentries: list[ConfigSubentry]) -> dict[str, Any]:
    """Build a dashboard with one score card per location, in display order.

    Entity IDs come from the entity registry, so renamed entities still work.
    Locations whose score entity isn't registered yet are skipped.
    """
    registry = er.async_get(hass)
    locations = sorted(
        (sub for sub in subentries if sub.subentry_type == SUBENTRY_TYPE_LOCATION),
        key=lambda sub: (int(sub.data.get(CONF_DISPLAY_ORDER, 0)), sub.title.casefold()),
    )
    score_entities = [
        entity_id
        for sub in locations
        if (entity_id := registry.async_get_entity_id("sensor", DOMAIN, f"{sub.subentry_id}_score"))
    ]

    cards: list[dict[str, Any]] = []
    if len(score_entities) > 1:
        cards.append({"type": "custom:paddle-spots-card", "entities": score_entities})
    cards.extend({"type": "custom:paddle-score-card", "entity": entity_id} for entity_id in score_entities)

    return {
        "views": [
            {
                "title": "Paddle Conditions",
                "path": "conditions",
                "icon": "mdi:kayaking",
                "cards": cards,
            },
        ],
    }
