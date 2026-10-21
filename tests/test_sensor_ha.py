"""Sensor entities on a real config entry."""

from __future__ import annotations

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.paddle_conditions.const import DOMAIN

from .conftest import AQI_URL, LAKE_SUBENTRY_ID, USGS_URL, WEATHER_URL, make_weather_payload, setup_integration

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")


def _serve(aioclient_mock, **current) -> None:
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload(**current))
    aioclient_mock.get(AQI_URL, json={"current": {"us_aqi": 30}})
    aioclient_mock.get(USGS_URL, json={"features": []})


async def test_rating_is_a_translated_enum(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.lake_natoma_rating")
    assert state.state == "go"
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == ["go", "caution", "no_go"]


@pytest.mark.parametrize(("code", "expected"), [(1, "mainly_clear"), (66, "light_freezing_rain"), (12345, "unknown")])
async def test_conditions_is_a_translated_enum(hass: HomeAssistant, config_entry, aioclient_mock, code, expected):
    _serve(aioclient_mock, weather_code=code)
    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.lake_natoma_conditions")
    assert state.state == expected
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM


async def test_wind_direction_uses_angle_statistics(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    state = hass.states.get("sensor.lake_natoma_wind_direction")
    assert state.state == "225"
    assert state.attributes["device_class"] == SensorDeviceClass.WIND_DIRECTION
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT_ANGLE


async def test_forecast_enabled_and_streamflow_follows_usgs_station(hass: HomeAssistant, config_entry, aioclient_mock):
    """The main card needs the forecast; streamflow is on when there is a gauge to read."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)
    registry = er.async_get(hass)

    forecast = registry.async_get("sensor.lake_natoma_3_hour_forecast")
    streamflow = registry.async_get("sensor.lake_natoma_streamflow")
    assert forecast.disabled_by is None
    assert forecast.entity_category is None
    assert streamflow.disabled_by is None  # Lake Natoma has USGS station 11446500


async def test_streamflow_disabled_without_usgs_station(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    config_entry.add_to_hass(hass)
    sub = config_entry.subentries[LAKE_SUBENTRY_ID]
    hass.config_entries.async_update_subentry(config_entry, sub, data={**sub.data, "usgs_station_id": ""})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{LAKE_SUBENTRY_ID}_streamflow")
    assert er.async_get(hass).async_get(entity).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_forecast_attributes_are_not_recorded(hass: HomeAssistant, config_entry, aioclient_mock):
    from custom_components.paddle_conditions.sensor import PaddleSensor

    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    entity = next(
        e
        for e in hass.data["entity_components"]["sensor"].entities
        if e.unique_id == f"{LAKE_SUBENTRY_ID}_forecast_3hr"
    )
    assert isinstance(entity, PaddleSensor)
    assert {"blocks", "hourly_times", "hourly_wind", "hourly_gusts", "daylight"} <= entity._unrecorded_attributes


async def test_device_is_a_service_with_readable_model(hass: HomeAssistant, config_entry, aioclient_mock):
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, LAKE_SUBENTRY_ID), config_entry.entry_id)
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.model == "Lake or reservoir"
    assert device.name == "Lake Natoma"


async def test_forecast_exposes_the_locations_own_daylight(hass: HomeAssistant, config_entry, aioclient_mock):
    """Cards judge "best time" by the paddle spot's sunrise and sunset, not the HA home's."""
    _serve(aioclient_mock)
    await setup_integration(hass, config_entry)

    daylight = hass.states.get("sensor.lake_natoma_3_hour_forecast").attributes["daylight"]
    assert len(daylight) == 3
    assert daylight[0]["sunrise"].endswith("+00:00") and daylight[0]["sunset"].endswith("+00:00")
    assert daylight[0]["sunrise"] < daylight[0]["sunset"]
