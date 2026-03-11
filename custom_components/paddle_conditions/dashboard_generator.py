"""Generate a Lovelace dashboard config for configured paddle locations."""

from __future__ import annotations

from typing import Any

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION


def _eid(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def _location_card(name: str, slug: str) -> dict[str, Any]:
    """Generate a single vertical-stack card for one location."""
    score = _eid(slug, "paddle_score")
    wind = _eid(slug, "wind_speed")
    gusts = _eid(slug, "wind_gusts")
    air_temp = _eid(slug, "air_temperature")
    water_temp = _eid(slug, "water_temperature")
    uv = _eid(slug, "uv_index")
    aqi = _eid(slug, "air_quality_index")
    precip = _eid(slug, "precipitation_chance")
    condition = _eid(slug, "conditions")

    return {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "gauge",
                "entity": score,
                "name": name,
                "min": 0,
                "max": 100,
                "severity": {"green": 70, "yellow": 40, "red": 0},
            },
            {
                "type": "glance",
                "columns": 4,
                "show_name": True,
                "show_state": True,
                "state_color": True,
                "entities": [
                    {"entity": condition, "name": "Weather"},
                    {"entity": wind, "name": "Wind"},
                    {"entity": gusts, "name": "Gusts"},
                    {"entity": aqi, "name": "AQI"},
                    {"entity": air_temp, "name": "Air"},
                    {"entity": water_temp, "name": "Water"},
                    {"entity": uv, "name": "UV"},
                    {"entity": precip, "name": "Rain"},
                ],
            },
            {
                "type": "history-graph",
                "title": "Today",
                "hours_to_show": 24,
                "entities": [
                    {"entity": score, "name": "Score"},
                    {"entity": wind, "name": "Wind"},
                ],
            },
        ],
    }


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

    cards = [_location_card(name, slug) for name, slug in locations]

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
