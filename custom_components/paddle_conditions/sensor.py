"""Sensor platform for Paddle Conditions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    EntityCategory,
    UnitOfConductivity,
    UnitOfLength,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.open_meteo import WEATHER_CODE_CONDITIONS
from .const import DOMAIN, WATER_BODY_BAY_OCEAN, WATER_BODY_LAKE, WATER_BODY_RIVER
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .models import PaddleConditions

PARALLEL_UPDATES = 0

RATINGS = ["go", "caution", "no_go"]

WATER_BODY_MODELS = {
    WATER_BODY_LAKE: "Lake or reservoir",
    WATER_BODY_RIVER: "River",
    WATER_BODY_BAY_OCEAN: "Bay or ocean",
}


@dataclass(frozen=True, kw_only=True)
class PaddleSensorEntityDescription(SensorEntityDescription):
    """Paddle Conditions sensor entity description."""

    value_fn: Callable[[PaddleConditions], StateType]
    extra_attrs_fn: Callable[[PaddleConditions], dict[str, Any]] | None = None
    # Overrides entity_registry_enabled_default per location when set.
    enabled_fn: Callable[[PaddleCoordinator], bool] | None = None


SENSOR_DESCRIPTIONS: tuple[PaddleSensorEntityDescription, ...] = (
    PaddleSensorEntityDescription(
        key="score",
        translation_key="paddle_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: data.score.value,
        extra_attrs_fn=lambda data: {
            "rating": data.score.rating,
            "activity": data.activity,
            "profile": data.profile,
            "limiting_factor": data.score.limiting_factor,
            "factors": data.score.factors,
            "missing_factors": data.score.missing_factors,
            "vetoed": data.score.vetoed,
            "veto_reason": data.score.veto_reason,
        },
    ),
    PaddleSensorEntityDescription(
        key="rating",
        translation_key="rating",
        device_class=SensorDeviceClass.ENUM,
        options=RATINGS,
        value_fn=lambda data: data.score.rating.lower(),
    ),
    PaddleSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wind_speed,
    ),
    PaddleSensorEntityDescription(
        key="wind_gusts",
        translation_key="wind_gusts",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wind_gusts,
    ),
    PaddleSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        value_fn=lambda data: data.wind_direction,
    ),
    PaddleSensorEntityDescription(
        key="air_temp",
        translation_key="air_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.air_temp,
    ),
    PaddleSensorEntityDescription(
        key="water_temp",
        translation_key="water_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.water_temp,
    ),
    PaddleSensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.uv_index,
    ),
    PaddleSensorEntityDescription(
        key="aqi",
        translation_key="aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.aqi,
    ),
    PaddleSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.visibility,
    ),
    PaddleSensorEntityDescription(
        key="precipitation",
        translation_key="precipitation",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.precipitation_probability,
    ),
    PaddleSensorEntityDescription(
        key="streamflow",
        translation_key="streamflow",
        # HA has no ft³/s unit and CFS is what paddlers read, so no device class.
        native_unit_of_measurement="CFS",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.streamflow_cfs,
        enabled_fn=lambda coordinator: bool(coordinator.usgs_station_id),
    ),
    # California CDEC gauges: on for locations that have them.
    PaddleSensorEntityDescription(
        key="river_stage",
        translation_key="river_stage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.FEET,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.river_stage_ft,
        enabled_fn=lambda coordinator: bool(coordinator.cdec_station_ids),
    ),
    PaddleSensorEntityDescription(
        key="reservoir_level",
        translation_key="reservoir_level",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.reservoir_percent_full,
        extra_attrs_fn=lambda data: {"storage_acre_feet": data.reservoir_storage_af},
        enabled_fn=lambda coordinator: bool(coordinator.cdec_station_ids and coordinator.reservoir_capacity_af),
    ),
    PaddleSensorEntityDescription(
        key="dam_outflow",
        translation_key="dam_outflow",
        native_unit_of_measurement="CFS",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.dam_outflow_cfs,
        enabled_fn=lambda coordinator: bool(coordinator.cdec_station_ids and coordinator.dam_outflow_threshold_cfs),
    ),
    # Few stations report water quality; off until the user wants them.
    PaddleSensorEntityDescription(
        key="turbidity",
        translation_key="turbidity",
        native_unit_of_measurement="NTU",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.turbidity_ntu,
    ),
    PaddleSensorEntityDescription(
        key="dissolved_oxygen",
        translation_key="dissolved_oxygen",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.dissolved_oxygen_mg_l,
    ),
    PaddleSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ph,
    ),
    PaddleSensorEntityDescription(
        key="conductivity",
        device_class=SensorDeviceClass.CONDUCTIVITY,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.conductivity_us,
    ),
    PaddleSensorEntityDescription(
        key="condition",
        translation_key="condition",
        device_class=SensorDeviceClass.ENUM,
        options=list(WEATHER_CODE_CONDITIONS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.condition,
    ),
    PaddleSensorEntityDescription(
        key="forecast_3hr",
        translation_key="forecast_3hr",
        value_fn=lambda data: data.forecast_blocks[0].score if data.forecast_blocks else None,
        extra_attrs_fn=lambda data: {
            "blocks": [
                {
                    "start": b.start,
                    "end": b.end,
                    "score": b.score,
                    "rating": b.rating,
                    "wind_mph": b.wind_mph,
                    "gust_mph": b.gust_mph,
                    "temp_f": b.temp_f,
                    "uv": b.uv,
                    "precip_pct": b.precip_pct,
                    "aqi": b.aqi,
                    "visibility_mi": b.visibility_mi,
                }
                for b in data.forecast_blocks
            ],
            "best_block": max(data.forecast_blocks, key=lambda b: b.score).start if data.forecast_blocks else None,
            "best_score": max(b.score for b in data.forecast_blocks) if data.forecast_blocks else None,
            "hourly_times": data.hourly_times,
            "hourly_wind": data.hourly_wind,
            "hourly_gusts": data.hourly_gusts,
            "hourly_temp": data.hourly_temp,
            "hourly_uv": data.hourly_uv,
            "hourly_precip": data.hourly_precip,
            "daylight": data.daylight,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PaddleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paddle Conditions sensor entities."""
    for subentry_id, coordinator in config_entry.runtime_data.items():
        async_add_entities(
            [PaddleSensor(coordinator, subentry_id, description) for description in SENSOR_DESCRIPTIONS],
            config_subentry_id=subentry_id,
        )


