"""Pioneer AVR media_player platform."""

from __future__ import annotations

import logging
import json
from typing import Any

import voluptuous as vol

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone
from aiopioneer.params import PARAM_VOLUME_STEP_ONLY

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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CLASS_PIONEER,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_CHANNEL_LEVELS,
    SERVICE_SET_AMP_SETTINGS,
    SERVICE_SET_VIDEO_SETTINGS,
    SERVICE_SET_DSP_SETTINGS,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
    ATTR_OPTIONS,
    ATTR_COMMAND,
    ATTR_PREFIX,
    ATTR_SUFFIX,
    ATTR_CHANNEL,
    ATTR_LEVEL,
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
from .coordinator import PioneerAVRZoneCoordinator
from .entity_base import PioneerEntityBase

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PARAM_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

PIONEER_SEND_COMMAND_SCHEMA = {
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PREFIX): cv.string,
    vol.Optional(ATTR_SUFFIX): cv.string,
}

PIONEER_SET_CHANNEL_LEVELS_SCHEMA = {
    vol.Required(ATTR_CHANNEL): cv.string,
    vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(float), vol.Range(min=-12, max=12)),
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
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    options: dict[str, Any] = pioneer_data[ATTR_OPTIONS]
    coordinators: list[PioneerAVRZoneCoordinator] = pioneer_data[ATTR_COORDINATORS]
    zone_device_info = pioneer_data[ATTR_DEVICE_INFO]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    if Zone.Z1 not in pioneer.properties.zones:
        _LOGGER.error("Main zone not found on AVR")
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    ## Add zone specific media_players
    entities = []
    _LOGGER.info("Adding entities for zones %s", pioneer.properties.zones)
    for zone in pioneer.properties.zones:
        entities.append(
            PioneerZone(
                pioneer,
                options,
                coordinator=coordinators[zone],
                device_info=zone_device_info[zone],
                zone=zone,
            )
        )
        _LOGGER.debug("Created entity for zone %s", zone)

    try:
        await pioneer.update()
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
        SERVICE_SET_CHANNEL_LEVELS,
        PIONEER_SET_CHANNEL_LEVELS_SCHEMA,
        "async_set_channel_levels",
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
    """Pioneer media_player class."""

    _attr_device_class = CLASS_PIONEER
    _attr_name = None
    _unrecorded_attributes = frozenset(
        {
            "sources_json",
            "device_max_volume",
        }
    )

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone,
    ) -> None:
        """Initialize the Pioneer media_player class."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

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
            self.zone == Zone.Z1
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
        if self.zone != Zone.Z1:
            return None
        return list(self.pioneer.get_listening_modes())

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.pioneer.properties.source_name.get(self.zone)

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self.pioneer.properties.get_source_list(self.zone)

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
            if self.zone == Zone.Z1:
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
        return await self.pioneer.update(zones=[self.zone])

    async def async_turn_on(self) -> None:
        """Turn the media player on."""

        async def turn_on() -> None:
            await self.pioneer.turn_on(zone=self.zone)

        await self.pioneer_command(turn_on)

    async def async_turn_off(self) -> None:
        """Turn off media player."""

        async def turn_off() -> None:
            await self.pioneer.turn_off(zone=self.zone)

        await self.pioneer_command(turn_off)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""

        async def select_source() -> None:
            await self.pioneer.select_source(source=source, zone=self.zone)

        await self.pioneer_command(select_source)

    async def async_volume_up(self) -> None:
        """Volume up media player."""

        async def volume_up() -> None:
            await self.pioneer.volume_up(zone=self.zone)

        await self.pioneer_command(volume_up)

    async def async_volume_down(self) -> None:
        """Volume down media player."""

        async def volume_down() -> None:
            await self.pioneer.volume_down(zone=self.zone)

        await self.pioneer_command(volume_down)

    async def async_media_play(self) -> None:
        """Send play command."""

        async def media_play() -> None:
            await self.pioneer.media_control("play")

        await self.pioneer_command(media_play)

    async def async_media_pause(self) -> None:
        """Send pause command."""

        async def media_pause() -> None:
            await self.pioneer.media_control("pause")

        await self.pioneer_command(media_pause)

    async def async_media_stop(self) -> None:
        """Send stop command."""

        async def media_stop() -> None:
            await self.pioneer.media_control("stop")

        await self.pioneer_command(media_stop)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""

        async def media_previous_track() -> None:
            await self.pioneer.media_control("previous")

        await self.pioneer_command(media_previous_track)

    async def async_media_next_track(self) -> None:
        """Send next track command."""

        async def media_next_track() -> None:
            return await self.pioneer.media_control("next")

        await self.pioneer_command(media_next_track)

    async def async_set_volume_level(self, volume) -> None:
        """Set volume level, range 0..1."""
        max_volume = self.pioneer.properties.max_volume.get(self.zone)

        async def set_volume_level() -> None:
            await self.pioneer.set_volume_level(
                round(volume * max_volume), zone=self.zone
            )

        if self.pioneer.params.get_param(PARAM_VOLUME_STEP_ONLY):
            await self.pioneer_command(set_volume_level)
        else:
            await self.pioneer_command(set_volume_level)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""

        async def mute_volume() -> None:
            if mute:
                await self.pioneer.mute_on(zone=self.zone)
            else:
                await self.pioneer.mute_off(zone=self.zone)

        await self.pioneer_command(mute_volume)

    async def async_select_sound_mode(self, sound_mode) -> None:
        """Select the sound mode."""

        async def select_sound_mode() -> None:
            ## aiopioneer will translate sound modes
            await self.pioneer.select_listening_mode(sound_mode)

        await self.pioneer_command(select_sound_mode)

    async def async_send_command(self, service_call: ServiceCall) -> ServiceResponse:
        """Send command to the AVR."""
        command = service_call.data[ATTR_COMMAND]
        prefix = service_call.data.get(ATTR_PREFIX, "")
        suffix = service_call.data.get(ATTR_SUFFIX, "")
        _LOGGER.info(
            ">> send_command(%s, command=%s, prefix=%s, suffix=%s)",
            self.zone,
            command,
            prefix,
            suffix,
        )

        async def send_command():
            return await self.pioneer.send_command(
                command, zone=self.zone, prefix=prefix, suffix=suffix
            )

        resp = await self.pioneer_command(send_command, command=command)
        if service_call.return_response:
            return resp

    async def async_set_channel_levels(self, channel: str, level: float) -> None:
        """Set AVR level (gain) for amplifier channel in zone."""

        async def set_channel_levels() -> None:
            await self.pioneer.set_channel_levels(channel, level, zone=self.zone)

        await self.pioneer_command(set_channel_levels)

    async def async_set_amp_settings(self, **kwargs) -> None:
        """Set AVR amp settings."""

        async def set_amp_settings() -> None:
            await self.pioneer.set_amp_settings(**kwargs)

        await self.pioneer_command(set_amp_settings)

    async def async_set_video_settings(self, **kwargs) -> None:
        """Set AVR video settings."""

        async def set_video_settings() -> None:
            await self.pioneer.set_video_settings(zone=self.zone, **kwargs)

        await self.pioneer_command(set_video_settings)

    async def async_set_dsp_settings(self, **kwargs) -> None:
        """Set AVR DSP settings."""

        async def set_dsp_settings() -> None:
            await self.pioneer.set_dsp_settings(zone=self.zone, **kwargs)

        await self.pioneer_command(set_dsp_settings)
