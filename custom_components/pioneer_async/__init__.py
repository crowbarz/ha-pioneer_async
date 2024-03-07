"""The Pioneer AVR integration."""

# pylint: disable=logging-format-interpolation

import asyncio
from datetime import timedelta
import json
import logging
from typing import Any

import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import PARAMS_ALL, PARAM_ZONE_SOURCES

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .config_flow import PioneerAVRConfigFlow
from .const import (
    DOMAIN,
    PLATFORMS_CONFIG_FLOW,
    PIONEER_OPTIONS_UPDATE,
    MIGRATE_OPTIONS,
    OPTIONS_DEFAULTS,
    CONF_SOURCES,
    CONF_PARAMS,
    CONF_DEBUG_CONFIG,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
)
from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug
from .device import check_device_unique_id, clear_device_unique_id
from .media_player import async_setup_shutdown_listener

_LOGGER = logging.getLogger(__name__)

# CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate Pioneer AVR config entry."""
    _LOGGER.debug("migrating config from version %d", config_entry.version)

    if config_entry.version < PioneerAVRConfigFlow.VERSION:
        data_current = config_entry.data
        data_new = {**data_current}
        options_current = config_entry.options
        options_new = {**options_current}

        ## Migrate options that have been renamed
        for option_current, option_new in MIGRATE_OPTIONS.items():
            if option_current in options_current:
                options_new[option_new] = options_current[option_current]
                del options_new[option_current]

        ## Ensure CONF_SOURCES is a dict and convert if string
        sources = options_current.get(CONF_SOURCES, {})
        try:
            if isinstance(sources, str):
                sources = json.loads(sources)
            if not isinstance(sources, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            _LOGGER.warning(
                '%s: invalid config "%s", resetting to default', CONF_SOURCES, sources
            )
        if sources:
            options_new[CONF_SOURCES] = sources
        elif CONF_SOURCES in options_new:
            del options_new[CONF_SOURCES]

        ## Validate PARAM_ZONE_*_SOURCES are lists and convert if string
        for zone, param_sources in PARAM_ZONE_SOURCES.items():
            sources_zone = options_current.get(param_sources, [])
            try:
                if isinstance(sources_zone, str):
                    sources_zone = json.loads(sources_zone)
                if not isinstance(sources_zone, list):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                _LOGGER.warning(
                    'invalid config for zone %s: "%s", resetting to default',
                    str(zone),
                    sources_zone,
                )
                sources_zone = []
            options_new[param_sources] = sources_zone

        ## Convert CONF_SCAN_INTERVAL timedelta object to seconds
        scan_interval = options_current.get(CONF_SCAN_INTERVAL)
        if isinstance(scan_interval, timedelta):
            options_new[CONF_SCAN_INTERVAL] = scan_interval.total_seconds()

        config_entry.version = PioneerAVRConfigFlow.VERSION
        hass.config_entries.async_update_entry(
            config_entry, data=data_new, options=options_new
        )

    _LOGGER.info("config migration to version %s successful", config_entry.version)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pioneer AVR from a config entry."""
    if CONF_DEBUG_CONFIG in entry.options:
        Debug.setconfig(None, entry.options[CONF_DEBUG_CONFIG])

    if _debug_atlevel(9):
        _LOGGER.debug(
            ">> async_setup_entry(entry_id=%s, data=%s, options=%s)",
            entry.entry_id,
            entry.data,
            entry.options,
        )

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data[CONF_NAME]

    ## Check whether Pioneer AVR has already been set up
    if check_device_unique_id(hass, host, port, entry.entry_id, configure=True) is None:
        return False

    ## Compile options and params
    entry_options = entry.options if entry.options else {}
    options = {**OPTIONS_DEFAULTS, **entry_options}
    scan_interval = options[CONF_SCAN_INTERVAL]
    timeout = options[CONF_TIMEOUT]
    sources = options[CONF_SOURCES]
    params = {k: entry_options[k] for k in PARAMS_ALL if k in entry_options}
    params.update(options.get(CONF_PARAMS, {}))

    ## Create PioneerAVR API object
    try:
        pioneer = PioneerAVR(
            host,
            port,
            timeout,
            scan_interval=scan_interval,
            params=params,
        )
        await pioneer.connect()
        await pioneer.query_device_info()
        await pioneer.query_zones()
        if sources:
            pioneer.set_source_dict(sources)
        else:
            await pioneer.build_source_dict()
    except (
        OSError,
        asyncio.TimeoutError,
        ValueError,
        AttributeError,
        RuntimeError,
    ) as exc:
        raise ConfigEntryNotReady from exc

    hass.data.setdefault(DOMAIN, {})
    pioneer_data = {}
    pioneer_data[ATTR_PIONEER] = pioneer

    ## Set up parent device for Pioneer AVR
    model = pioneer.model
    software_version = pioneer.software_version
    mac_addr = pioneer.mac_addr
    mac_addr_val = mac_addr if mac_addr != "unknown" else None

    ## TODO: migrate from using device_unique_id
    ## Remove old devices from device registry
    ## https://github.com/blakeblackshear/frigate-hass-integration/blob/master/custom_components/frigate/__init__.py#L220

    ## TODO: clean up MAC connections to unknown

    top_identifier = mac_addr_val or entry.entry_id
    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, mac_addr)},
        identifiers={(DOMAIN, top_identifier)},
        manufacturer="Pioneer",
        name=name,
        model=model,
        sw_version=software_version,
        configuration_url=f"http://{host}",
    )

    pioneer_data[ATTR_DEVICE_INFO] = {}
    pioneer_data[ATTR_DEVICE_INFO]["top"] = DeviceInfo(
        identifiers={(DOMAIN, top_identifier)},
    )

    ## Create DeviceInfo and DataUpdateCoordinator for each zone
    pioneer_data[ATTR_COORDINATORS] = {}
    for zone in pioneer.zones:
        zone_name_suffix = (
            "Main Zone" if zone == "1" else "HDZone" if zone == "Z" else "Zone " + zone
        )
        pioneer_data[ATTR_DEVICE_INFO][zone] = DeviceInfo(
            identifiers={(DOMAIN, top_identifier + "-" + zone)},
            manufacturer="Pioneer",
            sw_version=software_version,
            name=(name + " " + zone_name_suffix),
            model=model,
            via_device=(DOMAIN, top_identifier),
        )
        pioneer_data[ATTR_COORDINATORS][zone] = PioneerAVRZoneCoordinator(
            hass, pioneer, zone
        )

    hass.data[DOMAIN][entry.entry_id] = pioneer_data

    ## Set up platforms for Pioneer AVR
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_CONFIG_FLOW)

    async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
        """Handle options update."""

        ## Send signal to platform to update options
        async_dispatcher_send(
            hass, f"{PIONEER_OPTIONS_UPDATE}-{entry.entry_id}", entry.options
        )

    ## Create update listener
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    ## Create shutdown event listener
    await async_setup_shutdown_listener(hass, entry, pioneer)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if _debug_atlevel(9):
        _LOGGER.debug(">> async_unload_entry()")

    ## Clear callback references from Pioneer AVR (to allow entities to unload)
    pioneer: PioneerAVR = hass.data[DOMAIN][entry.entry_id][ATTR_PIONEER]
    pioneer.clear_zone_callbacks()

    ## Unload platforms for Pioneer AVR
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_CONFIG_FLOW
    )

    ## Shutdown Pioneer AVR for removal
    await pioneer.shutdown()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        clear_device_unique_id(hass, host, port)
    else:
        _LOGGER.warning("unload_entry unload failed")

    return unload_ok


class PioneerEntityBase(Entity):
    """Pioneer AVR base entity class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        pioneer: PioneerAVR,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zones | None = None,
    ) -> None:
        """Initialize the Pioneer AVR display sensor."""
        if _debug_atlevel(9):
            _LOGGER.debug("%s.__init__()", type(self).__name__)
        self.pioneer = pioneer
        self.coordinator = coordinator
        self.zone = zone
        self._attr_device_info = device_info
        self.unique_class_name = type(self).__name__  ## override for generic classes

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        entry_id = self.platform.config_entry.entry_id
        zone_suffix = "-" + str(self.zone) if self.zone is not None else ""
        return f"{entry_id}{zone_suffix}-{slugify(self._attr_name)}"

    @property
    def available(self) -> bool:
        """Returns whether the device is available."""
        return self.pioneer.available and (
            self.zone is None or self.zone in self.pioneer.zones
        )


def select_dict(orig_dict: dict[str, Any], include_keys: list[str]) -> dict[str, Any]:
    """Include only specified keys from dict."""
    return {k: v for k, v in orig_dict.items() if k in include_keys}


def reject_dict(orig_dict: dict[str, Any], exclude_keys: list[str]) -> dict[str, Any]:
    """Exclude specified keys from dict."""
    return {k: v for k, v in orig_dict.items() if k not in exclude_keys}
