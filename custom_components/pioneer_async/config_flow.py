"""Config flow for pioneer_async integration."""
from __future__ import annotations

import json
import logging
from typing import Any, Tuple

import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import (
    PARAM_IGNORED_ZONES,
    PARAM_ZONE_1_SOURCES,
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
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SOURCES,
    CONF_PARAMS,
    CONF_IGNORE_ZONE_2,
    CONF_IGNORE_ZONE_3,
    CONF_IGNORE_HDZONE,
    CONF_QUERY_SOURCES,
    CONF_DEBUG_CONFIG,
    DEFAULT_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
    DEFAULTS_EXCLUDE,
)
from .debug import Debug
from .device import check_device_unique_id, get_device_unique_id

_LOGGER = logging.getLogger(__name__)


def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate host:port is already configured."""


class InvalidSources(HomeAssistantError):
    """Error to indicate invalid sources specified."""


class PioneerAVRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Pioneer AVR config flow."""

    VERSION = 2
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
        if _debug_atlevel(8):
            _LOGGER.debug(">> PioneerAVRFlowHandler.async_step_user(%s)", user_input)
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = int(user_input[CONF_PORT])
            try:
                if check_device_unique_id(self.hass, host, port) is None:
                    raise AlreadyConfigured

                try:
                    pioneer = PioneerAVR(host, port)
                    await pioneer.connect()
                except Exception as exc:  # pylint: disable=broad-except
                    raise CannotConnect(str(exc)) from exc

                await pioneer.query_device_info()
                await pioneer.shutdown()
                del pioneer
                ## TODO: pass through PioneerAVR to async_setup_entry

                device_unique_id = get_device_unique_id(host, port)
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_unique_id,
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                    # options={CONF_QUERY_SOURCES: user_input[CONF_QUERY_SOURCES]},
                )

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")

            except CannotConnect as exc:
                errors["base"] = "cannot_connect"
                description_placeholders["exception"] = str(exc)

            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("unexpected exception: %s", str(exc))
                return self.async_abort(
                    reason="exception", description_placeholders={"exception", str(exc)}
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                ## TODO: have to define sources if not querying from AVR
                # vol.Optional(
                #     CONF_QUERY_SOURCES, default=True
                # ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class PioneerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Pioneer AVR options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # """Initialize Pioneer AVR options flow."""
        if _debug_atlevel(8):
            _LOGGER.debug(">> PioneerOptionsFlowHandler.__init__()")
        self.config_entry = config_entry
        self.pioneer = None
        self.defaults = {}
        self.options = {}
        self.options_parsed = {}
        self.default_source_ids = {}
        # self.requery_task = None

    def update_zone_source_subsets(self) -> None:
        """Update zone source IDs to be a valid subset of configured/available sources."""
        ## NOTE: param defaults may include sources excluded from main zone
        if _debug_atlevel(8):
            _LOGGER.debug(">> PioneerOptionsFlowHandler.update_zone_source_subsets()")
        defaults = self.defaults
        sources = self.options_parsed[CONF_SOURCES]
        source_ids = sources.values()
        for zone, param_sources in PARAM_ZONE_SOURCES.items():
            zone_valid_ids = [
                zone_id for zone_id in defaults[param_sources] if zone_id in source_ids
            ] or source_ids
            self.default_source_ids[zone] = zone_valid_ids
            self.options[param_sources] = [
                zone_id
                for zone_id in self.options.get(param_sources, [])
                if zone_id in zone_valid_ids
            ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow for Pioneer AVR."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_init(%s)", user_input
            )

        config_entry = self.config_entry
        if config_entry.entry_id not in self.hass.data[DOMAIN]:
            return self.async_abort(reason="not_set_up")

        pioneer: PioneerAVR = self.hass.data[DOMAIN][config_entry.entry_id]
        self.pioneer = pioneer
        default_params = pioneer.get_default_params()
        # self.requery_task = None

        defaults = {
            **OPTIONS_DEFAULTS,  ## defaults
            **default_params,  ## aiopioneer defaults
        }
        entry_options = config_entry.options
        defaults_inherit = {
            k: v for k, v in defaults.items() if k not in DEFAULTS_EXCLUDE
        }
        options = {**defaults_inherit, **entry_options}

        ## Convert CONF_SOURCES for options flow
        sources = options[CONF_SOURCES]
        query_sources = True if not sources else options[CONF_QUERY_SOURCES]
        if query_sources:
            sources = pioneer.get_source_dict() or {}
        options[CONF_QUERY_SOURCES] = query_sources
        options[CONF_SOURCES] = list([f"{v}:{k}" for k, v in sources.items()])
        self.options_parsed[CONF_SOURCES] = sources

        ## Convert CONF_PARAMS for options flow
        params_config = options[CONF_PARAMS]
        self.options_parsed[CONF_PARAMS] = params_config
        options[CONF_PARAMS] = list(
            [f"{k}: {json.dumps(v)}" for k, v in params_config.items()]
        )

        ## Convert CONF_DEBUG_CONFIG for options flow
        debug_config = options[CONF_DEBUG_CONFIG]
        self.options_parsed[CONF_DEBUG_CONFIG] = debug_config
        options[CONF_DEBUG_CONFIG] = list(
            [f"{k}: {json.dumps(v)}" for k, v in debug_config.items()]
        )

        self.options = options
        self.defaults = defaults
        self.update_zone_source_subsets()

        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_basic_options(%s)", user_input
            )

        step_id = "basic_options"

        # async def _requery_sources():
        #     """Re-query AVR sources after enabling query_sources."""
        #     pioneer = self.pioneer
        #     await pioneer.build_source_dict()
        #     _LOGGER.debug("flow_id=%s", self.flow_id)
        #     self.hass.async_create_task(
        #         self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        #     )

        errors = {}
        description_placeholders = {}
        if user_input is not None:
            # query_sources = options[CONF_QUERY_SOURCES]
            result = await self._update_options(step_id, user_input)
            if result is True:
                # if not query_sources and options[CONF_QUERY_SOURCES]:
                #     ## Query sources turned on, query AVR and restart options flow
                #     _LOGGER.debug("flow_id=%s", self.flow_id)
                #     if not self.requery_task:
                #         self.requery_task = self.hass.async_create_task(
                #             _requery_sources()
                #         )
                #         return self.async_show_progress(
                #             step_id=step_id,
                #             progress_action="query_sources",
                #         )

                #     return self.async_show_progress_done(next_step_id="basic_options")
                return await self.async_step_zone_options()
            (errors, description_placeholders) = result

        options = self.options
        defaults = self.defaults
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
                ): vol.Coerce(
                    int,
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=2592000,  # 30 days
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
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
            description_placeholders=description_placeholders,
            last_step=False,
        )

    async def async_step_zone_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle zone options for Pioneer AVR."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_zone_options(%s)", user_input
            )

        step_id = "zone_options"
        errors = {}
        description_placeholders = {}
        if user_input is not None:
            result = await self._update_options(step_id, user_input)
            if result is True:
                if self.show_advanced_options:
                    return await self.async_step_advanced_options()
                return await self._create_entry()
            (errors, description_placeholders) = result

        options = self.options
        defaults = self.defaults
        zone_labels = dict(
            [
                (v, k)
                for k, v in (
                    self.options_parsed.get(CONF_SOURCES) or defaults[CONF_SOURCES]
                ).items()
            ]
        )

        def zone_options(zone: Zones):
            return sorted(
                (
                    dict([("label", zone_labels.get(v, f"Source {v}")), ("value", v)])
                    for v in self.default_source_ids[zone]
                ),
                key=lambda i: i["label"],
            )

        data_schema = vol.Schema(
            {
                vol.Optional(PARAM_ZONE_1_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.Z1),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_ZONE_2_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.Z2),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_ZONE_3_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.Z3),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_HDZONE_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zones.HDZ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=defaults[PARAM_MAX_SOURCE_ID]
                ): vol.Coerce(
                    int,
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=99,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
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
            description_placeholders=description_placeholders,
            last_step=not self.show_advanced_options,
        )

    async def async_step_advanced_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced options for Pioneer AVR."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_advanced_options(%s)",
                user_input,
            )

        step_id = "advanced_options"
        errors = {}
        description_placeholders = {}
        if user_input is not None:
            result = await self._update_options(step_id, user_input)
            if result is True:
                return await self.async_step_debug_options()
            (errors, description_placeholders) = result

        options = self.options
        defaults = self.defaults
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
                ): vol.Coerce(
                    int,
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                ),
                vol.Optional(
                    PARAM_MAX_VOLUME_ZONEX, default=defaults[PARAM_MAX_VOLUME_ZONEX]
                ): vol.Coerce(
                    int,
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=PARAM_DEFAULTS[PARAM_MAX_VOLUME],
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                ),
                vol.Optional(CONF_PARAMS, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=False,
        )

    async def async_step_debug_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle debug options for Pioneer AVR."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler.async_step_debug_options(%s)", user_input
            )

        step_id = "debug_options"
        errors = {}
        description_placeholders = {}
        if user_input is not None:
            result = await self._update_options(step_id, user_input)
            if result is True:
                return await self._create_entry()
            (errors, description_placeholders) = result

        options = self.options
        defaults = self.defaults
        data_schema = vol.Schema(
            {
                vol.Optional(
                    PARAM_DEBUG_LISTENER, default=defaults[PARAM_DEBUG_LISTENER]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_RESPONDER, default=defaults[PARAM_DEBUG_RESPONDER]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_UPDATER, default=defaults[PARAM_DEBUG_UPDATER]
                ): selector.BooleanSelector(),
                vol.Optional(CONF_DEBUG_CONFIG, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    ),
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, options),
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=True,
        )

    async def _update_options(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> Tuple[list[str], list[str]] | bool:
        """Update config entry options."""
        if _debug_atlevel(8):
            _LOGGER.debug(
                ">> PioneerOptionsFlowHandler._update_options(step_id=%s, user_input=%s)",
                step_id,
                dict(user_input),
            )
        errors = {}
        description_placeholders = {}
        self.options.update(user_input)

        ## Coalesce CONF_IGNORE_ZONE_* options into param
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

        def _validate_sources(sources_list: list[str]) -> dict[str, Any] | None:
            """Validate sources are in correct format and convert to dict."""
            sources_invalid = []
            sources_tuple = list(
                map(
                    lambda x: (v[1], v[0]) if len(v := x.split(":", 1)) == 2 else x,
                    sources_list,
                )
            )
            for source_tuple in sources_tuple:
                if not isinstance(source_tuple, tuple):
                    sources_invalid.append(source_tuple)
                else:
                    (_, source_id) = source_tuple
                    if not (
                        len(source_id) == 2
                        and source_id[0].isdigit()
                        and source_id[1].isdigit()
                    ):
                        sources_invalid.append(source_tuple)
            if sources_invalid:
                errors[CONF_SOURCES] = "invalid_sources"
                description_placeholders["sources"] = json.dumps(sources_invalid)
                return None
            return dict(sources_tuple)

        ## Validate CONF_SOURCES is a dict of names to numeric IDs
        if step_id == "basic_options":
            query_sources = user_input[CONF_QUERY_SOURCES]
            sources_list = user_input[CONF_SOURCES]
            if not sources_list:
                query_sources = True
            elif not query_sources:
                if (sources_new := _validate_sources(sources_list)) is not None:
                    self.options_parsed[CONF_SOURCES] = sources_new
            self.options[CONF_QUERY_SOURCES] = query_sources
            self.update_zone_source_subsets()  ## Recalculate valid zones for sub-zones

        ## Parse and validate CONF_PARAMS
        if CONF_PARAMS in user_input:
            params_config = {}
            params_invalid = []
            for param_item in user_input[CONF_PARAMS]:
                try:
                    (param_name, _, param_value_str) = param_item.partition(":")
                    param_value = json.loads(param_value_str)
                    params_config.update({param_name: param_value})
                except (json.JSONDecodeError, ValueError):
                    params_invalid.append(param_item)

            if params_invalid:
                errors[CONF_PARAMS] = "invalid_params"
                description_placeholders["params"] = json.dumps(params_invalid)
            else:
                self.options_parsed[CONF_PARAMS] = params_config

        ## Parse and validate CONF_DEBUG_CONFIG
        if CONF_DEBUG_CONFIG in user_input:
            debug_config = {}
            debug_invalid = []
            for debug_item in user_input[CONF_DEBUG_CONFIG]:
                try:
                    (debug_category, _, debug_value_str) = debug_item.partition(":")
                    debug_value = json.loads(debug_value_str)
                    debug_config.update({debug_category: debug_value})
                except (json.JSONDecodeError, ValueError):
                    debug_invalid.append(debug_item)

            if debug_invalid:
                errors[CONF_DEBUG_CONFIG] = "invalid_debug"
                description_placeholders["debug"] = json.dumps(debug_invalid)
            else:
                self.options_parsed[CONF_DEBUG_CONFIG] = debug_config

        return (errors, description_placeholders) if errors else True

    async def _create_entry(self) -> FlowResult:
        """Create/update config entry using submitted options."""
        options = self.options
        defaults = self.defaults
        Debug.setconfig(None, self.options_parsed.get(CONF_DEBUG_CONFIG, {}))

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

        ## Include CONF_SOURCES only if not querying sources
        if options[CONF_QUERY_SOURCES] and CONF_SOURCES in self.options_parsed:
            del self.options_parsed[CONF_SOURCES]

        data = {**options_conf, **self.options_parsed, **params, **zone_sources}
        if _debug_atlevel(8):
            _LOGGER.debug(">> PioneerOptionsFlowHandler._create_entry(data=%s)", data)

        return self.async_create_entry(title="", data=data)
