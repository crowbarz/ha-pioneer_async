"""Pioneer AVR media_player platform."""

import logging
import json
from typing import Any
import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import PARAMS_ALL, PARAM_IGNORED_ZONES, PARAM_DISABLE_AUTO_QUERY

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
    STATE_UNKNOWN,
    EVENT_HOMEASSISTANT_CLOSE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SOURCES,
    CONF_PARAMS,
    CONF_DEBUG_CONFIG,
    MIGRATE_CONFIG,
    MIGRATE_PARAMS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_SOURCES,
    DEFAULT_SCAN_INTERVAL,
    PIONEER_OPTIONS_UPDATE,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
    CLASS_PIONEER,
    SERVICE_SET_PANEL_LOCK,
    SERVICE_SET_REMOTE_LOCK,
    SERVICE_SET_DIMMER,
    SERVICE_SET_TONE_SETTINGS,
    # SERVICE_SET_AMP_SETTINGS,
    SERVICE_SET_TUNER_BAND,
    SERVICE_SET_FM_TUNER_FREQUENCY,
    SERVICE_SET_AM_TUNER_FREQUENCY,
    SERVICE_SET_TUNER_PRESET,
    SERVICE_SET_CHANNEL_LEVELS,
    # SERVICE_SET_VIDEO_SETTINGS,
    # SERVICE_SET_DSP_SETTINGS,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
    ATTR_ENTITY_ID,
    ATTR_PANEL_LOCK,
    ATTR_REMOTE_LOCK,
    ATTR_DIMMER,
    ATTR_TONE,
    ATTR_TREBLE,
    ATTR_BASS,
    ATTR_BAND,
    ATTR_FREQUENCY,
    ATTR_CLASS,
    ATTR_PRESET,
    ATTR_CHANNEL,
    ATTR_LEVEL,
)
from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug

# from .device import get_device_unique_id, check_device_unique_id
from .entity_base import PioneerEntityBase

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PARAM_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
        vol.Optional(CONF_PARAMS, default={}): PARAM_SCHEMA,
        vol.Optional(CONF_DEBUG_CONFIG, default={}): vol.Schema(
            {}, extra=vol.ALLOW_EXTRA
        ),
    }
)

PIONEER_SET_PANEL_LOCK_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_PANEL_LOCK): cv.string,
}

PIONEER_SET_REMOTE_LOCK_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_REMOTE_LOCK): cv.boolean,
}

PIONEER_SERVICE_SET_DIMMER_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_DIMMER): cv.string,
}

PIONEER_SET_TONE_SETTINGS_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_TONE): cv.string,
    vol.Required(ATTR_TREBLE): vol.All(vol.Coerce(int), vol.Range(min=-6, max=6)),
    vol.Required(ATTR_BASS): vol.All(vol.Coerce(int), vol.Range(min=-6, max=6)),
}

# PIONEER_SET_AMP_SETTINGS_SCHEMA = {
#     vol.Required(ATTR_ENTITY_ID): cv.entity_id,
# }

PIONEER_SET_TUNER_BAND_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_BAND): str,
}


PIONEER_SET_FM_TUNER_FREQUENCY_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_FREQUENCY): vol.All(
        vol.Coerce(float), vol.Range(min=87.5, max=108)
    ),
}

PIONEER_SET_AM_TUNER_FREQUENCY_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_FREQUENCY): vol.All(
        vol.Coerce(int), vol.Range(min=530, max=1700)
    ),
}

PIONEER_SET_TUNER_PRESET_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_CLASS): cv.string,
    vol.Required(ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1, max=9)),
}

PIONEER_SET_CHANNEL_LEVELS_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_CHANNEL): cv.string,
    vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(float), vol.Range(min=-12, max=12)),
}

# PIONEER_SET_VIDEO_SETTINGS_SCHEMA = {
#     vol.Required(ATTR_ENTITY_ID): cv.entity_id,
# }

# PIONEER_SET_DSP_SETTINGS_SCHEMA = {
#     vol.Required(ATTR_ENTITY_ID): cv.entity_id,
# }


## Debug levels:
##  1: service calls
##  7: callback calls
##  8: update options flow
##  9: component load/unload
def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


