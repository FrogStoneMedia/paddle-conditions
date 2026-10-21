"""DataUpdateCoordinator for Paddle Conditions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Sequence
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .api.base import RateLimitedError
from .api.cdec import CDEC_TZ, CDECClient, CDECData, CDECReading
from .api.noaa import NOAAClient
from .api.open_meteo import THUNDERSTORM_CODES, AQIData, OpenMeteoAQIClient, OpenMeteoWeatherClient, WeatherData
from .api.paddle_conditions import PaddleConditionsClient
from .api.usgs import USGSClient, USGSData
from .cache import PaddleCache, location_fingerprint
from .const import (
    ACTIVITY_SUP,
    CONF_ACTIVITY,
    CONF_CDEC_STATION_IDS,
    CONF_DAM_OUTFLOW_THRESHOLD_CFS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NOAA_STATION_ID,
    CONF_OPTIMAL_CFS,
    CONF_PROFILE,
    CONF_RESERVOIR_CAPACITY_AF,
    CONF_SPOT_SLUG,
    CONF_USGS_API_KEY,
    CONF_USGS_STATION_ID,
    CONF_WATER_BODY_TYPE,
    DEFAULT_PROFILES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    LOGGER,
)
from .models import ForecastBlock, PaddleConditions
from .profiles import ProfileConfig, get_profile
from .scoring import StageBaseline, compute_paddle_score

type PaddleConfigEntry = ConfigEntry[dict[str, PaddleCoordinator]]

# Conditions older than this are not shown as current, however the update
# interval is configured. A weather outage shorter than this keeps the last
# good reading on screen instead of flapping to unavailable.
MIN_STALE_AFTER = timedelta(hours=1)

BLOCK_HOURS = 3
MAX_BLOCKS = 8

# USGS publishes every 15 minutes and the keyless quota is small, so USGS is
# polled on its own schedule and its last reading reused in between.
USGS_INTERVAL = timedelta(hours=1)
USGS_INTERVAL_WITH_KEY = timedelta(minutes=15)
# Gauges often transmit every 1 to 4 hours; older observations aren't current.
USGS_MAX_AGE = timedelta(hours=6)
ISSUE_USGS_RATE_LIMITED = "usgs_rate_limited"
# Locations currently rate limited by USGS. The repair issue is shared, so it
# is only cleared once none are left.
USGS_RATE_LIMITED: HassKey[set[str]] = HassKey(f"{DOMAIN}_usgs_rate_limited")

# CDEC river and water quality gauges report every 15 minutes, reservoirs hourly.
CDEC_INTERVAL = timedelta(minutes=30)
CDEC_MAX_AGE = timedelta(hours=6)
# Stage baselines are curated by hand; a daily read is plenty.
BASELINE_INTERVAL = timedelta(days=1)
BASELINE_RETRY = timedelta(hours=1)


class PaddleCoordinator(DataUpdateCoordinator[PaddleConditions]):
    """Fetch and score paddle conditions for a single location."""

    config_entry: PaddleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PaddleConfigEntry,
        subentry: ConfigSubentry,
        cache: PaddleCache,
    ) -> None:
        interval = timedelta(minutes=config_entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL_MINUTES))
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry.subentry_id}",
            update_interval=interval,
        )
        self.subentry_id = subentry.subentry_id
        self.location_name = subentry.title
        self.latitude: float = subentry.data[CONF_LATITUDE]
        self.longitude: float = subentry.data[CONF_LONGITUDE]
        self.water_body_type: str = subentry.data[CONF_WATER_BODY_TYPE]
        self.usgs_station_id: str = subentry.data.get(CONF_USGS_STATION_ID, "")
        self.noaa_station_id: str = subentry.data.get(CONF_NOAA_STATION_ID, "")
        self.optimal_cfs: float | None = subentry.data.get(CONF_OPTIMAL_CFS)
        self.cdec_station_ids = [
            part.strip() for part in str(subentry.data.get(CONF_CDEC_STATION_IDS) or "").split(",") if part.strip()
        ]
        self.reservoir_capacity_af: float | None = subentry.data.get(CONF_RESERVOIR_CAPACITY_AF)
        self.dam_outflow_threshold_cfs: float | None = subentry.data.get(CONF_DAM_OUTFLOW_THRESHOLD_CFS)
        self.spot_slug: str | None = subentry.data.get(CONF_SPOT_SLUG)
        self.stale_after = max(MIN_STALE_AFTER, 2 * interval)

        self._cache = cache
        self._fingerprint = location_fingerprint(subentry.data, config_entry.options)
        # Sources currently failing, so each outage is logged once, not every poll.
        self._failing: set[str] = set()

        session = async_get_clientsession(hass)
        self.weather_client = OpenMeteoWeatherClient(session)
        self.aqi_client = OpenMeteoAQIClient(session)
        self.usgs_client = USGSClient(session, api_key=config_entry.options.get(CONF_USGS_API_KEY))
        self._usgs_reading: USGSData | None = None
        self._usgs_next_fetch = dt_util.utcnow()
        config_entry.async_on_unload(self._clear_usgs_rate_limit)
        self.noaa_client = NOAAClient(session)
        self.cdec_client = CDECClient(session)
        # Per station, nearest first, as last read.
        self._cdec_readings: list[tuple[str, CDECData]] = []
        self._cdec_next_fetch = dt_util.utcnow()
        self.pc_client = PaddleConditionsClient(session)
        self._stage_baselines: dict[str, dict[int, StageBaseline]] = {}
        self._baselines_next_fetch = dt_util.utcnow()

    async def _async_setup(self) -> None:
        """Start from the last good conditions, if they are recent and for this exact location."""
        cached = self._cache.get(self.subentry_id, self._fingerprint)
        if cached is not None and self._is_fresh(cached):
            self.data = cached
            LOGGER.debug("Loaded cached conditions for %s", self.location_name)

    def _is_fresh(self, conditions: PaddleConditions) -> bool:
        fetched = dt_util.parse_datetime(conditions.fetched_at)
        return fetched is not None and dt_util.utcnow() - fetched <= self.stale_after

    @property
    def failing_sources(self) -> frozenset[str]:
        """Sources whose last fetch failed."""
        return frozenset(self._failing)

    def _source_failed(self, source: str, err: BaseException) -> None:
        if source not in self._failing:
            self._failing.add(source)
            LOGGER.warning("%s data for %s is unavailable: %s", source, self.location_name, err)

    def _source_ok(self, source: str) -> None:
        if source in self._failing:
            self._failing.discard(source)
            LOGGER.info("%s data for %s is available again", source, self.location_name)

    async def _async_update_data(self) -> PaddleConditions:
        """Fetch every source in parallel and compute the score."""
        sources: dict[str, Awaitable[Any]] = {
            "Weather": self.weather_client.fetch(self.latitude, self.longitude),
            "Air quality": self.aqi_client.fetch(self.latitude, self.longitude),
        }
        now = dt_util.utcnow()
        if self.usgs_station_id and now >= self._usgs_next_fetch:
            sources["USGS"] = self.usgs_client.fetch(self.usgs_station_id)
        if self.noaa_station_id:
            sources["NOAA"] = self.noaa_client.fetch_water_temp(self.noaa_station_id)
        if self.cdec_station_ids and now >= self._cdec_next_fetch:
            sources["CDEC"] = self._fetch_cdec(now)
        if self.spot_slug and self.cdec_station_ids and now >= self._baselines_next_fetch:
            sources["Stage baselines"] = self.pc_client.spot_stations(self.spot_slug)

        outcomes = dict(zip(sources, await asyncio.gather(*sources.values(), return_exceptions=True), strict=True))

        # Record USGS before any early return, so its backoff and readings
        # survive a weather outage.
        if self.usgs_station_id:
            self._handle_usgs(now, outcomes.get("USGS"))
        self._handle_cdec(now, outcomes)

        # Weather drives the score. Without it, keep recent conditions briefly,
        # then let the entities go unavailable rather than show old data as current.
        weather = outcomes["Weather"]
        if isinstance(weather, BaseException):
            if self.data is not None and self._is_fresh(self.data):
                self._source_failed("Weather", weather)
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="weather_unavailable",
                translation_placeholders={"location": self.location_name, "error": str(weather)},
            ) from weather
        self._source_ok("Weather")

        optional: dict[str, Any] = {}
        for source in ("Air quality", "NOAA"):
            if source not in outcomes:
                continue
            outcome = outcomes[source]
            if isinstance(outcome, BaseException):
                self._source_failed(source, outcome)
            else:
                self._source_ok(source)
                optional[source] = outcome

        aqi_data = optional.get("Air quality")
        noaa_water_temp: float | None = optional.get("NOAA")
        usgs_temp, streamflow_cfs = self._current_usgs(now)

        cdec, cdec_stations = self._current_cdec(now)
        # California gauges take precedence, as in the Paddle Conditions API; then USGS, then NOAA.
        water_temp = next((t for t in (cdec.get("water_temp_f"), usgs_temp, noaa_water_temp) if t is not None), None)
        if cdec.get("flow_cfs") is not None:
            streamflow_cfs = cdec["flow_cfs"]
        aqi = aqi_data.aqi if aqi_data else None
        storage = cdec.get("storage_af")
        percent_full = (
            round(storage / self.reservoir_capacity_af * 100, 1)
            if storage is not None and self.reservoir_capacity_af
            else None
        )
        water_quality: dict[str, float | None] = {
            key: cdec[key] for key in ("turbidity_ntu", "dissolved_oxygen_mg_l", "ph", "conductivity_us") if key in cdec
        }

        options = self.config_entry.options
        activity = options.get(CONF_ACTIVITY, ACTIVITY_SUP)
        profile_name = options.get(CONF_PROFILE, DEFAULT_PROFILES.get(activity, "recreational"))
        profile = get_profile(activity, profile_name)
        # Weights saved before a factor existed lack it; fall back to the profile's.
        weights: dict[str, float] = {**profile.weights, **options.get("weights", {})}

        score = compute_paddle_score(
            wind_speed=weather.wind_speed,
            wind_gusts=weather.wind_gusts,
            aqi=aqi,
            air_temp=weather.air_temp,
            uv_index=weather.uv_index,
            visibility=weather.visibility,
            precipitation=weather.precipitation_probability,
            streamflow_cfs=streamflow_cfs,
            tide_current=None,  # No tidal current source yet.
            has_thunderstorm=weather.has_thunderstorm,
            weights=weights,
            water_body_type=self.water_body_type,
            optimal_cfs=self.optimal_cfs or 500,
            curves=profile.curves,
            temp_curve=profile.temp_curve,
            veto_thresholds=profile.vetoes,
            reservoir_storage_af=storage,
            reservoir_capacity_af=self.reservoir_capacity_af,
            river_stage_ft=cdec.get("river_stage_ft"),
            stage_baseline=self._stage_baseline(cdec_stations.get("river_stage_ft"), now),
            stage_inverted=profile.river_stage_inverted,
            water_quality=water_quality or None,
            dam_outflow_cfs=cdec.get("outflow_cfs"),
            dam_outflow_threshold_cfs=self.dam_outflow_threshold_cfs,
        )

        conditions = PaddleConditions(
            score=score,
            activity=activity,
            profile=profile_name,
            wind_speed=weather.wind_speed,
            wind_gusts=weather.wind_gusts,
            wind_direction=weather.wind_direction,
            air_temp=weather.air_temp,
            water_temp=water_temp,
            uv_index=weather.uv_index,
            aqi=aqi,
            visibility=weather.visibility,
            precipitation_probability=weather.precipitation_probability,
            streamflow_cfs=streamflow_cfs,
            tide_factor=None,
            condition=weather.condition,
            forecast_blocks=self._build_forecast_blocks(weather, aqi_data, weights, profile),
            hourly_times=weather.hourly_times,
            hourly_wind=weather.hourly_wind,
            hourly_gusts=weather.hourly_gusts,
            hourly_temp=weather.hourly_temp,
            hourly_uv=weather.hourly_uv,
            hourly_precip=weather.hourly_precip,
            fetched_at=dt_util.utcnow().isoformat(),
            daylight=[{"sunrise": rise, "sunset": down} for rise, down in weather.daylight],
            river_stage_ft=cdec.get("river_stage_ft"),
            reservoir_storage_af=storage,
            reservoir_percent_full=percent_full,
            dam_outflow_cfs=cdec.get("outflow_cfs"),
            turbidity_ntu=cdec.get("turbidity_ntu"),
            dissolved_oxygen_mg_l=cdec.get("dissolved_oxygen_mg_l"),
            ph=cdec.get("ph"),
            conductivity_us=cdec.get("conductivity_us"),
        )
        self._cache.set(self.subentry_id, self._fingerprint, conditions)
        return conditions

    def _handle_usgs(self, now: datetime, outcome: USGSData | BaseException | None) -> None:
        """Record a USGS result and decide when to ask again."""
        if outcome is None:  # Not due this poll.
            return
        interval = USGS_INTERVAL_WITH_KEY if self.usgs_client.has_api_key else USGS_INTERVAL
        if isinstance(outcome, BaseException):
            self._source_failed("USGS", outcome)
        else:
            self._source_ok("USGS")
        if isinstance(outcome, RateLimitedError):
            self._usgs_next_fetch = now + max(interval, timedelta(seconds=outcome.retry_after or 0))
            if not self.usgs_client.has_api_key:
                self.hass.data.setdefault(USGS_RATE_LIMITED, set()).add(self.subentry_id)
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    ISSUE_USGS_RATE_LIMITED,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_USGS_RATE_LIMITED,
                    learn_more_url="https://api.waterdata.usgs.gov/signup/",
                )
        elif isinstance(outcome, BaseException):
            self._usgs_next_fetch = now  # Transient failure: try again next poll.
        else:
            self._usgs_reading = outcome
            self._usgs_next_fetch = now + interval
            self._clear_usgs_rate_limit()

    def _clear_usgs_rate_limit(self) -> None:
        """Drop this location from the rate-limited set; clear the repair when none remain."""
        limited = self.hass.data.get(USGS_RATE_LIMITED)
        if limited is None or self.subentry_id not in limited:
            return
        limited.discard(self.subentry_id)
        if not limited:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_USGS_RATE_LIMITED)

    def _current_usgs(self, now: datetime) -> tuple[float | None, float | None]:
        """Water temperature and streamflow from the last reading, if observed recently."""
        reading = self._usgs_reading
        if reading is None:
            return None, None

        def recent(observed: datetime | None) -> bool:
            return observed is not None and now - observed <= USGS_MAX_AGE

        return (
            reading.water_temp_f if recent(reading.water_temp_observed) else None,
            reading.streamflow_cfs if recent(reading.streamflow_observed) else None,
        )

    async def _fetch_cdec(self, now: datetime) -> list[tuple[str, CDECData | BaseException]]:
        """Read every CDEC station; one failing station doesn't sink the rest."""
        results = await asyncio.gather(
            *(self.cdec_client.fetch(station, now) for station in self.cdec_station_ids), return_exceptions=True
        )
        return list(zip(self.cdec_station_ids, results, strict=True))

    def _handle_cdec(self, now: datetime, outcomes: dict[str, Any]) -> None:
        """Record CDEC readings and stage baselines and decide when to ask again."""
        if (cdec := outcomes.get("CDEC")) is not None:
            if isinstance(cdec, BaseException):  # Not expected: per-station errors are returned.
                cdec = [(station, cdec) for station in self.cdec_station_ids]
            readings = [(station, data) for station, data in cdec if isinstance(data, CDECData)]
            errors = [err for _, err in cdec if isinstance(err, BaseException)]
            if readings:
                self._source_ok("CDEC")
                self._cdec_readings = readings
                self._cdec_next_fetch = now + CDEC_INTERVAL
            else:
                self._source_failed("CDEC", errors[0])
                self._cdec_next_fetch = now  # Try again next poll.
        if (spot := outcomes.get("Stage baselines")) is not None:
            if isinstance(spot, BaseException):
                self._source_failed("Stage baselines", spot)
                self._baselines_next_fetch = now + BASELINE_RETRY
            else:
                self._source_ok("Stage baselines")
                self._stage_baselines = spot.stage_baselines
                self._baselines_next_fetch = now + BASELINE_INTERVAL

    def _current_cdec(self, now: datetime) -> tuple[dict[str, float], dict[str, str]]:
        """Each CDEC value from the nearest station that observed it recently, and that station."""
        values: dict[str, float] = {}
        stations: dict[str, str] = {}
        for station, data in self._cdec_readings:
            for key, reading in vars(data).items():
                if isinstance(reading, CDECReading) and key not in values and now - reading.observed <= CDEC_MAX_AGE:
                    values[key] = reading.value
                    stations[key] = station
        return values, stations

    def _stage_baseline(self, station: str | None, now: datetime) -> StageBaseline | None:
        """This month's stage percentiles for the gauge that reported the stage (CDEC months are PST)."""
        if station is None:
            return None
        return self._stage_baselines.get(station, {}).get(now.astimezone(CDEC_TZ).month)

    def _build_forecast_blocks(
        self, weather: WeatherData, aqi_data: AQIData | None, weights: dict[str, float], profile: ProfileConfig
    ) -> list[ForecastBlock]:
        """Score consecutive 3-hour windows, starting at the current hour."""
        blocks: list[ForecastBlock] = []
        times = weather.hourly_times

        for start in range(0, len(times) - BLOCK_HOURS + 1, BLOCK_HOURS):
            window = slice(start, start + BLOCK_HOURS)
            max_wind = _max(weather.hourly_wind[window])
            max_gust = _max(weather.hourly_gusts[window])
            avg_temp = _mean(weather.hourly_temp[window])
            max_uv = _max(weather.hourly_uv[window])
            max_precip = _max(weather.hourly_precip[window])
            min_visibility = _min(weather.hourly_visibility[window])
            hourly_aqi = aqi_data.hourly_aqi if aqi_data else {}
            max_aqi = _max([hourly_aqi.get(t) for t in times[window]])
            has_thunderstorm = any(code in THUNDERSTORM_CODES for code in weather.hourly_weather_codes[window])

            block_score = compute_paddle_score(
                wind_speed=max_wind,
                wind_gusts=max_gust,
                aqi=None if max_aqi is None else round(max_aqi),
                air_temp=avg_temp,
                uv_index=max_uv,
                visibility=min_visibility,
                precipitation=None if max_precip is None else round(max_precip),
                has_thunderstorm=has_thunderstorm,
                weights=weights,
                curves=profile.curves,
                temp_curve=profile.temp_curve,
                veto_thresholds=profile.vetoes,
            )

            block_start = dt_util.parse_datetime(times[start])
            block_end = block_start + timedelta(hours=BLOCK_HOURS) if block_start else None
            blocks.append(
                ForecastBlock(
                    start=times[start],
                    end=block_end.isoformat() if block_end else times[start],
                    score=block_score.value,
                    rating=block_score.rating,
                    wind_mph=max_wind,
                    gust_mph=max_gust,
                    temp_f=None if avg_temp is None else round(avg_temp, 1),
                    uv=None if max_uv is None else round(max_uv, 1),
                    precip_pct=None if max_precip is None else round(max_precip),
                    aqi=None if max_aqi is None else round(max_aqi),
                    visibility_mi=None if min_visibility is None else round(min_visibility, 1),
                )
            )
            if len(blocks) == MAX_BLOCKS:
                break

        return blocks


def _max(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _min(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None
