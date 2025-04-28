"""Constants for the pioneer_async integration."""

from datetime import timedelta

from aiopioneer.const import Zone
from aiopioneer.params import (
    PARAM_MODEL,
    PARAM_HDZONE_SOURCES,
    PARAM_DISABLE_AUTO_QUERY,
    PARAM_RETRY_COUNT,
)

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.const import (
    Platform,
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
)

DOMAIN = "pioneer_async"
PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]
VERSION = "0.11.0"
CONFIG_ENTRY_VERSION = 5
CONFIG_ENTRY_VERSION_MINOR = 3

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

## Deprecated options
# CONF_NAME  ## deprecated
OLD_CONF_IGNORE_ZONE_H = "ignore_zone_h"  ## deprecated
OLD_CONF_IGNORE_ZONE_Z = "ignore_zone_z"  ## deprecated
OLD_CONF_DEBUG_CONFIG = "debug_config"  ## deprecated
OLD_PARAM_HDZONE_SOURCES = "zone_z_sources"  ## deprecated
OLD_PARAM_DISABLE_AUTO_QUERY = "disable_autoquery"  ## deprecated
OLD_CONF_REPEAT_COUNT = "repeat_count"
OLD_CONF_DEBUG_INTEGRATION = "debug_integration"  # integration load/unload
OLD_CONF_DEBUG_CONFIG_FLOW = "debug_config_flow"  # config and options flow
OLD_CONF_DEBUG_ACTION = "debug_action"  # action

MIGRATE_CONFIG = {
    CONF_NAME: None,
    OLD_CONF_DEBUG_CONFIG: None,
    OLD_CONF_IGNORE_ZONE_H: CONF_IGNORE_HDZONE,
    OLD_CONF_IGNORE_ZONE_Z: CONF_IGNORE_HDZONE,
    OLD_PARAM_HDZONE_SOURCES: PARAM_HDZONE_SOURCES,
    OLD_PARAM_DISABLE_AUTO_QUERY: PARAM_DISABLE_AUTO_QUERY,
    OLD_CONF_REPEAT_COUNT: PARAM_RETRY_COUNT,
    OLD_CONF_DEBUG_INTEGRATION: None,
    OLD_CONF_DEBUG_CONFIG_FLOW: None,
    OLD_CONF_DEBUG_ACTION: None,
}

PIONEER_OPTIONS_UPDATE = "pioneer_options_update"

DATA_DEFAULTS = {
    PARAM_MODEL: "",
}
DATA_ALL = [
    CONF_HOST,
    CONF_PORT,
    *DATA_DEFAULTS.keys(),
]

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.total_seconds(),
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_SOURCES: {},
    CONF_PARAMS: {},
    CONF_IGNORE_ZONE_2: False,
    CONF_IGNORE_ZONE_3: False,
    CONF_IGNORE_HDZONE: False,
    ## NOTE: CONF_QUERY_SOURCES is not retained in config entry
}
OPTIONS_ALL = OPTIONS_DEFAULTS.keys()
OPTIONS_DICT_INT_KEY = [
    CONF_SOURCES,
    CONF_PARAMS,
]

CONFIG_IGNORE_ZONES = {
    Zone.Z2: CONF_IGNORE_ZONE_2,
    Zone.Z3: CONF_IGNORE_ZONE_3,
    Zone.HDZ: CONF_IGNORE_HDZONE,
}
CONFIG_DEFAULTS = OPTIONS_DEFAULTS | DATA_DEFAULTS  # default params from aiopioneer

CLASS_PIONEER = MediaPlayerDeviceClass.RECEIVER

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_AMP_SETTINGS = "set_amp_settings"
SERVICE_SET_CHANNEL_LEVELS = "set_channel_levels"
SERVICE_SET_VIDEO_SETTINGS = "set_video_settings"
SERVICE_SET_DSP_SETTINGS = "set_dsp_settings"

## hass.data attributes
ATTR_PIONEER = "pioneer"
ATTR_COORDINATORS = "coordinators"
ATTR_DEVICE_INFO = "device_info"
ATTR_DEVICE_ENTRY = "device_entry"
ATTR_OPTIONS = "options"

## Config attributes
ATTR_COMMAND = "command"
ATTR_PREFIX = "prefix"
ATTR_SUFFIX = "suffix"
ATTR_ENTITY_ID = "entity_id"
ATTR_CHANNEL = "channel"
ATTR_LEVEL = "level"

