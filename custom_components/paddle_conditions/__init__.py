"""The Paddle Conditions integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.persistent_notification import async_create as pn_async_create
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SUBENTRY_TYPE_LOCATION
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .dashboard_generator import write_dashboard

PLATFORMS: list[Platform] = [Platform.SENSOR]

_FRONTEND_DIR: str = str(Path(__file__).parent / "frontend" / "dist")
_FRONTEND_URL_BASE: str = f"/{DOMAIN}/frontend"
_JS_FILENAME: str = "paddle-cards.js"
_VERSION: str = "1.0.0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Paddle Conditions domain (frontend resources)."""
    if hass.state == CoreState.running:
        await _async_register_frontend(hass)
    else:

        async def _on_started(_event: Event[Any]) -> None:
            await _async_register_frontend(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register static path and JS resource for Lovelace cards."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_FRONTEND_URL_BASE, _FRONTEND_DIR, cache_headers=True)]
    )
    add_extra_js_url(hass, f"{_FRONTEND_URL_BASE}/{_JS_FILENAME}?v={_VERSION}")


async def async_setup_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Set up Paddle Conditions from a config entry."""
    coordinators: dict[str, PaddleCoordinator] = {}

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_LOCATION:
            coordinator = PaddleCoordinator(hass, entry, subentry_id, subentry)
            await coordinator.async_config_entry_first_refresh()
            coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Generate dashboard YAML for configured locations
    dashboard_path = await hass.async_add_executor_job(write_dashboard, entry.subentries)
    if dashboard_path:
        pn_async_create(
            hass,
            "Your Paddle Conditions dashboard has been generated with all your "
            "configured locations.\n\n"
            "**To import it:**\n"
            "1. Go to **Settings → Dashboards → Add Dashboard**\n"
            "2. Create a new dashboard, then open it\n"
            "3. Click the three-dot menu → **Edit Dashboard** → three-dot menu → "
            "**Raw configuration editor**\n"
            "4. Paste the contents of:\n"
            f"`{dashboard_path}`\n\n"
            "The dashboard is regenerated each time you add or remove a location.",
            title="Paddle Conditions Dashboard Ready",
            notification_id=f"{DOMAIN}_dashboard",
        )

    # Reload on subentry changes (add/remove locations)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> None:
    """Reload entry when subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Unload Paddle Conditions config entry."""
    result: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return result