# async def async_setup_shutdown_listener(
#     hass: HomeAssistant, entry: ConfigEntry, pioneer: PioneerAVR
# ) -> None:
#     """Set up handler for Home Assistant shutdown."""

#     async def _shutdown_listener(_event) -> None:
#         await pioneer.shutdown()

#     ## Create shutdown event listener
#     shutdown_listener = hass.bus.async_listen_once(
#         EVENT_HOMEASSISTANT_CLOSE, _shutdown_listener
#     )
#     if entry:
#         entry.async_on_unload(shutdown_listener)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pioneer AVR media_player from config entry."""
    if _debug_atlevel(9):
        _LOGGER.debug(
            ">> media_player.async_setup_entry(entry_id=%s, data=%s, options=%s)",
            config_entry.entry_id,
            config_entry.data,
            config_entry.options,
        )
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    coordinator_list = pioneer_data[ATTR_COORDINATORS]
    device_info_dict = pioneer_data[ATTR_DEVICE_INFO]

    _LOGGER.info("Adding entities for zones %s", pioneer.zones)
    entities = []
    main_entity = False
    for zone in pioneer.zones:
        entities.append(
            PioneerZone(
                pioneer,
                coordinator_list[zone],
                device_info_dict.get(zone),
                zone,
            )
        )
        if zone == "1":
            main_entity = True
        _LOGGER.debug("Created entity for zone %s", zone)
    if not main_entity:
        _LOGGER.error("Main zone not found on AVR")
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    ## TODO: defer update to first power on
    try:
        await pioneer.update()
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error(
            "Could not perform AVR initial update: %s: %s",
            type(exc).__name__,
            str(exc),
        )
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    async_add_entities(entities)

    ## Register platform specific services
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_PANEL_LOCK, PIONEER_SET_PANEL_LOCK_SCHEMA, "set_panel_lock"
    )
    platform.async_register_entity_service(
        SERVICE_SET_REMOTE_LOCK, PIONEER_SET_REMOTE_LOCK_SCHEMA, "set_remote_lock"
    )
    platform.async_register_entity_service(
        SERVICE_SET_DIMMER, PIONEER_SERVICE_SET_DIMMER_SCHEMA, "set_dimmer"
    )
    platform.async_register_entity_service(
        SERVICE_SET_TONE_SETTINGS, PIONEER_SET_TONE_SETTINGS_SCHEMA, "set_tone_settings"
    )
    # platform.async_register_entity_service(
    #     SERVICE_SET_AMP_SETTINGS, PIONEER_SET_AMP_SETTINGS_SCHEMA, "set_amp_settings"
    # )

    platform.async_register_entity_service(
        SERVICE_SET_TUNER_BAND,
        PIONEER_SET_TUNER_BAND_SCHEMA,
        "set_tuner_band",
    )
    platform.async_register_entity_service(
        SERVICE_SET_FM_TUNER_FREQUENCY,
        PIONEER_SET_FM_TUNER_FREQUENCY_SCHEMA,
        "set_fm_tuner_frequency",
    )
    platform.async_register_entity_service(
        SERVICE_SET_AM_TUNER_FREQUENCY,
        PIONEER_SET_AM_TUNER_FREQUENCY_SCHEMA,
        "set_am_tuner_frequency",
    )
    platform.async_register_entity_service(
        SERVICE_SET_TUNER_PRESET, PIONEER_SET_TUNER_PRESET_SCHEMA, "set_tuner_preset"
    )
    platform.async_register_entity_service(
        SERVICE_SET_CHANNEL_LEVELS,
        PIONEER_SET_CHANNEL_LEVELS_SCHEMA,
        "set_channel_levels",
    )
    # platform.async_register_entity_service(
    #     SERVICE_SET_VIDEO_SETTINGS, PIONEER_SET_VIDEO_SETTINGS_SCHEMA, "set_video_settings"
    # )
    # platform.async_register_entity_service(
    #     SERVICE_SET_DSP_SETTINGS, PIONEER_SET_DSP_SETTINGS_SCHEMA, "set_dsp_settings"
    # )


