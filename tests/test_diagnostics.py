"""Tests for Paddle Conditions diagnostics."""

from unittest.mock import MagicMock

from custom_components.paddle_conditions.diagnostics import (
    REDACT_KEYS,
    async_get_config_entry_diagnostics,
)


def _make_coordinator(**overrides):
    """Create a mock coordinator for diagnostics."""
    defaults = {
        "location_name": "Lake Natoma",
        "latitude": 38.637,
        "longitude": -121.227,
        "water_body_type": "lake",
        "usgs_station_id": "11446500",
        "noaa_station_id": "",
        "last_update_success": True,
        "update_interval": "0:10:00",
    }
    defaults.update(overrides)
    coordinator = MagicMock()
    for key, val in defaults.items():
        setattr(coordinator, key, val)
    return coordinator


class TestDiagnostics:
    """Tests for diagnostics output."""

    async def test_redacts_cloud_sync_token(self, mock_config_entry):
        """Cloud sync token in options should be redacted."""
        mock_config_entry.options = {
            "cloud_sync_token": "tok_abc",
            "update_interval": 10,
        }
        mock_config_entry.runtime_data = {}

        result = await async_get_config_entry_diagnostics(None, mock_config_entry)

        assert result["options"]["cloud_sync_token"] == "**REDACTED**"
        assert result["options"]["update_interval"] == 10

    async def test_empty_keys_not_redacted(self, mock_config_entry):
        """Empty token should not be redacted."""
        mock_config_entry.options = {
            "cloud_sync_token": "",
            "update_interval": 10,
        }
        mock_config_entry.runtime_data = {}

        result = await async_get_config_entry_diagnostics(None, mock_config_entry)
        assert result["options"]["cloud_sync_token"] == ""

    async def test_coordinator_info(self, mock_config_entry):
        """Coordinator status should be included."""
        coordinator = _make_coordinator()
        mock_config_entry.options = {}
        mock_config_entry.runtime_data = {"sub_001": coordinator}

        result = await async_get_config_entry_diagnostics(None, mock_config_entry)

        info = result["coordinators"]["sub_001"]
        assert info["location"] == "Lake Natoma"
        assert info["latitude"] == 38.637
        assert info["longitude"] == -121.227
        assert info["water_body_type"] == "lake"
        assert info["usgs_station_id"] == "11446500"
        assert info["last_update_success"] is True

    async def test_multiple_coordinators(self, mock_config_entry):
        """Multiple locations should all appear in diagnostics."""
        coord1 = _make_coordinator(location_name="Lake Natoma")
        coord2 = _make_coordinator(location_name="SF Bay", water_body_type="bay_ocean")
        mock_config_entry.options = {}
        mock_config_entry.runtime_data = {"sub_001": coord1, "sub_002": coord2}

        result = await async_get_config_entry_diagnostics(None, mock_config_entry)

        assert len(result["coordinators"]) == 2
        assert result["coordinators"]["sub_001"]["location"] == "Lake Natoma"
        assert result["coordinators"]["sub_002"]["location"] == "SF Bay"

    async def test_no_coordinators(self, mock_config_entry):
        """Empty runtime_data should produce empty coordinators dict."""
        mock_config_entry.options = {}
        mock_config_entry.runtime_data = {}

        result = await async_get_config_entry_diagnostics(None, mock_config_entry)
        assert result["coordinators"] == {}

    def test_redact_keys_contains_only_real_secrets(self):
        """REDACT_KEYS should only contain keys the integration actually uses."""
        assert "cloud_sync_token" in REDACT_KEYS
        # No dead keys for APIs we don't use
        assert "openweathermap_api_key" not in REDACT_KEYS
        assert "purpleair_api_key" not in REDACT_KEYS
        assert "stormglass_api_key" not in REDACT_KEYS
