"""NOAA CO-OPS API client for tide predictions and water temperature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession

from .base import BaseAPIClient

COOPS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


@dataclass(frozen=True)
class TidePrediction:
    """A single tide prediction."""

    time: str
    height_ft: float
    type: str  # "H" (high) or "L" (low)


@dataclass(frozen=True)
class NOAAData:
    """Parsed NOAA data."""

    tide_predictions: list[TidePrediction]
    water_temp_f: float | None


class NOAAClient(BaseAPIClient):
    """Client for NOAA CO-OPS tide predictions and water temperature."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)

    async def fetch_tides(self, station_id: str) -> NOAAData:
        """Fetch tide predictions for a CO-OPS station."""
        params = {
            "station": station_id,
            "product": "predictions",
            "datum": "MLLW",
            "units": "english",
            "time_zone": "lst_ldt",
            "interval": "hilo",
            "format": "json",
            "range": 48,
            "application": "PaddleConditions",
        }
        data = await self._get_json(COOPS_URL, params=params)
        return self._parse_tides(data)

    def _parse_tides(self, data: dict[str, Any]) -> NOAAData:
        predictions = []
        for entry in data.get("predictions", []):
            try:
                predictions.append(
                    TidePrediction(
                        time=entry["t"],
                        height_ft=float(entry["v"]),
                        type=entry.get("type", ""),
                    )
                )
            except (KeyError, ValueError):
                continue

        return NOAAData(tide_predictions=predictions, water_temp_f=None)

    async def fetch_water_temp(self, station_id: str) -> float | None:
        """Fetch latest water temperature from a CO-OPS station."""
        params = {
            "station": station_id,
            "product": "water_temperature",
            "units": "english",
            "time_zone": "gmt",
            "format": "json",
            "date": "latest",
            "application": "PaddleConditions",
        }
        data = await self._get_json(COOPS_URL, params=params)
        entries = data.get("data", [])
        if not entries:
            return None
        try:
            return float(entries[-1]["v"])
        except (KeyError, ValueError, TypeError):
            return None
