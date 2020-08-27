"""Constants for the pioneer_async integration."""

import voluptuous as vol

from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)

DOMAIN = "pioneer_async"
PLATFORMS = ["media_player"]

SUPPORT_PIONEER = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

DEFAULT_HOST = "avr"
DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 8102  # Some Pioneer AVRs use 23
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TIMEOUT = 2
DEFAULT_SOURCES = {}
DEFAULT_COMMAND_DELAY = 0.1
DEFAULT_VOLUME_WORKAROUND = False

CONF_SOURCES = "sources"
CONF_COMMAND_DELAY = "command_delay"
CONF_VOLUME_WORKAROUND = "volume_workaround"
CONF_UNIQUE_ID = "unique_id"

PIONEER_OPTIONS_UPDATE = "pioneer_options_update"

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

## NOTE: not used, defined directly in config_flow.py
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): float,
        vol.Optional(CONF_COMMAND_DELAY, default=DEFAULT_COMMAND_DELAY): float,
        vol.Optional(CONF_VOLUME_WORKAROUND, default=DEFAULT_VOLUME_WORKAROUND): bool,
    }
)

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_COMMAND_DELAY: DEFAULT_COMMAND_DELAY,
    CONF_VOLUME_WORKAROUND: DEFAULT_VOLUME_WORKAROUND,
}
