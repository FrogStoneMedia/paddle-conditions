"""Tests for frontend resource registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import CoreState

from custom_components.paddle_conditions import async_setup, _async_register_frontend
from custom_components.paddle_conditions.const import DOMAIN


@pytest.fixture
def mock_hass_running():
    """Create a mock HomeAssistant instance in running state."""
    hass = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.state = CoreState.running
    return hass


@pytest.fixture
def mock_hass_starting():
    """Create a mock HomeAssistant instance in starting state."""
    hass = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.state = CoreState.starting
    return hass


async def test_async_setup_returns_true(mock_hass_running: MagicMock) -> None:
    """async_setup must return True to allow entry setup to proceed."""
    with patch("custom_components.paddle_conditions._async_register_frontend"):
        result = await async_setup(mock_hass_running, {})
    assert result is True


async def test_async_setup_registers_when_running(mock_hass_running: MagicMock) -> None:
    """async_setup awaits _async_register_frontend immediately when HA is running."""
    with patch(
        "custom_components.paddle_conditions._async_register_frontend",
        new_callable=AsyncMock,
    ) as mock_register:
        await async_setup(mock_hass_running, {})
    mock_register.assert_awaited_once_with(mock_hass_running)


async def test_async_register_frontend_calls_static_paths(mock_hass_running: MagicMock) -> None:
    """_async_register_frontend registers static path and JS URL."""
    with patch(
        "custom_components.paddle_conditions.add_extra_js_url"
    ) as mock_add_js:
        await _async_register_frontend(mock_hass_running)

    # Verify static path registration was called
    mock_hass_running.http.async_register_static_paths.assert_called_once()
    static_call = mock_hass_running.http.async_register_static_paths.call_args
    configs = static_call[0][0]
    assert len(configs) == 1
    config = configs[0]
    assert "/paddle_conditions" in config.url_path

    # Verify JS URL registration was called with version for cache-busting
    mock_add_js.assert_called_once()
    js_url = mock_add_js.call_args[0][1]
    assert "paddle-cards.js" in js_url
    assert "v=" in js_url


async def test_async_register_frontend_url_has_version(mock_hass_running: MagicMock) -> None:
    """JS resource URL includes version string for cache-busting."""
    with patch(
        "custom_components.paddle_conditions.add_extra_js_url"
    ) as mock_add_js:
        await _async_register_frontend(mock_hass_running)

    js_url = mock_add_js.call_args[0][1]
    assert "1.0.0" in js_url


async def test_async_setup_defers_when_not_running(mock_hass_starting: MagicMock) -> None:
    """When HA is not fully started, registration is deferred."""
    with patch(
        "custom_components.paddle_conditions._async_register_frontend"
    ) as mock_register:
        result = await async_setup(mock_hass_starting, {})

    assert result is True
    mock_register.assert_not_called()
    mock_hass_starting.bus.async_listen_once.assert_called_once()


async def test_manifest_has_frontend_dependency() -> None:
    """manifest.json must declare frontend and http dependencies."""
    import json
    from pathlib import Path

    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "paddle_conditions"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    assert "frontend" in manifest["dependencies"]
    assert "http" in manifest["dependencies"]
