"""Pioneer AVR media_player platform."""

from __future__ import annotations

import logging
import json
from typing import Any

import voluptuous as vol

from aiopioneer.const import Zone

from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CLASS_PIONEER,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_AMP_SETTINGS,
    SERVICE_SET_VIDEO_SETTINGS,
    SERVICE_SET_DSP_SETTINGS,
    PioneerData,
    ATTR_COMMAND,
    ATTR_PREFIX,
    ATTR_SUFFIX,
    ATTR_ARGS,
    ATTR_AMP_SPEAKER_MODE,
    ATTR_AMP_HDMI_OUT,
    ATTR_AMP_HDMI3_OUT,
    ATTR_AMP_HDMI_AUDIO,
    ATTR_AMP_PQLS,
    ATTR_AMP_DIMMER,
    ATTR_AMP_SLEEP_TIME,
    ATTR_AMP_MODE,
    ATTR_AMP_PANEL_LOCK,
    ATTR_AMP_REMOTE_LOCK,
    ATTR_VIDEO_RESOLUTION,
    ATTR_VIDEO_CONVERTER,
    ATTR_VIDEO_PURE_CINEMA,
    ATTR_VIDEO_PROG_MOTION,
    ATTR_VIDEO_STREAM_SMOOTHER,
    ATTR_VIDEO_ADVANCED_VIDEO_ADJUST,
    ATTR_VIDEO_YNR,
    ATTR_VIDEO_CNR,
    ATTR_VIDEO_BNR,
    ATTR_VIDEO_MNR,
    ATTR_VIDEO_DETAIL,
    ATTR_VIDEO_SHARPNESS,
    ATTR_VIDEO_BRIGHTNESS,
    ATTR_VIDEO_CONTRAST,
    ATTR_VIDEO_HUE,
    ATTR_VIDEO_CHROMA,
    ATTR_VIDEO_BLACK_SETUP,
    ATTR_VIDEO_ASPECT,
    ATTR_VIDEO_SUPER_RESOLUTION,
    ATTR_DSP_MCACC_MEMORY_SET,
    ATTR_DSP_PHASE_CONTROL,
    ATTR_DSP_PHASE_CONTROL_PLUS,
    ATTR_DSP_VIRTUAL_SPEAKERS,
    ATTR_DSP_VIRTUAL_SB,
    ATTR_DSP_VIRTUAL_HEIGHT,
    ATTR_DSP_VIRTUAL_WIDE,
    ATTR_DSP_VIRTUAL_DEPTH,
    ATTR_DSP_SOUND_RETRIEVER,
    ATTR_DSP_SIGNAL_SELECT,
    ATTR_DSP_INPUT_ATTENUATOR,
    ATTR_DSP_EQ,
    ATTR_DSP_STANDING_WAVE,
    ATTR_DSP_SOUND_DELAY,
    ATTR_DSP_DIGITAL_NOISE_REDUCTION,
    ATTR_DSP_DIALOG_ENHANCEMENT,
    ATTR_DSP_AUDIO_SCALER,
    ATTR_DSP_HI_BIT,
    ATTR_DSP_UP_SAMPLING,
    ATTR_DSP_DIGITAL_FILTER,
    ATTR_DSP_DUAL_MONO,
    ATTR_DSP_FIXED_PCM,
    ATTR_DSP_DYNAMIC_RANGE,
    ATTR_DSP_LFE_ATTENUATOR,
    ATTR_DSP_SACD_GAIN,
    ATTR_DSP_AUTO_DELAY,
    ATTR_DSP_CENTER_WIDTH,
    ATTR_DSP_PANORAMA,
    ATTR_DSP_DIMENSION,
    ATTR_DSP_CENTER_IMAGE,
    ATTR_DSP_EFFECT,
    ATTR_DSP_HEIGHT_GAIN,
    ATTR_DSP_LOUDNESS_MANAGEMENT,
    ATTR_DSP_CENTER_SPREAD,
    ATTR_DSP_RENDERING_MODE,
)
from .entity_base import PioneerEntityBase

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PARAM_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

PIONEER_SEND_COMMAND_SCHEMA = {
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PREFIX): cv.string,
    vol.Optional(ATTR_SUFFIX): cv.string,
    vol.Optional(ATTR_ARGS): cv.ensure_list,
}

