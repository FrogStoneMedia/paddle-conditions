"""DataUpdateCoordinator for Paddle Conditions."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.noaa import NOAAClient
from .api.open_meteo import THUNDERSTORM_CODES, OpenMeteoAQIClient, OpenMeteoWeatherClient
from .api.usgs import USGSClient
from .cloud_sync import CloudSyncClient
from .const import (
    ACTIVITY_SUP,
    CONF_ACTIVITY,
    CONF_CLOUD_SYNC_TOKEN,
    CONF_CLOUD_SYNC_URL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NOAA_STATION_ID,
    CONF_OPTIMAL_CFS,
    CONF_USGS_STATION_ID,
    CONF_WATER_BODY_TYPE,
    DEFAULT_PROFILES,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    LOGGER,
)
from .models import ForecastBlock, PaddleConditions
from .scoring import compute_paddle_score

type PaddleConfigEntry = ConfigEntry[dict[str, PaddleCoordinator]]


class PaddleCoordinator(DataUpdateCoordinator[PaddleConditions]):  # type: ignore[misc]
    """Fetch and score paddle conditions for a single location."""

    config_entry: PaddleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PaddleConfigEntry,
        subentry_id: str,
        subentry: ConfigSubentry,
    ) -> None:
        interval = config_entry.options.get(
            "update_interval", DEFAULT_UPDATE_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry_id}",
            update_interval=timedelta(minutes=interval),
        )
        self.subentry_id = subentry_id
        self.location_name = subentry.title
        self.latitude = subentry.data[CONF_LATITUDE]
        self.longitude = subentry.data[CONF_LONGITUDE]
        self.water_body_type = subentry.data[CONF_WATER_BODY_TYPE]
        self.usgs_station_id = subentry.data.get(CONF_USGS_STATION_ID, "")
        self.noaa_station_id = subentry.data.get(CONF_NOAA_STATION_ID, "")
        self.optimal_cfs = subentry.data.get(CONF_OPTIMAL_CFS)

        session = async_get_clientsession(hass)
        self.weather_client = OpenMeteoWeatherClient(session)
        self.aqi_client = OpenMeteoAQIClient(session)
        self.usgs_client = USGSClient(session)
        self.noaa_client = NOAAClient(session)

        # Cloud sync (optional)
        sync_url = config_entry.options.get(CONF_CLOUD_SYNC_URL, "")
        sync_token = config_entry.options.get(CONF_CLOUD_SYNC_TOKEN, "")
        self.sync_client = CloudSyncClient(session, sync_url, sync_token)

    async def _async_update_data(self) -> PaddleConditions:
        """Fetch data from all APIs and compute score."""
        # Launch all API calls in parallel for faster updates
        weather_task = self.weather_client.fetch(self.latitude, self.longitude)
        aqi_task = self.aqi_client.fetch(self.latitude, self.longitude)
        usgs_task = (
            self.usgs_client.fetch(self.usgs_station_id)
            if self.usgs_station_id
            else asyncio.sleep(0)
        )
        noaa_task = (
            self.noaa_client.fetch_water_temp(self.noaa_station_id)
            if self.noaa_station_id
            else asyncio.sleep(0)
        )

        results = await asyncio.gather(
            weather_task, aqi_task, usgs_task, noaa_task,
            return_exceptions=True,
        )

        # Weather is required
        if isinstance(results[0], Exception):
            raise UpdateFailed(f"Weather API failed: {results[0]}") from results[0]
        weather = results[0]

        # AQI is optional
        aqi = None
        if isinstance(results[1], Exception):
            LOGGER.warning("AQI fetch failed for %s: %s", self.location_name, results[1])
        else:
            aqi = results[1]

        # USGS is optional
        usgs = None
        if self.usgs_station_id:
            if isinstance(results[2], Exception):
                LOGGER.warning("USGS fetch failed for %s: %s", self.location_name, results[2])
            else:
                usgs = results[2]

        # NOAA is optional
        noaa_water_temp = None
        if self.noaa_station_id:
            if isinstance(results[3], Exception):
                LOGGER.warning("NOAA water temp fetch failed for %s: %s", self.location_name, results[3])
            else:
                noaa_water_temp = results[3]

        # Determine water temp (prefer USGS, fallback to NOAA)
        water_temp = None
        if usgs and usgs.water_temp_f is not None:
            water_temp = usgs.water_temp_f
        elif noaa_water_temp is not None:
            water_temp = noaa_water_temp

        # Load activity, profile, and scoring parameters
        from .profiles import get_profile

        activity = self.config_entry.options.get(CONF_ACTIVITY, ACTIVITY_SUP)
        default_profile = DEFAULT_PROFILES.get(activity, "recreational")
        profile_name = self.config_entry.options.get("profile", default_profile)
        profile = get_profile(activity, profile_name)

        # Use custom weights if set, otherwise profile defaults
        weights = self.config_entry.options.get("weights", profile.weights)

        # Get streamflow CFS if available (for river locations)
        streamflow_cfs = usgs.streamflow_cfs if usgs else None

        # Tide current not yet implemented
        tide_current = None

        # Compute score with profile curves, vetoes, and water-body-type factors
        score = compute_paddle_score(
            wind_speed=weather.wind_speed,
            wind_gusts=weather.wind_gusts,
            aqi=aqi.aqi if aqi else None,
            air_temp=weather.air_temp,
            uv_index=weather.uv_index,
            visibility=weather.visibility,
            precipitation=weather.precipitation_probability,
            streamflow_cfs=streamflow_cfs,
            tide_current=tide_current,
            has_thunderstorm=weather.has_thunderstorm,
            weights=weights,
            water_body_type=self.water_body_type,
            optimal_cfs=self.optimal_cfs or 500,
            curves=profile.curves,
            temp_curve=profile.temp_curve,
            veto_thresholds=profile.vetoes,
        )

        # Build forecast blocks from hourly data
        forecast_blocks = self._build_forecast_blocks(weather, weights, profile)

        # Push to cloud (non-blocking, fire-and-forget)
        if self.sync_client.enabled:
            import datetime

            self.hass.async_create_task(
                self.sync_client.push(
                    {
                        "location": self.location_name,
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "water_body_type": self.water_body_type,
                        "activity": activity,
                        "profile": profile_name,
                        "score": score.value,
                        "rating": score.rating,
                        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    }
                )
            )

        return PaddleConditions(
            score=score,
            activity=activity,
            profile=profile_name,
            wind_speed=weather.wind_speed,
            wind_gusts=weather.wind_gusts,
            wind_direction=weather.wind_direction,
            air_temp=weather.air_temp,
            water_temp=water_temp,
            uv_index=weather.uv_index,
            aqi=aqi.aqi if aqi else None,
            visibility=weather.visibility,
            precipitation_probability=weather.precipitation_probability,
            streamflow_cfs=streamflow_cfs,
            tide_factor=tide_current,
            condition_text=weather.condition_text,
            forecast_blocks=forecast_blocks,
        )

    def _build_forecast_blocks(self, weather: Any, weights: dict[str, float], profile: Any) -> list[ForecastBlock]:
        """Aggregate hourly data into 3-hour forecast blocks."""
        blocks: list[ForecastBlock] = []
        times = weather.hourly_times
        winds = weather.hourly_wind
        temps = weather.hourly_temp
        uvs = weather.hourly_uv
        codes = weather.hourly_weather_codes

        if not times:
            return blocks

        for i in range(0, min(len(times), 48), 3):
            chunk_end = min(i + 3, len(times))
            if chunk_end <= i:
                break

            block_winds = winds[i:chunk_end]
            block_temps = temps[i:chunk_end]
            block_uvs = uvs[i:chunk_end]
            block_codes = codes[i:chunk_end] if codes else []

            max_wind = max(block_winds) if block_winds else 0
            avg_temp = sum(block_temps) / len(block_temps) if block_temps else 0
            max_uv = max(block_uvs) if block_uvs else 0
            has_thunderstorm = any(c in THUNDERSTORM_CODES for c in block_codes)

            block_score = compute_paddle_score(
                wind_speed=max_wind,
                wind_gusts=None,
                aqi=None,
                air_temp=avg_temp,
                uv_index=max_uv,
                visibility=None,
                precipitation=None,
                has_thunderstorm=has_thunderstorm,
                weights=weights,
                curves=profile.curves,
                temp_curve=profile.temp_curve,
                veto_thresholds=profile.vetoes,
            )

            start_time = times[i]
            end_idx = i + 3
            end_time = times[end_idx] if end_idx < len(times) else times[-1]

            blocks.append(
                ForecastBlock(
                    start=start_time,
                    end=end_time,
                    score=block_score.value,
                    rating=block_score.rating,
                    wind_mph=max_wind,
                    temp_f=round(avg_temp, 1),
                    uv=round(max_uv, 1),
                )
            )

        return blocks[:8]
