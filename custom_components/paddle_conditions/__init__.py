"""The Paddle Conditions integration."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .cache import PaddleCache
from .const import (
    CONF_ACTIVITY,
    CONF_PROFILE,
    CONF_USGS_STATION_ID,
    DEFAULT_ACTIVITY,
    DEFAULT_PROFILES,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_LOCATION,
)
from .coordinator import PaddleConfigEntry, PaddleCoordinator
from .frontend import async_register_cards
from .profiles import get_profile
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Paddle Conditions domain."""
    async_setup_services(hass)
    await async_register_cards(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Set up Paddle Conditions from a config entry."""
    # What this setup is built from, by value (HA edits subentries in place);
    # see the check after the listener below.
    configured = _config_snapshot(entry)
    locations = [sub for sub in entry.subentries.values() if sub.subentry_type == SUBENTRY_TYPE_LOCATION]

    cache = PaddleCache(hass, entry.entry_id)
    await cache.async_load(keep={sub.subentry_id for sub in locations})
    entry.async_on_unload(cache.async_flush)

    coordinators = {sub.subentry_id: PaddleCoordinator(hass, entry, sub, cache) for sub in locations}

    # Refresh every location concurrently; each upstream timeout is 10 s.
    # A location with no data at all raises ConfigEntryNotReady so HA retries.
    results = await asyncio.gather(
        *(c.async_config_entry_first_refresh() for c in coordinators.values()),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on subentry changes (add/remove locations)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    # HA only notifies listeners registered at the time of a change, so a
    # location added or edited while this entry was unloaded or setting up
    # (e.g. two locations added back to back) would otherwise be lost until
    # restart. Reload once more if anything changed since setup began.
    if _config_snapshot(entry) != configured:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Migrate an older config entry to the current schema."""
    if entry.version > 1:
        # Downgraded from a future major version we don't understand.
        return False

    if entry.minor_version < 2:
        # 1.2 removed cloud sync; drop its URL and bearer token from options.
        options = {k: v for k, v in entry.options.items() if k not in ("cloud_sync_url", "cloud_sync_token")}
        # 1.1's options form saved only the seven slider weights, dropping
        # streamflow and tide; restore them from the profile.
        if "weights" in options:
            activity = options.get(CONF_ACTIVITY, DEFAULT_ACTIVITY)
            profile = get_profile(activity, options.get(CONF_PROFILE, DEFAULT_PROFILES.get(activity, "")))
            options["weights"] = {**profile.weights, **options["weights"]}
        # 1.2 also replaced one cache file per location with a single cache per entry.
        for subentry_id in entry.subentries:
            await Store[dict[str, Any]](hass, 1, f"{DOMAIN}_{subentry_id}_cache").async_remove()
        _enable_entities_disabled_by_old_defaults(hass, entry)
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)

    LOGGER.debug("Migrated config entry to version %s.%s", entry.version, entry.minor_version)
    return True


def _enable_entities_disabled_by_old_defaults(hass: HomeAssistant, entry: PaddleConfigEntry) -> None:
    """Enable forecast and streamflow sensors that 1.1 disabled by default.

    Only entities the integration disabled are touched; a user's choice stays.
    Streamflow is enabled only where the location has a USGS station.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.disabled_by is not er.RegistryEntryDisabler.INTEGRATION or entity.config_subentry_id is None:
            continue
        subentry = entry.subentries.get(entity.config_subentry_id)
        if subentry is None:
            continue
        has_station = bool(subentry.data.get(CONF_USGS_STATION_ID))
        if entity.unique_id.endswith("_forecast_3hr") or (entity.unique_id.endswith("_streamflow") and has_station):
            registry.async_update_entity(entity.entity_id, disabled_by=None)


async def _async_reload_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> None:
    """Reload entry when subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _config_snapshot(entry: PaddleConfigEntry) -> tuple[dict[str, Any], dict[str, Any]]:
    """Everything setup depends on, copied by value."""
    subentries = {
        sid: {"type": sub.subentry_type, "title": sub.title, "data": dict(sub.data)}
        for sid, sub in entry.subentries.items()
    }
    return subentries, dict(entry.options)


async def async_unload_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> bool:
    """Unload Paddle Conditions config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PaddleConfigEntry) -> None:
    """Delete the conditions cache when the integration is removed."""
    await PaddleCache(hass, entry.entry_id).async_remove()