class PaddleSensor(CoordinatorEntity[PaddleCoordinator], SensorEntity):
    """A Paddle Conditions sensor entity."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by Open-Meteo, USGS, NOAA, CDEC and Paddle Conditions"
    # Forecast series are large and change every update; keep them out of the recorder.
    _unrecorded_attributes = frozenset(
        {
            "blocks",
            "best_block",
            "best_score",
            "hourly_times",
            "hourly_wind",
            "hourly_gusts",
            "hourly_temp",
            "hourly_uv",
            "hourly_precip",
            "daylight",
        }
    )
    entity_description: PaddleSensorEntityDescription

    def __init__(
        self,
        coordinator: PaddleCoordinator,
        subentry_id: str,
        description: PaddleSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{subentry_id}_{description.key}"
        if description.enabled_fn is not None:
            self._attr_entity_registry_enabled_default = description.enabled_fn(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=coordinator.location_name,
            manufacturer="Paddle Conditions",
            model=WATER_BODY_MODELS.get(coordinator.water_body_type, coordinator.water_body_type),
            model_id=coordinator.water_body_type,
            entry_type=DeviceEntryType.SERVICE,
        )

    # Entities are only added after a successful first refresh, so data is set.

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.extra_attrs_fn is None:
            return None
        return self.entity_description.extra_attrs_fn(self.coordinator.data)
