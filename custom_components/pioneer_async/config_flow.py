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
    PARAM_DEFAULTS,
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
from homeassistant.helpers.selector import selector

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
        # """Initialize Pioneer AVR options flow."""
        # _LOGGER.debug(">> options.__init__()")
        self.config_entry = config_entry
        self.pioneer = None
        self.defaults = {}
        self.errors = {}
        self.options = {}
        self.options_parsed = {}
        self.current_sources = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow for Pioneer AVR."""
        _LOGGER.debug(">> options.async_step_init(%s)", user_input)

        config_entry = self.config_entry
        if config_entry.entry_id not in self.hass.data[DOMAIN]:
            return self.async_abort(reason="not_set_up")

        pioneer: PioneerAVR = self.hass.data[DOMAIN][config_entry.entry_id]
        self.pioneer = pioneer
        default_params = pioneer.get_default_params()
        self.current_sources = pioneer.get_source_dict()

        defaults = {
            **OPTIONS_DEFAULTS,  # defaults
            **default_params,  # aiopioneer default
        }
        self.defaults = defaults
        entry_options = config_entry.options
        options = {**defaults, **entry_options}

        ## Serialise sources options and check JSON if string

        ## not in config_entry.options -> do not set
        ## in config_entry.options -> override

        ## user_input == "" -> delete from config_entry.options
        ## user_input == "current" -> copy current sources to config_entry.options

        sources = entry_options.get(CONF_SOURCES)
        if isinstance(sources, str):
            try:
                json.loads(sources)
            except json.JSONDecodeError:
                _LOGGER.warning(
                    "%s: JSON parse error, resetting to default", CONF_SOURCES
                )
                options[CONF_SOURCES] = ""
        elif isinstance(sources, dict):
            options[CONF_SOURCES] = json.dumps(sources)
        else:
            if sources:
                _LOGGER.warning(
                    "%s: invalid config, resetting to default", CONF_SOURCES
                )
            options[CONF_SOURCES] = ""

        ## not in config_entry.options -> using default
        ## in config_entry.options -> override

        ## user_input == "" -> delete from config_entry.options
        ## user_input == "default" -> copy default params to config_entry.options

        sources_z2 = entry_options.get(PARAM_ZONE_2_SOURCES)
        if isinstance(sources_z2, str):
            try:
                json.loads(sources_z2)
            except json.JSONDecodeError:
                _LOGGER.warning(
                    "%s: JSON parse error, resetting to default", PARAM_ZONE_2_SOURCES
                )
                options[PARAM_ZONE_2_SOURCES] = ""
        elif isinstance(sources_z2, list):
            if sources_z2:
                options[PARAM_ZONE_2_SOURCES] = json.dumps(sources_z2)
        else:
            if sources_z2:
                _LOGGER.warning(
                    "%s: invalid config, resetting to default", PARAM_ZONE_2_SOURCES
                )
            options[PARAM_ZONE_2_SOURCES] = ""

        sources_z3 = entry_options.get(PARAM_ZONE_3_SOURCES)
        if isinstance(sources_z3, str):
            try:
                json.loads(sources_z3)
            except json.JSONDecodeError:
                _LOGGER.warning(
                    "%s: JSON parse error, resetting to default", PARAM_ZONE_3_SOURCES
                )
                options[PARAM_ZONE_3_SOURCES] = ""
        elif isinstance(sources_z3, list):
            options[PARAM_ZONE_3_SOURCES] = json.dumps(sources_z3)
        else:
            if sources_z3:
                _LOGGER.warning(
                    "%s: invalid config, resetting to default", PARAM_ZONE_3_SOURCES
                )
            options[PARAM_ZONE_3_SOURCES] = ""

        sources_hdz = entry_options.get(PARAM_HDZONE_SOURCES)
        if isinstance(sources_hdz, str):
            try:
                json.loads(sources_hdz)
            except json.JSONDecodeError:
                _LOGGER.warning(
                    "%s: JSON parse error, resetting to default", PARAM_HDZONE_SOURCES
                )
                options[PARAM_HDZONE_SOURCES] = ""
        elif isinstance(sources_hdz, list):
            options[PARAM_HDZONE_SOURCES] = json.dumps(sources_hdz)
        else:
            if sources_hdz:
                _LOGGER.warning(
                    "%s: invalid config, resetting to default", PARAM_HDZONE_SOURCES
                )
            options[PARAM_HDZONE_SOURCES] = ""

        ## Convert timedelta object to seconds
        if isinstance(options[CONF_SCAN_INTERVAL], timedelta):
            options[CONF_SCAN_INTERVAL] = options[CONF_SCAN_INTERVAL].total_seconds()

        self.options = options

        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        # _LOGGER.debug(">> options.async_step_basic_options(%s)", user_input)

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "basic_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                if self.show_advanced_options:
                    return await self.async_step_advanced_options()
                else:
                    return await self._create_entry()

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_SOURCES, default=""): selector(
                    {"text": {"multiline": False}}
                ),
                vol.Optional(PARAM_ZONE_2_SOURCES, default=""): selector(
                    {"text": {"multiline": False}}
                ),
                vol.Optional(PARAM_ZONE_3_SOURCES, default=""): selector(
                    {"text": {"multiline": False}}
                ),
                vol.Optional(PARAM_HDZONE_SOURCES, default=""): selector(
                    {"text": {"multiline": False}}
                ),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=defaults[PARAM_MAX_SOURCE_ID]
                ): selector(
                    {
                        "number": {
                            "min": 1,
                            "max": 99,
                            "mode": "box",
                        }
                    }
                ),
                vol.Optional(
                    CONF_IGNORE_ZONE_2, default=options[CONF_IGNORE_ZONE_2]
                ): selector({"boolean": {}}),
                vol.Optional(
                    CONF_IGNORE_ZONE_3, default=options[CONF_IGNORE_ZONE_3]
                ): selector({"boolean": {}}),
                vol.Optional(
                    CONF_IGNORE_ZONE_Z, default=options[CONF_IGNORE_ZONE_Z]
                ): selector({"boolean": {}}),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            last_step=not self.show_advanced_options,
        )

    async def async_step_advanced_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced options for Pioneer AVR."""
        # _LOGGER.debug(">> options.async_step_advanced_options(%s)", user_input)

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "advanced_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self.async_step_debug_options()

        ## Build advanced options schema
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): selector(
                    {
                        "number": {
                            "min": 1,
                            "max": 2592000,  # 30 days
                            "unit_of_measurement": "s",
                            "mode": "box",
                        }
                    }
                ),
                vol.Optional(CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]): selector(
                    {
                        "number": {
                            "min": 1.0,
                            "max": 10.0,
                            "step": 0.1,
                            "unit_of_measurement": "s",
                            "mode": "slider",
                        }
                    }
                ),
                vol.Optional(
                    PARAM_COMMAND_DELAY, default=defaults[PARAM_COMMAND_DELAY]
                ): selector(
                    {
                        "number": {
                            "min": 0.0,
                            "max": 1.0,
                            "step": 0.1,
                            "unit_of_measurement": "s",
                            "mode": "slider",
                        }
                    }
                ),
                vol.Optional(
                    PARAM_MAX_VOLUME, default=defaults[PARAM_MAX_VOLUME]
                ): selector(
                    {
                        "number": {
                            "min": 0,
                            "max": PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                            "mode": "box",
                        }
                    }
                ),
                vol.Optional(
                    PARAM_MAX_VOLUME_ZONEX, default=defaults[PARAM_MAX_VOLUME_ZONEX]
                ): selector(
                    {
                        "number": {
                            "min": 0,
                            "max": PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                            "mode": "box",
                        }
                    }
                ),
                vol.Optional(
                    PARAM_POWER_ON_VOLUME_BOUNCE,
                    default=defaults[PARAM_POWER_ON_VOLUME_BOUNCE],
                ): selector({"boolean": {}}),
                vol.Optional(
                    PARAM_IGNORE_VOLUME_CHECK,
                    default=defaults[PARAM_IGNORE_VOLUME_CHECK],
                ): selector({"boolean": {}}),
                vol.Optional(
                    PARAM_VOLUME_STEP_ONLY, default=defaults[PARAM_VOLUME_STEP_ONLY]
                ): selector({"boolean": {}}),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            last_step=False,
        )

    async def async_step_debug_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle debug options for Pioneer AVR."""
        # _LOGGER.debug(">> options.async_step_debug_options(%s)", user_input)

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "debug_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self._create_entry()

        ## Build debug options schema
        data_schema = vol.Schema(
            {
                vol.Optional(
                    PARAM_DISABLE_AUTO_QUERY, default=defaults[PARAM_DISABLE_AUTO_QUERY]
                ): selector({"boolean": {}}),
                vol.Optional(
                    PARAM_DEBUG_LISTENER, default=defaults[PARAM_DEBUG_LISTENER]
                ): selector({"boolean": {}}),
                vol.Optional(
                    PARAM_DEBUG_RESPONDER, default=defaults[PARAM_DEBUG_RESPONDER]
                ): selector({"boolean": {}}),
                vol.Optional(
                    PARAM_DEBUG_UPDATER, default=defaults[PARAM_DEBUG_UPDATER]
                ): selector({"boolean": {}}),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
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
        errors = {}
        defaults = self.defaults

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
            except Exception as exc:  # pylint: disable=broad-except
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
        if CONF_SOURCES in user_input:
            sources_json = user_input[CONF_SOURCES]
            if sources_json == "current":
                self.options_parsed[CONF_SOURCES] = self.pioneer.get_source_dict()
            elif sources_json == "":
                if CONF_SOURCES in self.options_parsed:
                    del self.options_parsed[CONF_SOURCES]
            elif new_sources := validate_sources(sources_json):
                self.options_parsed[CONF_SOURCES] = new_sources
            else:
                errors[CONF_SOURCES] = "invalid_sources"
        sources = self.options_parsed.get(CONF_SOURCES, {})

        def validate_source_subset(
            zone: str, sources: dict, zone_sources_json: str
        ) -> dict[str, Any] | None:
            """Validate zone sources is a valid subset of sources."""
            source_ids = sources.values()
            try:
                zone_sources = json.loads(zone_sources_json)
            except json.JSONDecodeError:
                return None
            except Exception as exc:  # pylint: disable=broad-except
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

        ## Validate zone 2 sources is a list of zone IDs and a subset of sources
        if PARAM_ZONE_2_SOURCES in user_input:
            sources_z2_json = user_input[PARAM_ZONE_2_SOURCES]
            if sources_z2_json == "default":
                self.options_parsed[PARAM_ZONE_2_SOURCES] = self.defaults[
                    PARAM_ZONE_2_SOURCES
                ]
            elif sources_z2_json == "":
                if PARAM_ZONE_2_SOURCES in self.options_parsed:
                    del self.options_parsed[PARAM_ZONE_2_SOURCES]
            elif sources_z2 := validate_source_subset("2", sources, sources_z2_json):
                self.options_parsed[PARAM_ZONE_2_SOURCES] = sources_z2
            else:
                errors[PARAM_ZONE_2_SOURCES] = "invalid_sources"

        ## Validate zone 3 sources is a list of zone IDs and a subset of sources
        if PARAM_ZONE_3_SOURCES in user_input:
            sources_z3_json = user_input[PARAM_ZONE_3_SOURCES]
            if sources_z3_json == "default":
                self.options_parsed[PARAM_ZONE_3_SOURCES] = self.defaults[
                    PARAM_ZONE_3_SOURCES
                ]
            elif sources_z3_json == "":
                if PARAM_ZONE_3_SOURCES in self.options_parsed:
                    del self.options_parsed[PARAM_ZONE_3_SOURCES]
            elif sources_z3 := validate_source_subset("3", sources, sources_z3_json):
                self.options_parsed[PARAM_ZONE_3_SOURCES] = sources_z3
            else:
                errors[PARAM_ZONE_3_SOURCES] = "invalid_sources"

        ## Validate zone Z sources is a list of zone IDs and a subset of sources
        if PARAM_HDZONE_SOURCES in user_input:
            sources_hdz_json = user_input[PARAM_HDZONE_SOURCES]
            if sources_hdz_json == "default":
                user_input[PARAM_HDZONE_SOURCES] = self.defaults[PARAM_HDZONE_SOURCES]
            elif sources_hdz_json == "":
                if PARAM_HDZONE_SOURCES in self.options_parsed:
                    del self.options_parsed[PARAM_HDZONE_SOURCES]
            elif sources_hdz := validate_source_subset("Z", sources, sources_hdz_json):
                self.options_parsed[PARAM_HDZONE_SOURCES] = sources_hdz
            else:
                errors[PARAM_HDZONE_SOURCES] = "invalid_sources"

        # _LOGGER.debug(
        #     ">> user_input=%s, options_parsed=%s, errors=%s",
        #     user_input,
        #     self.options_parsed,
        #     errors,
        # )
        self.options.update(user_input)
        return errors

    async def _create_entry(self) -> FlowResult:
        """Create/update config entry using submitted options."""

        ## Save integration options and params for non-default values only
        opts = {
            k: self.options[k]
            for k in OPTIONS_ALL
            if k not in [CONF_SOURCES]
            and k in self.options
            and self.options[k] != self.defaults[k]
        }
        opts_parsed = {
            k: self.options_parsed[k]
            for k in [CONF_SOURCES]
            if k in self.options_parsed
        }

        params = {
            k: self.options[k]
            for k in PARAMS_ALL
            if k
            not in [PARAM_ZONE_2_SOURCES, PARAM_ZONE_3_SOURCES, PARAM_HDZONE_SOURCES]
            and k in self.options
            and self.options[k] != self.defaults[k]
        }
        params_parsed = {
            k: self.options_parsed[k]
            for k in [PARAM_ZONE_2_SOURCES, PARAM_ZONE_3_SOURCES, PARAM_HDZONE_SOURCES]
            if k in self.options_parsed
        }

        data = {**opts, **opts_parsed, **params, **params_parsed}
        _LOGGER.debug(">> options._create_entry(data=%s)", data)

        return self.async_create_entry(title="", data=data)
