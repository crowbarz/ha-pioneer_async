"""Config flow for pioneer_async integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import json
from typing import Any
import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import (
    PARAM_IGNORED_ZONES,
    PARAM_ZONE_2_SOURCES,
    PARAM_ZONE_3_SOURCES,
    PARAM_HDZONE_SOURCES,
    PARAM_ZONE_SOURCES,
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
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    LOGIN_SCHEMA,
    CONF_SOURCES,
    CONF_IGNORE_ZONE_2,
    CONF_IGNORE_ZONE_3,
    CONF_IGNORE_HDZONE,
    CONF_QUERY_SOURCES,
    CONF_OLD_IGNORE_ZONE_Z,
    CONF_DEBUG_LEVEL,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
)
from .device import check_device_unique_id, get_device_unique_id
from .debug import Debug

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
        if Debug.level >= 8:
            _LOGGER.debug(">> PioneerAVRFlowHandler.async_step_user(%s)", user_input)
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
        if Debug.level >= 8:
            _LOGGER.debug(">> PioneerOptionsFlowHandler.__init__()")
        self.config_entry = config_entry
        self.pioneer = None
        self.defaults = {}
        self.errors = {}
        self.options = {}
        self.options_parsed = {}
        self.default_source_ids = {}

    def update_zone_source_subsets(self) -> None:
        """Update zone source IDs to be a valid subset of configured sources."""
        ## NOTE: param defaults may include sources excluded from main zone
        defaults = self.defaults
        sources = self.options_parsed.get(CONF_SOURCES) or defaults[CONF_SOURCES]
        source_ids = sources.values()
        for zone, param_sources in PARAM_ZONE_SOURCES.items():
            zone_valid_ids = [
                zone_id for zone_id in defaults[param_sources] if zone_id in source_ids
            ] or source_ids
            self.default_source_ids[zone] = zone_valid_ids
            self.options[param_sources] = [
                zone_id
                for zone_id in self.options[param_sources]
                if zone_id in zone_valid_ids
            ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow for Pioneer AVR."""
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_init(%s)", user_input
            )

        config_entry = self.config_entry
        if config_entry.entry_id not in self.hass.data[DOMAIN]:
            return self.async_abort(reason="not_set_up")

        pioneer: PioneerAVR = self.hass.data[DOMAIN][config_entry.entry_id]
        self.pioneer = pioneer
        default_params = pioneer.get_default_params()

        defaults = {
            **OPTIONS_DEFAULTS,  ## defaults
            **default_params,  ## aiopioneer defaults
        }
        entry_options = config_entry.options
        options = {**defaults, **entry_options}

        ## Initialise ignored zones
        if CONF_OLD_IGNORE_ZONE_Z in options:  ## deprecated
            options[CONF_IGNORE_HDZONE] = options[CONF_OLD_IGNORE_ZONE_Z]

        ## Initialise sources
        sources = entry_options.get(CONF_SOURCES, {})
        query_sources = options[CONF_QUERY_SOURCES]
        if not sources:  ## no sources configured, enable query_sources
            query_sources = True
        elif CONF_QUERY_SOURCES not in entry_options:  ## convert legacy config
            query_sources = False
        try:
            if isinstance(sources, str):  ## convert legacy config
                sources = json.loads(sources)
            if not isinstance(sources, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            _LOGGER.warning(
                '%s: invalid config "%s", resetting to default', CONF_SOURCES, sources
            )
            query_sources = True

        if query_sources:
            sources = pioneer.get_source_dict() or {}
        options[CONF_QUERY_SOURCES] = query_sources
        options[CONF_SOURCES] = list([f"{v} {k}" for k, v in sources.items()])
        defaults[CONF_SOURCES] = sources

        ## Initialise sub-zone source IDs
        for zone, param_sources in PARAM_ZONE_SOURCES.items():
            sources_zone = entry_options.get(param_sources, [])
            try:
                if isinstance(sources_zone, str):
                    sources_zone = json.loads(sources_zone)
                if not isinstance(sources_zone, list):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                _LOGGER.warning(
                    'invalid config for zone %s: "%s", resetting to default',
                    zone,
                    sources_zone,
                )
                sources_zone = []
            options[param_sources] = sources_zone

        ## Convert scan interval timedelta object to seconds
        if isinstance(options[CONF_SCAN_INTERVAL], timedelta):
            options[CONF_SCAN_INTERVAL] = options[CONF_SCAN_INTERVAL].total_seconds()

        self.options = options
        self.defaults = defaults

        self.update_zone_source_subsets()

        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_basic_options(%s)", user_input
            )

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "basic_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self.async_step_zone_options()

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_QUERY_SOURCES, default=defaults[CONF_QUERY_SOURCES]
                ): selector.BooleanSelector(),
                vol.Optional(CONF_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    ),
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=2592000,  # 30 days
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=10.0,
                        step=0.1,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    PARAM_COMMAND_DELAY, default=defaults[PARAM_COMMAND_DELAY]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=1.0,
                        step=0.1,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            last_step=False,
        )

    async def async_step_zone_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle zone options for Pioneer AVR."""
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_zone_options(%s)", user_input
            )

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "zone_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                if self.show_advanced_options:
                    return await self.async_step_advanced_options()
                else:
                    return await self._create_entry()

        zone_labels = dict(
            [
                (v, k)
                for k, v in (
                    self.options_parsed.get(CONF_SOURCES) or defaults[CONF_SOURCES]
                ).items()
            ]
        )

        def zone_options(zone: Zones):
            return list(
                dict([("label", zone_labels.get(v, f"Source {v}")), ("value", v)])
                for v in self.default_source_ids[zone]
            )

        data_schema = vol.Schema(
            {
                vol.Optional(PARAM_ZONE_2_SOURCES, default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.Z2),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_ZONE_3_SOURCES, default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.Z3),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_HDZONE_SOURCES, default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.HDZ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=defaults[PARAM_MAX_SOURCE_ID]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=99,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_IGNORE_ZONE_2, default=defaults[CONF_IGNORE_ZONE_2]
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_IGNORE_ZONE_3, default=defaults[CONF_IGNORE_ZONE_3]
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_IGNORE_HDZONE, default=defaults[CONF_IGNORE_HDZONE]
                ): selector.BooleanSelector(),
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
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_advanced_options(%s)",
                user_input,
            )

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "advanced_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self.async_step_debug_options()

        data_schema = vol.Schema(
            {
                vol.Optional(
                    PARAM_DISABLE_AUTO_QUERY, default=defaults[PARAM_DISABLE_AUTO_QUERY]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_POWER_ON_VOLUME_BOUNCE,
                    default=defaults[PARAM_POWER_ON_VOLUME_BOUNCE],
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_IGNORE_VOLUME_CHECK,
                    default=defaults[PARAM_IGNORE_VOLUME_CHECK],
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_VOLUME_STEP_ONLY, default=defaults[PARAM_VOLUME_STEP_ONLY]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_MAX_VOLUME, default=defaults[PARAM_MAX_VOLUME]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    PARAM_MAX_VOLUME_ZONEX, default=defaults[PARAM_MAX_VOLUME_ZONEX]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
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
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_debug_options(%s)", user_input
            )

        errors = {}
        options = self.options
        defaults = self.defaults
        step_id = "debug_options"

        if user_input is not None:
            errors = await self._update_options(step_id, user_input)
            if not errors:
                return await self._create_entry()

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEBUG_LEVEL, default=defaults[CONF_DEBUG_LEVEL]
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=9,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    PARAM_DEBUG_LISTENER, default=defaults[PARAM_DEBUG_LISTENER]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_RESPONDER, default=defaults[PARAM_DEBUG_RESPONDER]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_UPDATER, default=defaults[PARAM_DEBUG_UPDATER]
                ): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            last_step=True,
        )

    async def _update_options(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> list[str]:
        """Update config entry options."""
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler._update_options(step_id=%s, user_input=%s)",
                step_id,
                dict(user_input),
            )
        errors = {}

        ## Coalesce ignore_zone options into param
        if step_id == "zone_options":
            ignored_zones = []
            if user_input.get(CONF_IGNORE_ZONE_2):
                ignored_zones.append("2")
            if user_input.get(CONF_IGNORE_ZONE_3):
                ignored_zones.append("3")
            if user_input.get(CONF_IGNORE_HDZONE):
                ignored_zones.append("Z")
            if ignored_zones:
                self.options[PARAM_IGNORED_ZONES] = ignored_zones

        def validate_sources(sources_list: list[str]) -> dict[str, Any] | None:
            """Validate sources are in correct format."""
            source_err = False
            sources_tuple = list(
                map(
                    lambda x: (v[1], v[0]) if len(v := x.split(" ", 1)) == 2 else x,
                    sources_list,
                )
            )
            for source_tuple in sources_tuple:
                if not isinstance(source_tuple, tuple):
                    _LOGGER.error("invalid source specification: %s", source_tuple)
                    source_err = True
                else:
                    (_, source_id) = source_tuple
                    if not (
                        len(source_id) == 2
                        and source_id[0].isdigit()
                        and source_id[1].isdigit()
                    ):
                        _LOGGER.error("invalid source ID: %s", source_id)
                        source_err = True
            return dict(sources_tuple) if not source_err else None

        ## Validate sources is a dict of names to numeric IDs
        if step_id == "basic_options":
            query_sources = user_input[CONF_QUERY_SOURCES]
            sources_list = user_input[CONF_SOURCES]
            if query_sources:
                pass
            elif sources_list == []:
                query_sources = True
            elif new_sources := validate_sources(sources_list):
                self.options_parsed[CONF_SOURCES] = new_sources
            else:
                errors[CONF_SOURCES] = "invalid_sources"
            if query_sources:
                _LOGGER.debug("configuring integration to query sources from AVR")
                if CONF_SOURCES in self.options_parsed:
                    del self.options_parsed[CONF_SOURCES]

            self.update_zone_source_subsets()  ## Recalculate valid zones for sub-zones

        self.options.update(user_input)
        return errors

    async def _create_entry(self) -> FlowResult:
        """Create/update config entry using submitted options."""
        if Debug.level >= 8:
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler._create_entry(options=%s, options_parsed=%s)",
                self.options,
                self.options_parsed,
            )

        options = self.options
        options_parsed = self.options_parsed
        defaults = self.defaults
        Debug.level = options[CONF_DEBUG_LEVEL]

        ## Save integration options for non-default values only
        options_conf = {
            k: options[k]
            for k in OPTIONS_ALL
            if k not in [CONF_SOURCES] and k in options and options[k] != defaults[k]
        }

        ## Save params for non-default values only
        params = {
            k: options[k]
            for k in PARAMS_ALL
            if k not in PARAM_ZONE_SOURCES.values()
            and k in options
            and options[k] != defaults[k]
        }

        ## Save zone sources that differ from default
        zone_sources = {
            param_sources: sources_zone
            for zone, param_sources in PARAM_ZONE_SOURCES.items()
            if param_sources in options
            and (sources_zone := options[param_sources]) != []
            and sorted(sources_zone) != sorted(self.default_source_ids[zone])
        }

        data = {**options_conf, **options_parsed, **params, **zone_sources}

        return self.async_create_entry(title="", data=data)
