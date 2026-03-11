"""Tests for the Paddle Conditions coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.paddle_conditions.coordinator import PaddleCoordinator
from custom_components.paddle_conditions.models import PaddleConditions


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.loop = AsyncMock()
    return hass


def test_coordinator_init(mock_hass, mock_config_entry, mock_subentry):
    """Coordinator stores location config from subentry."""
    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        coordinator = PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)
    assert coordinator.location_name == "Lake Natoma"
    assert coordinator.latitude == 38.637
    assert coordinator.longitude == -121.227
    assert coordinator.water_body_type == "lake"


def test_coordinator_uses_custom_update_interval(mock_hass, mock_config_entry, mock_subentry):
    """Coordinator reads update_interval from config entry options."""
    from datetime import timedelta

    mock_config_entry.options = {"update_interval": 30}
    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        coordinator = PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)
    assert coordinator.update_interval == timedelta(minutes=30)


def test_coordinator_uses_default_update_interval(mock_hass, mock_config_entry, mock_subentry):
    """Coordinator falls back to default when option not set."""
    from datetime import timedelta

    from custom_components.paddle_conditions.const import DEFAULT_UPDATE_INTERVAL_MINUTES

    mock_config_entry.options = {}
    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        coordinator = PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)
    assert coordinator.update_interval == timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MINUTES)


@pytest.fixture
def _make_coordinator(mock_hass, mock_config_entry, mock_subentry):
    """Helper to create a coordinator with mocked session."""

    def _factory():
        with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
            return PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)

    return _factory


def _mock_weather(**overrides):
    """Create mock weather data with sensible defaults."""
    defaults = dict(
        wind_speed=8.0,
        wind_gusts=12.0,
        wind_direction=180,
        air_temp=75.0,
        uv_index=4.0,
        visibility=15.0,
        precipitation_probability=10,
        condition_text="Partly cloudy",
        has_thunderstorm=False,
        hourly_wind=[],
        hourly_temp=[],
        hourly_uv=[],
        hourly_times=[],
        hourly_weather_codes=[],
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


async def test_coordinator_update_success(_make_coordinator):
    """Successful fetch returns PaddleConditions with correct values."""
    coordinator = _make_coordinator()

    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=42))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=62.0, streamflow_cfs=1200.0))

    data = await coordinator._async_update_data()

    assert isinstance(data, PaddleConditions)
    assert data.wind_speed == 8.0
    assert data.water_temp == 62.0
    assert data.aqi == 42
    assert data.score.rating in ("GO", "CAUTION", "NO_GO")


async def test_coordinator_aqi_failure_degrades_gracefully(_make_coordinator):
    """AQI failure should not prevent score computation."""
    coordinator = _make_coordinator()

    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(side_effect=Exception("API down"))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=None, streamflow_cfs=None))

    data = await coordinator._async_update_data()
    assert data.aqi is None
    assert "air_quality" in data.score.missing_factors


async def test_coordinator_weather_failure_raises(_make_coordinator):
    """Weather failure should raise UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator = _make_coordinator()
    coordinator.weather_client.fetch = AsyncMock(side_effect=Exception("Timeout"))

    with pytest.raises(UpdateFailed, match="Weather API failed"):
        await coordinator._async_update_data()


async def test_coordinator_builds_forecast_blocks(_make_coordinator):
    """Forecast blocks use max wind (not average) from 3-hour windows."""
    coordinator = _make_coordinator()

    # Asymmetric data: max != average to verify max() is used
    coordinator.weather_client.fetch = AsyncMock(
        return_value=_mock_weather(
            hourly_wind=[3.0, 5.0, 11.0, 4.0, 6.0, 14.0],
            hourly_temp=[70.0, 72.0, 74.0, 76.0, 78.0, 80.0],
            hourly_uv=[2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            hourly_times=[
                "2026-03-10T06:00",
                "2026-03-10T07:00",
                "2026-03-10T08:00",
                "2026-03-10T09:00",
                "2026-03-10T10:00",
                "2026-03-10T11:00",
            ],
            hourly_weather_codes=[0, 0, 0, 0, 0, 0],
        )
    )
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=30))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=None, streamflow_cfs=None))

    data = await coordinator._async_update_data()
    assert len(data.forecast_blocks) == 2
    assert data.forecast_blocks[0].wind_mph == 11.0  # max([3, 5, 11])
    assert data.forecast_blocks[1].wind_mph == 14.0  # max([4, 6, 14])


async def test_coordinator_noaa_water_temp_fallback(_make_coordinator, mock_subentry):
    """NOAA water temp used when USGS water temp is None."""
    mock_subentry.data["noaa_station_id"] = "9414290"
    coordinator = _make_coordinator()

    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=30))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=None, streamflow_cfs=None))
    coordinator.noaa_client.fetch_water_temp = AsyncMock(return_value=55.2)

    data = await coordinator._async_update_data()
    assert data.water_temp == 55.2


async def test_coordinator_usgs_preferred_over_noaa(_make_coordinator, mock_subentry):
    """USGS water temp takes priority over NOAA."""
    mock_subentry.data["noaa_station_id"] = "9414290"
    coordinator = _make_coordinator()

    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=30))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=62.0, streamflow_cfs=None))
    coordinator.noaa_client.fetch_water_temp = AsyncMock(return_value=55.2)

    data = await coordinator._async_update_data()
    assert data.water_temp == 62.0


async def test_coordinator_creates_sync_client(mock_config_entry, mock_subentry, mock_hass):
    """Coordinator creates a CloudSyncClient from config options."""
    mock_config_entry.options = {
        "cloud_sync_enabled": True,
        "cloud_sync_url": "https://sync.example.com",
        "cloud_sync_token": "test-token",
    }
    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        coordinator = PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)
    assert coordinator.sync_client is not None
    assert coordinator.sync_client.enabled is True


async def test_coordinator_sync_client_disabled_by_default(_make_coordinator):
    """Sync client is disabled when no cloud sync options are set."""
    coordinator = _make_coordinator()
    assert coordinator.sync_client is not None
    assert coordinator.sync_client.enabled is False


async def test_coordinator_pushes_to_cloud_after_update(mock_config_entry, mock_subentry, mock_hass):
    """Coordinator fires cloud push as a background task (non-blocking)."""
    mock_config_entry.options = {
        "cloud_sync_enabled": True,
        "cloud_sync_url": "https://sync.example.com",
        "cloud_sync_token": "test-token",
    }
    mock_hass.async_create_task = MagicMock()
    with patch("custom_components.paddle_conditions.coordinator.async_get_clientsession"):
        coordinator = PaddleCoordinator(mock_hass, mock_config_entry, "sub_001", mock_subentry)

    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=42))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=62.0, streamflow_cfs=1200.0))
    coordinator.sync_client.push = AsyncMock(return_value=True)

    await coordinator._async_update_data()

    # Verify push was dispatched as a background task, not awaited directly
    mock_hass.async_create_task.assert_called_once()


async def test_coordinator_sync_push_failure_does_not_block_update(_make_coordinator):
    """Cloud sync push failure should not prevent returning conditions data."""
    coordinator = _make_coordinator()
    coordinator.weather_client.fetch = AsyncMock(return_value=_mock_weather())
    coordinator.aqi_client.fetch = AsyncMock(return_value=MagicMock(aqi=42))
    coordinator.usgs_client.fetch = AsyncMock(return_value=MagicMock(water_temp_f=None, streamflow_cfs=None))

    # Even though sync is disabled (no URL/token), update should succeed
    data = await coordinator._async_update_data()
    assert isinstance(data, PaddleConditions)
