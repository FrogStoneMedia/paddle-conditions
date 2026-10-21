"""Serve the bundled Lovelace cards and register them as dashboard resources."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL_BASE = "/paddle_conditions"
CARDS_DIR = Path(__file__).parent / "www"
CARD_FILES = ("paddle-score-card.js", "paddle-spots-card.js")


async def async_register_cards(hass: HomeAssistant) -> None:
    """Serve each card and add it to Lovelace exactly once, at the current version."""
    version = (await async_get_integration(hass, DOMAIN)).version

    # Every URL carries ?v=<version>, so browsers may cache the files.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{URL_BASE}/{name}", str(CARDS_DIR / name), cache_headers=True) for name in CARD_FILES]
    )

    lovelace = hass.data.get(LOVELACE_DATA)
    if (
        lovelace is None
        or lovelace.resource_mode != MODE_STORAGE
        or not isinstance(lovelace.resources, ResourceStorageCollection)
    ):
        # YAML-managed resources can't be edited; inject the modules instead.
        for name in CARD_FILES:
            add_extra_js_url(hass, f"{URL_BASE}/{name}?v={version}")
        return

    # Registering through the resources collection (rather than only
    # add_extra_js_url) is what makes the companion app load the cards.
    resources = lovelace.resources
    await resources.async_get_info()  # Loads the collection from storage if needed.
    for name in CARD_FILES:
        path = f"{URL_BASE}/{name}"
        versioned = f"{path}?v={version}"
        matches = [item for item in resources.async_items() if str(item.get("url", "")).split("?", 1)[0] == path]
        if not matches:
            await resources.async_create_item({"res_type": "module", "url": versioned})
            continue
        keep, *duplicates = matches
        if keep["url"] != versioned:
            await resources.async_update_item(keep["id"], {"res_type": "module", "url": versioned})
        # Releases before 1.1 could register a card more than once.
        for item in duplicates:
            await resources.async_delete_item(item["id"])
