"""Config flow for pioneer_async integration."""

from datetime import timedelta
import logging
import json
import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.param import (
    PARAM_IGNORED_ZONES,
    PARAM_COMMAND_DELAY,
    PARAM_MAX_SOURCE_ID,
    PARAM_MAX_VOLUME,
    PARAM_MAX_VOLUME_ZONEX,
    PARAM_POWER_ON_VOLUME_BOUNCE,
    PARAM_VOLUME_STEP_ONLY,
    PARAM_VOLUME_STEP_DELTA,
    PARAM_IGNORE_VOLUME_CHECK,
    PARAM_DEBUG_LISTENER,
    PARAM_DEBUG_RESPONDER,
    PARAM_DEBUG_UPDATER,
    PARAMS_ALL,
)

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.core import callback

from .const import (
    DATA_SCHEMA,
    CONF_SOURCES,
    CONF_IGNORE_ZONE_2,
    CONF_IGNORE_ZONE_3,
    CONF_IGNORE_ZONE_Z,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
)
from .const import DOMAIN  # pylint: disable=unused-import
from .media_player import check_device_unique_id, get_device_unique_id

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """
    Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug(">> validate_input(%s)", data)
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    if check_device_unique_id(hass, host, port) is None:
        raise AlreadyConfigured
    try:
        pioneer = PioneerAVR(host, port)
        await pioneer.connect()
        await pioneer.query_device_info()
        await pioneer.shutdown()
        del pioneer
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.debug("exception caught: %s", str(exc))
        raise CannotConnect  # pylint: disable=raise-missing-from

    # Return info that you want to store in the config entry.
    return data


class PioneerAVRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Pioneer AVR config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        _LOGGER.debug(">> config.async_step_user(%s)", user_input)
        errors = {}
        if user_input is not None:
            try:
                data = await validate_input(self.hass, user_input)
                device_unique_id = get_device_unique_id(
                    data[CONF_HOST], data[CONF_PORT]
                )
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=device_unique_id, data=data)
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected exception: %s", str(exc))
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Harmony."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        _LOGGER.debug(">> options.__init__()")
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        _LOGGER.debug(">> options.async_step_init(%s)", user_input)

        entry = self.config_entry
        pioneer = self.hass.data[DOMAIN][entry.entry_id]
        default_params = pioneer.get_default_params()
        errors = {}

        if user_input is not None:
            ## Save options and params for non-default values only
            options = {
                k: user_input[k]
                for k in OPTIONS_ALL
                if k in user_input and user_input[k] != OPTIONS_DEFAULTS[k]
            }
            params = {
                k: user_input[k]
                for k in PARAMS_ALL
                if k in user_input and user_input[k] != default_params[k]
            }

            ## Coalesce ignore_zone options into param
            ignored_zones = []
            if options.get(CONF_IGNORE_ZONE_2):
                ignored_zones.append("2")
            if options.get(CONF_IGNORE_ZONE_3):
                ignored_zones.append("3")
            if options.get(CONF_IGNORE_ZONE_Z):
                ignored_zones.append("Z")
            if ignored_zones:
                params[PARAM_IGNORED_ZONES] = ignored_zones

            _LOGGER.debug("options=%s, params=%s", options, params)

            try:
                ## Validate sources is a dict of names to numeric IDs
                if CONF_SOURCES in options:
                    sources = json.loads(options[CONF_SOURCES])
                    if not isinstance(sources, dict):
                        raise Exception
                    for (source_name, source_id) in sources.items():
                        if not (
                            isinstance(source_name, str)
                            and len(source_id) == 2
                            and source_id[0].isdigit()
                            and source_id[1].isdigit()
                        ):
                            raise Exception

            except:  # pylint: disable=bare-except
                errors[CONF_SOURCES] = "invalid_sources"

            if not errors:
                return self.async_create_entry(title="", data={**options, **params})

        ## Get current set of options
        entry_options = entry.options if entry.options else {}
        options = {
            **OPTIONS_DEFAULTS,
            **default_params,
            **entry_options,
        }
        if isinstance(options[CONF_SCAN_INTERVAL], timedelta):
            options[CONF_SCAN_INTERVAL] = options[CONF_SCAN_INTERVAL].total_seconds()

        ## Build options schema
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=options[CONF_SCAN_INTERVAL]
                ): int,
                vol.Optional(CONF_TIMEOUT, default=options[CONF_TIMEOUT]): vol.Coerce(
                    float
                ),
                ## sources option specified as a JSON string
                vol.Optional(CONF_SOURCES, default=options[CONF_SOURCES]): str,
                vol.Optional(
                    PARAM_COMMAND_DELAY, default=options[PARAM_COMMAND_DELAY]
                ): vol.Coerce(float),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=options[PARAM_MAX_SOURCE_ID]
                ): int,
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
                    PARAM_VOLUME_STEP_DELTA, default=options[PARAM_VOLUME_STEP_DELTA]
                ): int,
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
            step_id="init", data_schema=data_schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host:port is already configured."""
