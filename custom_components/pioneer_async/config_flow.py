"""Config flow for pioneer_async integration."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from typing import Any, Tuple

import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone
from aiopioneer.exceptions import AVRConnectError
from aiopioneer.params import (
    PARAM_MODEL,
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
    PARAM_ALWAYS_POLL,
    PARAM_DEBUG_LISTENER,
    PARAM_DEBUG_UPDATER,
    PARAM_DEBUG_COMMAND,
    PARAM_DEBUG_COMMAND_QUEUE,
    PARAM_DEFAULTS,
    PARAMS_ALL,
)

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONFIG_ENTRY_VERSION,
    CONFIG_ENTRY_VERSION_MINOR,
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_SOURCES,
    CONF_PARAMS,
    CONF_REPEAT_COUNT,
    CONF_IGNORE_ZONE_2,
    CONF_IGNORE_ZONE_3,
    CONF_IGNORE_HDZONE,
    CONF_QUERY_SOURCES,
    CONF_DEBUG_INTEGRATION,
    CONF_DEBUG_CONFIG_FLOW,
    CONF_DEBUG_ACTION,
    DEFAULT_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    OPTIONS_DEFAULTS,
    CONFIG_DATA,
    OPTIONS_ALL,
    DEFAULTS_EXCLUDE,
    ATTR_PIONEER,
    OPTIONS_DICT_INT_KEY,
    PARAMS_DICT_INT_KEY,
)
from .debug import Debug

_LOGGER = logging.getLogger(__name__)


def _get_schema_basic_options(defaults: dict) -> dict:
    """Return basic options schema."""
    return {
        vol.Optional(PARAM_MODEL): selector.TextSelector(selector.TextSelectorConfig()),
        vol.Required(CONF_SOURCES, default=[]): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[], custom_value=True, multiple=True),
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
        vol.Optional(
            CONF_REPEAT_COUNT, default=defaults[CONF_REPEAT_COUNT]
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=10,
                step=1,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        ),
    }


def _convert_sources(sources: dict[str, Any]) -> list[str]:
    """Convert sources dict to format for data entry flow."""
    return list(f"{k}:{v}" for k, v in sources.items())


def get_entry_config(
    config_entry: config_entries.ConfigEntry, pioneer: PioneerAVR
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate config from config entry."""
    options = config_entry.options.copy()
    process_entry_options(options, remove_invalid=True)
    config = deepcopy(config_entry.data | options)
    config[CONF_QUERY_SOURCES] = bool(not config.get(CONF_SOURCES, {}))
    defaults = OPTIONS_DEFAULTS | pioneer.params.default_params
    return config, defaults


def process_entry_options(
    options: dict[str, Any], process_options: list[str] = None, remove_invalid=False
) -> list[str]:
    """Process config entry options."""
    if process_options is None:
        process_options = OPTIONS_DICT_INT_KEY
    options_invalid = []
    for option in process_options:
        try:
            ## Restore dicts with int keys converted to str on JSON serialisation
            if option in options:
                if option == CONF_PARAMS:
                    options_invalid.extend(
                        process_entry_options(
                            options[CONF_PARAMS], process_options=PARAMS_DICT_INT_KEY
                        )
                    )
                elif isinstance(options[option], dict):
                    options[option] = {int(k): v for k, v in options[option].items()}
        except ValueError:
            options_invalid.append(option)

    if options_invalid and remove_invalid:
        _LOGGER.warning("removing invalid options %s", options_invalid)
        for option in options_invalid:
            del options[option]

    return options_invalid


def _validate_sources(sources_list: list[str]) -> Tuple[dict[str, Any] | None, list]:
    """Validate sources are in correct format and convert to dict."""
    sources_invalid = []
    sources = {}
    for source_entry in sources_list:
        try:
            if len(source_items := source_entry.split(":", 1)) != 2:
                raise ValueError
            if (source_id := int(source_items[0])) < 0 or source_id > 99:
                raise ValueError
        except ValueError:
            sources_invalid.append(source_entry)
        else:
            sources[source_id] = source_items[1]

    return sources, sources_invalid


