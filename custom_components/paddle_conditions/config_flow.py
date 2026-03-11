"""Config flow for Paddle Conditions."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    ACTIVITY_KAYAKING,
    ACTIVITY_SUP,
    CONF_CLOUD_SYNC_TOKEN,
    CONF_CLOUD_SYNC_URL,
    CONF_DISPLAY_ORDER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_NOAA_STATION_ID,
    CONF_OPTIMAL_CFS,
    CONF_USGS_STATION_ID,
    CONF_WATER_BODY_TYPE,
    DEFAULT_ACTIVITY,
    DEFAULT_PROFILES,
    DOMAIN,
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


class PaddleConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg, misc]
    """Handle the initial config flow for Paddle Conditions."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Paddle Conditions", data={})

        return self.async_show_form(step_id="user")

    @classmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {"location": LocationSubentryFlow}

    @staticmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return PaddleOptionsFlow()


class LocationSubentryFlow(ConfigSubentryFlow):  # type: ignore[misc]
    """Handle adding a paddle location."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Handle location subentry creation."""
        if user_input is not None:
            user_input.setdefault(CONF_USGS_STATION_ID, "")
            user_input.setdefault(CONF_NOAA_STATION_ID, "")
            user_input.setdefault(CONF_DISPLAY_ORDER, 0)
            user_input.setdefault(CONF_OPTIMAL_CFS, None)
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_LATITUDE): cv.latitude,
                    vol.Required(CONF_LONGITUDE): cv.longitude,
                    vol.Required(CONF_WATER_BODY_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": WATER_BODY_LAKE, "label": "Lake / Reservoir"},
                                {"value": WATER_BODY_RIVER, "label": "River"},
                                {"value": WATER_BODY_BAY_OCEAN, "label": "Bay / Ocean"},
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_DISPLAY_ORDER, default=0): int,
                    vol.Optional(CONF_USGS_STATION_ID, default=""): str,
                    vol.Optional(CONF_NOAA_STATION_ID, default=""): str,
                    vol.Optional(CONF_OPTIMAL_CFS): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50000,
                            step=50,
                            unit_of_measurement="CFS",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )


class PaddleOptionsFlow(OptionsFlow):  # type: ignore[misc]
    """Handle options for Paddle Conditions."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow init."""
        if user_input is not None:
            current = self.config_entry.options

            # Extract and normalize weight sliders to sum to 1.0
            weight_keys = [k for k in user_input if k.startswith("weight_")]
            if weight_keys:
                total = sum(user_input[k] for k in weight_keys)
                if total > 0:
                    user_input["weights"] = {k.removeprefix("weight_"): user_input.pop(k) / total for k in weight_keys}
                else:
                    for k in weight_keys:
                        user_input.pop(k)
                    from .profiles import get_profile

                    activity = user_input.get("activity", DEFAULT_ACTIVITY)
                    profile_name = user_input.get("profile", DEFAULT_PROFILES[activity])
                    user_input["weights"] = get_profile(activity, profile_name).weights

            # If activity changed, reset profile to activity's default
            new_activity = user_input.get("activity")
            current_activity = current.get("activity", DEFAULT_ACTIVITY)
            if new_activity and new_activity != current_activity:
                from .profiles import get_profile

                default_profile = DEFAULT_PROFILES[new_activity]
                user_input["profile"] = default_profile
                profile = get_profile(new_activity, default_profile)
                user_input["weights"] = profile.weights
            else:
                new_profile = user_input.get("profile")
                activity = user_input.get("activity", current.get("activity", DEFAULT_ACTIVITY))
                current_profile = current.get("profile", DEFAULT_PROFILES.get(activity, PROFILE_RECREATIONAL))
                if new_profile and new_profile != current_profile:
                    from .profiles import get_profile

                    profile = get_profile(activity, new_profile)
                    user_input["weights"] = profile.weights

            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        current_activity = current.get("activity", DEFAULT_ACTIVITY)
        default_profile = DEFAULT_PROFILES.get(current_activity, PROFILE_RECREATIONAL)
        from .profiles import get_profile

        profile = get_profile(current_activity, current.get("profile", default_profile))
        weights = current.get("weights", profile.weights)

        if current_activity == ACTIVITY_KAYAKING:
            profile_options = [
                {"value": PROFILE_FLATWATER, "label": "Flatwater"},
                {"value": PROFILE_RIVER, "label": "River"},
                {"value": PROFILE_OCEAN, "label": "Ocean"},
            ]
        else:
            profile_options = [
                {"value": PROFILE_RECREATIONAL, "label": "Recreational"},
                {"value": PROFILE_RACING, "label": "Racing"},
                {"value": PROFILE_FAMILY, "label": "Family"},
            ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "activity",
                        default=current_activity,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": ACTIVITY_SUP, "label": "Paddle Boarding"},
                                {
                                    "value": ACTIVITY_KAYAKING,
                                    "label": "Kayaking",
                                },
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "profile",
                        default=current.get("profile", default_profile),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=profile_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "update_interval",
                        default=current.get("update_interval", 10),
                    ): NumberSelector(NumberSelectorConfig(min=5, max=60, step=5, mode=NumberSelectorMode.SLIDER)),
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
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
                    vol.Optional(
                        CONF_CLOUD_SYNC_URL,
                        default=current.get(CONF_CLOUD_SYNC_URL, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                    vol.Optional(
                        CONF_CLOUD_SYNC_TOKEN,
                        default=current.get(CONF_CLOUD_SYNC_TOKEN, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                }
            ),
        )
