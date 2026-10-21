"""CDEC (California Data Exchange Center) client for reservoir, river stage and water quality readings."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .base import APIError, BaseAPIClient

CDEC_URL = "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet"

# CDEC stamps readings in Pacific Standard Time all year (no daylight time)
# and does not zero-pad: "2026-10-21 9:45".
CDEC_TZ = timezone(timedelta(hours=-8))
_DATE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?: (\d{1,2}):(\d{2}))?$")

# CDEC pads every slot not reported yet with this value.
NO_DATA = -9999
# N = error, v = out of range.
BAD_FLAGS = frozenset({"N", "v"})

# Sensor numbers, as in the Paddle Conditions API (src/services/cdec.ts).
# Event (15-minute) sensors:
EVENT_SENSORS = {
    25: "water_temp_f",
    20: "flow_cfs",
    1: "river_stage_ft",
    27: "turbidity_ntu",
    61: "dissolved_oxygen_mg_l",
    62: "ph",
    100: "conductivity_us",
}
# Hourly reservoir sensors:
HOURLY_SENSORS = {
    15: "storage_af",
    6: "elevation_ft",
    76: "inflow_cfs",
    23: "outflow_cfs",
}


@dataclass(frozen=True)
class CDECReading:
    """One sensor value and when it was observed."""

    value: float
    observed: datetime


@dataclass(frozen=True)
class CDECData:
    """Latest readings from one or more CDEC stations. None = not reported."""

    water_temp_f: CDECReading | None = None
    flow_cfs: CDECReading | None = None
    river_stage_ft: CDECReading | None = None
    turbidity_ntu: CDECReading | None = None
    dissolved_oxygen_mg_l: CDECReading | None = None
    ph: CDECReading | None = None
    conductivity_us: CDECReading | None = None
    storage_af: CDECReading | None = None
    elevation_ft: CDECReading | None = None
    inflow_cfs: CDECReading | None = None
    outflow_cfs: CDECReading | None = None

    def merged_with(self, other: CDECData) -> CDECData:
        """Fill fields this station lacks from *other* (stations are ordered nearest first)."""
        return CDECData(**{f.name: getattr(self, f.name) or getattr(other, f.name) for f in fields(self)})


def parse_cdec_date(raw: Any) -> datetime | None:
    """Parse a CDEC timestamp to an aware datetime, or None."""
    match = _DATE.match(str(raw or "").strip())
    if not match:
        return None
    year, month, day, hour, minute = (int(part) if part else 0 for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute, tzinfo=CDEC_TZ)
    except ValueError:
        return None


def _latest(records: list[dict[str, Any]], sensors: dict[int, str], now: datetime) -> dict[str, CDECReading]:
    """Newest valid reading per field, skipping bad flags, placeholders and future slots.

    Orders by parsed time: as strings, '9:45' sorts after '14:00'.
    """
    latest: dict[str, CDECReading] = {}
    for record in records:
        field = sensors.get(record.get("SENSOR_NUM"))  # type: ignore[arg-type]
        flag = record.get("dataFlag")
        value = record.get("value")
        if field is None or flag is None or str(flag).strip() in BAD_FLAGS:
            continue
        if not isinstance(value, int | float) or isinstance(value, bool) or not math.isfinite(value):
            continue
        if value <= NO_DATA:
            continue
        observed = parse_cdec_date(record.get("obsDate"))
        if observed is None or observed > now:
            continue
        if field not in latest or observed > latest[field].observed:
            latest[field] = CDECReading(float(value), observed)
    return latest


class CDECClient(BaseAPIClient):
    """Client for CDEC's JSONDataServlet."""

    async def fetch(self, station_id: str, now: datetime | None = None) -> CDECData:
        """Fetch the latest event and hourly readings for a station (two requests)."""
        now = now or datetime.now(UTC)
        today = now.astimezone(CDEC_TZ).date()
        # End is exclusive and both dates are PST days: ask through tomorrow.
        window = {"Start": str(today - timedelta(days=2)), "End": str(today + timedelta(days=1))}
        station = station_id.strip().upper()
        readings: dict[str, CDECReading] = {}
        for dur_code, sensors in (("E", EVENT_SENSORS), ("H", HOURLY_SENSORS)):
            params = {
                "Stations": station,
                "SensorNums": ",".join(str(n) for n in sensors),
                "dur_code": dur_code,
                **window,
            }
            # CDEC serves its JSON as text/plain, which aiohttp's json() refuses.
            text = await self._get_text(CDEC_URL, params=params)
            try:
                records = json.loads(text)
            except ValueError as err:
                raise APIError(f"CDEC returned invalid JSON for {station}") from err
            readings |= _latest(records if isinstance(records, list) else [], sensors, now)
        return CDECData(**readings)
