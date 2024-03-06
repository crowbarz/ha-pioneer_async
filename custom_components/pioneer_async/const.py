"""Constants for the pioneer_async integration."""

from datetime import timedelta

from aiopioneer.param import (
    PARAM_HDZONE_SOURCES,
    PARAM_ZONE_1_SOURCES,
    PARAM_ZONE_2_SOURCES,
    PARAM_ZONE_3_SOURCES,
    PARAM_DISABLE_AUTO_QUERY,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
)
from homeassistant.const import (
    Platform,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)


DOMAIN = "pioneer_async"
PLATFORMS = [Platform.MEDIA_PLAYER]
PLATFORMS_CONFIG_FLOW = [Platform.MEDIA_PLAYER, Platform.SENSOR]
# , Platform.BINARY_SENSOR]
VERSION = "0.8.6"

DEFAULT_HOST = "avr"
DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 8102  # Some Pioneer AVRs use 23
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_TIMEOUT = 5
DEFAULT_SOURCES = {}

CONF_SOURCES = "sources"
CONF_PARAMS = "params"
CONF_IGNORE_ZONE_2 = "ignore_zone_2"  ## UI option only
CONF_IGNORE_ZONE_3 = "ignore_zone_3"  ## UI option only
CONF_IGNORE_HDZONE = "ignore_hdzone"  ## UI option only
CONF_QUERY_SOURCES = "query_sources"  ## UI option only, inferred from CONF_SOURCES
CONF_DEBUG_CONFIG = "debug_config"

## Deprecated options
OLD_CONF_IGNORE_ZONE_H = "ignore_zone_h"  ## deprecated
OLD_CONF_IGNORE_ZONE_Z = "ignore_zone_z"  ## deprecated
OLD_PARAM_HDZONE_SOURCES = "zone_z_sources"  ## deprecated
OLD_PARAM_DISABLE_AUTO_QUERY = "disable_autoquery"  ## deprecated

MIGRATE_CONFIG = {
    OLD_CONF_IGNORE_ZONE_H: CONF_IGNORE_HDZONE,
    OLD_CONF_IGNORE_ZONE_Z: CONF_IGNORE_HDZONE,
}
MIGRATE_PARAMS = {
    OLD_PARAM_HDZONE_SOURCES: PARAM_HDZONE_SOURCES,
    OLD_PARAM_DISABLE_AUTO_QUERY: PARAM_DISABLE_AUTO_QUERY,
}
MIGRATE_OPTIONS = {**MIGRATE_CONFIG, **MIGRATE_PARAMS}

PIONEER_OPTIONS_UPDATE = "pioneer_options_update"

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_SOURCES: {},
    CONF_PARAMS: {},
    CONF_IGNORE_ZONE_2: False,
    CONF_IGNORE_ZONE_3: False,
    CONF_IGNORE_HDZONE: False,
    CONF_DEBUG_CONFIG: {},
}
OPTIONS_ALL = OPTIONS_DEFAULTS.keys()

## Don't inherit defaults for these options/parameters
DEFAULTS_EXCLUDE = [
    PARAM_ZONE_1_SOURCES,
    PARAM_ZONE_2_SOURCES,
    PARAM_ZONE_3_SOURCES,
    PARAM_HDZONE_SOURCES,
]

CLASS_PIONEER = MediaPlayerDeviceClass.RECEIVER

SERVICE_SET_PANEL_LOCK = "set_panel_lock"
SERVICE_SET_REMOTE_LOCK = "set_remote_lock"
SERVICE_SET_DIMMER = "set_dimmer"
SERVICE_SET_TONE_SETTINGS = "set_tone_settings"
SERVICE_SET_AMP_SETTINGS = "set_amp_settings"
SERVICE_SET_TUNER_BAND = "set_tuner_band"
SERVICE_SET_FM_TUNER_FREQUENCY = "set_fm_tuner_frequency"
SERVICE_SET_AM_TUNER_FREQUENCY = "set_am_tuner_frequency"
SERVICE_SET_TUNER_PRESET = "set_tuner_preset"
SERVICE_SET_CHANNEL_LEVELS = "set_channel_levels"
SERVICE_SET_VIDEO_SETTINGS = "set_video_settings"
SERVICE_SET_DSP_SETTINGS = "set_dsp_settings"

## hass.data attributes
ATTR_PIONEER = "pioneer"
ATTR_COORDINATORS = "coordinators"
ATTR_DEVICE_INFO = "device_info"

## Config attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_PANEL_LOCK = "panel_lock"
ATTR_REMOTE_LOCK = "remote_lock"
ATTR_DIMMER = "dimmer"
ATTR_TONE = "tone"
ATTR_TREBLE = "treble"
ATTR_BASS = "bass"
ATTR_BAND = "band"
ATTR_FREQUENCY = "frequency"
ATTR_CLASS = "class"
ATTR_PRESET = "preset"
ATTR_CHANNEL = "channel"
ATTR_LEVEL = "level"

## State attribute lists
ATTRS_SYSTEM_PROMOTE = "speaker_system"
ATTRS_SYSTEM_EXCLUDE = ["speaker_system"]
ATTRS_AMP_PROMOTE = "speakers"
ATTRS_AMP_EXCLUDE = ["display", "dimmer", "speakers"]
ATTRS_DSP_PROMOTE = "signal_select"
ATTRS_DSP_EXCLUDE = ["signal_select"]
ATTRS_TUNER_PROMOTE = "frequency"
ATTRS_TUNER_EXCLUDE = ["frequency"]
ATTRS_VIDEO_PROMOTE = "signal_output_resolution"
ATTRS_VIDEO_EXCLUDE = ["signal_output_resolution", "1", "2", "3", "Z"]
ATTRS_AUDIO_PROMOTE = "input_signal"
ATTRS_AUDIO_EXCLUDE = ["input_signal", "1", "2", "3", "Z"]
## TODO: add binary_sensor for input_multichannel
ATTRS_ZONE_VIDEO_PROMOTE = "status"  # TODO
ATTRS_ZONE_VIDEO_EXCLUDE = []  # TODO
ATTRS_TONE_PROMOTE = "status"
ATTRS_TONE_EXCLUDE = ["status"]
ATTRS_CHANNEL_LEVEL_PROMOTE = "C"
ATTRS_CHANNEL_LEVEL_EXCLUDE = ["C"]
