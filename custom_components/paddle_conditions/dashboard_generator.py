"""Generate a Lovelace dashboard config for configured paddle locations."""

from __future__ import annotations

from typing import Any

from homeassistant.util import slugify

from .const import CONF_NAME, SUBENTRY_TYPE_LOCATION


def _eid(location_slug: str, sensor_key: str) -> str:
    """Build the expected entity ID for a location sensor."""
    return f"sensor.{location_slug}_{sensor_key}"


def _score_hero(name: str, score_entity: str) -> dict[str, Any]:
    """Score hero card: location name, big score, rating, limiting factor."""
    e = score_entity
    template = (
        f"{{% set s = states('{e}') | int(0) %}}"
        f"{{% set r = state_attr('{e}', 'rating') %}}"
        f"{{% set lf = state_attr('{e}', 'limiting_factor') %}}"
        f"{{% set factors = state_attr('{e}', 'factors') %}}"
        f"\n## {name}"
        "\n# {{ s }}%"
        "\n{% if r == 'GO' %}**\U0001f7e2 GO PADDLE**"
        "{% elif r == 'CAUTION' %}**\U0001f7e1 CAUTION**"
        "{% else %}**\U0001f534 NO GO**{% endif %}"
        "\n{% if lf %}"
        "\n*Limiting factor: {{ lf | replace('_', ' ') | title }}"
        "{% if factors and factors[lf] is defined %}"
        " ({{ factors[lf] }}/100)"
        "{% endif %}*"
        "\n{% endif %}"
    )
    return {"type": "markdown", "content": template}


def _factors_card(slug: str, score_entity: str) -> dict[str, Any]:
    """Factor detail card showing each factor's value and score."""
    e = score_entity
    wind = _eid(slug, "wind_speed")
    gusts = _eid(slug, "wind_gusts")
    wind_dir = _eid(slug, "wind_direction")
    aqi = _eid(slug, "air_quality_index")
    air = _eid(slug, "air_temperature")
    water = _eid(slug, "water_temperature")
    uv = _eid(slug, "uv_index")
    vis = _eid(slug, "visibility")
    precip = _eid(slug, "precipitation_chance")
    cond = _eid(slug, "conditions")

    template = (
        f"{{% set f = state_attr('{e}', 'factors') %}}"
        f"{{% set wind = states('{wind}') %}}"
        f"{{% set gusts = states('{gusts}') %}}"
        f"{{% set wind_dir = states('{wind_dir}') %}}"
        f"{{% set aqi_val = states('{aqi}') %}}"
        f"{{% set air = states('{air}') %}}"
        f"{{% set water = states('{water}') %}}"
        f"{{% set uv = states('{uv}') %}}"
        f"{{% set vis = states('{vis}') %}}"
        f"{{% set precip = states('{precip}') %}}"
        f"{{% set cond = states('{cond}') %}}"
        "{%- macro icon(score) -%}"
        "{% if score >= 70 %}\U0001f7e2"
        "{% elif score >= 40 %}\U0001f7e1"
        "{% else %}\U0001f534{% endif %}"
        "{%- endmacro -%}"
        "\n{% if f %}"
        "\n| | | |"
        "\n|:---|:---|---:|"
        "\n| **\U0001f32c\ufe0f Wind** | {{ wind }} mph \u00b7 Gusts {{ gusts }} mph"
        " | {{ icon(f.wind_speed | default(0)) }}"
        " {{ f.wind_speed | default('-') }}/100 |"
        "\n| **\U0001f4a8 Air Quality** | {{ aqi_val }} AQI"
        " | {{ icon(f.air_quality | default(0)) }}"
        " {{ f.air_quality | default('-') }}/100 |"
        "\n| **\U0001f321\ufe0f Temperature** | {{ air }}\u00b0F"
        " \u00b7 Water {{ water }}\u00b0F"
        " | {{ icon(f.temperature | default(0)) }}"
        " {{ f.temperature | default('-') }}/100 |"
        "\n| **\u2600\ufe0f UV Index** | {{ uv }}"
        " | {{ icon(f.uv_index | default(0)) }}"
        " {{ f.uv_index | default('-') }}/100 |"
        "\n| **\U0001f441\ufe0f Visibility** | {{ vis }} mi"
        " | {{ icon(f.visibility | default(0)) }}"
        " {{ f.visibility | default('-') }}/100 |"
        "\n| **\U0001f327\ufe0f Precipitation** | {{ precip }}%"
        " | {{ icon(f.precipitation | default(0)) }}"
        " {{ f.precipitation | default('-') }}/100 |"
        "\n{% endif %}"
    )
    return {"type": "markdown", "content": template}


def _forecast_card(forecast_entity: str) -> dict[str, Any]:
    """Forecast time blocks showing score, wind, temp per 3hr window."""
    e = forecast_entity
    template = (
        f"{{% set blocks = state_attr('{e}', 'blocks') %}}"
        "{% if blocks %}"
        "\n| Time | Score | Wind | Temp |"
        "\n|:-----|:------|-----:|-----:|"
        "\n{% for b in blocks %}"
        "{% set t = b.start | as_timestamp | timestamp_custom('%I %p') %}"
        "{% set icon = '\U0001f7e2' if b.rating == 'GO' "
        "else '\U0001f7e1' if b.rating == 'CAUTION' "
        "else '\U0001f534' %}"
        "\n| {{ t }} | {{ icon }} {{ b.score }}%"
        " | {{ b.wind_mph | round(0) }} mph"
        " | {{ b.temp_f | round(0) }}\u00b0F |"
        "\n{% endfor %}"
        "{% else %}"
        "\nForecast data not yet available."
        "\n{% endif %}"
    )
    return {"type": "markdown", "title": "Forecast", "content": template}


def _all_spots_card(locations: list[tuple[str, str]]) -> dict[str, Any]:
    """All spots at a glance — horizontal score comparison."""
    header = "| " + " | ".join(name for name, _ in locations) + " |"
    align = "| " + " | ".join(":---:" for _ in locations) + " |"

    cells = []
    for _, slug in locations:
        e = _eid(slug, "paddle_score")
        cells.append(f"{{% set s{slug} = states('{e}') | int(0) %}}{{% set r{slug} = state_attr('{e}', 'rating') %}}")

    score_row_parts = []
    for _, slug in locations:
        score_row_parts.append(
            f"{{{{ '\U0001f7e2' if r{slug} == 'GO' "
            f"else '\U0001f7e1' if r{slug} == 'CAUTION' "
            f"else '\U0001f534' }}}} "
            f"**{{{{ s{slug} }}}}**"
        )
    score_row = "| " + " | ".join(score_row_parts) + " |"

    template = "".join(cells) + f"\n{header}\n{align}\n{score_row}"
    return {"type": "markdown", "title": "All Spots", "content": template}


def _location_cards(name: str, slug: str) -> list[dict[str, Any]]:
    """Generate cards for one location."""
    score = _eid(slug, "paddle_score")
    forecast = _eid(slug, "3_hour_forecast")

    return [
        _score_hero(name, score),
        _factors_card(slug, score),
        _forecast_card(forecast),
    ]


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
        cards.append(_all_spots_card(locations))

    # Per-location sections
    for name, slug in locations:
        location_cards = _location_cards(name, slug)
        cards.append({"type": "vertical-stack", "cards": location_cards})

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
