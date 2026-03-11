"""Constants for the Paddle Conditions integration."""

from __future__ import annotations

import logging

DOMAIN = "paddle_conditions"
LOGGER = logging.getLogger(__name__)

SUBENTRY_TYPE_LOCATION = "location"

# Config keys
CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_WATER_BODY_TYPE = "water_body_type"
CONF_DISPLAY_ORDER = "display_order"
CONF_USGS_STATION_ID = "usgs_station_id"
CONF_NOAA_STATION_ID = "noaa_station_id"

# Water body types
WATER_BODY_LAKE = "lake"
WATER_BODY_RIVER = "river"
WATER_BODY_BAY_OCEAN = "bay_ocean"

# Location subentry optional fields
CONF_OPTIMAL_CFS = "optimal_cfs"

# Scoring defaults
DEFAULT_UPDATE_INTERVAL_MINUTES = 10
MIN_UPDATE_INTERVAL_MINUTES = 5
API_TIMEOUT_SECONDS = 10

# Score thresholds
SCORE_GO = 70
SCORE_CAUTION = 40

# Activities
ACTIVITY_SUP = "sup"
ACTIVITY_KAYAKING = "kayaking"
CONF_ACTIVITY = "activity"
DEFAULT_ACTIVITY = ACTIVITY_SUP

# SUP profiles
PROFILE_RECREATIONAL = "recreational"
PROFILE_RACING = "racing"
PROFILE_FAMILY = "family"

# Kayaking profiles
PROFILE_FLATWATER = "flatwater"
PROFILE_RIVER = "river"
PROFILE_OCEAN = "ocean"

CONF_PROFILE = "profile"

# Default profiles per activity
DEFAULT_PROFILES = {
    ACTIVITY_SUP: PROFILE_RECREATIONAL,
    ACTIVITY_KAYAKING: PROFILE_FLATWATER,
}

# Cloud sync
CONF_CLOUD_SYNC_ENABLED = "cloud_sync_enabled"
CONF_CLOUD_SYNC_URL = "cloud_sync_url"
CONF_CLOUD_SYNC_TOKEN = "cloud_sync_token"
CONF_CLOUD_SYNC_INTERVAL = "cloud_sync_interval"
DEFAULT_CLOUD_SYNC_INTERVAL_MINUTES = 5
