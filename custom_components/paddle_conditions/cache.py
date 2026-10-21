"""Persistent cache of the last good conditions for each location."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_ACTIVITY, CONF_PROFILE, DOMAIN, LOGGER
from .models import PaddleConditions

STORAGE_VERSION = 1
SAVE_DELAY_SECONDS = 30

# Options that change the computed score. Anything else (update interval)
# can change without invalidating cached conditions.
_SCORING_OPTIONS = (CONF_ACTIVITY, CONF_PROFILE, "weights")


def location_fingerprint(location: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Hash everything that determines a location's conditions and score."""
    material = {
        "location": dict(location),
        "options": {key: options.get(key) for key in _SCORING_OPTIONS},
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()


def storage_key(entry_id: str) -> str:
    """Return the storage key for an entry's cache."""
    return f"{DOMAIN}.{entry_id}.conditions"


class PaddleCache:
    """Last good conditions per location subentry, keyed by fingerprint."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, storage_key(entry_id))
        self._locations: dict[str, dict[str, Any]] = {}
        self._loaded = False

    async def async_load(self, keep: set[str]) -> None:
        """Load the cache, dropping locations that no longer exist."""
        stored = await self._store.async_load() or {}
        locations = stored.get("locations", {})
        self._locations = {sid: row for sid, row in locations.items() if sid in keep}
        self._loaded = True
        if len(self._locations) != len(locations):
            self._schedule_save()

    def get(self, subentry_id: str, fingerprint: str) -> PaddleConditions | None:
        """Return cached conditions if they were computed for this exact configuration."""
        row = self._locations.get(subentry_id)
        if row is None or row.get("fingerprint") != fingerprint:
            return None
        try:
            return PaddleConditions.from_dict(row["conditions"])
        except KeyError, TypeError, ValueError:
            LOGGER.debug("Ignoring unreadable cached conditions for %s", subentry_id)
            return None

    def set(self, subentry_id: str, fingerprint: str, conditions: PaddleConditions) -> None:
        """Remember conditions and save them shortly after."""
        self._locations[subentry_id] = {"fingerprint": fingerprint, "conditions": conditions.to_dict()}
        self._schedule_save()

    async def async_flush(self) -> None:
        """Write the current data now, on this Store.

        Delayed saves are only flushed when Home Assistant stops, so without
        this a reload (options change, reconfigure) would lose the latest data.
        Saving unconditionally on the same Store also waits out any write that
        is already in flight, so nothing can land after the entry is removed.
        """
        if self._loaded:
            await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Delete the cache from disk."""
        self._locations = {}
        self._loaded = False
        await self._store.async_remove()

    def _data(self) -> dict[str, Any]:
        return {"locations": self._locations}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data, SAVE_DELAY_SECONDS)
