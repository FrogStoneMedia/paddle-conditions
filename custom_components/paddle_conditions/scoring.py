"""Paddle Conditions scoring engine.

Pure functions — no Home Assistant dependencies.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .models import PaddleScore


def _round_half_up(value: float) -> int:
    """Round .5 up like JavaScript's Math.round, so scores match the Paddle Conditions API.

    Python's round() rounds half to even (92.5 -> 92); the API gives 93.
    """
    return math.floor(value + 0.5)


def _linear_score(value: float, ideal_max: float, marginal: float, nogo: float) -> int:
    """Piecewise linear interpolation: ideal->100, marginal->50, nogo->0.

    For factors where lower values are better (wind, AQI, UV, precip).
    """
    if value <= ideal_max:
        return 100
    if value >= nogo:
        return 0
    if value <= marginal:
        return _round_half_up(100 - 50 * (value - ideal_max) / (marginal - ideal_max))
    return _round_half_up(50 * (nogo - value) / (nogo - marginal))


def _linear_score_inverted(
    value: float,
    ideal_min: float,
    marginal: float,
    nogo: float,
) -> int:
    """For factors where higher values are better (temp cold side, visibility)."""
    if value >= ideal_min:
        return 100
    if value <= nogo:
        return 0
    if value >= marginal:
        return _round_half_up(100 - 50 * (ideal_min - value) / (ideal_min - marginal))
    return _round_half_up(50 * (value - nogo) / (marginal - nogo))


def score_wind_speed(
    value: float | None,
    ideal_max: float = 5,
    marginal: float = 11,
    nogo: float = 20,
) -> int | None:
    """Score wind speed (mph). Lower is better."""
    if value is None:
        return None
    return _linear_score(value, ideal_max=ideal_max, marginal=marginal, nogo=nogo)


def score_wind_gusts(
    value: float | None,
    ideal_max: float = 8,
    marginal: float = 16,
    nogo: float = 25,
) -> int | None:
    """Score wind gusts (mph). Lower is better."""
    if value is None:
        return None
    return _linear_score(value, ideal_max=ideal_max, marginal=marginal, nogo=nogo)


def score_aqi(
    value: int | None,
    ideal_max: float = 25,
    marginal: float = 87,
    nogo: float = 150,
) -> int | None:
    """Score air quality index. Lower is better."""
    if value is None:
        return None
    return _linear_score(float(value), ideal_max=ideal_max, marginal=marginal, nogo=nogo)


def score_temperature(
    value: float | None,
    ideal_low: float = 70,
    ideal_high: float = 85,
    cold_marginal: float = 55,
    cold_nogo: float = 40,
    hot_marginal: float = 95,
    hot_nogo: float = 105,
) -> int | None:
    """Score air temperature (F). Ideal is a range; too cold or too hot is bad."""
    if value is None:
        return None
    if ideal_low <= value <= ideal_high:
        return 100
    if value < ideal_low:
        return _linear_score_inverted(
            value,
            ideal_min=ideal_low,
            marginal=cold_marginal,
            nogo=cold_nogo,
        )
    return _linear_score(
        value,
        ideal_max=ideal_high,
        marginal=hot_marginal,
        nogo=hot_nogo,
    )


def score_uv_index(
    value: float | None,
    ideal_max: float = 4,
    marginal: float = 6.5,
    nogo: float = 11,
) -> int | None:
    """Score UV index. Lower is better."""
    if value is None:
        return None
    return _linear_score(value, ideal_max=ideal_max, marginal=marginal, nogo=nogo)


def score_visibility(
    value: float | None,
    ideal_min: float = 10,
    marginal: float = 4,
    nogo: float = 1,
) -> int | None:
    """Score visibility (miles). Higher is better."""
    if value is None:
        return None
    return _linear_score_inverted(
        value,
        ideal_min=ideal_min,
        marginal=marginal,
        nogo=nogo,
    )


def score_precipitation(
    value: int | None,
    ideal_max: float = 0,
    marginal: float = 35,
    nogo: float = 80,
) -> int | None:
    """Score precipitation probability (%). Lower is better."""
    if value is None:
        return None
    return _linear_score(float(value), ideal_max=ideal_max, marginal=marginal, nogo=nogo)


def score_streamflow(
    value: float | None,
    optimal_cfs: float = 500,
) -> int | None:
    """Score streamflow (CFS). Optimal is location-specific.

    At optimal -> 100, at 2x optimal -> ~71, at 4x optimal -> 0 (flood).
    Below optimal: at 0.5x -> ~57, at 0.1x -> 0 (too low).
    """
    if value is None:
        return None
    if optimal_cfs <= 0:
        return None
    ratio = value / optimal_cfs
    if 0.8 <= ratio <= 1.2:
        return 100
    if ratio > 1.2:
        return max(0, _round_half_up(100 - 100 * (ratio - 1.2) / 2.8))
    return max(0, _round_half_up(100 * (ratio - 0.1) / 0.7))


def score_tide(
    value: float | None,
    ideal_max: float = 0.5,
    marginal: float = 1.5,
    nogo: float = 3.0,
) -> int | None:
    """Score tide current (knots). Lower current = better. 0 = slack."""
    if value is None:
        return None
    return _linear_score(abs(value), ideal_max=ideal_max, marginal=marginal, nogo=nogo)


# ============================================================================
# CDEC factors (California reservoirs and rivers); ported from the API
# ============================================================================

MIN_STAGE_SAMPLES = 60


@dataclass(frozen=True)
class StageBaseline:
    """Historical river-stage percentiles (ft) for a gauge."""

    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    sample_count: int

    @property
    def reliable(self) -> bool:
        """Enough history to judge a stage as high or low."""
        return self.sample_count >= MIN_STAGE_SAMPLES


def score_reservoir_level(storage_af: float | None, capacity_af: float | None) -> int | None:
    """100 at or above 60% full, 0 at or below 20%, linear between."""
    if storage_af is None or capacity_af is None or capacity_af <= 0:
        return None
    pct = storage_af / capacity_af * 100
    if pct >= 60:
        return 100
    if pct <= 20:
        return 0
    return _round_half_up(100 * (pct - 20) / 40)


def score_river_stage(stage_ft: float | None, baseline: StageBaseline | None, inverted: bool) -> int | None:
    """Lower is better from the median (p50/p75/p90); inverted profiles want higher water (p50/p25/p10)."""
    if stage_ft is None or baseline is None or not baseline.reliable:
        return None
    if inverted:
        return _linear_score_inverted(stage_ft, baseline.p50, baseline.p25, baseline.p10)
    return _linear_score(stage_ft, baseline.p50, baseline.p75, baseline.p90)


def score_water_quality(wq: Mapping[str, float | None]) -> int | None:
    """Mean of turbidity, dissolved oxygen, pH and conductivity sub-scores, for those reported."""
    scores: list[int] = []
    if (turbidity := wq.get("turbidity_ntu")) is not None:
        scores.append(_linear_score(turbidity, 10, 50, 100))
    if (oxygen := wq.get("dissolved_oxygen_mg_l")) is not None:
        scores.append(_linear_score_inverted(oxygen, 6, 4, 2))
    if (ph := wq.get("ph")) is not None:
        if 6.5 <= ph <= 8.5:
            scores.append(100)
        elif ph < 6.5:
            scores.append(_linear_score_inverted(ph, 6.5, 6.0, 5.0))
        else:
            scores.append(_linear_score(ph, 8.5, 9.0, 10.0))
    if (conductivity := wq.get("conductivity_us")) is not None:
        scores.append(_linear_score(conductivity, 1000, 2000, 3000))
    if not scores:
        return None
    return _round_half_up(sum(scores) / len(scores))


# ============================================================================
# Hard vetoes
# ============================================================================

_DEFAULT_VETOES: dict[str, float] = {
    "wind_speed": 25,
    "wind_gusts": 35,
    "aqi": 200,
    "visibility": 0.5,
    "air_temp_min": 32,
}


def check_hard_vetoes(
    *,
    wind_speed: float | None,
    wind_gusts: float | None,
    aqi: int | None,
    air_temp: float | None,
    visibility: float | None,
    has_thunderstorm: bool,
    veto_thresholds: dict[str, float] | None = None,
) -> str | None:
    """Check for hard veto conditions. Returns reason string or None."""
    if has_thunderstorm:
        return "Thunderstorm / Lightning"

    vt = veto_thresholds or _DEFAULT_VETOES

    if wind_speed is not None and wind_speed > vt["wind_speed"]:
        return f"Wind > {vt['wind_speed']} mph sustained"
    if wind_gusts is not None and wind_gusts > vt["wind_gusts"]:
        return f"Gusts > {vt['wind_gusts']} mph"
    if aqi is not None and aqi > vt["aqi"]:
        return f"AQI > {vt['aqi']}"
    if visibility is not None and visibility < vt["visibility"]:
        return f"Visibility < {vt['visibility']} mi"
    if air_temp is not None and air_temp < vt["air_temp_min"]:
        return f"Air temp < {vt['air_temp_min']} °F"
    return None


# ============================================================================
# Final score computation
# ============================================================================

_BASE_FACTOR_SCORERS: dict[str, Any] = {
    "wind_speed": score_wind_speed,
    "wind_gusts": score_wind_gusts,
    "air_quality": score_aqi,
    "temperature": score_temperature,
    "uv_index": score_uv_index,
    "visibility": score_visibility,
    "precipitation": score_precipitation,
}


def _veto(reason: str) -> PaddleScore:
    return PaddleScore(
        value=0,
        rating="NO_GO",
        limiting_factor=None,
        factors={},
        missing_factors=[],
        vetoed=True,
        veto_reason=reason,
    )


def compute_paddle_score(
    *,
    wind_speed: float | None,
    wind_gusts: float | None,
    aqi: int | None,
    air_temp: float | None,
    uv_index: float | None,
    visibility: float | None,
    precipitation: int | None,
    streamflow_cfs: float | None = None,
    tide_current: float | None = None,
    has_thunderstorm: bool,
    weights: dict[str, float],
    water_body_type: str = "lake",
    optimal_cfs: float = 500,
    curves: dict[str, tuple[float, float, float]] | None = None,
    temp_curve: dict[str, float] | None = None,
    veto_thresholds: dict[str, float] | None = None,
    reservoir_storage_af: float | None = None,
    reservoir_capacity_af: float | None = None,
    river_stage_ft: float | None = None,
    stage_baseline: StageBaseline | None = None,
    stage_inverted: bool = False,
    water_quality: Mapping[str, float | None] | None = None,
    dam_outflow_cfs: float | None = None,
    dam_outflow_threshold_cfs: float | None = None,
) -> PaddleScore:
    """Compute the paddle score from raw condition values.

    Factors are determined by water_body_type:
    - lake: 7 base factors only
    - river: 7 base + streamflow
    - bay_ocean: 7 base + tide
    """
    veto_reason = check_hard_vetoes(
        wind_speed=wind_speed,
        wind_gusts=wind_gusts,
        aqi=aqi,
        air_temp=air_temp,
        visibility=visibility,
        has_thunderstorm=has_thunderstorm,
        veto_thresholds=veto_thresholds,
    )
    if veto_reason:
        return PaddleScore(
            value=0,
            rating="NO_GO",
            limiting_factor=None,
            factors={},
            missing_factors=[],
            vetoed=True,
            veto_reason=veto_reason,
        )

    raw_values: dict[str, float | int | None] = {
        "wind_speed": wind_speed,
        "wind_gusts": wind_gusts,
        "air_quality": aqi,
        "temperature": air_temp,
        "uv_index": uv_index,
        "visibility": visibility,
        "precipitation": precipitation,
    }

    factor_scores: dict[str, int] = {}
    missing: list[str] = []

    for factor_name, scorer in _BASE_FACTOR_SCORERS.items():
        value = raw_values[factor_name]
        if curves and factor_name in curves and factor_name != "temperature":
            curve = curves[factor_name]
            if factor_name == "visibility":
                sub_score = scorer(value, ideal_min=curve[0], marginal=curve[1], nogo=curve[2])
            else:
                sub_score = scorer(value, ideal_max=curve[0], marginal=curve[1], nogo=curve[2])
        elif factor_name == "temperature" and temp_curve:
            sub_score = scorer(value, **temp_curve)
        else:
            sub_score = scorer(value)
        if sub_score is not None:
            factor_scores[factor_name] = sub_score
        elif weights.get(factor_name, 0) > 0:
            # A factor the user weighted 0 isn't "missing"; matches the API.
            missing.append(factor_name)

    # Water-body-type-driven factors
    if water_body_type == "river" and "streamflow" in weights:
        sf_score = score_streamflow(streamflow_cfs, optimal_cfs=optimal_cfs)
        if sf_score is not None:
            factor_scores["streamflow"] = sf_score
        else:
            missing.append("streamflow")
    if water_body_type == "bay_ocean" and "tide" in weights:
        t_score = score_tide(tide_current)
        if t_score is not None:
            factor_scores["tide"] = t_score
        else:
            missing.append("tide")

    # CDEC vetoes and factors, in the API's order.
    if (
        dam_outflow_cfs is not None
        and dam_outflow_threshold_cfs is not None
        and dam_outflow_cfs > dam_outflow_threshold_cfs
    ):
        return _veto(f"High dam release: {dam_outflow_cfs:g} CFS exceeds {dam_outflow_threshold_cfs:g} CFS threshold")
    if (
        river_stage_ft is not None
        and stage_baseline is not None
        and stage_baseline.reliable
        and river_stage_ft >= stage_baseline.p95
    ):
        return _veto("Dangerous water level")

    if water_body_type == "lake" and weights.get("reservoir_level"):
        level = score_reservoir_level(reservoir_storage_af, reservoir_capacity_af)
        if level is not None:
            factor_scores["reservoir_level"] = level
        elif reservoir_capacity_af is not None:
            missing.append("reservoir_level")
    if water_quality and weights.get("water_quality"):
        quality = score_water_quality(water_quality)
        if quality is not None:
            factor_scores["water_quality"] = quality
    if water_body_type == "river" and weights.get("river_stage"):
        stage = score_river_stage(river_stage_ft, stage_baseline, stage_inverted)
        if stage is not None:
            factor_scores["river_stage"] = stage
        elif river_stage_ft is not None:
            missing.append("river_stage")

    # Determine applicable factors
    applicable_factors = set(raw_values.keys())
    if water_body_type == "river":
        applicable_factors.add("streamflow")
    elif water_body_type == "bay_ocean":
        applicable_factors.add("tide")

    if not factor_scores:
        return PaddleScore(
            value=0,
            rating="NO_GO",
            limiting_factor=None,
            factors={},
            missing_factors=list(applicable_factors),
            vetoed=False,
            veto_reason=None,
        )

    # Renormalize weights for available factors
    available_weights = {k: weights[k] for k in factor_scores if k in weights}
    total_weight = sum(available_weights.values())
    if total_weight <= 0:
        return PaddleScore(
            value=0,
            rating="NO_GO",
            limiting_factor=None,
            factors=factor_scores,
            missing_factors=missing,
            vetoed=False,
            veto_reason=None,
        )
    weighted_sum = sum(factor_scores[k] * (v / total_weight) for k, v in available_weights.items())

    score_value = _round_half_up(weighted_sum)
    if score_value >= 70:
        rating = "GO"
    elif score_value >= 40:
        rating = "CAUTION"
    else:
        rating = "NO_GO"

    # Only factors that count toward the score can limit it; matches the API.
    weighted = [k for k in factor_scores if weights.get(k, 0) > 0]
    limiting = min(weighted, key=lambda k: factor_scores[k]) if weighted else None

    return PaddleScore(
        value=score_value,
        rating=rating,
        limiting_factor=limiting,
        factors=factor_scores,
        missing_factors=missing,
        vetoed=False,
        veto_reason=None,
    )
