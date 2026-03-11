"""The Paddle Conditions integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SUBENTRY_TYPE_LOCATION
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .dashboard_generator import generate_dashboard

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_GET_DASHBOARD = "get_dashboard_yaml"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Paddle Conditions domain."""
    return True


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
