"""Config flow for Paddle Conditions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import homeassistant.helpers.config_validation as cv
import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.base import APIError
from .api.open_meteo import OpenMeteoWeatherClient
from .const import (
    ACTIVITY_KAYAKING,
    ACTIVITY_SUP,
    CONF_ACTIVITY,
    CONF_DISPLAY_ORDER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_NOAA_STATION_ID,
    CONF_OPTIMAL_CFS,
    CONF_PROFILE,
    CONF_USGS_API_KEY,
    CONF_USGS_STATION_ID,
    CONF_WATER_BODY_TYPE,
    DEFAULT_ACTIVITY,
    DEFAULT_PROFILES,
    DOMAIN,
    LOGGER,
    PROFILE_FAMILY,
    PROFILE_FLATWATER,
    PROFILE_OCEAN,
    PROFILE_RACING,
    PROFILE_RECREATIONAL,
    PROFILE_RIVER,
    WATER_BODY_BAY_OCEAN,
    WATER_BODY_LAKE,
    WATER_BODY_RIVER,
)
from .presets import PRESET_CUSTOM, PRESET_LOCATIONS
from .profiles import get_profile


class PaddleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for Paddle Conditions."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Paddle Conditions", data={})

        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {"location": LocationSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return PaddleOptionsFlow()


class LocationSubentryFlow(ConfigSubentryFlow):
    """Handle adding and editing paddle locations."""

    _preset_defaults: dict[str, str | float] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Handle preset selection."""
        if user_input is not None:
            preset_key = user_input.get("preset", PRESET_CUSTOM)
            if preset_key != PRESET_CUSTOM and preset_key in PRESET_LOCATIONS:
                self._preset_defaults = dict(PRESET_LOCATIONS[preset_key])
            else:
                self._preset_defaults = None
            return await self.async_step_location()

        preset_options = [
            SelectOptionDict(value=key, label=str(data[CONF_NAME])) for key, data in PRESET_LOCATIONS.items()
        ]
        preset_options.append(SelectOptionDict(value=PRESET_CUSTOM, label="Custom location"))

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required("preset", default=next(iter(PRESET_LOCATIONS))): SelectSelector(
                        SelectSelectorConfig(
                            options=preset_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    def _location_schema(self, defaults: Mapping[str, Any]) -> probatio.Schema:
        """Build the location form schema with given defaults."""
        return probatio.Schema(
            {
                probatio.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
                probatio.Required(CONF_LATITUDE, default=defaults.get(CONF_LATITUDE)): cv.latitude,
                probatio.Required(CONF_LONGITUDE, default=defaults.get(CONF_LONGITUDE)): cv.longitude,
                probatio.Required(
                    CONF_WATER_BODY_TYPE,
                    default=defaults.get(CONF_WATER_BODY_TYPE, WATER_BODY_LAKE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[WATER_BODY_LAKE, WATER_BODY_RIVER, WATER_BODY_BAY_OCEAN],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_WATER_BODY_TYPE,
                    )
                ),
                probatio.Optional(CONF_DISPLAY_ORDER, default=int(defaults.get(CONF_DISPLAY_ORDER, 0))): int,
                probatio.Optional(
                    CONF_USGS_STATION_ID,
                    default=str(defaults.get(CONF_USGS_STATION_ID, "")),
                ): str,
                probatio.Optional(
                    CONF_NOAA_STATION_ID,
                    default=str(defaults.get(CONF_NOAA_STATION_ID, "")),
                ): str,
                probatio.Optional(
                    CONF_OPTIMAL_CFS,
                    **({"default": defaults[CONF_OPTIMAL_CFS]} if defaults.get(CONF_OPTIMAL_CFS) is not None else {}),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=50000,
                        step=50,
                        unit_of_measurement="CFS",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    async def _async_validate_location(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Fill optional fields and check the weather API answers for these coordinates."""
        user_input.setdefault(CONF_USGS_STATION_ID, "")
        user_input.setdefault(CONF_NOAA_STATION_ID, "")
        user_input.setdefault(CONF_DISPLAY_ORDER, 0)
        user_input.setdefault(CONF_OPTIMAL_CFS, None)

        client = OpenMeteoWeatherClient(async_get_clientsession(self.hass))
        try:
            await client.fetch(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
        except APIError:
            return {"base": "cannot_connect"}
        except Exception:
            LOGGER.exception("Unexpected error validating location")
            return {"base": "unknown"}
        return {}

    async def async_step_location(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Handle location details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_location(user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        defaults = self._preset_defaults or {}
        return self.async_show_form(
            step_id="location",
            data_schema=self._location_schema(defaults),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Handle editing an existing location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_location(user_input)
            if not errors:
                # The entry's update listener reloads it; a reloading helper here
                # would reload twice (and HA rejects the combination).
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        current = self._get_reconfigure_subentry().data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._location_schema(current),
            errors=errors,
        )


class PaddleOptionsFlow(OptionsFlow):
    """Handle options for Paddle Conditions."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow init."""
        if user_input is not None:
            current = self.config_entry.options

            # Extract and normalize weight sliders to sum to 1.0
            weight_keys = [k for k in user_input if k.startswith("weight_")]
            if weight_keys:
                activity = user_input.get("activity", DEFAULT_ACTIVITY)
                profile_name = user_input.get("profile", DEFAULT_PROFILES[activity])
                profile_weights = get_profile(activity, profile_name).weights
                total = sum(user_input[k] for k in weight_keys)
                if total > 0:
                    sliders = {k.removeprefix("weight_"): user_input.pop(k) / total for k in weight_keys}
                    # Streamflow and tide have no slider; keep their current weights,
                    # falling back to the profile's for any that are missing.
                    stored = {**profile_weights, **current.get("weights", {})}
                    hidden = {k: v for k, v in stored.items() if k not in sliders}
                    user_input["weights"] = {**hidden, **sliders}
                else:
                    for k in weight_keys:
                        user_input.pop(k)
                    user_input["weights"] = profile_weights

            # If activity changed, reset profile to activity's default
            new_activity = user_input.get("activity")
            current_activity = current.get("activity", DEFAULT_ACTIVITY)
            if new_activity and new_activity != current_activity:
                default_profile = DEFAULT_PROFILES.get(new_activity, PROFILE_RECREATIONAL)
                user_input["profile"] = default_profile
                profile = get_profile(new_activity, default_profile)
                user_input["weights"] = profile.weights
            else:
                new_profile = user_input.get("profile")
                activity = user_input.get("activity", current.get("activity", DEFAULT_ACTIVITY))
                current_profile = current.get("profile", DEFAULT_PROFILES.get(activity, PROFILE_RECREATIONAL))
                if new_profile and new_profile != current_profile:
                    profile = get_profile(activity, new_profile)
                    user_input["weights"] = profile.weights

            if not user_input.get(CONF_USGS_API_KEY):
                user_input.pop(CONF_USGS_API_KEY, None)
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        current_activity = current.get("activity", DEFAULT_ACTIVITY)
        default_profile = DEFAULT_PROFILES.get(current_activity, PROFILE_RECREATIONAL)
        profile = get_profile(current_activity, current.get("profile", default_profile))
        weights = current.get("weights", profile.weights)

        if current_activity == ACTIVITY_KAYAKING:
            profile_options = [PROFILE_FLATWATER, PROFILE_RIVER, PROFILE_OCEAN]
        else:
            profile_options = [PROFILE_RECREATIONAL, PROFILE_RACING, PROFILE_FAMILY]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        "activity",
                        default=current_activity,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[ACTIVITY_SUP, ACTIVITY_KAYAKING],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_ACTIVITY,
                        )
                    ),
                    probatio.Optional(
                        "profile",
                        default=current.get("profile", default_profile),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=profile_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_PROFILE,
                        )
                    ),
                    probatio.Optional(
                        "update_interval",
                        default=current.get("update_interval", 10),
                    ): NumberSelector(NumberSelectorConfig(min=5, max=60, step=5, mode=NumberSelectorMode.SLIDER)),
                    probatio.Optional(
                        "weight_wind_speed",
                        default=int(weights.get("wind_speed", 0.30) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_wind_gusts",
                        default=int(weights.get("wind_gusts", 0.10) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_air_quality",
                        default=int(weights.get("air_quality", 0.20) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_temperature",
                        default=int(weights.get("temperature", 0.15) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_uv_index",
                        default=int(weights.get("uv_index", 0.10) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_visibility",
                        default=int(weights.get("visibility", 0.10) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        "weight_precipitation",
                        default=int(weights.get("precipitation", 0.05) * 100),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=5,
                            unit_of_measurement="%",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Optional(
                        CONF_USGS_API_KEY,
                        description={"suggested_value": current.get(CONF_USGS_API_KEY)},
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
        )