def _filter_options(config: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Filter options and remove defaults."""
    return {
        k: config[k]
        for k in OPTIONS_ALL
        if k in config and config[k] != defaults.get(k)
    }


def _filter_params(config: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Filter params and remove defaults."""
    return {
        k: config[k]
        for k in PARAMS_ALL
        if k not in PARAM_ZONE_SOURCES.values()
        and k in config
        and config[k] != defaults.get(k)
    }


class Zone1NotDiscovered(HomeAssistantError):
    """Error to indicate an AVR protocol failure."""


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate host:port is already configured."""


class InvalidSources(HomeAssistantError):
    """Error to indicate invalid sources specified."""


class PioneerAVRConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):  # pylint:disable=abstract-method
    """Handle Pioneer AVR config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_VERSION_MINOR
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialise Pioneer AVR config flow."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerAVRConfigFlow.__init__()")
        self.config_entry: config_entries.ConfigEntry = None
        self.pioneer: PioneerAVR = None
        self.model: str = None
        self.defaults: dict[str, Any] = OPTIONS_DEFAULTS
        self.data: dict[str, Any] = {}
        self.config: dict[str, Any] = {CONF_QUERY_SOURCES: True}
        self.config_parsed: dict[str, Any] = {}
        self.interview_task: asyncio.Task = None
        self.interview_errors: dict[str, str] = {}
        self.interview_description_placeholders: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerAVRConfigFlow.async_step_user(%s)", user_input)
        return await self.async_step_connection()

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> FlowResult:
        """Handle user requested reconfigure."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerAVRConfigFlow.async_step_reconfigure(%s)", user_input
            )
        self.config_entry = self._get_reconfigure_entry()
        self.pioneer = self.hass.data[DOMAIN][self.config_entry.entry_id][ATTR_PIONEER]
        config, self.defaults = get_entry_config(self.config_entry, self.pioneer)
        self.defaults |= {k: config[k] for k in CONFIG_DATA if k in config}

        sources = config.get(CONF_SOURCES, {})
        config[CONF_SOURCES] = _convert_sources(sources)
        self.config_parsed[CONF_SOURCES] = sources

        ignore_volume_check = config.get(PARAM_IGNORE_VOLUME_CHECK)
        if ignore_volume_check is not None:
            config[PARAM_IGNORE_VOLUME_CHECK] = "on" if ignore_volume_check else "off"
            self.config_parsed[PARAM_IGNORE_VOLUME_CHECK] = ignore_volume_check

        self.config = config
        return await self.async_step_connection()

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device connection details for Pioneer AVR."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerAVRConfigFlow.async_step_connection(%s)", user_input
            )

        _LOGGER.critical("connection: config=%s", self.config)

        step_id = "connection"
        errors = self.interview_errors
        description_placeholders = self.interview_description_placeholders
        self.interview_errors = {}
        self.interview_description_placeholders = {}

        if user_input is not None and not errors:
            self.config |= user_input

            ## Convert PARAM_IGNORE_VOLUME_CHECK to config entry value
            ignore_volume_check = {"default": None, "off": False, "on": True}[
                self.config[PARAM_IGNORE_VOLUME_CHECK]
            ]
            if ignore_volume_check is None:
                del self.config[PARAM_IGNORE_VOLUME_CHECK]
                if PARAM_IGNORE_VOLUME_CHECK in self.config_parsed:
                    del self.config_parsed[PARAM_IGNORE_VOLUME_CHECK]
            else:
                self.config_parsed[PARAM_IGNORE_VOLUME_CHECK] = ignore_volume_check

            self.data = {k: v for k, v in self.config.items() if k in CONFIG_DATA}
            return await self.async_step_interview()

        if user_input is None:
            user_input = self.config

            ## Convert PARAM_IGNORE_VOLUME_CHECK to user input value
            if PARAM_IGNORE_VOLUME_CHECK in user_input:
                ignore_volume_check = user_input[PARAM_IGNORE_VOLUME_CHECK]
                self.config_parsed[PARAM_IGNORE_VOLUME_CHECK] = ignore_volume_check
                user_input[PARAM_IGNORE_VOLUME_CHECK] = (
                    "on" if ignore_volume_check else "off"
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Optional(
                    CONF_QUERY_SOURCES, default=True
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=PARAM_DEFAULTS[PARAM_MAX_SOURCE_ID]
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=99,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Optional(
                    PARAM_IGNORE_VOLUME_CHECK, default="default"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"label": "AVR default", "value": "default"},
                            {"label": "Enabled", "value": "on"},
                            {"label": "Disabled", "value": "off"},
                        ]
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_interview(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Interview Pioneer AVR to determine capabilities."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerAVRConfigFlow.async_step_interview(%s)", user_input
            )
        _LOGGER.critical("interview: config=%s", self.config)

        async def interview_avr():
            """Perform AVR interview."""
            pioneer = PioneerAVR(
                host=self.config[CONF_HOST],
                port=self.config[CONF_PORT],
                params=_filter_params(config=self.config, defaults={}),
            )
            try:
                await pioneer.connect(reconnect=False)
                await pioneer.query_zones()
                if not Zone.Z1 in pioneer.properties.zones:
                    raise Zone1NotDiscovered()
                if self.config[CONF_QUERY_SOURCES]:
                    await pioneer.build_source_dict()
                    sources = pioneer.properties.get_source_dict()
                    self.config[CONF_SOURCES] = _convert_sources(sources)
                    self.config_parsed[CONF_SOURCES] = sources
                self.config[PARAM_MODEL] = pioneer.properties.amp.get("model")
                self.defaults = OPTIONS_DEFAULTS | pioneer.params.default_params
            finally:
                await pioneer.shutdown()

        async def update_sources():
            """Update AVR sources on reconfigure."""
            await self.pioneer.build_source_dict()
            sources = self.pioneer.properties.get_source_dict()
            self.config[CONF_SOURCES] = _convert_sources(sources)
            self.config_parsed[CONF_SOURCES] = sources

        if not self.interview_task:
            if self.config_entry and self.data == self.config_entry.data:
                ## Update sources on reconfigure of unchanged connection
                if not self.config[CONF_QUERY_SOURCES]:
                    return await self.async_step_basic_options()
                coro = update_sources()
            else:
                coro = interview_avr()
            self.interview_task = self.hass.async_create_task(coro)
        if not self.interview_task.done():
            return self.async_show_progress(
                step_id="interview",
                progress_action="interview",
                progress_task=self.interview_task,
            )
        try:
            await self.interview_task
        except AlreadyConfigured:
            self.interview_errors["abort"] = "already_configured"
            return self.async_show_progress_done(next_step_id="interview_exception")
        except Zone1NotDiscovered:
            self.interview_errors["abort"] = "zone_1_not_discovered"
            return self.async_show_progress_done(next_step_id="interview_exception")
        except AVRConnectError as exc:
            self.interview_errors["base"] = "cannot_connect"
            self.interview_description_placeholders["exception"] = exc.err
            return self.async_show_progress_done(next_step_id="connection")
        except Exception as exc:  # pylint: disable=broad-except
            self.interview_errors["abort"] = "exception"
            self.interview_description_placeholders = {"exception": repr(exc)}
            return self.async_show_progress_done(next_step_id="interview_exception")
        finally:
            self.interview_task = None

        return self.async_show_progress_done(next_step_id="basic_options")

    async def async_step_interview_exception(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> FlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(
            reason=self.interview_errors["abort"],
            description_placeholders=self.interview_description_placeholders,
        )

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerAVRConfigFlow.async_step_basic_options(%s)", user_input
            )
        _LOGGER.critical("basic_options: config=%s", self.config)

        step_id = "basic_options"
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            self.config |= user_input

            ## Convert CONF_SOURCES to config entry value
            sources, sources_invalid = _validate_sources(self.config[CONF_SOURCES])
            if sources_invalid:
                errors[CONF_SOURCES] = "invalid_sources"
                description_placeholders["sources"] = json.dumps(sources_invalid)
            elif not sources:
                errors[CONF_SOURCES] = "sources_required"
            else:
                self.config_parsed[CONF_SOURCES] = sources

            if not errors:
                return await self.create_update_config_entry()
        else:
            user_input = self.config

        defaults = self.defaults
        data_schema = vol.Schema(
            {
                vol.Optional(PARAM_MODEL): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required(CONF_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    ),
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=2592000,  # 30 days
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
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
                vol.Optional(
                    CONF_REPEAT_COUNT, default=defaults[CONF_REPEAT_COUNT]
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=10,
                            step=1,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Coerce(int),
                ),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=True,
        )

    async def create_update_config_entry(self) -> FlowResult:
        """Create or update config entry using submitted options."""
        config = self.config | self.config_parsed
        defaults = self.defaults
        data = {k: v for k, v in config.items() if k in CONFIG_DATA}
        options = _filter_options(config, defaults) | _filter_params(config, defaults)
        _LOGGER.critical("create_config_entry: data=%s, options=%s", data, options)

        if self.source == config_entries.SOURCE_RECONFIGURE:
            ## Complete reconfiguration
            # self.async_set_unique_id(user_id)
            # self._abort_if_unique_id_mismatch()
            if data == self.config_entry.data:
                ## Data has not changed, just update options
                self.hass.config_entries.async_update_entry(
                    entry=self.config_entry, options=options
                )
                ## TODO: update PioneerAVR and abort instead of reloading
            return self.async_update_reload_and_abort(
                entry=self.config_entry, data=data, options=options
            )

        return self.async_create_entry(
            title=self.config[CONF_NAME], data=data, options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PioneerOptionsFlow:
        """Get the options flow for this handler."""
        return PioneerOptionsFlow()


class PioneerOptionsFlow(config_entries.OptionsFlow):
    """Handle Pioneer AVR options."""

    def __init__(self) -> None:
        """Initialise Pioneer AVR options flow."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerOptionsFlow.__init__()")
        self.pioneer = None
        self.defaults = {}
        self.options = {}
        self.options_parsed = {}
        self.default_source_ids: list[int] = {}

    def update_zone_source_subsets(self) -> None:
        """Update zone source IDs to be a valid subset of configured/available sources."""
        ## NOTE: param defaults may include sources excluded from main zone
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerOptionsFlow.update_zone_source_subsets()")
        sources = self.options_parsed[CONF_SOURCES]
        source_ids = list(sources.keys())
        for zone, param_zone_sources in PARAM_ZONE_SOURCES.items():
            self.default_source_ids[zone] = default_source_ids = (
                list([s for s in self.defaults[param_zone_sources] if s in source_ids])
                or source_ids
            )

            ## Filter zone sources with valid sources for zone
            zone_sources = [
                source_id
                for source_id_str in self.options.get(param_zone_sources, [])
                if (source_id := int(source_id_str)) in self.default_source_ids[zone]
            ]

            ## Set parsed zone sources and update options with str zone sources
            if zone_sources and (sorted(zone_sources) != sorted(default_source_ids)):
                self.options_parsed[param_zone_sources] = list(zone_sources)
                self.options[param_zone_sources] = list([str(s) for s in zone_sources])
            else:
                if param_zone_sources in self.options_parsed:
                    del self.options_parsed[param_zone_sources]
                if param_zone_sources in self.options:
                    del self.options[param_zone_sources]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow for Pioneer AVR."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerOptionsFlow.async_step_init(%s)", user_input)

        config_entry = self.config_entry
        if config_entry.entry_id not in self.hass.data[DOMAIN]:
            return self.async_abort(reason="not_set_up")

        pioneer: PioneerAVR = self.hass.data[DOMAIN][config_entry.entry_id][
            ATTR_PIONEER
        ]
        self.pioneer = pioneer

        defaults = {
            **OPTIONS_DEFAULTS,  ## defaults
            **pioneer.params.default_params,  ## aiopioneer defaults
        }
        entry_options = config_entry.options
        defaults_inherit = {
            k: v for k, v in defaults.items() if k not in DEFAULTS_EXCLUDE
        }
        options = {**defaults_inherit, **entry_options}
        options_parsed = {}
        process_entry_options(options, remove_invalid=True)

        ## Convert CONF_SOURCES for options flow
        sources = options[CONF_SOURCES]
        options[CONF_QUERY_SOURCES] = False
        if not sources:
            sources = pioneer.properties.get_source_dict()
            options[CONF_QUERY_SOURCES] = True
        options[CONF_SOURCES] = _convert_sources(sources)
        options_parsed[CONF_SOURCES] = sources

        self.options = options
        self.options_parsed = options_parsed
        self.defaults = defaults
        self.update_zone_source_subsets()

        return await self.async_step_basic_options()

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerOptionsFlow.async_step_basic_options(%s)", user_input
            )

        step_id = "basic_options"

        errors = {}
        description_placeholders = {}
        if user_input is not None:
            # query_sources = options[CONF_QUERY_SOURCES]
            result = await self._update_options(step_id, user_input)
            if result is True:
                if user_input[CONF_QUERY_SOURCES]:
                    pioneer = self.pioneer
                    pioneer.params.set_user_params(  # update max_source_id before query
                        pioneer.params.user_params
                        | {PARAM_MAX_SOURCE_ID: user_input[PARAM_MAX_SOURCE_ID]}
                    )
                    await pioneer.build_source_dict()
                    sources = pioneer.properties.get_source_dict() or {}
                    self.options[CONF_SOURCES] = _convert_sources(sources)
                    self.options[CONF_QUERY_SOURCES] = False
                else:
                    return await self.async_step_zone_options()
            else:
                (errors, description_placeholders) = result

        options = self.options
        defaults = self.defaults
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_QUERY_SOURCES, default=True
                ): selector.BooleanSelector(),
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
                **_get_schema_basic_options(defaults),
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
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerOptionsFlow.async_step_zone_options(%s)", user_input
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

        def zone_options(zone: Zone):
            return sorted(
                [
                    {
                        "label": self.options_parsed[CONF_SOURCES].get(
                            source_id, f"Source {source_id}"
                        ),
                        "value": str(source_id),
                    }
                    for source_id in self.default_source_ids[zone]
                ],
                key=lambda i: i["label"],
            )

        data_schema = vol.Schema(
            {
                vol.Optional(PARAM_ZONE_1_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zone.Z1),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_ZONE_2_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zone.Z2),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_ZONE_3_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zone.Z3),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(PARAM_HDZONE_SOURCES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_options(Zone.HDZ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
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
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerOptionsFlow.async_step_advanced_options(%s)",
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
                    PARAM_ALWAYS_POLL, default=defaults[PARAM_ALWAYS_POLL]
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
                vol.Optional(CONF_PARAMS, default={}): selector.ObjectSelector(),
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
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerOptionsFlow.async_step_debug_options(%s)", user_input
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
                    PARAM_DEBUG_UPDATER, default=defaults[PARAM_DEBUG_UPDATER]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_COMMAND, default=defaults[PARAM_DEBUG_COMMAND]
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_DEBUG_COMMAND_QUEUE,
                    default=defaults[PARAM_DEBUG_COMMAND_QUEUE],
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_DEBUG_INTEGRATION,
                    default=defaults[CONF_DEBUG_INTEGRATION],
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_DEBUG_CONFIG_FLOW,
                    default=defaults[CONF_DEBUG_CONFIG_FLOW],
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_DEBUG_ACTION,
                    default=defaults[CONF_DEBUG_ACTION],
                ): selector.BooleanSelector(),
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
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerOptionsFlow._update_options(step_id=%s, user_input=%s)",
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

        ## Validate CONF_SOURCES is a dict of names to numeric IDs
        if step_id == "basic_options":
            if not user_input.get(PARAM_MODEL):
                del self.options[PARAM_MODEL]
            if not user_input[CONF_QUERY_SOURCES]:
                sources_new, sources_invalid = _validate_sources(
                    user_input[CONF_SOURCES]
                )
                if sources_new is None:
                    errors[CONF_SOURCES] = "invalid_sources"
                    description_placeholders["sources"] = json.dumps(sources_invalid)
                elif not sources_new:
                    errors[CONF_SOURCES] = "sources_required"
                else:
                    self.options_parsed[CONF_SOURCES] = sources_new

        if step_id == "zone_options":
            self.update_zone_source_subsets()  ## Recalculate valid zones for sub-zones

        ## Convert params dict options with int keys back to int
        if options_invalid := process_entry_options(
            self.options[CONF_PARAMS], process_options=PARAMS_DICT_INT_KEY
        ):
            errors[CONF_PARAMS] = "invalid_params"
            description_placeholders["params"] = json.dumps(options_invalid)

        return (errors, description_placeholders) if errors else True

    async def _create_entry(self) -> FlowResult:
        """Create/update config entry using submitted options."""
        options = self.options
        defaults = self.defaults
        Debug.setconfig(self.options_parsed)

        options_conf = _filter_options(options, defaults)  ## non-default options only
        params = _filter_params(options, defaults)  ## non-default params only

        ## Include CONF_SOURCES only if not querying sources
        if options[CONF_QUERY_SOURCES] and CONF_SOURCES in self.options_parsed:
            del self.options_parsed[CONF_SOURCES]

        data = {**options_conf, **self.options_parsed, **params}
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerOptionsFlow._create_entry(data=%s)", data)

        return self.async_create_entry(title="", data=data)
