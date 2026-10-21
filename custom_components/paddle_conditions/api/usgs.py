"""USGS Water Data API client (OGC API, replaces the retired WaterServices)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientSession

from .base import BaseAPIClient

# Legacy waterservices.usgs.gov is throttled from 2026-11-16 and shut down
# 2027-02-22. latest-continuous returns the newest value of each time series.
USGS_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/latest-continuous/items"
PARAM_WATER_TEMP = "00010"
PARAM_STREAMFLOW = "00060"

_TO_FAHRENHEIT = {
    "degC": lambda v: v * 9 / 5 + 32,
    "deg C": lambda v: v * 9 / 5 + 32,
    "degF": lambda v: v,
    "deg F": lambda v: v,
}
_CFS_UNITS = {"ft^3/s", "ft3/s", "cfs"}


@dataclass(frozen=True)
class USGSData:
    """Latest USGS readings for a monitoring location, with when each was observed."""

    water_temp_f: float | None
    streamflow_cfs: float | None
    water_temp_observed: datetime | None = None
    streamflow_observed: datetime | None = None


def monitoring_location_id(site_id: str) -> str:
    """Accept '11446500' or 'USGS-11446500' and return the agency-prefixed form."""
    site_id = site_id.strip()
    return site_id if "-" in site_id else f"USGS-{site_id}"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: Any) -> datetime | None:
    """Parse an offset-aware ISO 8601 observation time; reject anything else."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class USGSClient(BaseAPIClient):
    """Client for the USGS latest-continuous collection."""

    def __init__(self, session: ClientSession, api_key: str | None = None) -> None:
        super().__init__(session)
        self._api_key = api_key or None

    @property
    def has_api_key(self) -> bool:
        """Whether requests carry the user's own api.waterdata.usgs.gov key."""
        return self._api_key is not None

    async def fetch(self, site_id: str) -> USGSData:
        """Fetch the latest water temperature and streamflow for a site."""
        params = {
            "f": "json",
            "monitoring_location_id": monitoring_location_id(site_id),
            "parameter_code": f"{PARAM_WATER_TEMP},{PARAM_STREAMFLOW}",
        }
        headers = {"X-Api-Key": self._api_key} if self._api_key else None
        data = await self._get_json(USGS_URL, params=params, headers=headers)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> USGSData:
        # A site can have several series per parameter (e.g. two temperature
        # sensors); keep the most recent reading of each.
        newest: dict[str, tuple[datetime, float]] = {}
        for feature in data.get("features") or []:
            props = feature.get("properties") or {}
            code = props.get("parameter_code")
            value = _number(props.get("value"))
            unit = props.get("unit_of_measure")
            time = _timestamp(props.get("time"))
            if value is None or time is None:
                continue
            if code == PARAM_WATER_TEMP and unit in _TO_FAHRENHEIT:
                value = _TO_FAHRENHEIT[unit](value)
            elif not (code == PARAM_STREAMFLOW and unit in _CFS_UNITS):
                continue
            if code not in newest or time > newest[code][0]:
                newest[code] = (time, value)

        temp = newest.get(PARAM_WATER_TEMP)
        flow = newest.get(PARAM_STREAMFLOW)
        return USGSData(
            water_temp_f=temp[1] if temp else None,
            streamflow_cfs=flow[1] if flow else None,
            water_temp_observed=temp[0] if temp else None,
            streamflow_observed=flow[0] if flow else None,
        )
