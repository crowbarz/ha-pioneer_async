"""Config flow for pioneer_async integration."""

from __future__ import annotations

import json
import logging
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
    CONFIG_ENTRY_VERSION,
    CONFIG_ENTRY_VERSION_MINOR,
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
    OPTIONS_ALL,
    DEFAULTS_EXCLUDE,
    ATTR_PIONEER,
    OPTIONS_DICT_INT_KEY,
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


def process_entry_options(options: dict[str, Any]) -> None:
    """Process config entry options."""
    for option in OPTIONS_DICT_INT_KEY:
        ## Restore dicts with int keys converted to str on JSON serialisation
        if option in options and isinstance(options[option], dict):
            options[option] = {int(k): v for k, v in options[option].items()}


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


def _filter_options(
    options: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    """Filter options and remove defaults."""
    return {
        k: options[k]
        for k in OPTIONS_ALL
        if k not in [CONF_SOURCES] and k in options and options[k] != defaults[k]
    }


def _filter_params(options: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Filter params and remove defaults."""
    return {
        k: options[k]
        for k in PARAMS_ALL
        if k not in PARAM_ZONE_SOURCES.values()
        and k in options
        and options[k] != defaults[k]
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

    def __init__(self) -> None:
        """Initialise Pioneer AVR config flow."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerAVRConfigFlow.__init__()")
        self.name: str = None
        self.host: str = None
        self.port: int = None
        self.model: str = None
        self.defaults: dict[str, Any] = {}
        self.query_sources = False
        self.sources: dict[int, str] = {}
        self.options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PioneerOptionsFlow:
        """Get the options flow for this handler."""
        return PioneerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if Debug.config_flow:
            _LOGGER.debug(">> PioneerAVRConfigFlow.async_step_user(%s)", user_input)
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            self.options = {}
            self.name = user_input[CONF_NAME]
            self.host = user_input[CONF_HOST]
            self.port = int(user_input[CONF_PORT])
            self.query_sources = user_input[CONF_QUERY_SOURCES]
            self.options |= {PARAM_MAX_SOURCE_ID: user_input[PARAM_MAX_SOURCE_ID]}
            ignore_volume_check = user_input[PARAM_IGNORE_VOLUME_CHECK]
            if ignore_volume_check != "default":
                opts_all = {"on": True, "off": False}
                self.options |= {
                    PARAM_IGNORE_VOLUME_CHECK: opts_all[ignore_volume_check]
                }

            pioneer = None
            try:
                pioneer = PioneerAVR(self.host, self.port, params=self.options)
                await pioneer.connect(reconnect=False)
                await pioneer.query_zones()
                if not Zone.Z1 in pioneer.properties.zones:
                    raise Zone1NotDiscovered()
                if self.query_sources:
                    await pioneer.build_source_dict()
                    self.sources = pioneer.properties.get_source_dict()
                self.defaults = OPTIONS_DEFAULTS | pioneer.params.default_params
                self.model = pioneer.properties.amp.get("model")

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except AVRConnectError as exc:
                errors["base"] = "cannot_connect"
                description_placeholders["exception"] = exc.err
            except Zone1NotDiscovered:
                return self.async_abort(reason="zone_1_not_discovered")
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("unexpected exception: %s", repr(exc))
                return self.async_abort(
                    reason="exception",
                    description_placeholders={"exception": repr(exc)},
                )
            finally:
                if pioneer:
                    await pioneer.shutdown()
                    del pioneer

            if not errors:
                return await self.async_step_basic_options()

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
                vol.Optional(
                    CONF_QUERY_SOURCES, default=True
                ): selector.BooleanSelector(),
                vol.Optional(
                    PARAM_MAX_SOURCE_ID, default=PARAM_DEFAULTS[PARAM_MAX_SOURCE_ID]
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
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_basic_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic options for Pioneer AVR."""
        if Debug.config_flow:
            _LOGGER.debug(
                ">> PioneerAVRConfigFlow.async_step_basic_options(%s)", user_input
            )

        step_id = "basic_options"
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            self.options |= user_input
            self.sources, sources_invalid = _validate_sources(user_input[CONF_SOURCES])
            if sources_invalid:
                errors[CONF_SOURCES] = "invalid_sources"
                description_placeholders["sources"] = json.dumps(sources_invalid)
            elif not self.sources:
                errors[CONF_SOURCES] = "sources_required"
            if not errors:
                return await self._create_config_entry()
        else:
            user_input = {
                PARAM_MODEL: self.model,
                CONF_SOURCES: _convert_sources(self.sources),
            }

        data_schema = vol.Schema(_get_schema_basic_options(self.defaults))

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=True,
        )

    async def _create_config_entry(self) -> FlowResult:
        """Create config entry using submitted options."""
        return self.async_create_entry(
            title=self.name,
            data={
                CONF_NAME: self.name,
                CONF_HOST: self.host,
                CONF_PORT: self.port,
            },
            options={
                **_filter_options(self.options, self.defaults),
                **_filter_params(self.options, self.defaults),
                CONF_SOURCES: self.sources,
            },
        )


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
        self.sources: dict[int, str] = {}
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
        process_entry_options(options)

        ## Convert CONF_SOURCES for options flow
        sources = options[CONF_SOURCES]
        options[CONF_QUERY_SOURCES] = False
        if not sources:
            sources = pioneer.properties.get_source_dict()
            options[CONF_QUERY_SOURCES] = True
        options[CONF_SOURCES] = _convert_sources(sources)
        options_parsed[CONF_SOURCES] = sources

        ## Convert CONF_PARAMS for options flow
        params_config: dict[str, Any] = options[CONF_PARAMS]
        options_parsed[CONF_PARAMS] = params_config
        options[CONF_PARAMS] = list(
            [f"{k}: {json.dumps(v)}" for k, v in params_config.items()]
        )

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
            return [
                {
                    "label": self.options_parsed[CONF_SOURCES].get(
                        source_id, f"Source {source_id}"
                    ),
                    "value": str(source_id),
                }
                for source_id in self.default_source_ids[zone]
            ]

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
