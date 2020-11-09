"""The Pioneer AVR integration."""
# pylint: disable=logging-format-interpolation

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_SCAN_INTERVAL,
    CONF_COMMAND_DELAY,
    CONF_VOLUME_WORKAROUND,
    PIONEER_OPTIONS_UPDATE,
    OPTIONS_DEFAULTS,
)
from aiopioneer import PioneerAVR

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the pioneer_async component."""
    # _LOGGER.debug(f">> async_setup()")

    ## Mark integration as set up via config entry
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Pioneer AVR from a config entry."""
    ## Create PioneerAVR API object
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data[CONF_NAME]
    options = {**OPTIONS_DEFAULTS, **entry.options}
    scan_interval = options[CONF_SCAN_INTERVAL]
    timeout = options[CONF_TIMEOUT]
    command_delay = options[CONF_COMMAND_DELAY]
    volume_workaround = options[CONF_VOLUME_WORKAROUND]
    try:
        pioneer = PioneerAVR(
            host,
            port,
            timeout,
            scan_interval=scan_interval,
            command_delay=command_delay,
            volume_workaround=volume_workaround,
        )
        await pioneer.connect()
        await pioneer.query_device_info()
        await pioneer.query_zones()
        await pioneer.build_source_dict()
    except (asyncio.TimeoutError, ValueError, AttributeError) as exc:
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][entry.entry_id] = pioneer

    ## Set up parent device for this Pioneer AVR
    model = pioneer.model
    software_version = pioneer.software_version
    mac_addr = pioneer.mac_addr
    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_addr)},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Pioneer",
        name=name,
        model=model,
        sw_version=software_version,
    )

    ## Set up platforms for this Pioneer AVR
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    entry.add_update_listener(_update_listener)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    ## Send signal to platform to update options
    async_dispatcher_send(
        hass, f"{PIONEER_OPTIONS_UPDATE}-{entry.unique_id}", entry.options
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # _LOGGER.debug(f">> async_unload_entry({entry})")
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    ## Shutdown Pioneer AVR for removal
    pioneer = hass.data[DOMAIN][entry.entry_id]
    await pioneer.shutdown()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
