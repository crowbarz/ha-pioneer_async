"""Config flow for pioneer_async integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.core import callback

from aiopioneer import PioneerAVR  # pylint: disable=import-error

from .const import (
    DATA_SCHEMA,
    OPTIONS_DEFAULTS,
    CONF_UNIQUE_ID,
    CONF_COMMAND_DELAY,
    CONF_VOLUME_WORKAROUND,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """
    Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug(">> validate_input(%s)", data)
    try:
        pioneer = PioneerAVR(data[CONF_HOST], data[CONF_PORT])
        await pioneer.connect()
    except:
        raise CannotConnect  # pylint: disable=raise-missing-from

    await pioneer.shutdown()
    del pioneer

    # Return info that you want to store in the config entry.
    device_unique_id = data[CONF_HOST] + ":" + str(data[CONF_PORT])
    return {
        **data,
        CONF_UNIQUE_ID: device_unique_id,
    }


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
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info[CONF_UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info[CONF_UNIQUE_ID], data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PioneerAVROptionsFlowHandler(config_entry)


class PioneerAVROptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Harmony."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        _LOGGER.debug(">> options.__init__(%s)", config_entry)
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        _LOGGER.debug(">> options.async_step_init(%s)", user_input)
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        ## Get current set of options and build options schema
        options = {
            **OPTIONS_DEFAULTS,
            **(self.config_entry.options if self.config_entry.options else {}),
        }
        data_schema = vol.Schema(
            {
                ## TODO: add sources option: how to ask the user for a dictionary in config flow?
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=options[CONF_SCAN_INTERVAL]
                ): int,
                vol.Optional(CONF_TIMEOUT, default=options[CONF_TIMEOUT]): vol.Coerce(
                    float
                ),
                vol.Optional(
                    CONF_COMMAND_DELAY, default=options[CONF_COMMAND_DELAY]
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_VOLUME_WORKAROUND, default=options[CONF_VOLUME_WORKAROUND]
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
