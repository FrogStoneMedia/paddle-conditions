"""Tests for Paddle Conditions sensor entities."""

from unittest.mock import MagicMock

from custom_components.paddle_conditions.models import (
    ForecastBlock,
    PaddleConditions,
    PaddleScore,
)
from custom_components.paddle_conditions.sensor import (
    SENSOR_DESCRIPTIONS,
    PaddleSensor,
    PaddleSensorEntityDescription,
)


def _make_conditions(**overrides):
    """Create a PaddleConditions with sensible defaults."""
    defaults = {
        "score": PaddleScore(
            value=82,
            rating="GO",
            limiting_factor="wind_speed",
            factors={"wind_speed": 85, "aqi": 95},
            missing_factors=[],
            vetoed=False,
            veto_reason=None,
        ),
        "activity": "sup",
        "profile": "recreational",
        "wind_speed": 8.0,
        "wind_gusts": 12.0,
        "wind_direction": 180,
        "air_temp": 75.0,
        "water_temp": 62.0,
        "uv_index": 4.0,
        "aqi": 42,
        "visibility": 10.0,
        "precipitation_probability": 10,
        "streamflow_cfs": None,
        "tide_factor": None,
        "condition_text": "Partly cloudy",
        "forecast_blocks": [],
        "hourly_times": [],
        "hourly_wind": [],
        "hourly_temp": [],
        "hourly_uv": [],
        "hourly_precip": [],
    }
    defaults.update(overrides)
    return PaddleConditions(**defaults)


def _make_coordinator(conditions=None):
    """Create a mock coordinator with data."""
    coordinator = MagicMock()
    coordinator.data = conditions or _make_conditions()
    coordinator.location_name = "Lake Natoma"
    coordinator.water_body_type = "lake"
    return coordinator


class TestSensorDescriptions:
    """Tests for sensor description definitions."""

    def test_expected_keys_exist(self):
        """All expected sensor types are defined."""
        keys = {d.key for d in SENSOR_DESCRIPTIONS}
        expected = {
            "score",
            "wind_speed",
            "wind_gusts",
            "wind_direction",
            "air_temp",
            "water_temp",
            "uv_index",
            "aqi",
            "visibility",
            "precipitation",
            "streamflow",
            "condition",
            "forecast_3hr",
        }
        assert expected == keys

    def test_all_have_value_fn(self):
        """Every description has a value_fn callable."""
        for desc in SENSOR_DESCRIPTIONS:
            assert callable(desc.value_fn), f"{desc.key} missing value_fn"

    def test_descriptions_are_frozen(self):
        """Descriptions should be frozen dataclasses."""
        for desc in SENSOR_DESCRIPTIONS:
            assert isinstance(desc, PaddleSensorEntityDescription)


