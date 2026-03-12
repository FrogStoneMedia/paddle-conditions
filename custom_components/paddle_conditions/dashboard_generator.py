"""Generate a Lovelace dashboard config for configured paddle locations."""

from __future__ import annotations

from typing import Any

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION


def _eid(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def generate_dashboard(subentries: dict) -> dict[str, Any]:
    """Generate complete dashboard config from configured subentries."""
    locations: list[tuple[str, str]] = []
    for subentry in subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_LOCATION:
            continue
        name = subentry.data.get(CONF_NAME, subentry.title)
        slug = slugify(name)
        locations.append((name, slug))

    if not locations:
        return {"views": []}

    cards: list[dict[str, Any]] = []

    # All spots at a glance (only if multiple locations)
    if len(locations) > 1:
        cards.append(
            {
                "type": "custom:paddle-spots-card",
                "entities": [_eid(slug, "paddle_score") for _, slug in locations],
            }
        )

    # Per-location score cards
    for _name, slug in locations:
        cards.append(
            {
                "type": "custom:paddle-score-card",
                "entity": _eid(slug, "paddle_score"),
            }
        )

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