PIONEER_SET_AMP_SETTINGS_SCHEMA = {
    vol.Optional(ATTR_AMP_SPEAKER_MODE): cv.string,
    vol.Optional(ATTR_AMP_HDMI_OUT): cv.string,
    vol.Optional(ATTR_AMP_HDMI3_OUT): cv.boolean,
    vol.Optional(ATTR_AMP_HDMI_AUDIO): cv.string,
    vol.Optional(ATTR_AMP_PQLS): cv.string,
    vol.Optional(ATTR_AMP_DIMMER): cv.string,
    vol.Optional(ATTR_AMP_SLEEP_TIME): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=90)
    ),
    vol.Optional(ATTR_AMP_MODE): cv.string,
    vol.Optional(ATTR_AMP_PANEL_LOCK): cv.string,
    vol.Optional(ATTR_AMP_REMOTE_LOCK): cv.boolean,
}

PIONEER_SET_VIDEO_SETTINGS_SCHEMA = {
    vol.Optional(ATTR_VIDEO_RESOLUTION): cv.string,
    vol.Optional(ATTR_VIDEO_CONVERTER): cv.boolean,
    vol.Optional(ATTR_VIDEO_PURE_CINEMA): cv.string,
    vol.Optional(ATTR_VIDEO_PROG_MOTION): vol.All(
        vol.Coerce(int), vol.Range(min=-4, max=4)
    ),
    vol.Optional(ATTR_VIDEO_STREAM_SMOOTHER): cv.string,
    vol.Optional(ATTR_VIDEO_ADVANCED_VIDEO_ADJUST): cv.string,
    vol.Optional(ATTR_VIDEO_YNR): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional(ATTR_VIDEO_CNR): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional(ATTR_VIDEO_BNR): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional(ATTR_VIDEO_MNR): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional(ATTR_VIDEO_DETAIL): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional(ATTR_VIDEO_SHARPNESS): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=8)
    ),
    vol.Optional(ATTR_VIDEO_BRIGHTNESS): vol.All(
        vol.Coerce(int), vol.Range(min=-6, max=6)
    ),
    vol.Optional(ATTR_VIDEO_CONTRAST): vol.All(
        vol.Coerce(int), vol.Range(min=-6, max=6)
    ),
    vol.Optional(ATTR_VIDEO_HUE): vol.All(vol.Coerce(int), vol.Range(min=-6, max=6)),
    vol.Optional(ATTR_VIDEO_CHROMA): vol.All(vol.Coerce(int), vol.Range(min=-6, max=6)),
    vol.Optional(ATTR_VIDEO_BLACK_SETUP): cv.boolean,
    vol.Optional(ATTR_VIDEO_ASPECT): cv.string,
    vol.Optional(ATTR_VIDEO_SUPER_RESOLUTION): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=3)
    ),
}

