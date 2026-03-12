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
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .models import PaddleConditions

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PaddleSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """Paddle Conditions sensor entity description."""

    value_fn: Callable[[PaddleConditions], StateType]
    extra_attrs_fn: Callable[[PaddleConditions], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[PaddleSensorEntityDescription, ...] = (
    PaddleSensorEntityDescription(
        key="score",
        translation_key="paddle_score",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
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
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
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
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.precipitation_probability,
    ),
    PaddleSensorEntityDescription(
        key="streamflow",
        translation_key="streamflow",
        native_unit_of_measurement="CFS",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.streamflow_cfs,
    ),
    PaddleSensorEntityDescription(
        key="condition",
        translation_key="condition",
        value_fn=lambda data: data.condition_text,
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
                    "temp_f": b.temp_f,
                    "uv": b.uv,
                    "precip_pct": b.precip_pct,
                }
                for b in data.forecast_blocks
            ],
            "best_block": max(data.forecast_blocks, key=lambda b: b.score).start if data.forecast_blocks else None,
            "best_score": max(b.score for b in data.forecast_blocks) if data.forecast_blocks else None,
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


class PaddleSensor(CoordinatorEntity[PaddleCoordinator], SensorEntity):  # type: ignore[misc]
    """A Paddle Conditions sensor entity."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by Open-Meteo, USGS, and NOAA"
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=coordinator.location_name,
            manufacturer="Paddle Conditions",
            model=coordinator.water_body_type,
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.extra_attrs_fn is not None:
            return self.entity_description.extra_attrs_fn(self.coordinator.data)
        return None
