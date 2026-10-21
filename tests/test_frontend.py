"""Tests for serving and registering the bundled Lovelace cards (real frontend + lovelace)."""

from __future__ import annotations

import pytest
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.paddle_conditions.const import DOMAIN
from custom_components.paddle_conditions.frontend import CARD_FILES, URL_BASE

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _version(hass: HomeAssistant) -> str:
    return str((await async_get_integration(hass, DOMAIN)).version)


async def _resource_urls(hass: HomeAssistant) -> list[str]:
    resources = hass.data[LOVELACE_DATA].resources
    await resources.async_get_info()
    return sorted(item["url"] for item in resources.async_items())


async def test_cards_registered_once_in_storage_mode(hass: HomeAssistant, hass_storage):
    """Each card gets one versioned module resource, and setting up again adds nothing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    version = await _version(hass)

    expected = sorted(f"{URL_BASE}/{name}?v={version}" for name in CARD_FILES)
    assert await _resource_urls(hass) == expected

    from custom_components.paddle_conditions.frontend import async_register_cards

    await async_register_cards(hass)
    assert await _resource_urls(hass) == expected


async def test_existing_resources_are_upgraded_and_deduplicated(hass: HomeAssistant, hass_storage):
    """Old versions are bumped in place and duplicates from earlier releases are removed."""
    first = CARD_FILES[0]
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {"id": "a", "type": "module", "url": f"{URL_BASE}/{first}?v=0.9.0"},
                {"id": "b", "type": "module", "url": f"{URL_BASE}/{first}?v=1.0.0"},
                {"id": "c", "type": "module", "url": "/local/someone-elses-card.js"},
            ]
        },
    }

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    version = await _version(hass)

    urls = await _resource_urls(hass)
    assert urls.count(f"{URL_BASE}/{first}?v={version}") == 1
    assert not any(u.startswith(f"{URL_BASE}/{first}") and not u.endswith(version) for u in urls)
    assert "/local/someone-elses-card.js" in urls


async def test_yaml_mode_falls_back_to_extra_module_urls(hass: HomeAssistant):
    """With YAML resources the cards are injected as extra modules instead."""
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"resource_mode": "yaml"}})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    version = await _version(hass)

    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    extra = hass.data[DATA_EXTRA_MODULE_URL].urls
    for name in CARD_FILES:
        assert f"{URL_BASE}/{name}?v={version}" in extra


async def test_card_files_are_served(hass: HomeAssistant, hass_client):
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()

    for name in CARD_FILES:
        resp = await client.get(f"{URL_BASE}/{name}")
        assert resp.status == 200
        assert "customElements.define" in await resp.text()
