"""Paddler profile definitions.

Each profile defines scoring curves, default weights, and hard veto
thresholds. Organized by activity (SUP, Kayaking) then by profile name.
The scoring engine reads curve parameters from the active profile.

Weights include streamflow and tide factors. These only activate when
the location's water_body_type matches (river -> streamflow, bay_ocean -> tide).
Non-applicable factors are excluded and weights renormalize automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
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


@dataclass(frozen=True)
class ProfileConfig:
    """Scoring configuration for a paddler profile."""

    curves: dict[str, tuple[float, float, float]]
    # Each curve is (ideal_max, marginal, nogo) for "lower is better" factors.
    # Temperature uses a special key — see scoring.py for handling.
    temp_curve: dict[str, float]
    # Keys: ideal_low, ideal_high, cold_marginal, cold_nogo, hot_marginal, hot_nogo
    weights: dict[str, float]
    # Includes all 9 possible factors. Scoring engine filters by water_body_type.
    vetoes: dict[str, float]


PROFILES: dict[str, dict[str, ProfileConfig]] = {
    ACTIVITY_SUP: {
        PROFILE_RECREATIONAL: ProfileConfig(
            curves={
                "wind_speed": (5, 11, 20),
                "wind_gusts": (8, 16, 25),
                "air_quality": (25, 87, 150),
                "uv_index": (4, 6.5, 11),
                "visibility": (10, 4, 1),  # inverted: ideal_min, marginal, nogo
                "precipitation": (0, 35, 80),
            },
            temp_curve={
                "ideal_low": 70,
                "ideal_high": 85,
                "cold_marginal": 55,
                "cold_nogo": 40,
                "hot_marginal": 95,
                "hot_nogo": 105,
            },
            weights={
                "wind_speed": 0.30,
                "wind_gusts": 0.10,
                "air_quality": 0.20,
                "temperature": 0.15,
                "uv_index": 0.10,
                "visibility": 0.10,
                "precipitation": 0.05,
                "streamflow": 0.15,
                "tide": 0.10,
            },
            vetoes={
                "wind_speed": 25,
                "wind_gusts": 35,
                "aqi": 200,
                "visibility": 0.5,
                "air_temp_min": 32,
            },
        ),
        PROFILE_RACING: ProfileConfig(
            curves={
                "wind_speed": (8, 16, 25),
                "wind_gusts": (12, 21, 30),
                "air_quality": (25, 87, 150),
                "uv_index": (6, 8.5, 11),
                "visibility": (10, 4, 1),
                "precipitation": (0, 45, 80),
            },
            temp_curve={
                "ideal_low": 60,
                "ideal_high": 90,
                "cold_marginal": 50,
                "cold_nogo": 40,
                "hot_marginal": 95,
                "hot_nogo": 105,
            },
            weights={
                "wind_speed": 0.25,
                "wind_gusts": 0.10,
                "air_quality": 0.15,
                "temperature": 0.10,
                "uv_index": 0.10,
                "visibility": 0.15,
                "precipitation": 0.15,
                "streamflow": 0.10,
                "tide": 0.15,
            },
            vetoes={
                "wind_speed": 30,
                "wind_gusts": 40,
                "aqi": 200,
                "visibility": 0.5,
                "air_temp_min": 32,
            },
        ),
        PROFILE_FAMILY: ProfileConfig(
            curves={
                "wind_speed": (3, 7.5, 15),
                "wind_gusts": (5, 11, 20),
                "air_quality": (25, 62, 100),
                "uv_index": (3, 5.5, 9),
                "visibility": (10, 6, 2),
                "precipitation": (0, 25, 60),
            },
            temp_curve={
                "ideal_low": 72,
                "ideal_high": 85,
                "cold_marginal": 60,
                "cold_nogo": 50,
                "hot_marginal": 92,
                "hot_nogo": 100,
            },
            weights={
                "wind_speed": 0.35,
                "wind_gusts": 0.15,
                "air_quality": 0.20,
                "temperature": 0.15,
                "uv_index": 0.05,
                "visibility": 0.05,
                "precipitation": 0.05,
                "streamflow": 0.20,
                "tide": 0.15,
            },
            vetoes={
                "wind_speed": 18,
                "wind_gusts": 25,
                "aqi": 150,
                "visibility": 1.0,
                "air_temp_min": 45,
            },
        ),
    },
    ACTIVITY_KAYAKING: {
        PROFILE_FLATWATER: ProfileConfig(
            curves={
                "wind_speed": (8, 15, 25),
                "wind_gusts": (12, 19, 30),
                "air_quality": (25, 87, 150),
                "uv_index": (5, 7.5, 11),
                "visibility": (10, 4, 1),
                "precipitation": (0, 40, 80),
            },
            temp_curve={
                "ideal_low": 65,
                "ideal_high": 85,
                "cold_marginal": 50,
                "cold_nogo": 35,
                "hot_marginal": 95,
                "hot_nogo": 105,
            },
            weights={
                "wind_speed": 0.25,
                "wind_gusts": 0.10,
                "air_quality": 0.20,
                "temperature": 0.15,
                "uv_index": 0.10,
                "visibility": 0.10,
                "precipitation": 0.10,
                "streamflow": 0.15,
                "tide": 0.10,
            },
            vetoes={
                "wind_speed": 22,
                "wind_gusts": 30,
                "aqi": 200,
                "visibility": 0.5,
                "air_temp_min": 32,
            },
        ),
        PROFILE_RIVER: ProfileConfig(
            curves={
                "wind_speed": (10, 19, 30),
                "wind_gusts": (15, 23, 35),
                "air_quality": (25, 87, 150),
                "uv_index": (6, 8.5, 11),
                "visibility": (10, 4, 1),
                "precipitation": (0, 35, 70),
            },
            temp_curve={
                "ideal_low": 60,
                "ideal_high": 85,
                "cold_marginal": 45,
                "cold_nogo": 35,
                "hot_marginal": 95,
                "hot_nogo": 105,
            },
            weights={
                "wind_speed": 0.10,
                "wind_gusts": 0.05,
                "air_quality": 0.15,
                "temperature": 0.15,
                "uv_index": 0.05,
                "visibility": 0.05,
                "precipitation": 0.10,
                "streamflow": 0.35,
                "tide": 0.0,
            },
            vetoes={
                "wind_speed": 35,
                "wind_gusts": 45,
                "aqi": 200,
                "visibility": 0.5,
                "air_temp_min": 32,
            },
        ),
        PROFILE_OCEAN: ProfileConfig(
            curves={
                "wind_speed": (10, 19, 28),
                "wind_gusts": (15, 23, 35),
                "air_quality": (25, 87, 150),
                "uv_index": (5, 7.5, 11),
                "visibility": (10, 6, 2),
                "precipitation": (0, 40, 80),
            },
            temp_curve={
                "ideal_low": 60,
                "ideal_high": 85,
                "cold_marginal": 50,
                "cold_nogo": 40,
                "hot_marginal": 95,
                "hot_nogo": 105,
            },
            weights={
                "wind_speed": 0.20,
                "wind_gusts": 0.10,
                "air_quality": 0.10,
                "temperature": 0.10,
                "uv_index": 0.05,
                "visibility": 0.20,
                "precipitation": 0.10,
                "streamflow": 0.0,
                "tide": 0.15,
            },
            vetoes={
                "wind_speed": 35,
                "wind_gusts": 45,
                "aqi": 200,
                "visibility": 1.0,
                "air_temp_min": 32,
            },
        ),
    },
}


def get_profile(activity: str, name: str) -> ProfileConfig:
    """Get a profile by activity and name.

    Falls back to the activity's default profile, or SUP Recreational
    if the activity is also unknown.
    """
    activity_profiles = PROFILES.get(activity)
    if activity_profiles is None:
        return PROFILES[ACTIVITY_SUP][PROFILE_RECREATIONAL]
    default_name = DEFAULT_PROFILES.get(activity, PROFILE_RECREATIONAL)
    return activity_profiles.get(name, activity_profiles[default_name])
