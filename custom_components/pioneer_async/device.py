"""Pioneer AVR device functions."""
import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# devices = {}


def get_device_unique_id(host: str, port: int) -> str:
    """Get unique ID for Pioneer AVR."""
    return host + ":" + str(port)


def check_device_unique_id(
    hass: HomeAssistant,
    host: str,
    port: int,
    entry_id: str = "configuration.yaml",
    configure=False,
) -> str:
    """Check whether Pioneer AVR has already been set up."""
    device_unique_id = get_device_unique_id(host, port)
    _LOGGER.debug(
        ">> check_device_unique_id(unique_id=%s, configure=%s)",
        device_unique_id,
        configure,
    )
    hass.data.setdefault(DOMAIN, {})
    configured_entry_id = hass.data[DOMAIN].get(device_unique_id)
    # configured_entry_id = devices.get(device_unique_id)
    if configured_entry_id and configured_entry_id != entry_id:
        # if configure:
        _LOGGER.error(
            'AVR "%s" is already configured via entry %s',
            device_unique_id,
            configured_entry_id,
        )
        return None
    if configure:
        _LOGGER.debug(
            'Configuring AVR "%s" via entry_id %s', device_unique_id, entry_id
        )
        hass.data[DOMAIN][device_unique_id] = entry_id  ## flag as configured
        # devices[device_unique_id] = entry  ## flag as configured
    return device_unique_id


def clear_device_unique_id(hass: HomeAssistant, host: str, port: int) -> None:
    """Clear Pioneer AVR setup."""
    device_unique_id = get_device_unique_id(host, port)
    _LOGGER.debug(">> clear_device_unique_id(unique_id=%s)", device_unique_id)
    if device_unique_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(device_unique_id)
        # devices.pop(device_unique_id)
    else:
        _LOGGER.error('Clear requested for unconfigured AVR "%s"', device_unique_id)
