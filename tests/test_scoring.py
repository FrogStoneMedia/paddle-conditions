"""Tests for the Paddle Conditions scoring engine."""

from __future__ import annotations

import pytest

from custom_components.paddle_conditions.models import (
    FactorResult,
    ForecastBlock,
    PaddleConditions,
    PaddleScore,
)
from custom_components.paddle_conditions.scoring import (
    check_hard_vetoes,
    compute_paddle_score,
    score_aqi,
    score_precipitation,
    score_streamflow,
    score_temperature,
    score_tide,
    score_uv_index,
    score_visibility,
    score_wind_gusts,
    score_wind_speed,
)


def test_factor_result_creation():
    result = FactorResult(name="wind_speed", value=8.0, score=75, weight=0.30)
    assert result.name == "wind_speed"
    assert result.value == 8.0
    assert result.score == 75
    assert result.weight == 0.30


def test_factor_result_none_value():
    result = FactorResult(name="water_temp", value=None, score=0, weight=0.10)
    assert result.value is None


def test_paddle_score_go():
    score = PaddleScore(
        value=82,
        rating="GO",
        limiting_factor="wind_speed",
        factors={"wind_speed": 68, "air_quality": 95},
        missing_factors=[],
        vetoed=False,
        veto_reason=None,
    )
    assert score.value == 82
    assert score.rating == "GO"
    assert not score.vetoed


def test_paddle_score_vetoed():
    score = PaddleScore(
        value=0,
        rating="NO_GO",
        limiting_factor=None,
        factors={},
        missing_factors=[],
        vetoed=True,
        veto_reason="Wind > 25 mph sustained",
    )
    assert score.vetoed
    assert score.veto_reason == "Wind > 25 mph sustained"


def test_paddle_conditions_creation():
    score = PaddleScore(
        value=75,
        rating="GO",
        limiting_factor="wind_speed",
        factors={},
        missing_factors=[],
        vetoed=False,
        veto_reason=None,
    )
    conditions = PaddleConditions(
        score=score,
        activity="sup",
        profile="recreational",
        wind_speed=8.0,
        wind_gusts=12.0,
        wind_direction=180,
        air_temp=75.0,
        water_temp=68.0,
        uv_index=5.0,
        aqi=42,
        visibility=10.0,
        precipitation_probability=10,
        streamflow_cfs=None,
        tide_factor=None,
        condition="partly_cloudy",
        forecast_blocks=[],
        hourly_times=[],
        hourly_wind=[],
        hourly_temp=[],
        hourly_uv=[],
        hourly_precip=[],
        hourly_gusts=[],
        fetched_at="2026-10-21T19:00:00+00:00",
    )
    assert conditions.wind_speed == 8.0
    assert conditions.water_temp == 68.0
    assert conditions.score.value == 75
    assert conditions.activity == "sup"


def test_forecast_block_creation():
    block = ForecastBlock(
        start="2026-03-10T12:00:00",
        end="2026-03-10T15:00:00",
        score=72,
        rating="GO",
        wind_mph=8.0,
        gust_mph=None,
        temp_f=78.0,
        uv=5.2,
        precip_pct=0,
    )
    assert block.score == 72
    assert block.rating == "GO"


def test_paddle_conditions_with_forecast():
    score = PaddleScore(
        value=75,
        rating="GO",
        limiting_factor=None,
        factors={},
        missing_factors=[],
        vetoed=False,
        veto_reason=None,
    )
    block = ForecastBlock(
        start="2026-03-10T12:00:00",
        end="2026-03-10T15:00:00",
        score=72,
        rating="GO",
        wind_mph=8.0,
        gust_mph=None,
        temp_f=78.0,
        uv=5.2,
        precip_pct=0,
    )
    conditions = PaddleConditions(
        score=score,
        activity="sup",
        profile="recreational",
        wind_speed=8.0,
        wind_gusts=12.0,
        wind_direction=180,
        air_temp=75.0,
        water_temp=None,
        uv_index=5.0,
        aqi=42,
        visibility=10.0,
        precipitation_probability=10,
        streamflow_cfs=None,
        tide_factor=None,
        condition=None,
        forecast_blocks=[block],
        hourly_times=[],
        hourly_wind=[],
        hourly_temp=[],
        hourly_uv=[],
        hourly_precip=[],
        hourly_gusts=[],
        fetched_at="2026-10-21T19:00:00+00:00",
    )
    assert len(conditions.forecast_blocks) == 1
    assert conditions.forecast_blocks[0].score == 72


