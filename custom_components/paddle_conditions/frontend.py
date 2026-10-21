"""Serve the bundled Lovelace cards and register them as a dashboard resource."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

URL_BASE = "/paddle_conditions"
DIST_DIR = Path(__file__).parent / "frontend" / "dist"
# One ES module defining every card (built from frontend/ by esbuild).
BUNDLE = "paddle-cards.js"
# Per-card files registered by 1.x; replaced by the bundle.
LEGACY_FILES = ("paddle-score-card.js", "paddle-spots-card.js")
_STATIC_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_static_registered")


async def async_register_cards(hass: HomeAssistant) -> None:
    """Serve the bundle and add it to Lovelace exactly once, at the current version."""
    version = (await async_get_integration(hass, DOMAIN)).version
    url = f"{URL_BASE}/{BUNDLE}"
    versioned = f"{url}?v={version}"

    # The URL carries ?v=<version>, so browsers may cache the file.
    if not hass.data.get(_STATIC_REGISTERED):
        await hass.http.async_register_static_paths([StaticPathConfig(url, str(DIST_DIR / BUNDLE), cache_headers=True)])
        hass.data[_STATIC_REGISTERED] = True

    lovelace = hass.data.get(LOVELACE_DATA)
    if (
        lovelace is None
        or lovelace.resource_mode != MODE_STORAGE
        or not isinstance(lovelace.resources, ResourceStorageCollection)
    ):
        # YAML-managed resources can't be edited; inject the module instead.
        add_extra_js_url(hass, versioned)
        return

    # Registering through the resources collection (rather than only
    # add_extra_js_url) is what makes the companion app load the cards.
    resources = lovelace.resources
    await resources.async_get_info()  # Loads the collection from storage if needed.
    ours = [item for item in resources.async_items() if str(item.get("url", "")).split("?", 1)[0] == url]
    legacy = {f"{URL_BASE}/{name}" for name in LEGACY_FILES}
    for item in resources.async_items():
        if str(item.get("url", "")).split("?", 1)[0] in legacy:
            await resources.async_delete_item(item["id"])

    if not ours:
        await resources.async_create_item({"res_type": "module", "url": versioned})
        return
    keep, *duplicates = ours
    if keep["url"] != versioned:
        await resources.async_update_item(keep["id"], {"res_type": "module", "url": versioned})
    for item in duplicates:
        await resources.async_delete_item(item["id"])
