"""Tests for frontend resource registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import CoreState

from custom_components.paddle_conditions import _async_register_frontend, async_setup


@pytest.fixture
def mock_hass_running():
    """Create a mock HomeAssistant instance in running state."""
    hass = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.state = CoreState.running
    hass.data = {}
    return hass


@pytest.fixture
def mock_hass_starting():
    """Create a mock HomeAssistant instance in starting state."""
    hass = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.state = CoreState.starting
    hass.data = {}
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
    """_async_register_frontend registers static paths for card JS files."""
    # Make Lovelace resources unavailable so it falls back to add_extra_js_url
    mock_hass_running.data = {}

    with patch("homeassistant.components.frontend.add_extra_js_url"):
        await _async_register_frontend(mock_hass_running)

    # Verify static path registration was called
    mock_hass_running.http.async_register_static_paths.assert_called_once()
    static_call = mock_hass_running.http.async_register_static_paths.call_args
    configs = static_call[0][0]
    # Two card files: paddle-score-card.js and paddle-spots-card.js
    assert len(configs) == 2
    urls = [c.url_path for c in configs]
    assert any("paddle-score-card.js" in u for u in urls)
    assert any("paddle-spots-card.js" in u for u in urls)


async def test_async_register_frontend_url_has_version(mock_hass_running: MagicMock) -> None:
    """JS resource URLs include version string for cache-busting."""
    mock_hass_running.data = {}

    with patch("homeassistant.components.frontend.add_extra_js_url") as mock_add_js:
        await _async_register_frontend(mock_hass_running)

    # add_extra_js_url called once per card file
    assert mock_add_js.call_count == 2
    for call in mock_add_js.call_args_list:
        js_url = call[0][1]
        assert "v=" in js_url


async def test_async_setup_defers_when_not_running(mock_hass_starting: MagicMock) -> None:
    """When HA is not fully started, registration is deferred."""
    with patch("custom_components.paddle_conditions._async_register_frontend") as mock_register:
        result = await async_setup(mock_hass_starting, {})

    assert result is True
    mock_register.assert_not_called()
    mock_hass_starting.bus.async_listen_once.assert_called_once()
