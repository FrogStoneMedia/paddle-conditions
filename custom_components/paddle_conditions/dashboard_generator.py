"""Generate a Lovelace dashboard YAML for configured paddle locations."""

from __future__ import annotations

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION

# Rotate icons so each location tab is visually distinct
_LOCATION_ICONS = [
    "mdi:kayaking",
    "mdi:sail-boat",
    "mdi:waves",
    "mdi:fish",
    "mdi:map-marker",
    "mdi:pine-tree",
    "mdi:weather-sunny",
    "mdi:compass",
]


def _entity_id(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def _location_view(name: str, slug: str, icon: str) -> str:
    """Generate a detail view for one location."""
    score = _entity_id(slug, "paddle_score")
    wind = _entity_id(slug, "wind_speed")
    gusts = _entity_id(slug, "wind_gusts")
    air_temp = _entity_id(slug, "air_temperature")
    water_temp = _entity_id(slug, "water_temperature")
    uv = _entity_id(slug, "uv_index")
    aqi = _entity_id(slug, "air_quality_index")
    vis = _entity_id(slug, "visibility")
    precip = _entity_id(slug, "precipitation_chance")
    condition = _entity_id(slug, "conditions")
    streamflow = _entity_id(slug, "streamflow")

    path = slugify(name)

    return f"""  - title: "{name}"
    path: {path}
    icon: {icon}
    cards:
      - type: markdown
        content: "# {name}"
      - type: gauge
        entity: {score}
        name: Paddle Score
        min: 0
        max: 100
        severity:
          green: 70
          yellow: 40
          red: 0
      - type: entity
        entity: {condition}
        name: Conditions
      - type: entities
        title: Wind
        entities:
          - entity: {wind}
            name: Speed
          - entity: {gusts}
            name: Gusts
      - type: entities
        title: Environment
        entities:
          - entity: {air_temp}
            name: Air Temp
          - entity: {water_temp}
            name: Water Temp
          - entity: {uv}
            name: UV Index
          - entity: {aqi}
            name: Air Quality
          - entity: {vis}
            name: Visibility
          - entity: {precip}
            name: Precipitation
          - entity: {streamflow}
            name: Streamflow
      - type: history-graph
        title: Score History
        hours_to_show: 48
        entities:
          - entity: {score}
            name: Score
      - type: history-graph
        title: Wind History
        hours_to_show: 48
        entities:
          - entity: {wind}
            name: Speed
          - entity: {gusts}
            name: Gusts
"""


def generate_dashboard_yaml(
    subentries: dict,
) -> str:
    """Generate complete dashboard YAML from configured subentries."""
    locations: list[tuple[str, str]] = []
    for subentry in subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_LOCATION:
            continue
        name = subentry.data.get(CONF_NAME, subentry.title)
        slug = slugify(name)
        locations.append((name, slug))

    if not locations:
        return ""

    views = "views:\n"

    # Overview tab when multiple locations
    if len(locations) > 1:
        views += "  - title: Overview\n    path: overview\n    icon: mdi:view-dashboard\n    cards:\n"
        for name, slug in locations:
            score = _entity_id(slug, "paddle_score")
            condition = _entity_id(slug, "conditions")
            wind = _entity_id(slug, "wind_speed")
            aqi = _entity_id(slug, "air_quality_index")
            air_temp = _entity_id(slug, "air_temperature")
            views += f"""      - type: vertical-stack
        cards:
          - type: markdown
            content: "### {name}"
          - type: gauge
            entity: {score}
            name: Paddle Score
            min: 0
            max: 100
            severity:
              green: 70
              yellow: 40
              red: 0
          - type: glance
            entities:
              - entity: {condition}
                name: Conditions
              - entity: {wind}
                name: Wind
              - entity: {aqi}
                name: AQI
              - entity: {air_temp}
                name: Temp
"""

    # Per-location detail views with rotating icons
    for i, (name, slug) in enumerate(locations):
        icon = _LOCATION_ICONS[i % len(_LOCATION_ICONS)]
        views += _location_view(name, slug, icon)

    return views
