"""Tests for paddler profile definitions."""

from __future__ import annotations

from custom_components.paddle_conditions.const import (
    ACTIVITY_KAYAKING,
    ACTIVITY_SUP,
    DEFAULT_PROFILES,
    PROFILE_FAMILY,
    PROFILE_FLATWATER,
    PROFILE_OCEAN,
    PROFILE_RACING,
    PROFILE_RECREATIONAL,
    PROFILE_RIVER,
)
from custom_components.paddle_conditions.profiles import (
    PROFILES,
    ProfileConfig,
    get_profile,
)


def test_all_activities_exist():
    assert ACTIVITY_SUP in PROFILES
    assert ACTIVITY_KAYAKING in PROFILES


def test_all_sup_profiles_exist():
    assert PROFILE_RECREATIONAL in PROFILES[ACTIVITY_SUP]
    assert PROFILE_RACING in PROFILES[ACTIVITY_SUP]
    assert PROFILE_FAMILY in PROFILES[ACTIVITY_SUP]


def test_all_kayaking_profiles_exist():
    assert PROFILE_FLATWATER in PROFILES[ACTIVITY_KAYAKING]
    assert PROFILE_RIVER in PROFILES[ACTIVITY_KAYAKING]
    assert PROFILE_OCEAN in PROFILES[ACTIVITY_KAYAKING]


def test_profile_weights_are_positive():
    """All weights should be non-negative."""
    for activity, profiles in PROFILES.items():
        for name, profile in profiles.items():
            for factor, weight in profile.weights.items():
                assert weight >= 0, f"{activity}/{name} {factor} has negative weight {weight}"


def test_profile_total_weights_reasonable():
    """Total of all 9 weights should be > 1.0 (renormalization handles it).

    Profiles define weights for all 9 factors. Only applicable factors are
    included per water body type, then weights renormalize. The total across
    all 9 exceeds 1.0 by design.
    """
    for activity, profiles in PROFILES.items():
        for name, profile in profiles.items():
            total = sum(profile.weights.values())
            assert total >= 0.9, f"{activity}/{name} total weights too low: {total}"


def test_profile_has_base_curves():
    # Temperature uses temp_curve (separate dict), not the curves dict
    base_expected = {
        "wind_speed",
        "wind_gusts",
        "air_quality",
        "uv_index",
        "visibility",
        "precipitation",
    }
    for activity, profiles in PROFILES.items():
        for name, profile in profiles.items():
            assert base_expected.issubset(set(profile.curves.keys())), f"{activity}/{name} missing base curves"
            assert profile.temp_curve, f"{activity}/{name} missing temp_curve"


def test_river_profile_has_streamflow_weight():
    river_kayak = PROFILES[ACTIVITY_KAYAKING][PROFILE_RIVER]
    assert "streamflow" in river_kayak.weights


def test_ocean_profile_has_tide_weight():
    ocean_kayak = PROFILES[ACTIVITY_KAYAKING][PROFILE_OCEAN]
    assert "tide" in ocean_kayak.weights


def test_sup_profiles_have_water_body_type_weights():
    for name, profile in PROFILES[ACTIVITY_SUP].items():
        assert "streamflow" in profile.weights, f"SUP/{name} missing streamflow weight"
        assert "tide" in profile.weights, f"SUP/{name} missing tide weight"


def test_profile_has_all_vetoes():
    base_expected = {"wind_speed", "wind_gusts", "aqi", "visibility", "air_temp_min"}
    for activity, profiles in PROFILES.items():
        for name, profile in profiles.items():
            assert base_expected.issubset(set(profile.vetoes.keys())), f"{activity}/{name} missing vetoes"


def test_recreational_wind_curve():
    profile = PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    curve = profile.curves["wind_speed"]
    assert curve == (5, 11, 20)


def test_racing_wind_more_tolerant():
    rec = PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    racing = PROFILES[ACTIVITY_SUP][PROFILE_RACING]
    assert racing.curves["wind_speed"][2] > rec.curves["wind_speed"][2]


def test_family_wind_stricter():
    rec = PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    family = PROFILES[ACTIVITY_SUP][PROFILE_FAMILY]
    assert family.curves["wind_speed"][2] < rec.curves["wind_speed"][2]


def test_family_veto_stricter():
    rec = PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    family = PROFILES[ACTIVITY_SUP][PROFILE_FAMILY]
    assert family.vetoes["wind_speed"] < rec.vetoes["wind_speed"]


def test_kayak_flatwater_more_wind_tolerant_than_sup_recreational():
    sup_rec = PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    kayak_flat = PROFILES[ACTIVITY_KAYAKING][PROFILE_FLATWATER]
    assert kayak_flat.curves["wind_speed"][0] > sup_rec.curves["wind_speed"][0]


def test_get_profile_returns_default():
    profile = get_profile(ACTIVITY_SUP, PROFILE_RECREATIONAL)
    assert isinstance(profile, ProfileConfig)


def test_get_profile_unknown_returns_activity_default():
    profile = get_profile(ACTIVITY_SUP, "nonexistent")
    assert profile == PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]


def test_get_profile_unknown_activity_returns_sup_recreational():
    profile = get_profile("nonexistent", "nonexistent")
    assert profile == PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]


def test_activity_switch_resets_to_default_profile():
    assert DEFAULT_PROFILES[ACTIVITY_SUP] == PROFILE_RECREATIONAL
    assert DEFAULT_PROFILES[ACTIVITY_KAYAKING] == PROFILE_FLATWATER


def test_all_profiles_have_temp_curve():
    required_keys = {
        "ideal_low",
        "ideal_high",
        "cold_marginal",
        "cold_nogo",
        "hot_marginal",
        "hot_nogo",
    }
    for activity, profiles in PROFILES.items():
        for name, profile in profiles.items():
            assert required_keys == set(profile.temp_curve.keys()), f"{activity}/{name} temp_curve missing keys"
