"""Preset paddle locations with pre-filled data."""

from __future__ import annotations

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_NOAA_STATION_ID,
    CONF_USGS_STATION_ID,
    CONF_WATER_BODY_TYPE,
    WATER_BODY_LAKE,
)

PRESET_CUSTOM = "custom"

PRESET_LOCATIONS: dict[str, dict[str, str | float]] = {
    "lake_natoma": {
        CONF_NAME: "Lake Natoma",
        CONF_LATITUDE: 38.636,
        CONF_LONGITUDE: -121.185,
        CONF_WATER_BODY_TYPE: WATER_BODY_LAKE,
        CONF_USGS_STATION_ID: "11446220",
        CONF_NOAA_STATION_ID: "",
    },
    "lake_clementine": {
        CONF_NAME: "Lake Clementine",
        CONF_LATITUDE: 38.934,
        CONF_LONGITUDE: -121.049,
        CONF_WATER_BODY_TYPE: WATER_BODY_LAKE,
        CONF_USGS_STATION_ID: "11427000",
        CONF_NOAA_STATION_ID: "",
    },
    "sand_harbor_lake_tahoe": {
        CONF_NAME: "Sand Harbor, Lake Tahoe",
        CONF_LATITUDE: 39.198,
        CONF_LONGITUDE: -119.931,
        CONF_WATER_BODY_TYPE: WATER_BODY_LAKE,
        CONF_USGS_STATION_ID: "10337000",
        CONF_NOAA_STATION_ID: "",
    },
    "new_bullards_bar": {
        CONF_NAME: "New Bullards Bar Reservoir",
        CONF_LATITUDE: 39.390,
        CONF_LONGITUDE: -121.140,
        CONF_WATER_BODY_TYPE: WATER_BODY_LAKE,
        CONF_USGS_STATION_ID: "",
        CONF_NOAA_STATION_ID: "",
    },
}
