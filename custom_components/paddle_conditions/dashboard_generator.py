"""Generate a Lovelace dashboard YAML for configured paddle locations."""

from __future__ import annotations

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION


def _eid(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def _location_cards(name: str, slug: str) -> str:
    """Generate cards for one location section."""
    score = _eid(slug, "paddle_score")
    wind = _eid(slug, "wind_speed")
    gusts = _eid(slug, "wind_gusts")
    wind_dir = _eid(slug, "wind_direction")
    air_temp = _eid(slug, "air_temperature")
    water_temp = _eid(slug, "water_temperature")
    uv = _eid(slug, "uv_index")
    aqi = _eid(slug, "air_quality_index")
    vis = _eid(slug, "visibility")
    precip = _eid(slug, "precipitation_chance")
    condition = _eid(slug, "conditions")
    forecast = _eid(slug, "3_hour_forecast")

    # Conditions summary template
    summary_tpl = (
        "{{% set s = states('" + score + "') %}}"
        "{{% set r = state_attr('" + score + "', 'rating') %}}"
        "{{% set lf = state_attr('" + score + "', 'limiting_factor') %}}"
        "{{% set v = state_attr('" + score + "', 'vetoed') %}}"
        "{{% set vr = state_attr('" + score + "', 'veto_reason') %}}"
        "{{% if v %}}"
        "\\U0001f6d1 **NO GO** — {{{{ vr }}}}\\n"
        "{{% elif r == 'GO' %}}"
        "\\u2705 **GO** — {{{{ s }}}}%\\n"
        "{{% elif r == 'CAUTION' %}}"
        "\\u26a0\\ufe0f **CAUTION** — {{{{ s }}}}%\\n"
        "{{% else %}}"
        "\\U0001f6d1 **NO GO** — {{{{ s }}}}%\\n"
        "{{% endif %}}"
        "{{{{ states('" + condition + "') }}}}"
        " &bull; "
        "{{{{ states('" + air_temp + "') }}}}\\u00b0F"
        " &bull; "
        "Wind {{{{ states('" + wind + "') }}}} mph"
        " (gusts {{{{ states('" + gusts + "') }}}})"
        "\\n\\n"
        "{{% if lf %}}"
        "Limiting factor: "
        "**{{{{ lf | replace('_', ' ') | title }}}}**"
        "{{% endif %}}"
    )

    # Forecast table template
    forecast_tpl = (
        "{{% set blocks = state_attr('" + forecast + "', 'blocks') %}}"
        "{{% if blocks %}}"
        "| Time | Score | Wind | Temp | UV |\\n"
        "|------|-------|------|------|----|\\n"
        "{{% for b in blocks %}}"
        "| {{{{ b.start[-8:-3] }}}}"
        "-{{{{ b.end[-8:-3] }}}} "
        "| {{% if b.score >= 70 %}}\\u2705"
        "{{% elif b.score >= 40 %}}\\u26a0\\ufe0f"
        "{{% else %}}\\U0001f6d1{{% endif %}} "
        "{{{{ b.score }}}}% "
        "| {{{{ b.wind_mph }}}} mph "
        "| {{{{ b.temp_f }}}}\\u00b0F "
        "| {{{{ b.uv }}}} |\\n"
        "{{% endfor %}}"
        "{{% else %}}"
        "No forecast data available."
        "{{% endif %}}"
    )

    return f"""      - type: vertical-stack
        cards:
          - type: markdown
            content: "## {name}"
          - type: markdown
            content: >-
              {summary_tpl}
          - type: gauge
            entity: {score}
            name: Paddle Score
            min: 0
            max: 100
            severity:
              green: 70
              yellow: 40
              red: 0
          - type: horizontal-stack
            cards:
              - type: entity
                entity: {wind}
                name: Wind
                icon: mdi:weather-windy
              - type: entity
                entity: {gusts}
                name: Gusts
                icon: mdi:weather-windy-variant
              - type: entity
                entity: {wind_dir}
                name: Dir
                icon: mdi:compass-outline
          - type: horizontal-stack
            cards:
              - type: entity
                entity: {air_temp}
                name: Air
                icon: mdi:thermometer
              - type: entity
                entity: {water_temp}
                name: Water
                icon: mdi:thermometer-water
              - type: entity
                entity: {uv}
                name: UV
                icon: mdi:white-balance-sunny
          - type: horizontal-stack
            cards:
              - type: entity
                entity: {aqi}
                name: AQI
                icon: mdi:air-filter
              - type: entity
                entity: {vis}
                name: Visibility
                icon: mdi:eye
              - type: entity
                entity: {precip}
                name: Rain
                icon: mdi:weather-rainy
          - type: markdown
            title: Today's Forecast
            content: >-
              {forecast_tpl}
          - type: history-graph
            title: Score & Wind (24h)
            hours_to_show: 24
            entities:
              - entity: {score}
                name: Score
              - entity: {wind}
                name: Wind
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
    views += "  - title: Paddle Conditions\n"
    views += "    path: conditions\n"
    views += "    icon: mdi:kayaking\n"
    views += "    cards:\n"

    for name, slug in locations:
        views += _location_cards(name, slug)

    # Reference tab with scoring guide
    views += _reference_view()

    return views


def _reference_view() -> str:
    """Generate a reference tab explaining the scoring system."""
    guide = (
        "## How Scores Work\\n\\n"
        "Your **Paddle Score** (0-100%) combines seven weather factors "
        "into a single Go / Caution / No-go rating.\\n\\n"
        "| Score | Rating | Meaning |\\n"
        "|-------|--------|---------|\\n"
        "| 70-100% | \\u2705 GO | Great conditions |\\n"
        "| 40-69% | \\u26a0\\ufe0f CAUTION | Paddle with care |\\n"
        "| 0-39% | \\U0001f6d1 NO GO | Stay off the water |\\n\\n"
        "### Scoring Factors\\n\\n"
        "| Factor | What It Measures |\\n"
        "|--------|-----------------|\\n"
        "| Wind Speed | Sustained wind — biggest factor for most paddlers |\\n"
        "| Wind Gusts | Gust intensity above sustained wind |\\n"
        "| Air Quality | US AQI — matters for extended exertion |\\n"
        "| Temperature | Comfort range, penalties for extremes |\\n"
        "| UV Index | Sun exposure risk |\\n"
        "| Visibility | Fog, haze, low-visibility hazards |\\n"
        "| Precipitation | Rain probability |\\n\\n"
        "### Hard Vetoes\\n\\n"
        "These override the score entirely:\\n"
        "- **Thunderstorms** (always enforced)\\n"
        "- **Extreme wind** (profile-dependent)\\n"
        "- **Dangerous AQI** (200+)\\n\\n"
        "### Profiles\\n\\n"
        "| Profile | Best For |\\n"
        "|---------|----------|\\n"
        "| Recreational | Typical adult paddler |\\n"
        "| Racing | Experienced, higher wind tolerance |\\n"
        "| Family | Loaded boards, kids, beginners |\\n\\n"
        "Change your profile in **Settings \\u2192 Integrations "
        "\\u2192 Paddle Conditions \\u2192 Configure**."
    )

    return f"""  - title: Guide
    path: guide
    icon: mdi:help-circle-outline
    cards:
      - type: markdown
        content: >-
          {guide}
"""
