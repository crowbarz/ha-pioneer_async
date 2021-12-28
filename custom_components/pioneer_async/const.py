"""Constants for the pioneer_async integration."""

from datetime import timedelta

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
VERSION = "0.3"

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
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_TIMEOUT = 2
DEFAULT_SOURCES = {}

CONF_SOURCES = "sources"
CONF_PARAMS = "params"
CONF_IGNORE_ZONE_2 = "ignore_zone_2"
CONF_IGNORE_ZONE_3 = "ignore_zone_3"
CONF_IGNORE_ZONE_Z = "ignore_zone_Z"

PIONEER_OPTIONS_UPDATE = "pioneer_options_update"

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_SOURCES: "{}",
    CONF_IGNORE_ZONE_2: False,
    CONF_IGNORE_ZONE_3: False,
    CONF_IGNORE_ZONE_Z: False,
}
OPTIONS_ALL = OPTIONS_DEFAULTS.keys()
