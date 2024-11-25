"""The Pioneer AVR integration."""

# pylint: disable=logging-format-interpolation

import asyncio
from datetime import timedelta
import json
import logging
from typing import Any

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
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import UNDEFINED

from .config_flow import PioneerAVRConfigFlow
from .const import (
    DOMAIN,
    PLATFORMS_CONFIG_FLOW,
    MIGRATE_OPTIONS,
    OPTIONS_DEFAULTS,
    CONF_SOURCES,
    CONF_PARAMS,
    CONF_DEBUG_CONFIG,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
    ATTR_DEVICE_ENTRY,
    ATTR_OPTIONS,
)
from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug

_LOGGER = logging.getLogger(__name__)


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
                    zone,
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

    hass.data.setdefault(DOMAIN, {})
    pioneer_data = {}
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data[CONF_NAME]

    ## Compile options and params
    entry_options = entry.options if entry.options else {}
    pioneer_data[ATTR_OPTIONS] = (options := OPTIONS_DEFAULTS | entry_options)
    scan_interval = options[CONF_SCAN_INTERVAL]
    timeout = options[CONF_TIMEOUT]
    sources = options[CONF_SOURCES]
    params = {k: entry_options[k] for k in PARAMS_ALL if k in entry_options}
    params |= options.get(CONF_PARAMS, {})

    if _debug_atlevel(9):
        _LOGGER.debug(
            ">> async_setup_entry(entry_id=%s, data=%s, options=%s)",
            entry.entry_id,
            entry.data,
            entry.options,
        )

    ## Create PioneerAVR API object
    pioneer = None
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
        TimeoutError,
        ValueError,
        AttributeError,
        RuntimeError,
    ) as exc:
        _LOGGER.error("exception on initialising Pioneer AVR: %s", exc)
        if pioneer:
            await pioneer.shutdown()
        raise ConfigEntryNotReady from exc

    pioneer_data[ATTR_PIONEER] = pioneer

    ## Set up parent device for Pioneer AVR
    model = pioneer.model
    software_version = pioneer.software_version
    mac_addr = pioneer.mac_addr
    connections = set()
    top_identifiers = {(DOMAIN, entry.entry_id)}
    if mac_addr:
        connections = {(device_registry.CONNECTION_NETWORK_MAC, mac_addr)}
        top_identifiers |= {(DOMAIN, mac_addr)}

    def get_zone_identifiers(zone: str) -> set[tuple[str, str]]:
        return {(DOMAIN, i + "-" + zone) for _, i in top_identifiers}

    ## Update devices with new device_unique_ids (config entry and MAC address)
    ## TODO: remove legacy device_unique_ids from device entries in 0.10.0 or later
    ## NOTE: legacy connections with "unknown" MAC address can't be removed
    legacy_unique_id = host + ":" + str(port)

    dr = device_registry.async_get(hass)
    for device_entry in device_registry.async_entries_for_config_entry(
        dr, entry.entry_id
    ):
        id_list = [(legacy_unique_id, top_identifiers)]
        id_list += [
            (legacy_unique_id + "-" + z, get_zone_identifiers(z)) for z in pioneer.zones
        ]
        for legacy_id, new_ids in id_list:
            if (DOMAIN, legacy_id) in device_entry.identifiers and (
                device_entry.identifiers | new_ids != device_entry.identifiers
            ):
                _LOGGER.warning(
                    "updating device ID for legacy device %s (%s)",
                    device_entry.name,
                    legacy_id,
                )
                dr.async_update_device(device_entry.id, merge_identifiers=new_ids)
                break

    ## Create top level devices
    device_entry = dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=connections,
        identifiers=top_identifiers,
        manufacturer="Pioneer",
        name=name,
        model=model,
        sw_version=software_version or UNDEFINED,
        configuration_url=f"http://{host}",
    )

    pioneer_data[ATTR_DEVICE_INFO] = {}
    pioneer_data[ATTR_DEVICE_INFO][Zones.ALL] = DeviceInfo(
        identifiers=top_identifiers,
    )
    pioneer_data[ATTR_DEVICE_ENTRY] = {}
    pioneer_data[ATTR_DEVICE_ENTRY][Zones.ALL] = device_entry

    ## Create top level DataUpdateCooordinator
    def update_top_device() -> None:
        """Update top level device attributes."""
        device_registry.async_get(hass).async_update_device(
            device_entry.id,
            model=pioneer.model,
            sw_version=pioneer.software_version or UNDEFINED,
        )

    coordinator = PioneerAVRZoneCoordinator(hass, pioneer, Zones.ALL)
    await coordinator.async_config_entry_first_refresh()
    coordinator.set_zone_callback()
    pioneer_data[ATTR_COORDINATORS] = {}
    pioneer_data[ATTR_COORDINATORS][Zones.ALL] = coordinator

    ## Create DeviceInfo and DataUpdateCoordinator for each zone
    for zone in pioneer.zones:
        zone_name_suffix = (
            "Main Zone"
            if zone is Zones.Z1
            else "HDZone" if zone is Zones.HDZ else "Zone " + zone
        )
        pioneer_data[ATTR_DEVICE_INFO][zone] = DeviceInfo(
            identifiers=get_zone_identifiers(zone),
            manufacturer="Pioneer",
            name=(name + " " + zone_name_suffix),
            model=zone_name_suffix,
            via_device=(DOMAIN, entry.entry_id),
        )
        coordinator = PioneerAVRZoneCoordinator(hass, pioneer, zone)
        coordinator.set_zone_callback()
        if zone is Zones.Z1:
            coordinator.set_initial_refresh_callback(update_top_device)
        pioneer_data[ATTR_COORDINATORS][zone] = coordinator

    hass.data[DOMAIN][entry.entry_id] = pioneer_data

    ## Set up platforms for Pioneer AVR
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_CONFIG_FLOW)

    async def _update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
        """Handle options update."""
        await hass.config_entries.async_reload(config_entry.entry_id)

    ## Create update listener
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    async def _shutdown_listener(_event) -> None:
        await pioneer.shutdown()

    ## Create shutdown event listener
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _shutdown_listener)
    )

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
    else:
        _LOGGER.warning("unload_entry unload failed")

    return unload_ok


def select_dict(orig_dict: dict[str, Any], include_keys: list[str]) -> dict[str, Any]:
    """Include only specified keys from dict."""
    return {k: v for k, v in orig_dict.items() if k in include_keys}


def reject_dict(orig_dict: dict[str, Any], exclude_keys: list[str]) -> dict[str, Any]:
    """Exclude specified keys from dict."""
    return {k: v for k, v in orig_dict.items() if k not in exclude_keys}