## Amp settings attributes
ATTR_AMP_SPEAKER_MODE = "speaker_mode"
ATTR_AMP_HDMI_OUT = "hdmi_out"
ATTR_AMP_HDMI3_OUT = "hdmi3_out"
ATTR_AMP_HDMI_AUDIO = "hdmi_audio"
ATTR_AMP_PQLS = "pqls"
ATTR_AMP_DIMMER = "dimmer"
ATTR_AMP_SLEEP_TIME = "sleep_time"
ATTR_AMP_MODE = "mode"
ATTR_AMP_PANEL_LOCK = "panel_lock"
ATTR_AMP_REMOTE_LOCK = "remote_lock"

## Video settings attributes
ATTR_VIDEO_RESOLUTION = "resolution"
ATTR_VIDEO_CONVERTER = "converter"
ATTR_VIDEO_PURE_CINEMA = "pure_cinema"
ATTR_VIDEO_PROG_MOTION = "prog_motion"
ATTR_VIDEO_STREAM_SMOOTHER = "stream_smoother"
ATTR_VIDEO_ADVANCED_VIDEO_ADJUST = "advanced_video_adjust"
ATTR_VIDEO_YNR = "ynr"
ATTR_VIDEO_CNR = "cnr"
ATTR_VIDEO_BNR = "bnr"
ATTR_VIDEO_MNR = "mnr"
ATTR_VIDEO_DETAIL = "detail"
ATTR_VIDEO_SHARPNESS = "sharpness"
ATTR_VIDEO_BRIGHTNESS = "brightness"
ATTR_VIDEO_CONTRAST = "contrast"
ATTR_VIDEO_HUE = "hue"
ATTR_VIDEO_CHROMA = "chroma"
ATTR_VIDEO_BLACK_SETUP = "black_setup"
ATTR_VIDEO_ASPECT = "aspect"
ATTR_VIDEO_SUPER_RESOLUTION = "super_resolution"

## DSP settings attributes
ATTR_DSP_MCACC_MEMORY_SET = "mcacc_memory_set"
ATTR_DSP_PHASE_CONTROL = "phase_control"
ATTR_DSP_PHASE_CONTROL_PLUS = "phase_control_plus"
ATTR_DSP_VIRTUAL_SPEAKERS = "virtual_speakers"
ATTR_DSP_VIRTUAL_SB = "virtual_sb"
ATTR_DSP_VIRTUAL_HEIGHT = "virtual_height"
ATTR_DSP_VIRTUAL_WIDE = "virtual_wide"
ATTR_DSP_VIRTUAL_DEPTH = "virtual_depth"
ATTR_DSP_SOUND_RETRIEVER = "sound_retriever"
ATTR_DSP_SIGNAL_SELECT = "signal_select"
ATTR_DSP_INPUT_ATTENUATOR = "input_attenuator"
ATTR_DSP_EQ = "eq"
ATTR_DSP_STANDING_WAVE = "standing_wave"
ATTR_DSP_SOUND_DELAY = "sound_delay"
ATTR_DSP_DIGITAL_NOISE_REDUCTION = "digital_noise_reduction"
ATTR_DSP_DIALOG_ENHANCEMENT = "dialog_enhancement"
ATTR_DSP_AUDIO_SCALER = "audio_scaler"
ATTR_DSP_HI_BIT = "hi_bit"
ATTR_DSP_UP_SAMPLING = "up_sampling"
ATTR_DSP_DIGITAL_FILTER = "digital_filter"
ATTR_DSP_DUAL_MONO = "dual_mono"
ATTR_DSP_FIXED_PCM = "fixed_pcm"
ATTR_DSP_DYNAMIC_RANGE = "dynamic_range"
ATTR_DSP_LFE_ATTENUATOR = "lfe_attenuator"
ATTR_DSP_SACD_GAIN = "sacd_gain"
ATTR_DSP_AUTO_DELAY = "auto_delay"
ATTR_DSP_CENTER_WIDTH = "center_width"
ATTR_DSP_PANORAMA = "panorama"
ATTR_DSP_DIMENSION = "dimension"
ATTR_DSP_CENTER_IMAGE = "center_image"
ATTR_DSP_EFFECT = "effect"
ATTR_DSP_HEIGHT_GAIN = "height_gain"
ATTR_DSP_LOUDNESS_MANAGEMENT = "loudness_management"
ATTR_DSP_CENTER_SPREAD = "center_spread"
ATTR_DSP_RENDERING_MODE = "rendering_mode"

## Tuner attributes
ATTR_TUNER_AM_FREQUENCY_STEP = "am_frequency_step"
