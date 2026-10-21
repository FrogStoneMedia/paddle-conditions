"""Diagnostics for Paddle Conditions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_USGS_API_KEY
from .coordinator import PaddleConfigEntry

# Coordinates and the user's own names for spots can identify where they live.
TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_USGS_API_KEY, "title", "location"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PaddleConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    locations: dict[str, Any] = {}
    for subentry_id, coordinator in entry.runtime_data.items():
        data = coordinator.data
        locations[subentry_id] = {
            "config": dict(entry.subentries[subentry_id].data),
            "update_interval": str(coordinator.update_interval),
            "stale_after": str(coordinator.stale_after),
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "failing_sources": sorted(coordinator.failing_sources),
            "conditions": None
            if data is None
            else {
                "fetched_at": data.fetched_at,
                "activity": data.activity,
                "profile": data.profile,
                "score": data.score.value,
                "rating": data.score.rating,
                "factors": data.score.factors,
                "missing_factors": data.score.missing_factors,
                "vetoed": data.score.vetoed,
                "veto_reason": data.score.veto_reason,
                "forecast_blocks": len(data.forecast_blocks),
                "hourly_points": len(data.hourly_times),
            },
        }

    return async_redact_data(
        {
            "entry": {"version": f"{entry.version}.{entry.minor_version}", "options": dict(entry.options)},
            "locations": locations,
        },
        TO_REDACT,
    )
