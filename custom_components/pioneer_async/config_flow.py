"""Config flow for pioneer_async integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import json
from typing import Any
import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.param import (
    PARAM_IGNORED_ZONES,
    PARAM_ZONE_2_SOURCES,
    PARAM_ZONE_3_SOURCES,
    PARAM_HDZONE_SOURCES,
    PARAM_COMMAND_DELAY,
    PARAM_MAX_SOURCE_ID,
    PARAM_MAX_VOLUME,
    PARAM_MAX_VOLUME_ZONEX,
    PARAM_POWER_ON_VOLUME_BOUNCE,
    PARAM_VOLUME_STEP_ONLY,
    PARAM_IGNORE_VOLUME_CHECK,
    PARAM_DISABLE_AUTO_QUERY,
    PARAM_DEBUG_LISTENER,
    PARAM_DEBUG_RESPONDER,
    PARAM_DEBUG_UPDATER,
    PARAMS_ALL,
)

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    LOGIN_SCHEMA,
    CONF_SOURCES,
    CONF_IGNORE_ZONE_2,
    CONF_IGNORE_ZONE_3,
    CONF_IGNORE_ZONE_Z,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
)
from .const import DOMAIN  # pylint: disable=unused-import
from .device import check_device_unique_id, get_device_unique_id

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate host:port is already configured."""


class InvalidSources(HomeAssistantError):
    """Error to indicate invalid sources specified."""


# async def validate_input(hass: core.HomeAssistant, data):
#     """
#     Validate the user input allows us to connect.

#     Data has the keys from LOGIN_SCHEMA with values provided by the user.
#     """
#     _LOGGER.debug(">> validate_input(%s)", data)
#     host = data[CONF_HOST]
#     port = data[CONF_PORT]
#     if check_device_unique_id(hass, host, port) is None:
#         raise AlreadyConfigured
#     try:
#         pioneer = PioneerAVR(host, port)
#         await pioneer.connect()
#     except Exception as exc:  # pylint: disable=broad-except
#         raise CannotConnect from exc  # pylint: disable=raise-missing-from

#     try:
#         await pioneer.query_device_info()
#         await pioneer.shutdown()
#         del pioneer
#     except Exception as exc:  # pylint: disable=broad-except
#         raise Exception(  # pylint: disable=broad-exception-raised
#             f"exception caught: {exc}"
#         ) from exc

#     # Return info that you want to store in the config entry.
#     return data


class PioneerAVRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Pioneer AVR config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PioneerOptionsFlowHandler:
        """Get the options flow for this handler."""
        return PioneerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        _LOGGER.debug(">> config.async_step_user(%s)", user_input)

        errors = {}

        if user_input is not None:
            try:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                if check_device_unique_id(self.hass, host, port) is None:
                    raise AlreadyConfigured

                try:
                    pioneer = PioneerAVR(host, port)
                    await pioneer.connect()
                except Exception as exc:  # pylint: disable=broad-except
                    raise CannotConnect from exc

                await pioneer.query_device_info()
                await pioneer.shutdown()
                del pioneer

                device_unique_id = get_device_unique_id(host, port)
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=device_unique_id, data=user_input)

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")

            except CannotConnect:
                errors["base"] = "cannot_connect"

            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception: %s", str(exc))
                return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="user", data_schema=LOGIN_SCHEMA, errors=errors
        )


class PioneerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Pioneer AVR options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Pioneer AVR options flow."""
        _LOGGER.debug(">> options.__init__()")
        self.config_entry = config_entry
        self.pioneer = None
        self.default_params = {}
        self.errors = {}
        self.options = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow for Pioneer AVR."""
        _LOGGER.debug(">> options.async_step_init(%s)", user_input)
        if self.config_entry.entry_id not in self.hass.data[DOMAIN]:
            return self.async_abort(reason="not_set_up")

        pioneer: PioneerAVR = self.hass.data[DOMAIN][self.config_entry.entry_id]

        self.pioneer = pioneer
        self.default_params = pioneer.get_default_params()

        options = {
            **OPTIONS_DEFAULTS,  # defaults
            **self.default_params,  # aiopioneer default
            **self.config_entry.options,  # config_entry options
        }

        ## JSON unserialise sources parameters
        sources = options[CONF_SOURCES]
        if isinstance(sources, str):
            try:
                options[CONF_SOURCES] = json.loads(sources)
            except json.JSONDecodeError:
                options[CONF_SOURCES] = {}

        sources_z2 = options[PARAM_ZONE_2_SOURCES]
        if isinstance(sources_z2, str):
            try:
                options[PARAM_ZONE_2_SOURCES] = json.loads(sources_z2)
            except json.JSONDecodeError:
                options[PARAM_ZONE_2_SOURCES] = []

        sources_z3 = options[PARAM_ZONE_3_SOURCES]
        if isinstance(sources_z3, str):
            try:
                options[PARAM_ZONE_3_SOURCES] = json.loads(sources_z3)
            except json.JSONDecodeError:
                options[PARAM_ZONE_3_SOURCES] = []

        sources_hdz = options[PARAM_HDZONE_SOURCES]
        if isinstance(sources_hdz, str):
            try:
                options[PARAM_HDZONE_SOURCES] = json.loads(sources_hdz)
            except json.JSONDecodeError:
                options[PARAM_HDZONE_SOURCES] = []

        ## Convert timedelta object to seconds
        if isinstance(options[CONF_SCAN_INTERVAL], timedelta):
            options[CONF_SCAN_INTERVAL] = options[CONF_SCAN_INTERVAL].total_seconds()

        self.options = options

        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        _LOGGER.debug(">> options.async_step_basic_options(%s)", user_input)

        errors = {}
        options = self.options
        step_id = "basic_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                if self.show_advanced_options:
                    return await self.async_step_advanced_options()
                else:
                    return await self._create_entry()
        ## TODO: convert to put current values in suggested_value.
        ## Incorporate from user_input on error.
        ## Set default to integration or aiopioneer default.
        ## This avoids losing all values on error on any field.

        ## Build basic options schema
        sources = options[CONF_SOURCES]
        sources_json = json.dumps(sources) if sources else "default"
        sources_z2 = options[PARAM_ZONE_2_SOURCES]
        sources_z2_json = (
            json.dumps(sources_z2)
            if sources_z2 and sources_z2 != self.default_params[PARAM_ZONE_2_SOURCES]
            else "default"
        )
        sources_z3 = options[PARAM_ZONE_3_SOURCES]
        sources_z3_json = (
            json.dumps(sources_z3)
            if sources_z3 and sources_z3 != self.default_params[PARAM_ZONE_3_SOURCES]
            else "default"
        )
        sources_hdz = options[PARAM_HDZONE_SOURCES]
        sources_hdz_json = (
            json.dumps(sources_hdz)
            if sources_hdz and sources_hdz != self.default_params[PARAM_HDZONE_SOURCES]
            else "default"
        )
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=options[CONF_SCAN_INTERVAL]
                ): int,
                vol.Optional(CONF_TIMEOUT, default=options[CONF_TIMEOUT]): vol.Coerce(
                    float
                ),
                ## sources option specified as a JSON string
                vol.Optional(CONF_SOURCES, default=sources_json): str,
                vol.Optional(PARAM_ZONE_2_SOURCES, default=sources_z2_json): str,
                vol.Optional(PARAM_ZONE_3_SOURCES, default=sources_z3_json): str,
                vol.Optional(PARAM_HDZONE_SOURCES, default=sources_hdz_json): str,
                vol.Optional(
                    PARAM_COMMAND_DELAY, default=options[PARAM_COMMAND_DELAY]
                ): vol.Coerce(float),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=options[PARAM_MAX_SOURCE_ID]
                ): int,
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
            last_step=not self.show_advanced_options,
        )

    async def async_step_advanced_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced options for Pioneer AVR."""
        _LOGGER.debug(">> options.async_step_advanced_options(%s)", user_input)

        errors = {}
        options = self.options
        step_id = "advanced_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self.async_step_debug_options()

        ## Build advanced options schema
        data_schema = vol.Schema(
            {
                vol.Optional(PARAM_MAX_VOLUME, default=options[PARAM_MAX_VOLUME]): int,
                vol.Optional(
                    PARAM_MAX_VOLUME_ZONEX, default=options[PARAM_MAX_VOLUME_ZONEX]
                ): int,
                vol.Optional(
                    PARAM_POWER_ON_VOLUME_BOUNCE,
                    default=options[PARAM_POWER_ON_VOLUME_BOUNCE],
                ): bool,
                vol.Optional(
                    PARAM_VOLUME_STEP_ONLY, default=options[PARAM_VOLUME_STEP_ONLY]
                ): bool,
                vol.Optional(
                    PARAM_IGNORE_VOLUME_CHECK,
                    default=options[PARAM_IGNORE_VOLUME_CHECK],
                ): bool,
                vol.Optional(
                    CONF_IGNORE_ZONE_2, default=options[CONF_IGNORE_ZONE_2]
                ): bool,
                vol.Optional(
                    CONF_IGNORE_ZONE_3, default=options[CONF_IGNORE_ZONE_3]
                ): bool,
                vol.Optional(
                    CONF_IGNORE_ZONE_Z, default=options[CONF_IGNORE_ZONE_Z]
                ): bool,
            }
        )
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors, last_step=False
        )

    async def async_step_debug_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle debug options for Pioneer AVR."""
        _LOGGER.debug(">> options.async_step_debug_options(%s)", user_input)

        errors = {}
        options = self.options
        step_id = "debug_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self._create_entry()

        ## Build debug options schema
        data_schema = vol.Schema(
            {
                vol.Optional(
                    PARAM_DISABLE_AUTO_QUERY, default=options[PARAM_DISABLE_AUTO_QUERY]
                ): bool,
                vol.Optional(
                    PARAM_DEBUG_LISTENER, default=options[PARAM_DEBUG_LISTENER]
                ): bool,
                vol.Optional(
                    PARAM_DEBUG_RESPONDER, default=options[PARAM_DEBUG_RESPONDER]
                ): bool,
                vol.Optional(
                    PARAM_DEBUG_UPDATER, default=options[PARAM_DEBUG_UPDATER]
                ): bool,
            }
        )
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def _update_options(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> list[str]:
        """Update config entry options."""
        # _LOGGER.debug(
        #     ">> options._update_options(step_id=%s, user_input=%s)",
        #     step_id,
        #     dict(user_input),
        # )
        _LOGGER.debug(">> options._update_options(step_id=%s)", step_id)
        errors = {}

        ## Coalesce ignore_zone options into param
        if step_id == "advanced_options":
            ignored_zones = []
            if user_input.get(CONF_IGNORE_ZONE_2):
                ignored_zones.append("2")
            if user_input.get(CONF_IGNORE_ZONE_3):
                ignored_zones.append("3")
            if user_input.get(CONF_IGNORE_ZONE_Z):
                ignored_zones.append("Z")
            if ignored_zones:
                user_input[PARAM_IGNORED_ZONES] = ignored_zones

        def validate_sources(sources_json: str) -> dict[str, Any] | None:
            """Validate sources is in correct format."""
            try:
                sources = json.loads(sources_json)
            except json.JSONDecodeError:
                return None
            except Exception as exc:
                _LOGGER.error("exception serialising JSON sources: %s", exc)
                return None
            if not isinstance(sources, dict):
                _LOGGER.error("JSON sources not of type dict: %s", sources_json)
                return None
            for source_name, source_id in sources.items():
                if not (
                    isinstance(source_name, str)
                    and len(source_id) == 2
                    and source_id[0].isdigit()
                    and source_id[1].isdigit()
                ):
                    _LOGGER.error(
                        "source name/ID invalid: %s -> %s", source_name, source_id
                    )
                    return None
            return sources

        ## Validate sources is a dict of names to numeric IDs
        current_sources = self.options[CONF_SOURCES]
        if CONF_SOURCES in user_input:
            sources_json = user_input[CONF_SOURCES]
            if sources_json == "default":
                current_sources = self.pioneer.get_source_dict()
                user_input[CONF_SOURCES] = {}
            elif sources := validate_sources(sources_json):
                current_sources = sources
                user_input[CONF_SOURCES] = sources
            else:
                errors[CONF_SOURCES] = "invalid_sources"
        elif not current_sources:
            current_sources = self.pioneer.get_source_dict()

        def validate_source_subset(
            zone: str, sources: dict, zone_sources_json: str
        ) -> dict[str, Any] | None:
            """Validate zone sources is a valid subset of sources."""
            source_ids = sources.values()
            try:
                zone_sources = json.loads(zone_sources_json)
            except json.JSONDecodeError:
                return None
            except Exception as exc:
                _LOGGER.error(
                    "exception seralising zone %s JSON sources: %s", zone, exc
                )
                return None
            if not isinstance(zone_sources, list):
                _LOGGER.error(
                    "zone %s JSON sources not of type dict: %s", zone, zone_sources_json
                )
                return None
            for source_id in zone_sources:
                if not (
                    len(source_id) == 2
                    and source_id[0].isdigit()
                    and source_id[1].isdigit()
                    # and source_id in source_ids
                    ## TODO: default source IDs are not actually a subset of zone 1 sources
                ):
                    _LOGGER.error("zone %s source ID invalid: %s", zone, source_id)
                    return None
            return zone_sources

        # _LOGGER.debug("current_sources=%s", current_sources)
        ## Validate zone 2 sources is a list of zone IDs and a subset of sources
        if PARAM_ZONE_2_SOURCES in user_input:
            sources_z2_json = user_input[PARAM_ZONE_2_SOURCES]
            if sources_z2_json == "default":
                user_input[PARAM_ZONE_2_SOURCES] = self.default_params[
                    PARAM_ZONE_2_SOURCES
                ]
            elif sources_z2 := validate_source_subset(
                "2", current_sources, sources_z2_json
            ):
                user_input[PARAM_ZONE_2_SOURCES] = sources_z2
            else:
                errors[PARAM_ZONE_2_SOURCES] = "invalid_sources"

        ## Validate zone 3 sources is a list of zone IDs and a subset of sources
        if PARAM_ZONE_3_SOURCES in user_input:
            sources_z3_json = user_input[PARAM_ZONE_3_SOURCES]
            if sources_z3_json == "default":
                user_input[PARAM_ZONE_3_SOURCES] = self.default_params[
                    PARAM_ZONE_3_SOURCES
                ]
            elif sources_z3 := validate_source_subset(
                "3", current_sources, sources_z3_json
            ):
                user_input[PARAM_ZONE_3_SOURCES] = sources_z3
            else:
                errors[PARAM_ZONE_3_SOURCES] = "invalid_sources"

        ## Validate zone Z sources is a list of zone IDs and a subset of sources
        if PARAM_HDZONE_SOURCES in user_input:
            sources_hdz_json = user_input[PARAM_HDZONE_SOURCES]
            if sources_hdz_json == "default":
                user_input[PARAM_HDZONE_SOURCES] = self.default_params[
                    PARAM_HDZONE_SOURCES
                ]
            elif sources_hdz := validate_source_subset(
                "Z", current_sources, sources_hdz_json
            ):
                user_input[PARAM_HDZONE_SOURCES] = sources_hdz
            else:
                errors[PARAM_HDZONE_SOURCES] = "invalid_sources"

        _LOGGER.debug(">> user_input=%s, errors=%s", user_input, errors)
        if not errors:
            self.options.update(user_input)
        return errors

    async def _create_entry(self) -> FlowResult:
        """Create/update config entry using submitted options."""

        # def parse_opt(k: str) -> Any:
        #     """Parse option."""
        #     if k in [CONF_SOURCES]:
        #         return json.loads(self.options[k])
        #     else:
        #         return self.options[k]

        ## Save integration options and params for non-default values only
        opts = {
            k: self.options[k]
            for k in OPTIONS_ALL
            if k in self.options and self.options[k] != OPTIONS_DEFAULTS[k]
        }

        # def parse_param(k: str) -> Any:
        #     """Parse paramater."""
        #     if k in [PARAM_ZONE_2_SOURCES, PARAM_ZONE_3_SOURCES, PARAM_HDZONE_SOURCES]:
        #         return json.loads(self.options[k])
        #     else:
        #         return self.options[k]

        params = {
            k: self.options[k]
            for k in PARAMS_ALL
            if k in self.options and self.options[k] != self.default_params[k]
        }
        data = {**opts, **params}
        _LOGGER.debug(">> options._create_entry(data=%s)", data)

        return self.async_create_entry(title="", data=data)