# ============================================================================
# Task 5: Factor scoring functions
# ============================================================================

# --- Wind speed ---


def test_score_wind_speed_ideal():
    assert score_wind_speed(0) == 100
    assert score_wind_speed(3) == 100
    assert score_wind_speed(5) == 100


def test_score_wind_speed_marginal():
    assert 45 <= score_wind_speed(11) <= 55


def test_score_wind_speed_nogo():
    assert score_wind_speed(20) == 0
    assert score_wind_speed(30) == 0


def test_score_wind_speed_none():
    assert score_wind_speed(None) is None


# --- Wind gusts ---


def test_score_wind_gusts_ideal():
    assert score_wind_gusts(5) == 100


def test_score_wind_gusts_nogo():
    assert score_wind_gusts(25) == 0


def test_score_wind_gusts_none():
    assert score_wind_gusts(None) is None


# --- AQI ---


def test_score_aqi_ideal():
    assert score_aqi(20) == 100


def test_score_aqi_nogo():
    assert score_aqi(150) == 0


def test_score_aqi_none():
    assert score_aqi(None) is None


# --- Temperature ---


def test_score_temperature_ideal():
    assert score_temperature(75) == 100


def test_score_temperature_cold_nogo():
    assert score_temperature(40) == 0


def test_score_temperature_hot_nogo():
    assert score_temperature(105) == 0


def test_score_temperature_none():
    assert score_temperature(None) is None


def test_score_temperature_cold_marginal():
    assert 45 <= score_temperature(55) <= 55


def test_score_temperature_hot_marginal():
    assert 45 <= score_temperature(95) <= 55


# --- UV index ---


def test_score_uv_ideal():
    assert score_uv_index(3) == 100


def test_score_uv_nogo():
    assert score_uv_index(11) == 0


def test_score_uv_none():
    assert score_uv_index(None) is None


# --- Visibility ---


def test_score_visibility_ideal():
    assert score_visibility(10) == 100
    assert score_visibility(15) == 100


def test_score_visibility_nogo():
    assert score_visibility(1) == 0


def test_score_visibility_none():
    assert score_visibility(None) is None


# --- Precipitation ---


def test_score_precipitation_ideal():
    assert score_precipitation(0) == 100


def test_score_precipitation_nogo():
    assert score_precipitation(80) == 0


def test_score_precipitation_none():
    assert score_precipitation(None) is None


# --- Streamflow ---


def test_score_streamflow_optimal():
    assert score_streamflow(500, optimal_cfs=500) == 100


def test_score_streamflow_too_high():
    assert score_streamflow(2000, optimal_cfs=500) == 0


def test_score_streamflow_none():
    assert score_streamflow(None) is None


def test_score_streamflow_near_optimal():
    """Within 0.8-1.2x optimal should score 100."""
    assert score_streamflow(450, optimal_cfs=500) == 100
    assert score_streamflow(600, optimal_cfs=500) == 100


# --- Tide ---


def test_score_tide_slack():
    assert score_tide(0.0) == 100


def test_score_tide_strong():
    assert score_tide(3.0) == 0


def test_score_tide_none():
    assert score_tide(None) is None


def test_score_tide_negative_current():
    """Negative current (ebb) should use absolute value."""
    assert score_tide(-0.3) == 100


# ============================================================================
# Task 6: Hard vetoes and final score
# ============================================================================

# --- Hard vetoes ---


def test_no_vetoes_normal_conditions():
    assert (
        check_hard_vetoes(
            wind_speed=10,
            wind_gusts=15,
            aqi=50,
            air_temp=75,
            visibility=10,
            has_thunderstorm=False,
        )
        is None
    )


def test_veto_high_wind():
    result = check_hard_vetoes(
        wind_speed=26,
        wind_gusts=15,
        aqi=50,
        air_temp=75,
        visibility=10,
        has_thunderstorm=False,
    )
    assert result is not None
    assert "wind" in result.lower()


