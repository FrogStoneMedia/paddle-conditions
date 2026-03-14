"""The Paddle Conditions integration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import (
    CoreState,
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, SUBENTRY_TYPE_LOCATION
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .dashboard_generator import generate_dashboard

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_GET_DASHBOARD = "get_dashboard_yaml"

_CARDS_DIR = Path(__file__).parent / "www"
_MANIFEST = json.loads((Path(__file__).parent / "manifest.json").read_text())
_VERSION = _MANIFEST["version"]

_CARD_FILES = ["paddle-score-card.js", "paddle-spots-card.js"]


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register static paths and Lovelace resources for custom cards."""
    from homeassistant.components.http import StaticPathConfig

    configs = [
        StaticPathConfig(
            url_path=f"/paddle_conditions/{card_file}",
            path=str(_CARDS_DIR / card_file),
            cache_headers=False,
        )
        for card_file in _CARD_FILES
    ]
    await hass.http.async_register_static_paths(configs)

    # Register through the Lovelace resources collection so the companion
    # app loads the cards reliably (add_extra_js_url only injects into the
    # HTML page and isn't re-executed on app refresh).
    try:
        resources = hass.data["lovelace"].resources
        existing = resources.async_items()
        for card_file in _CARD_FILES:
            url = f"/paddle_conditions/{card_file}"
            versioned = f"{url}?v={_VERSION}"
            found = False
            for item in existing:
                if url in str(item.get("url", "")):
                    if item["url"] != versioned:
                        await resources.async_update_item(item["id"], {"res_type": "module", "url": versioned})
                    found = True
                    break
            if not found:
                await resources.async_create_item({"res_type": "module", "url": versioned})
    except Exception:
        # Lovelace resources API unavailable (YAML mode, etc.) — fall back
        from homeassistant.components.frontend import add_extra_js_url

        for card_file in _CARD_FILES:
            add_extra_js_url(hass, f"/paddle_conditions/{card_file}?v={_VERSION}")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Paddle Conditions domain."""
    if hass.data.get(f"{DOMAIN}_frontend"):
        return True
    hass.data[f"{DOMAIN}_frontend"] = True

    if hass.state is CoreState.running:
        await _async_register_frontend(hass)
    else:

        async def _on_started(event: Event) -> None:
            await _async_register_frontend(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Set up Paddle Conditions from a config entry."""
    coordinators: dict[str, PaddleCoordinator] = {}

    # Create all coordinators first, then refresh in parallel to avoid
    # serial API timeouts blocking setup (each timeout is 10s).
    pending: list[tuple[str, PaddleCoordinator]] = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_LOCATION:
            coordinator = PaddleCoordinator(hass, entry, subentry_id, subentry)
            pending.append((subentry_id, coordinator))

    # Refresh all locations concurrently
    results = await asyncio.gather(
        *(c.async_config_entry_first_refresh() for _, c in pending),
        return_exceptions=True,
    )

    for (subentry_id, coordinator), result in zip(pending, results, strict=True):
        if isinstance(result, Exception):
            LOGGER.warning("First refresh failed for %s: %s", coordinator.location_name, result)
        coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register dashboard YAML service
    if not hass.services.has_service(DOMAIN, SERVICE_GET_DASHBOARD):

        def handle_get_dashboard(call: ServiceCall) -> ServiceResponse:
            """Return generated dashboard config for all configured locations."""
            entries = hass.config_entries.async_entries(DOMAIN)
            all_subentries: dict = {}
            for cfg_entry in entries:
                all_subentries.update(cfg_entry.subentries)
            return generate_dashboard(all_subentries)

        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_DASHBOARD,
            handle_get_dashboard,
            supports_response=SupportsResponse.ONLY,
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