class TestPaddleSensor:
    """Tests for PaddleSensor entity."""

    def test_unique_id_format(self):
        """unique_id should be {subentry_id}_{key}."""
        coordinator = _make_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_abc123", desc)
        assert sensor._attr_unique_id == "sub_abc123_score"

    def test_device_info(self):
        """Device info should identify the location."""
        coordinator = _make_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor._attr_device_info is not None
        assert ("paddle_conditions", "sub_001") in sensor._attr_device_info["identifiers"]
        assert sensor._attr_device_info["name"] == "Lake Natoma"

    def test_score_native_value(self):
        """Score sensor returns the numeric score."""
        conditions = _make_conditions()
        coordinator = _make_coordinator(conditions)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 82

    def test_score_extra_attributes(self):
        """Score sensor includes rating, activity, profile in attributes."""
        conditions = _make_conditions()
        coordinator = _make_coordinator(conditions)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        attrs = sensor.extra_state_attributes
        assert attrs["rating"] == "GO"
        assert attrs["activity"] == "sup"
        assert attrs["profile"] == "recreational"
        assert attrs["limiting_factor"] == "wind_speed"
        assert attrs["vetoed"] is False

    def test_wind_speed_value(self):
        """Wind speed sensor returns wind_speed from conditions."""
        coordinator = _make_coordinator(_make_conditions(wind_speed=12.5))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "wind_speed")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 12.5

    def test_water_temp_value(self):
        """Water temp sensor returns water_temp from conditions."""
        coordinator = _make_coordinator(_make_conditions(water_temp=65.3))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "water_temp")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 65.3

    def test_water_temp_none(self):
        """Water temp sensor returns None when no data."""
        coordinator = _make_coordinator(_make_conditions(water_temp=None))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "water_temp")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value is None

    def test_aqi_value(self):
        """AQI sensor returns aqi from conditions."""
        coordinator = _make_coordinator(_make_conditions(aqi=55))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "aqi")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 55

    def test_condition_text(self):
        """Condition sensor returns the text description."""
        coordinator = _make_coordinator(_make_conditions(condition_text="Clear sky"))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "condition")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == "Clear sky"

    def test_streamflow_value(self):
        """Streamflow sensor returns CFS value."""
        coordinator = _make_coordinator(_make_conditions(streamflow_cfs=450.0))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "streamflow")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 450.0

    def test_forecast_value_with_blocks(self):
        """Forecast sensor returns first block score."""
        blocks = [
            ForecastBlock(
                start="12:00", end="15:00", score=78, rating="GO", wind_mph=10.0, temp_f=72.0, uv=5.0, precip_pct=0
            ),
            ForecastBlock(
                start="15:00",
                end="18:00",
                score=65,
                rating="CAUTION",
                wind_mph=15.0,
                temp_f=70.0,
                uv=3.0,
                precip_pct=10,
            ),
        ]
        coordinator = _make_coordinator(_make_conditions(forecast_blocks=blocks))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "forecast_3hr")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value == 78

    def test_forecast_value_empty(self):
        """Forecast sensor returns None when no blocks."""
        coordinator = _make_coordinator(_make_conditions(forecast_blocks=[]))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "forecast_3hr")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value is None

    def test_forecast_extra_attributes(self):
        """Forecast sensor includes block details and best block."""
        blocks = [
            ForecastBlock(
                start="12:00", end="15:00", score=65, rating="CAUTION", wind_mph=15.0, temp_f=70.0, uv=3.0, precip_pct=5
            ),
            ForecastBlock(
                start="15:00", end="18:00", score=85, rating="GO", wind_mph=8.0, temp_f=74.0, uv=4.0, precip_pct=0
            ),
        ]
        coordinator = _make_coordinator(_make_conditions(forecast_blocks=blocks))
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "forecast_3hr")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        attrs = sensor.extra_state_attributes
        assert len(attrs["blocks"]) == 2
        assert attrs["best_block"] == "15:00"
        assert attrs["best_score"] == 85

    def test_no_extra_attrs_for_simple_sensors(self):
        """Sensors without extra_attrs_fn return None for attributes."""
        coordinator = _make_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "wind_speed")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.extra_state_attributes is None

    def test_has_entity_name(self):
        """Sensor uses HA entity naming."""
        coordinator = _make_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor._attr_has_entity_name is True

    def test_attribution(self):
        """Sensor has proper attribution string."""
        coordinator = _make_coordinator()
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert "Open-Meteo" in sensor._attr_attribution
        assert "USGS" in sensor._attr_attribution
        assert "NOAA" in sensor._attr_attribution

    def test_native_value_none_when_no_data(self):
        """Sensor returns None when coordinator has no data."""
        coordinator = _make_coordinator()
        coordinator.data = None
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.native_value is None

    def test_extra_attrs_none_when_no_data(self):
        """Extra attrs returns None when coordinator has no data."""
        coordinator = _make_coordinator()
        coordinator.data = None
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "score")
        sensor = PaddleSensor(coordinator, "sub_001", desc)
        assert sensor.extra_state_attributes is None


class TestEntityCategories:
    """Tests for entity category and disabled-by-default assignments."""

    def test_streamflow_is_diagnostic(self):
        """Streamflow sensor should be categorized as diagnostic."""
        from homeassistant.const import EntityCategory

        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "streamflow")
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_condition_is_diagnostic(self):
        """Condition sensor should be categorized as diagnostic."""
        from homeassistant.const import EntityCategory

        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "condition")
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_forecast_is_diagnostic(self):
        """Forecast sensor should be categorized as diagnostic."""
        from homeassistant.const import EntityCategory

        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "forecast_3hr")
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_streamflow_disabled_by_default(self):
        """Streamflow sensor should be disabled by default."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "streamflow")
        assert desc.entity_registry_enabled_default is False

    def test_forecast_disabled_by_default(self):
        """Forecast sensor should be disabled by default."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "forecast_3hr")
        assert desc.entity_registry_enabled_default is False

    def test_primary_sensors_have_no_category(self):
        """Primary sensors (score, wind, temp, etc.) should not have a category."""
        primary_keys = {"score", "wind_speed", "wind_gusts", "wind_direction", "air_temp", "water_temp", "uv_index", "aqi", "visibility", "precipitation"}
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in primary_keys:
                assert desc.entity_category is None, f"{desc.key} should not have entity_category"