PIONEER_SET_DSP_SETTINGS_SCHEMA = {
    vol.Optional(ATTR_DSP_MCACC_MEMORY_SET): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=6)
    ),
    vol.Optional(ATTR_DSP_PHASE_CONTROL): cv.string,
    vol.Optional(ATTR_DSP_PHASE_CONTROL_PLUS): vol.Or(
        "auto", vol.All(vol.Coerce(int), vol.Range(min=0, max=16))
    ),
    vol.Optional(ATTR_DSP_VIRTUAL_SPEAKERS): cv.string,
    vol.Optional(ATTR_DSP_VIRTUAL_SB): cv.boolean,
    vol.Optional(ATTR_DSP_VIRTUAL_HEIGHT): cv.boolean,
    vol.Optional(ATTR_DSP_VIRTUAL_WIDE): cv.boolean,
    vol.Optional(ATTR_DSP_VIRTUAL_DEPTH): cv.string,
    vol.Optional(ATTR_DSP_SOUND_RETRIEVER): cv.boolean,
    vol.Optional(ATTR_DSP_SIGNAL_SELECT): cv.string,
    vol.Optional(ATTR_DSP_INPUT_ATTENUATOR): cv.boolean,
    vol.Optional(ATTR_DSP_EQ): cv.boolean,
    vol.Optional(ATTR_DSP_STANDING_WAVE): cv.boolean,
    vol.Optional(ATTR_DSP_SOUND_DELAY): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=800)
    ),
    vol.Optional(ATTR_DSP_DIGITAL_NOISE_REDUCTION): cv.boolean,
    vol.Optional(ATTR_DSP_DIALOG_ENHANCEMENT): cv.string,
    vol.Optional(ATTR_DSP_AUDIO_SCALER): cv.string,
    vol.Optional(ATTR_DSP_HI_BIT): cv.boolean,
    vol.Optional(ATTR_DSP_UP_SAMPLING): cv.string,
    vol.Optional(ATTR_DSP_DIGITAL_FILTER): cv.string,
    vol.Optional(ATTR_DSP_DUAL_MONO): cv.string,
    vol.Optional(ATTR_DSP_FIXED_PCM): cv.boolean,
    vol.Optional(ATTR_DSP_DYNAMIC_RANGE): cv.string,
    vol.Optional(ATTR_DSP_LFE_ATTENUATOR): vol.Or(
        "off", vol.All(vol.Coerce(int), vol.Range(min=-20, max=0))
    ),
    vol.Optional(ATTR_DSP_SACD_GAIN): vol.All(vol.Coerce(int), vol.Or(0, 6)),
    vol.Optional(ATTR_DSP_AUTO_DELAY): cv.boolean,
    vol.Optional(ATTR_DSP_CENTER_WIDTH): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=7)
    ),
    vol.Optional(ATTR_DSP_PANORAMA): cv.boolean,
    vol.Optional(ATTR_DSP_DIMENSION): vol.All(
        vol.Coerce(int), vol.Range(min=-3, max=3)
    ),
    vol.Optional(ATTR_DSP_CENTER_IMAGE): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=1)
    ),
    vol.Optional(ATTR_DSP_EFFECT): vol.All(vol.Coerce(int), vol.Range(min=10, max=90)),
    vol.Optional(ATTR_DSP_HEIGHT_GAIN): cv.string,
    vol.Optional(ATTR_DSP_LOUDNESS_MANAGEMENT): cv.boolean,
    vol.Optional(ATTR_DSP_CENTER_SPREAD): cv.boolean,
    vol.Optional(ATTR_DSP_RENDERING_MODE): cv.string,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform."""
    pioneer_data: PioneerData = hass.data[DOMAIN][config_entry.entry_id]
    pioneer = pioneer_data.pioneer
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    if Zone.Z1 not in pioneer.properties.zones:
        _LOGGER.error("Main zone not found on AVR")
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    ## Add zone media_player entities
    entities = []
    _LOGGER.info("Adding entities for zones %s", pioneer.properties.zones)
    for zone in pioneer.properties.zones:
        entities.append(PioneerZone(pioneer_data, zone=zone))
        _LOGGER.debug("Created entity for zone %s", zone)

    try:
        await pioneer.refresh()
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error("Could not perform AVR initial update: %s", repr(exc))
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    async_add_entities(entities)

    ## Register platform specific services
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        PIONEER_SEND_COMMAND_SCHEMA,
        PioneerZone.async_send_command,
        supports_response=SupportsResponse.OPTIONAL,
    )
    platform.async_register_entity_service(
        SERVICE_SET_AMP_SETTINGS,
        PIONEER_SET_AMP_SETTINGS_SCHEMA,
        "async_set_amp_settings",
    )
    platform.async_register_entity_service(
        SERVICE_SET_VIDEO_SETTINGS,
        PIONEER_SET_VIDEO_SETTINGS_SCHEMA,
        "async_set_video_settings",
    )
    platform.async_register_entity_service(
        SERVICE_SET_DSP_SETTINGS,
        PIONEER_SET_DSP_SETTINGS_SCHEMA,
        "async_set_dsp_settings",
    )


class PioneerZone(
    PioneerEntityBase, MediaPlayerEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer media_player entity class."""

    _attr_device_class = CLASS_PIONEER
    _attr_name = None
    _unrecorded_attributes = frozenset(
        {
            "sources_json",
            "device_max_volume",
        }
    )

    def __init__(self, pioneer_data: PioneerData, zone: Zone) -> None:
        """Initialize the Pioneer media_player class."""
        super().__init__(pioneer_data, zone=zone)
        CoordinatorEntity.__init__(self, pioneer_data.coordinators[zone])

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the zone."""
        state = self.pioneer.properties.power.get(self.zone)
        if state is None:
            return STATE_UNKNOWN
        return MediaPlayerState.ON if state else MediaPlayerState.OFF

    @property
    def available(self) -> bool:
        """Returns whether the AVR is available. Available even when zone is off."""
        return self.pioneer.available

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        volume = self.pioneer.properties.volume.get(self.zone)
        max_volume = self.pioneer.properties.max_volume.get(self.zone)
        return volume / max_volume if (volume and max_volume) else float(0)

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self.pioneer.properties.mute.get(self.zone, False)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        ## Automatically detect what features are supported by what parameters are available
        features = MediaPlayerEntityFeature(0)
        pioneer = self.pioneer
        if pioneer.properties.power.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.TURN_ON
            features |= MediaPlayerEntityFeature.TURN_OFF
        if pioneer.properties.volume.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.VOLUME_SET
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        if pioneer.properties.mute.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if pioneer.properties.source_name.get(self.zone) is not None:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE

        ## Sound mode is only available on main zone when it is powered on
        ## and listening modes are available
        if (
            self.zone is Zone.Z1
            and pioneer.properties.power.get(self.zone)
            and pioneer.get_listening_modes()
        ):
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        control_commands = pioneer.properties.get_supported_media_controls(self.zone)
        if control_commands:
            if "play" in control_commands:
                features |= MediaPlayerEntityFeature.PLAY
            if "pause" in control_commands:
                features |= MediaPlayerEntityFeature.PAUSE
            if "stop" in control_commands:
                features |= MediaPlayerEntityFeature.STOP
            if "previous" in control_commands:
                features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
            if "next" in control_commands:
                features |= MediaPlayerEntityFeature.NEXT_TRACK

        return features

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        ## Sound modes only supported on zones with speakers, return null if nothing found
        return self.pioneer.properties.listening_mode

    @property
    def sound_mode_list(self) -> list[str]:
        """Returns all valid sound modes from aiopioneer."""
        if self.zone is not Zone.Z1:
            return None
        return list(self.pioneer.get_listening_modes())

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.pioneer.properties.source_name.get(self.zone)

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return list(self.pioneer.properties.get_source_dict(self.zone).values())

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self.source

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        pioneer = self.pioneer
        attrs = {
            "sources_json": json.dumps(pioneer.properties.get_source_dict(self.zone))
        }

        ## Return max volume attributes
        volume = pioneer.properties.volume.get(self.zone)
        max_volume = pioneer.properties.max_volume.get(self.zone)
        if volume is not None and max_volume is not None:
            if self.zone is Zone.Z1:
                volume_db = volume / 2 - 80.5
            else:
                volume_db = volume - 81
            attrs |= {
                "device_volume": volume,
                "device_max_volume": max_volume,
                "device_volume_db": volume_db,
            }
        return attrs

    async def async_update(self) -> None:
        """Refresh zone properties on demand."""
        _LOGGER.debug(">> PioneerZone.async_update(%s)", self.zone)
        await self.pioneer.refresh(zones=[self.zone])

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.pioneer_command(self.pioneer.power_on, zone=self.zone)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self.pioneer_command(self.pioneer.power_off, zone=self.zone)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.pioneer_command(
            self.pioneer.select_source, source=source, zone=self.zone
        )

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.pioneer_command(self.pioneer.volume_up, zone=self.zone)

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.pioneer_command(self.pioneer.volume_down, zone=self.zone)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.pioneer_command(
            self.pioneer.media_control, action="play", zone=self.zone
        )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.pioneer_command(
            self.pioneer.media_control, action="pause", zone=self.zone
        )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.pioneer_command(
            self.pioneer.media_control, action="stop", zone=self.zone
        )

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.pioneer_command(
            await self.pioneer.media_control, action="previous", zone=self.zone
        )

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.pioneer_command(
            self.pioneer.media_control, action="next", zone=self.zone
        )

    async def async_set_volume_level(self, volume) -> None:
        """Set volume level, range 0..1."""
        max_volume = self.pioneer.properties.max_volume.get(self.zone)
        target_volume = round(volume * max_volume)
        await self.pioneer_command(
            self.pioneer.set_volume_level, target_volume=target_volume, zone=self.zone
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            await self.pioneer_command(self.pioneer.mute_on, zone=self.zone)
        else:
            await self.pioneer_command(self.pioneer.mute_off, zone=self.zone)

    async def async_select_sound_mode(self, sound_mode) -> None:
        """Select the sound mode."""
        await self.pioneer_command(self.pioneer.select_listening_mode, mode=sound_mode)

    async def async_send_command(self, service_call: ServiceCall) -> ServiceResponse:
        """Send command to the AVR."""
        command: str = service_call.data[ATTR_COMMAND]
        prefix: str = service_call.data.get(ATTR_PREFIX)
        suffix: str = service_call.data.get(ATTR_SUFFIX)
        args: list = service_call.data.get(ATTR_ARGS, [])
        _LOGGER.debug(
            ">> send_command(%s, command=%s, prefix=%s, suffix=%s, args=%s)",
            self.zone,
            command,
            prefix,
            suffix,
            args,
        )
        resp = await self.pioneer_command(
            command, *args, zone=self.zone, prefix=prefix, suffix=suffix
        )
        if service_call.return_response:
            return resp

    async def async_set_amp_settings(self, **kwargs) -> None:
        """Set AVR amp settings."""
        await self.pioneer_command(self.pioneer.set_amp_settings, **kwargs)

    async def async_set_video_settings(self, **kwargs) -> None:
        """Set AVR video settings."""
        await self.pioneer_command(
            self.pioneer.set_video_settings, zone=self.zone, **kwargs
        )

    async def async_set_dsp_settings(self, **kwargs) -> None:
        """Set AVR DSP settings."""
        await self.pioneer_command(
            self.pioneer.set_dsp_settings, zone=self.zone, **kwargs
        )
