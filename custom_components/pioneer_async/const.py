"""Constants for the pioneer_async integration."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
)

DOMAIN = "pioneer_async"
PLATFORMS = ["media_player"]
VERSION = "0.7.3"

DEFAULT_HOST = "avr"
DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 8102  # Some Pioneer AVRs use 23
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_TIMEOUT = 5
DEFAULT_SOURCES = {}

CONF_SOURCES = "sources"
CONF_PARAMS = "params"
CONF_IGNORE_ZONE_2 = "ignore_zone_2"
CONF_IGNORE_ZONE_3 = "ignore_zone_3"
CONF_IGNORE_ZONE_Z = "ignore_zone_Z"
CONF_DEBUG_LEVEL = "debug_level"

PIONEER_OPTIONS_UPDATE = "pioneer_options_update"

LOGIN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_SOURCES: {},
    CONF_IGNORE_ZONE_2: False,
    CONF_IGNORE_ZONE_3: False,
    CONF_IGNORE_ZONE_Z: False,
    CONF_DEBUG_LEVEL: 0,
}
OPTIONS_ALL = OPTIONS_DEFAULTS.keys()

CLASS_PIONEER = MediaPlayerDeviceClass.RECEIVER

SERVICE_SET_PANEL_LOCK = "set_panel_lock"
SERVICE_SET_REMOTE_LOCK = "set_remote_lock"
SERVICE_SET_DIMMER = "set_dimmer"
SERVICE_SET_TONE_SETTINGS = "set_tone_settings"
SERVICE_SET_AMP_SETTINGS = "set_amp_settings"
SERVICE_SET_FM_TUNER_FREQUENCY = "set_fm_tuner_frequency"
SERVICE_SET_AM_TUNER_FREQUENCY = "set_am_tuner_frequency"
SERVICE_SET_TUNER_PRESET = "set_tuner_preset"
SERVICE_SET_CHANNEL_LEVELS = "set_channel_levels"
SERVICE_SET_VIDEO_SETTINGS = "set_video_settings"
SERVICE_SET_DSP_SETTINGS = "set_dsp_settings"

ATTR_ENTITY_ID = "entity_id"
ATTR_PANEL_LOCK = "panel_lock"
ATTR_REMOTE_LOCK = "remote_lock"
ATTR_DIMMER = "dimmer"
ATTR_TONE = "tone"
ATTR_TREBLE = "treble"
ATTR_BASS = "bass"
ATTR_FREQUENCY = "frequency"
ATTR_CLASS = "class"
ATTR_PRESET = "preset"
ATTR_CHANNEL = "channel"
ATTR_LEVEL = "level"
