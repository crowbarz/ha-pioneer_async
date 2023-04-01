"""The Pioneer AVR integration."""
# pylint: disable=logging-format-interpolation

import asyncio
import logging
import json

import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.param import PARAMS_ALL

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

from .const import (
    DOMAIN,
    PLATFORMS,
    PIONEER_OPTIONS_UPDATE,
    OPTIONS_DEFAULTS,
    CONF_SOURCES,
)
from .device import check_device_unique_id, clear_device_unique_id
from .media_player import async_setup_shutdown_listener

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pioneer AVR from a config entry."""
    _LOGGER.debug(
        ">> init/async_setup_entry(entry_id=%s, data=%s, options=%s)",
        entry.entry_id,
        entry.data,
        entry.options,
    )

    ## Create PioneerAVR API object
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
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except json.JSONDecodeError:
            _LOGGER.warning("ignoring invalid sources: %s", sources)
            options[CONF_SOURCES] = (sources := {})
    params = {k: entry_options[k] for k in PARAMS_ALL if k in entry_options}

    ## Create PioneerAVR
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
    hass.data[DOMAIN][entry.entry_id] = pioneer

    ## Set up parent device for Pioneer AVR
    model = pioneer.model
    software_version = pioneer.software_version
    mac_addr = pioneer.mac_addr

    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, mac_addr)},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Pioneer",
        name=name,
        model=model,
        sw_version=software_version,
        configuration_url=f"http://{host}",
    )

    ## Set up platforms for Pioneer AVR
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    ## Create update listener
    entry.add_update_listener(_update_listener)

    ## Create shutdown event listener
    shutdown_listener = await async_setup_shutdown_listener(hass, pioneer)
    if shutdown_listener:
        entry.async_on_unload(shutdown_listener)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""

    ## Send signal to platform to update options
    async_dispatcher_send(
        hass, f"{PIONEER_OPTIONS_UPDATE}-{entry.entry_id}", entry.options
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(">> async_unload_entry()")

    ## Clear callback references from Pioneer AVR (to allow entities to unload)
    pioneer = hass.data[DOMAIN][entry.entry_id]
    pioneer.clear_zone_callbacks()

    ## Unload platforms for Pioneer AVR
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

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
