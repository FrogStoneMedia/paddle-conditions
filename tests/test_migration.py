"""Tests for config entry migrations."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paddle_conditions.const import DOMAIN

from .conftest import LAKE_LOCATION, LAKE_SUBENTRY_ID, setup_integration

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "mock_apis", "mock_frontend")


async def test_migrate_1_1_strips_cloud_sync_options(hass: HomeAssistant):
    """1.1 entries stored a cloud sync URL and bearer token; 1.2 drops both."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
        options={
            "update_interval": 15,
            "cloud_sync_url": "https://example.invalid",
            "cloud_sync_token": "secret-token",
        },
        subentries_data=[
            {
                "data": LAKE_LOCATION,
                "subentry_id": LAKE_SUBENTRY_ID,
                "subentry_type": "location",
                "title": "Lake Natoma",
                "unique_id": None,
            }
        ],
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.options == {"update_interval": 15}


async def test_migrate_rejects_future_major_version(hass: HomeAssistant):
    """A downgrade from a newer major version must not load."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, version=2, minor_version=1)

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


def _v1_entry(options: dict, station: str = "11446500") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        version=1,
        minor_version=1,
        options=options,
        subentries_data=[
            {
                "data": {**LAKE_LOCATION, "usgs_station_id": station},
                "subentry_id": LAKE_SUBENTRY_ID,
                "subentry_type": "location",
                "title": "Lake Natoma",
                "unique_id": None,
            }
        ],
    )


async def test_migrate_restores_weights_lost_to_the_options_bug(hass: HomeAssistant):
    """1.1 saved only the seven slider weights; streamflow and tide come back from the profile."""
    seven = {
        "wind_speed": 0.3,
        "wind_gusts": 0.1,
        "air_quality": 0.2,
        "temperature": 0.15,
        "uv_index": 0.1,
        "visibility": 0.1,
        "precipitation": 0.05,
    }
    entry = _v1_entry({"activity": "kayaking", "profile": "river", "weights": seven})

    await setup_integration(hass, entry)

    from custom_components.paddle_conditions.profiles import get_profile

    weights = entry.options["weights"]
    assert weights["streamflow"] == get_profile("kayaking", "river").weights["streamflow"]
    assert "tide" in weights
    assert weights["wind_speed"] == 0.3


async def test_migrate_keeps_an_explicit_zero_weight(hass: HomeAssistant):
    entry = _v1_entry({"weights": {"wind_speed": 1.0, "streamflow": 0.0}})

    await setup_integration(hass, entry)

    assert entry.options["weights"]["streamflow"] == 0.0


@pytest.mark.parametrize(
    ("key", "station", "disabled_by", "expected"),
    [
        ("forecast_3hr", "11446500", er.RegistryEntryDisabler.INTEGRATION, None),
        ("forecast_3hr", "11446500", er.RegistryEntryDisabler.USER, er.RegistryEntryDisabler.USER),
        ("streamflow", "11446500", er.RegistryEntryDisabler.INTEGRATION, None),
        ("streamflow", "", er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.INTEGRATION),
    ],
)
async def test_migrate_enables_entities_only_the_old_defaults_disabled(
    hass: HomeAssistant, key, station, disabled_by, expected
):
    entry = _v1_entry({}, station=station)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{LAKE_SUBENTRY_ID}_{key}",
        config_entry=entry,
        config_subentry_id=LAKE_SUBENTRY_ID,
        disabled_by=disabled_by,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(entity.entity_id).disabled_by == expected
