"""Actions for Paddle Conditions."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .dashboard_generator import generate_dashboard

SERVICE_GET_DASHBOARD = "get_dashboard_yaml"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

    @callback
    def handle_get_dashboard(call: ServiceCall) -> ServiceResponse:
        """Return a dashboard config for every loaded location."""
        subentries = [
            subentry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
            for subentry in entry.subentries.values()
        ]
        dashboard = generate_dashboard(hass, subentries)
        if not dashboard["views"][0]["cards"]:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_locations")
        return dashboard

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DASHBOARD,
        handle_get_dashboard,
        supports_response=SupportsResponse.ONLY,
    )
