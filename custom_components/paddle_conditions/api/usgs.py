"""USGS Water Services API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession

from .base import BaseAPIClient

USGS_URL = "https://waterservices.usgs.gov/nwis/iv/"
PARAM_WATER_TEMP = "00010"
PARAM_STREAMFLOW = "00060"


@dataclass(frozen=True)
class USGSData:
    """Parsed USGS water data."""

    water_temp_f: float | None
    streamflow_cfs: float | None


class USGSClient(BaseAPIClient):
    """Client for USGS Instantaneous Values API."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__(session)

    async def fetch(self, site_id: str) -> USGSData:
        """Fetch water temperature and streamflow for a USGS site."""
        params = {
            "format": "json",
            "sites": site_id,
            "parameterCd": f"{PARAM_WATER_TEMP},{PARAM_STREAMFLOW}",
        }
        data = await self._get_json(USGS_URL, params=params)
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> USGSData:
        time_series = data.get("value", {}).get("timeSeries", [])

        water_temp_c: float | None = None
        streamflow: float | None = None

        for series in time_series:
            var_code = series.get("variable", {}).get("variableCode", [{}])[0].get("value", "")
            values = series.get("values", [{}])[0].get("value", [])
            if not values:
                continue
            latest = values[-1].get("value")
            if latest is None:
                continue

            try:
                num = float(latest)
            except (ValueError, TypeError):
                continue

            if var_code == PARAM_WATER_TEMP:
                water_temp_c = num
            elif var_code == PARAM_STREAMFLOW:
                streamflow = num

        water_temp_f = (water_temp_c * 9 / 5 + 32) if water_temp_c is not None else None

        return USGSData(water_temp_f=water_temp_f, streamflow_cfs=streamflow)
