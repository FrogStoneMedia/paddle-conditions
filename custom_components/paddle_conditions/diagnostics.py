"""Diagnostics for Paddle Conditions."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PaddleConfigEntry

REDACT_KEYS = {
    "cloud_sync_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: PaddleConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    redacted_options = {}
    for key, value in entry.options.items():
        if key in REDACT_KEYS and value:
            redacted_options[key] = "**REDACTED**"
        else:
            redacted_options[key] = value

    coordinators_info = {}
    for subentry_id, coordinator in entry.runtime_data.items():
        coordinators_info[subentry_id] = {
            "location": coordinator.location_name,
            "latitude": coordinator.latitude,
            "longitude": coordinator.longitude,
            "water_body_type": coordinator.water_body_type,
            "usgs_station_id": coordinator.usgs_station_id,
            "noaa_station_id": coordinator.noaa_station_id,
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        }

    return {
        "options": redacted_options,
        "coordinators": coordinators_info,
    }
