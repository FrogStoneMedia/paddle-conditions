"""Client for the Paddle Conditions public API (curated spots and their gauges)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..scoring import StageBaseline
from .base import APIError, BaseAPIClient

PC_API_URL = "https://api.paddleconditions.com"


@dataclass(frozen=True)
class CuratedSpot:
    """A spot from the Paddle Conditions directory."""

    slug: str
    name: str
    type: str
    county: str | None
    state: str


@dataclass(frozen=True)
class SpotStations:
    """A curated spot's location, gauges and hand-curated scoring metadata."""

    slug: str
    name: str
    type: str
    latitude: float
    longitude: float
    usgs: tuple[str, ...]
    noaa: tuple[str, ...]
    cdec: tuple[str, ...]
    reservoir_capacity_af: float | None
    dam_outflow_threshold_cfs: float | None
    # CDEC station id -> month (1-12) -> percentiles.
    stage_baselines: dict[str, dict[int, StageBaseline]]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _station_ids(raw: Any) -> tuple[str, ...]:
    return tuple(str(s["id"]) for s in raw or [] if isinstance(s, dict) and s.get("id"))


def _baseline(raw: dict[str, Any]) -> tuple[int, StageBaseline] | None:
    keys = ("month", "p10", "p25", "p50", "p75", "p90", "p95", "sampleCount")
    values = [_number(raw.get(k)) for k in keys]
    if any(v is None for v in values):
        return None
    month, p10, p25, p50, p75, p90, p95, count = (float(v or 0) for v in values)
    return int(month), StageBaseline(p10, p25, p50, p75, p90, p95, int(count))


class PaddleConditionsClient(BaseAPIClient):
    """Reads the public, unauthenticated endpoints only."""

    async def curated_spots(self) -> list[CuratedSpot]:
        """Every curated spot, grouped by state then by popularity as the API orders them."""
        data = await self._get_json(f"{PC_API_URL}/public/spots/directory")
        spots: list[CuratedSpot] = []
        for state in (data or {}).get("states") or []:
            for spot in state.get("spots") or []:
                if spot.get("slug") and spot.get("name"):
                    spots.append(
                        CuratedSpot(
                            slug=spot["slug"],
                            name=spot["name"],
                            type=spot.get("type", ""),
                            county=spot.get("county"),
                            state=state.get("state", ""),
                        )
                    )
        return spots

    async def spot_stations(self, slug: str) -> SpotStations:
        """Gauges and metadata for one curated spot."""
        data = await self._get_json(f"{PC_API_URL}/public/spot/{slug}/stations")
        latitude, longitude = _number(data.get("lat")), _number(data.get("lng"))
        if latitude is None or longitude is None:
            raise APIError(f"Paddle Conditions returned no location for {slug}")
        stations = data.get("stations") or {}
        baselines: dict[str, dict[int, StageBaseline]] = {}
        for station_id, months in (data.get("stageBaselines") or {}).items():
            parsed = dict(b for raw in months or [] if isinstance(raw, dict) and (b := _baseline(raw)))
            if parsed:
                baselines[str(station_id)] = parsed
        return SpotStations(
            slug=str(data.get("slug", slug)),
            name=str(data.get("name", "")),
            type=str(data.get("type", "")),
            latitude=latitude,
            longitude=longitude,
            usgs=_station_ids(stations.get("usgs")),
            noaa=_station_ids(stations.get("noaa")),
            cdec=_station_ids(stations.get("cdec")),
            reservoir_capacity_af=_number(data.get("reservoirCapacityAf")),
            dam_outflow_threshold_cfs=_number(data.get("damOutflowThresholdCfs")),
            stage_baselines=baselines,
        )
