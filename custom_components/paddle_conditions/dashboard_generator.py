"""Generate a Lovelace dashboard YAML for configured paddle locations."""

from __future__ import annotations

from pathlib import Path

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION

_DASHBOARD_DIR: Path = Path(__file__).parent / "dashboard"
_GENERATED_FILE: str = "paddle-generated.yaml"


def _entity_id(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def _location_view(name: str, slug: str, *, is_first: bool) -> str:
    """Generate a Conditions view for one location."""
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
    forecast = _entity_id(slug, "3_hour_forecast")
    streamflow = _entity_id(slug, "streamflow")

    path = slugify(name)

    return f"""  - title: "{name}"
    path: {path}
    icon: mdi:kayaking
    cards:
      - type: custom:paddle-score-card
        entity: {score}
        show_profile: true
        show_limiting_factor: true

      - type: entities
        title: Current Conditions
        entities:
          - {wind}
          - {gusts}
          - {air_temp}
          - {water_temp}
          - {uv}
          - {aqi}
          - {vis}
          - {precip}
          - {streamflow}
          - {condition}

      - type: custom:paddle-factors-card
        entity: {score}

      - type: custom:paddle-forecast-card
        entity: {forecast}
        max_blocks: 8

      - type: custom:paddle-chart-card
        entity: {forecast}
        name: Forecast Chart
        default_metrics:
          - score
          - wind
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

    # Sort by display_order then name
    score_entities = [_entity_id(slug, "paddle_score") for _, slug in locations]

    # Build chips card listing all locations
    chips_yaml = "      - type: custom:paddle-chips-card\n        entities:\n"
    for entity in score_entities:
        chips_yaml += f"          - {entity}\n"
    chips_yaml += "        show_refresh: true\n"

    # Build overview + per-location views
    views = "views:\n"

    # Overview tab with all locations' scores
    if len(locations) > 1:
        views += "  - title: Overview\n    path: overview\n    icon: mdi:map-marker-multiple\n    cards:\n"
        views += chips_yaml
        for name, slug in locations:
            score = _entity_id(slug, "paddle_score")
            views += f"""      - type: custom:paddle-score-card
        entity: {score}
        show_profile: true
        show_limiting_factor: true
        name: "{name}"

"""

    # Per-location detail views
    for i, (name, slug) in enumerate(locations):
        views += _location_view(name, slug, is_first=(i == 0))

    # History view
    views += "  - title: History\n    path: history\n    icon: mdi:chart-line\n    cards:\n"
    for name, slug in locations:
        score = _entity_id(slug, "paddle_score")
        views += f"""      - type: custom:paddle-history-card
        entity: {score}
        name: "{name} History"
        default_range: 7d
        show_stats: true

"""

    header = (
        "# Paddle Conditions Dashboard\n"
        "# Auto-generated from your configured locations.\n"
        "# Re-generated each time you add or remove a location.\n\n"
    )

    return header + views


def write_dashboard(subentries: dict) -> Path | None:
    """Generate and write the dashboard YAML file. Returns the path or None."""
    yaml_content = generate_dashboard_yaml(subentries)
    if not yaml_content:
        return None

    output = _DASHBOARD_DIR / _GENERATED_FILE
    output.write_text(yaml_content)
    return output