class PioneerZone(
    PioneerEntityBase, MediaPlayerEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Representation of a Pioneer zone."""

    _attr_device_class = CLASS_PIONEER
    _attr_name = None

    def __init__(
        self,
        pioneer: PioneerAVR,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: str,
    ) -> None:
        """Initialize the Pioneer zone."""
        if _debug_atlevel(9):
            _LOGGER.debug("PioneerZone.__init__(%s)", zone)
        super().__init__(pioneer, device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    # async def async_added_to_hass(self) -> None:
    #     """Complete the initialization."""
    #     await super().async_added_to_hass()
    #     if _debug_atlevel(9):
    #         _LOGGER.debug(">> PioneerZone.async_added_to_hass(%s)", self.zone)

    #     if self.zone == "1":
    #         self.async_on_remove(
    #             async_dispatcher_connect(
    #                 self.hass,
    #                 f"{PIONEER_OPTIONS_UPDATE}-{self.platform.config_entry.entry_id}",
    #                 self._async_update_options,
    #             )
    #         )

    # async def _async_update_options(self, data):
    #     """Change options when the options flow does."""
    #     ## TODO: modify to just unload/load entities on options change
    #     if _debug_atlevel(8):
    #         _LOGGER.debug(">> PioneerZone._async_update_options(data=%s)", data)
    #     pioneer = self.pioneer
    #     options = {**OPTIONS_DEFAULTS, **{k: data[k] for k in OPTIONS_ALL if k in data}}
    #     params = {k: data[k] for k in PARAMS_ALL if k in data}
    #     params.update(options.get(CONF_PARAMS, {}))
    #     sources = options[CONF_SOURCES]
    #     query_sources_current = pioneer.query_sources
    #     params_current = pioneer.get_params()
    #     pioneer.set_user_params(params)
    #     params_new = pioneer.get_params()
    #     if sources:
    #         pioneer.set_source_dict(sources)
    #     elif not query_sources_current:
    #         await pioneer.build_source_dict()
    #     await pioneer.set_timeout(options[CONF_TIMEOUT])
    #     await pioneer.set_scan_interval(options[CONF_SCAN_INTERVAL])
    #     ## NOTE: trigger zone update only after scan_interval update due to
    #     ##       wait_for missing cancellation when awaited coroutine
    #     ##       has already completed: https://bugs.python.org/issue42130
    #     ##       Mitigated also by using safe_wait_for()
    #     if params_new[PARAM_IGNORED_ZONES] != params_current[PARAM_IGNORED_ZONES]:
    #         await pioneer.update_zones()

    #     ## TODO: load/unload entities if ignored_zones has changed
    #     self.schedule_update_ha_state(force_refresh=True)

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the zone."""
        state = self.pioneer.power.get(self.zone)
        if state is None:
            return STATE_UNKNOWN
        return MediaPlayerState.ON if state else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        volume = self.pioneer.volume.get(self.zone)
        max_volume = self.pioneer.max_volume.get(self.zone)
        return volume / max_volume if (volume and max_volume) else float(0)

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self.pioneer.mute.get(self.zone, False)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        ## Automatically detect what features are supported by what parameters are available
        features = MediaPlayerEntityFeature(0)
        pioneer = self.pioneer
        if pioneer.power.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.TURN_ON
            features |= MediaPlayerEntityFeature.TURN_OFF
        if pioneer.volume.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.VOLUME_SET
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        if pioneer.mute.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if pioneer.source.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE

        ## Sound mode is only available on main zone, also it does not return an
        ## output if the AVR is off so add this manually until we figure out a better way
        ## Disable sound mode also if autoquery is disabled
        if self.zone == "1" and not pioneer.get_params().get(PARAM_DISABLE_AUTO_QUERY):
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        return features

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        ## Sound modes only supported on zones with speakers, return null if nothing found
        return self.pioneer.listening_mode

    @property
    def sound_mode_list(self) -> list[str]:
        """Returns all valid sound modes from aiopioneer."""
        listening_modes = self.pioneer.get_zone_listening_modes(self.zone)
        return (
            [v for _, v in sorted(listening_modes.items())] if listening_modes else None
        )

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        source_id = self.pioneer.source.get(self.zone)
        if source_id:
            return self.pioneer.get_source_name(source_id)
        else:
            return None

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self.pioneer.get_source_list(zone=self.zone)

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self.source

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        pioneer = self.pioneer
        attrs = {"sources_json": json.dumps(pioneer.get_source_dict(self.zone))}

        ## Return max volume attributes
        volume = pioneer.volume.get(self.zone)
        max_volume = pioneer.max_volume.get(self.zone)
        if volume is not None and max_volume is not None:
            if self.zone == "1":
                volume_db = volume / 2 - 80.5
            else:
                volume_db = volume - 81
            attrs |= {
                "device_volume": volume,
                "device_max_volume": max_volume,
                "device_volume_db": volume_db,
            }
        return attrs

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        return await self.pioneer.turn_on(self.zone)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        return await self.pioneer.turn_off(self.zone)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        return await self.pioneer.select_source(source, self.zone)

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        return await self.pioneer.volume_up(self.zone)

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        return await self.pioneer.volume_down(self.zone)

    async def async_set_volume_level(self, volume) -> None:
        """Set volume level, range 0..1."""
        max_volume = self.pioneer.max_volume.get(self.zone)
        return await self.pioneer.set_volume_level(
            round(volume * max_volume), self.zone
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            return await self.pioneer.mute_on(self.zone)
        else:
            return await self.pioneer.mute_off(self.zone)

    async def async_select_sound_mode(self, sound_mode) -> None:
        """Select the sound mode."""
        ## aiopioneer will translate sound modes
        return await self.pioneer.set_listening_mode(sound_mode, self.zone)

    async def async_update(self) -> None:
        """Poll properties on demand."""
        if _debug_atlevel(8):
            _LOGGER.debug(">> PioneerZone.async_update(%s)", self.zone)
        return await self.pioneer.update()

    async def set_panel_lock(self, panel_lock: str) -> None:
        """Set AVR panel lock."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_panel_lock(%s, panel_lock=%s)",
                self.zone,
                panel_lock,
            )
        return await self.pioneer.set_panel_lock(panel_lock)

    async def set_remote_lock(self, remote_lock: bool):
        """Set AVR remote lock."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_remote_lock(%s, remote_lock=%s)",
                self.zone,
                remote_lock,
            )
        return await self.pioneer.set_remote_lock(remote_lock)

    async def set_dimmer(self, dimmer: str):
        """Set AVR display dimmer."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_dimmer(%s, dimmer=%s)",
                self.zone,
                dimmer,
            )
        return await self.pioneer.set_dimmer(dimmer)

    async def set_tone_settings(self, tone: str, treble: int, bass: int):
        """Set AVR tone settings for zone."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_tone_settings(%s, tone=%s, treble=%d, bass=%d)",
                self.zone,
                tone,
                treble,
                bass,
            )
        return await self.pioneer.set_tone_settings(tone, treble, bass, zone=self.zone)

    async def set_tuner_band(self, band: str):
        """Set AVR tuner band."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_tuner_band(%s, band=%s)",
                self.zone,
                band,
            )
        return await self.pioneer.set_tuner_frequency(band)

    async def set_fm_tuner_frequency(self, frequency: float):
        """Set AVR AM tuner frequency."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_fm_tuner_frequency(%s, frequency=%f)",
                self.zone,
                frequency,
            )
        return await self.pioneer.set_tuner_frequency("FM", frequency)

    async def set_am_tuner_frequency(self, frequency: int):
        """Set AVR AM tuner frequency."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_am_tuner_frequency(%s, frequency=%d)",
                self.zone,
                frequency,
            )
        return await self.pioneer.set_tuner_frequency("AM", float(frequency))

    async def set_tuner_preset(self, **kwargs):
        """Set AVR tuner preset."""
        tuner_class = kwargs[ATTR_CLASS]  ## workaround for "class" as argument
        preset = kwargs[ATTR_PRESET]
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_tuner_preset(%s, class=%s, preset=%d)",
                self.zone,
                tuner_class,
                preset,
            )
        return await self.pioneer.set_tuner_preset(tuner_class, preset)

    async def set_channel_levels(self, channel: str, level: float):
        """Set AVR level (gain) for amplifier channel in zone."""
        if _debug_atlevel(1):
            _LOGGER.debug(
                ">> PioneerZone.set_channel_levels(%s, channel=%s, level=%f)",
                self.zone,
                channel,
                level,
            )
        return await self.pioneer.set_channel_levels(channel, level, zone=self.zone)
