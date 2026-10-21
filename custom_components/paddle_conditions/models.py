"""Data models for Paddle Conditions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorResult:
    """Result of scoring a single condition factor."""

    name: str
    value: float | None
    score: int
    weight: float


@dataclass(frozen=True)
class PaddleScore:
    """Computed paddle conditions score."""

    value: int
    rating: str  # "GO", "CAUTION", "NO_GO"
    limiting_factor: str | None
    factors: dict[str, int]
    missing_factors: list[str]
    vetoed: bool
    veto_reason: str | None


@dataclass(frozen=True)
class ForecastBlock:
    """A 3-hour forecast window."""

    start: str
    end: str
    score: int
    rating: str
    wind_mph: float | None
    gust_mph: float | None
    temp_f: float | None
    uv: float | None
    precip_pct: int | None
    aqi: int | None = None
    visibility_mi: float | None = None


@dataclass(frozen=True)
class PaddleConditions:
    """Complete conditions data for a single location."""

    score: PaddleScore
    activity: str  # "sup" | "kayaking"
    profile: str
    wind_speed: float | None
    wind_gusts: float | None
    wind_direction: int | None
    air_temp: float | None
    water_temp: float | None
    uv_index: float | None
    aqi: int | None
    visibility: float | None
    precipitation_probability: int | None
    streamflow_cfs: float | None
    tide_factor: float | None
    condition: str | None  # WMO condition key, e.g. "partly_cloudy"
    forecast_blocks: list[ForecastBlock]
    hourly_times: list[str]
    hourly_wind: list[float | None]
    hourly_gusts: list[float | None]
    hourly_temp: list[float | None]
    hourly_uv: list[float | None]
    hourly_precip: list[int | None]
    fetched_at: str  # UTC ISO 8601, when the weather data was fetched
    daylight: list[dict[str, str]] = field(default_factory=list)  # [{"sunrise", "sunset"}], UTC

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PaddleConditions:
        """Deserialize from a dict without modifying it.

        Raises KeyError, TypeError or ValueError if the shape doesn't match.
        """
        fields = dict(data)
        fields["score"] = PaddleScore(**fields["score"])
        fields["forecast_blocks"] = [ForecastBlock(**b) for b in fields["forecast_blocks"]]
        return cls(**fields)
