"""Tests for Paddle Conditions diagnostics."""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from .conftest import AQI_URL, LAKE_SUBENTRY_ID, USGS_URL, WEATHER_URL, make_weather_payload, setup_integration

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_frontend")


async def test_diagnostics_hide_location_and_show_health(
    hass: HomeAssistant, hass_client, config_entry, aioclient_mock
):
    aioclient_mock.get(WEATHER_URL, json=make_weather_payload())
    aioclient_mock.get(AQI_URL, exc=TimeoutError())
    aioclient_mock.get(USGS_URL, json={"features": []})
    await setup_integration(hass, config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    dumped = json.dumps(diag)

    assert "38.637" not in dumped
    assert "-121.227" not in dumped
    assert "Lake Natoma" not in dumped

    location = diag["locations"][LAKE_SUBENTRY_ID]
    assert location["config"]["latitude"] == "**REDACTED**"
    assert location["config"]["water_body_type"] == "lake"
    assert location["last_update_success"] is True
    assert location["failing_sources"] == ["Air quality"]
    assert location["conditions"]["forecast_blocks"] == 8
    assert "air_quality" in location["conditions"]["missing_factors"]
    assert diag["entry"]["version"] == "1.2"