def test_veto_high_gusts():
    result = check_hard_vetoes(
        wind_speed=10,
        wind_gusts=36,
        aqi=50,
        air_temp=75,
        visibility=10,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_high_aqi():
    result = check_hard_vetoes(
        wind_speed=10,
        wind_gusts=15,
        aqi=201,
        air_temp=75,
        visibility=10,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_thunderstorm():
    result = check_hard_vetoes(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        visibility=10,
        has_thunderstorm=True,
    )
    assert result is not None
    assert "lightning" in result.lower() or "thunderstorm" in result.lower()


def test_veto_low_visibility():
    result = check_hard_vetoes(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        visibility=0.4,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_freezing():
    result = check_hard_vetoes(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=31,
        visibility=10,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_boundary_wind_at_threshold_no_veto():
    """Exactly at wind threshold should NOT veto (uses strict >)."""
    assert (
        check_hard_vetoes(
            wind_speed=25,
            wind_gusts=15,
            aqi=50,
            air_temp=75,
            visibility=10,
            has_thunderstorm=False,
        )
        is None
    )


def test_veto_boundary_wind_just_above_threshold():
    """Just above wind threshold should veto."""
    result = check_hard_vetoes(
        wind_speed=25.001,
        wind_gusts=15,
        aqi=50,
        air_temp=75,
        visibility=10,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_boundary_visibility_at_threshold_no_veto():
    """Exactly at visibility threshold should NOT veto (uses strict <)."""
    assert (
        check_hard_vetoes(
            wind_speed=5,
            wind_gusts=8,
            aqi=25,
            air_temp=75,
            visibility=0.5,
            has_thunderstorm=False,
        )
        is None
    )


def test_veto_boundary_visibility_just_below_threshold():
    """Just below visibility threshold should veto."""
    result = check_hard_vetoes(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        visibility=0.499,
        has_thunderstorm=False,
    )
    assert result is not None


def test_veto_none_values_no_veto():
    """Missing data should not trigger vetoes."""
    assert (
        check_hard_vetoes(
            wind_speed=None,
            wind_gusts=None,
            aqi=None,
            air_temp=None,
            visibility=None,
            has_thunderstorm=False,
        )
        is None
    )


def test_veto_custom_thresholds():
    """Family profile has stricter thresholds."""
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "family")
    result = check_hard_vetoes(
        wind_speed=20,
        wind_gusts=15,
        aqi=50,
        air_temp=75,
        visibility=10,
        has_thunderstorm=False,
        veto_thresholds=profile.vetoes,
    )
    assert result is not None  # Family veto at 18 mph


# --- compute_paddle_score ---


def test_compute_score_ideal_conditions():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=3,
        wind_gusts=5,
        aqi=15,
        air_temp=78,
        uv_index=3,
        visibility=12,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.rating == "GO"
    assert score.value >= 90
    assert not score.vetoed
    assert score.missing_factors == []


def test_compute_score_poor_conditions():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=18,
        wind_gusts=22,
        aqi=130,
        air_temp=45,
        uv_index=9,
        visibility=2,
        precipitation=60,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.rating in ("CAUTION", "NO_GO")
    assert score.value < 70


def test_compute_score_vetoed():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=30,
        wind_gusts=40,
        aqi=15,
        air_temp=78,
        uv_index=3,
        visibility=12,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.value == 0
    assert score.rating == "NO_GO"
    assert score.vetoed


def test_compute_score_missing_data():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=8,
        wind_gusts=None,
        aqi=None,
        air_temp=75,
        uv_index=4,
        visibility=None,
        precipitation=10,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.rating in ("GO", "CAUTION")
    assert "wind_gusts" in score.missing_factors
    assert "air_quality" in score.missing_factors
    assert "visibility" in score.missing_factors


def test_compute_score_all_missing():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=None,
        wind_gusts=None,
        aqi=None,
        air_temp=None,
        uv_index=None,
        visibility=None,
        precipitation=None,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.value == 0
    assert score.rating == "NO_GO"
    assert score.missing_factors != []


def test_compute_score_limiting_factor():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=18,
        wind_gusts=5,
        aqi=10,
        air_temp=78,
        uv_index=2,
        visibility=12,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert score.limiting_factor == "wind_speed"


def test_compute_score_river_includes_streamflow():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("kayaking", "river")
    score = compute_paddle_score(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        uv_index=3,
        visibility=10,
        precipitation=0,
        streamflow_cfs=500,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="river",
        optimal_cfs=500,
    )
    assert score.rating == "GO"
    assert "streamflow" not in score.missing_factors


def test_compute_score_bay_ocean_includes_tide():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        uv_index=3,
        visibility=10,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=0.3,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="bay_ocean",
    )
    assert score.rating == "GO"
    assert "tide" not in score.missing_factors


def test_compute_score_lake_excludes_streamflow_and_tide():
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        uv_index=3,
        visibility=10,
        precipitation=0,
        streamflow_cfs=500,
        tide_current=0.3,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
    )
    assert "streamflow" not in score.factors
    assert "tide" not in score.factors


def test_compute_score_with_profile_curves():
    """Score should use profile-specific curves when provided."""
    from custom_components.paddle_conditions.profiles import get_profile

    profile = get_profile("sup", "family")
    score = compute_paddle_score(
        wind_speed=10,
        wind_gusts=8,
        aqi=25,
        air_temp=78,
        uv_index=3,
        visibility=10,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=profile.weights,
        water_body_type="lake",
        curves=profile.curves,
        temp_curve=profile.temp_curve,
    )
    # Family profile: wind 10 mph is marginal (nogo at 15), so score should be lower
    assert score.factors["wind_speed"] < 50


def test_compute_score_zero_weights_no_crash():
    """All weights zero should return NO_GO without ZeroDivisionError."""
    zero_weights = {
        "wind_speed": 0,
        "wind_gusts": 0,
        "air_quality": 0,
        "temperature": 0,
        "uv_index": 0,
        "visibility": 0,
        "precipitation": 0,
    }
    score = compute_paddle_score(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        uv_index=3,
        visibility=10,
        precipitation=0,
        has_thunderstorm=False,
        weights=zero_weights,
        water_body_type="lake",
    )
    assert score.value == 0
    assert score.rating == "NO_GO"


def test_compute_score_missing_weight_key_no_crash():
    """Factors with scores but no weight key should not raise KeyError."""
    partial_weights = {
        "wind_speed": 0.50,
        "temperature": 0.50,
        # Missing: wind_gusts, air_quality, uv_index, visibility, precipitation
    }
    score = compute_paddle_score(
        wind_speed=5,
        wind_gusts=8,
        aqi=25,
        air_temp=75,
        uv_index=3,
        visibility=10,
        precipitation=0,
        has_thunderstorm=False,
        weights=partial_weights,
        water_body_type="lake",
    )
    # Should compute score from just wind_speed and temperature
    assert score.rating in ("GO", "CAUTION", "NO_GO")
    assert score.value >= 0


def test_zero_weight_factor_is_never_limiting_or_missing():
    """Matches the Paddle Conditions API: a factor weighted 0 can't limit the score or count as missing."""
    from custom_components.paddle_conditions.scoring import compute_paddle_score

    weights = {
        "wind_speed": 0.5,
        "wind_gusts": 0.0,
        "air_quality": 0.5,
        "temperature": 0.0,
        "uv_index": 0.0,
        "visibility": 0.0,
        "precipitation": 0.0,
    }
    score = compute_paddle_score(
        wind_speed=2.0,
        wind_gusts=None,
        aqi=20,
        air_temp=75.0,
        uv_index=11.0,  # Terrible UV, but weighted 0.
        visibility=None,
        precipitation=None,
        has_thunderstorm=False,
        weights=weights,
    )

    assert score.limiting_factor in {"wind_speed", "air_quality"}
    assert score.missing_factors == []


# --- Parity with the Paddle Conditions API (api/src/lib/scoring.ts) ---------

from custom_components.paddle_conditions.scoring import (  # noqa: E402
    StageBaseline,
    score_reservoir_level,
    score_river_stage,
    score_water_quality,
)

BASELINE = StageBaseline(p10=2.0, p25=3.0, p50=4.0, p75=6.0, p90=8.0, p95=10.0, sample_count=90)


@pytest.mark.parametrize(
    ("storage", "capacity", "expected"),
    [
        (700, 1000, 100),
        (600, 1000, 100),
        (200, 1000, 0),
        (100, 1000, 0),
        (400, 1000, 50),
        (None, 1000, None),
        (500, None, None),
        (500, 0, None),
    ],
)
def test_reservoir_level_matches_api(storage, capacity, expected):
    assert score_reservoir_level(storage, capacity) == expected


@pytest.mark.parametrize(
    ("stage", "inverted", "expected"),
    [
        (4.0, False, 100),
        (6.0, False, 50),
        (8.0, False, 0),
        (5.0, False, 75),
        (4.0, True, 100),
        (3.0, True, 50),
        (2.0, True, 0),
        (None, False, None),
    ],
)
def test_river_stage_matches_api(stage, inverted, expected):
    assert score_river_stage(stage, BASELINE, inverted) == expected


def test_river_stage_needs_enough_baseline_samples():
    thin = StageBaseline(p10=2.0, p25=3.0, p50=4.0, p75=6.0, p90=8.0, p95=10.0, sample_count=59)
    assert score_river_stage(5.0, thin, False) is None
    assert score_river_stage(5.0, None, False) is None


@pytest.mark.parametrize(
    ("wq", "expected"),
    [
        ({}, None),
        ({"turbidity_ntu": 5}, 100),
        ({"turbidity_ntu": 50}, 50),
        ({"dissolved_oxygen_mg_l": 4}, 50),
        ({"ph": 7.0}, 100),
        ({"ph": 6.0}, 50),
        ({"ph": 9.0}, 50),
        ({"conductivity_us": 2000}, 50),
        ({"turbidity_ntu": 5, "ph": 6.0}, 75),
    ],
)
def test_water_quality_matches_api(wq, expected):
    assert score_water_quality(wq) == expected


def _ideal(**overrides):
    from custom_components.paddle_conditions.scoring import compute_paddle_score

    args = dict(
        wind_speed=2.0,
        wind_gusts=4.0,
        aqi=20,
        air_temp=75.0,
        uv_index=2.0,
        visibility=10.0,
        precipitation=0,
        has_thunderstorm=False,
        weights={
            "wind_speed": 0.3,
            "wind_gusts": 0.1,
            "air_quality": 0.2,
            "temperature": 0.15,
            "uv_index": 0.1,
            "visibility": 0.1,
            "precipitation": 0.05,
            "streamflow": 0.15,
            "tide": 0.1,
            "reservoir_level": 0.1,
            "water_quality": 0.1,
            "river_stage": 0.1,
        },
    )
    args.update(overrides)
    return compute_paddle_score(**args)


def test_dam_release_above_threshold_is_a_veto():
    score = _ideal(dam_outflow_cfs=5200, dam_outflow_threshold_cfs=5000)
    assert score.vetoed and score.rating == "NO_GO"
    assert score.veto_reason == "High dam release: 5200 CFS exceeds 5000 CFS threshold"


def test_river_stage_at_p95_is_a_veto_for_every_water_body():
    score = _ideal(river_stage_ft=10.0, stage_baseline=BASELINE, water_body_type="lake")
    assert score.vetoed and score.veto_reason == "Dangerous water level"


def test_reservoir_level_scores_on_lakes_and_counts_as_missing_without_storage():
    low = _ideal(water_body_type="lake", reservoir_storage_af=200, reservoir_capacity_af=1000)
    assert low.factors["reservoir_level"] == 0
    missing = _ideal(water_body_type="lake", reservoir_storage_af=None, reservoir_capacity_af=1000)
    assert "reservoir_level" in missing.missing_factors
    not_configured = _ideal(water_body_type="lake")
    assert "reservoir_level" not in not_configured.missing_factors


def test_river_stage_scores_only_on_rivers():
    river = _ideal(water_body_type="river", streamflow_cfs=500, river_stage_ft=8.0, stage_baseline=BASELINE)
    assert river.factors["river_stage"] == 0
    lake = _ideal(water_body_type="lake", river_stage_ft=8.0, stage_baseline=BASELINE)
    assert "river_stage" not in lake.factors


def test_water_quality_scores_when_present():
    score = _ideal(water_quality={"turbidity_ntu": 50})
    assert score.factors["water_quality"] == 50


def test_rounding_matches_javascript_half_up():
    """Python's round() is banker's rounding; the API (Math.round) rounds .5 up."""
    from custom_components.paddle_conditions.scoring import _linear_score

    # 100 - 50 * (11.25 - 10) / (20 - 10) = 93.75 -> 94 either way; pick an exact .5:
    assert _linear_score(12.5, 10, 20, 30) == 88  # 87.5 -> 88 (round() would give 88 too)
    assert _linear_score(11.5, 10, 20, 30) == 93  # 92.5 -> 93, round() gives 92


def test_weighted_sum_accumulates_like_the_api():
    """Python's sum() compensates float error since 3.12; the API adds left to right.

    Same inputs, verified against the API's computePaddleScore: 69, CAUTION.
    """
    from custom_components.paddle_conditions.profiles import get_profile

    p = get_profile("sup", "recreational")
    score = compute_paddle_score(
        wind_speed=10,
        wind_gusts=12,
        aqi=50,
        air_temp=75,
        uv_index=2,
        visibility=10,
        precipitation=0,
        streamflow_cfs=None,
        tide_current=None,
        has_thunderstorm=False,
        weights=p.weights,
        water_body_type="lake",
        curves=p.curves,
        temp_curve=p.temp_curve,
        veto_thresholds=p.vetoes,
        reservoir_storage_af=300,
        reservoir_capacity_af=1000,
        water_quality={"turbidity_ntu": 100},
    )
    assert (score.value, score.rating) == (69, "CAUTION")
