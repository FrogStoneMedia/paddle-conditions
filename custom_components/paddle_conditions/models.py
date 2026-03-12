"""Data models for Paddle Conditions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    wind_mph: float
    temp_f: float
    uv: float
    precip_pct: int


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
    condition_text: str | None
    forecast_blocks: list[ForecastBlock]
    hourly_times: list[str]
    hourly_wind: list[float]
    hourly_temp: list[float]
    hourly_uv: list[float]
    hourly_precip: list[int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaddleConditions:
        """Deserialize from a dict."""
        data["score"] = PaddleScore(**data["score"])
        data["forecast_blocks"] = [ForecastBlock(**b) for b in data["forecast_blocks"]]
        return cls(**data)
