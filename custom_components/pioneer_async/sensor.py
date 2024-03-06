"""Pioneer AVR sensors."""

from __future__ import annotations

import logging

from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones


from homeassistant.components.sensor import (
    # SensorDeviceClass,
    SensorEntity,
    # SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    # OPTIONS_DEFAULTS,
    # OPTIONS_ALL,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
    ATTRS_SYSTEM_PROMOTE,
    ATTRS_SYSTEM_EXCLUDE,
    ATTRS_AMP_PROMOTE,
    ATTRS_AMP_EXCLUDE,
    ATTRS_DSP_PROMOTE,
    ATTRS_DSP_EXCLUDE,
    ATTRS_TUNER_PROMOTE,
    ATTRS_TUNER_EXCLUDE,
    ATTRS_VIDEO_PROMOTE,
    ATTRS_VIDEO_EXCLUDE,
    ATTRS_AUDIO_PROMOTE,
    ATTRS_AUDIO_EXCLUDE,
    ATTRS_ZONE_VIDEO_PROMOTE,
    ATTRS_ZONE_VIDEO_EXCLUDE,
    ATTRS_TONE_PROMOTE,
    ATTRS_TONE_EXCLUDE,
    ATTRS_CHANNEL_LEVEL_PROMOTE,
    ATTRS_CHANNEL_LEVEL_EXCLUDE,
)

from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug


_LOGGER = logging.getLogger(__name__)


## Debug levels:
##  1: service calls
##  7: callback calls
##  8: update options flow
##  9: component load/unload
def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    if _debug_atlevel(9):
        _LOGGER.debug(
            ">> sensor.async_setup_entry(entry_id=%s, data=%s, options=%s)",
            config_entry.entry_id,
            config_entry.data,
            config_entry.options,
        )
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    coordinator_list = pioneer_data[ATTR_COORDINATORS]
    device_info_dict: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]

    entities = []

    ## Add top level sensors
    zone = str(Zones.Z1)  ## TODO: move to Zones.ALL
    device_info = device_info_dict.get("top")
    coordinator = coordinator_list[zone]
    entities.append(PioneerDisplaySensor(pioneer, coordinator, device_info))
    entities.append(PioneerSystemSensor(pioneer, coordinator, device_info))
    entities.append(PioneerAmpSensor(pioneer, coordinator, device_info))
    entities.append(PioneerDspSensor(pioneer, coordinator, device_info))
    entities.append(PioneerTunerSensor(pioneer, coordinator, device_info))
    entities.append(PioneerVideoSensor(pioneer, coordinator, device_info))
    entities.append(PioneerAudioSensor(pioneer, coordinator, device_info))

    ## Add zone specific sensors
    for zone in pioneer.zones:
        device_info = device_info_dict.get(zone)
        coordinator = coordinator_list[zone]
        ## TODO: for all zones excluding known zones that do not work, entities.append()
        if zone == "1":
            entities.append(
                PioneerZoneVideoSensor(pioneer, zone, coordinator, device_info)
            )
            entities.append(PioneerToneSensor(pioneer, zone, coordinator, device_info))
            entities.append(
                PioneerChannelLevelSensor(pioneer, zone, coordinator, device_info)
            )

    async_add_entities(entities)


class PioneerSensor(SensorEntity, CoordinatorEntity):
    """Pioneer sensor base class."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # _attr_entity_registry_enabled_default = False  ## TODO: disable when debug over
    _attr_entity_registry_visible_default = True

    def __init__(
        self,
        pioneer: PioneerAVR,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Pioneer AVR display sensor."""
        if _debug_atlevel(9):
            _LOGGER.debug("%s.__init__()", type(self).__name__)
        self.pioneer = pioneer
        self.coordinator = coordinator
        self._attr_device_info = device_info
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        entry_id = self.platform.config_entry.entry_id
        return f"{entry_id}-{type(self).__name__}"

    @property
    def available(self) -> bool:
        """Returns whether the device is available."""
        return self.pioneer.available


class PioneerZoneSensor(PioneerSensor):
    """Pioneer zone sensor base class."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        zone: Zones,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Pioneer AVR display sensor."""
        self.zone = zone
        super().__init__(pioneer, coordinator, device_info)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        entry_id = self.platform.config_entry.entry_id
        return f"{entry_id}-{self.zone}-{type(self).__name__}"

    @property
    def available(self) -> bool:
        """Returns whether the device is available."""
        return self.pioneer.available and self.zone in self.pioneer.zones


class PioneerDisplaySensor(PioneerSensor):
    """Pioneer AVR display sensor."""

    _attr_name = "Display"
    _attr_entity_registry_enabled_default = True

    _unrecorded_attributes = frozenset({"dimmer"})

    @property
    def native_value(self) -> str:
        """Retrieve current display value."""
        return self.pioneer.amp.get("display", "").strip()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {"dimmer": self.pioneer.amp.get("dimmer", "")}


class PioneerSystemSensor(PioneerSensor):
    """Pioneer AVR system sensor."""

    _attr_name = "System"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.system.get(ATTRS_SYSTEM_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.system, ATTRS_SYSTEM_EXCLUDE)


class PioneerAmpSensor(PioneerSensor):
    """Pioneer AVR amp sensor."""

    _attr_name = "Amp"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.amp.get(ATTRS_AMP_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.amp, ATTRS_AMP_EXCLUDE)


class PioneerDspSensor(PioneerSensor):
    """Pioneer AVR dsp sensor."""

    _attr_name = "DSP"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.dsp.get(ATTRS_DSP_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.dsp, ATTRS_DSP_EXCLUDE)


class PioneerTunerSensor(PioneerSensor):
    """Pioneer AVR tuner sensor."""

    _attr_name = "Tuner"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.tuner.get(ATTRS_TUNER_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.tuner, ATTRS_TUNER_EXCLUDE)


class PioneerVideoSensor(PioneerSensor):
    """Pioneer AVR global video sensor."""

    _attr_name = "Video"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.video.get(ATTRS_VIDEO_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.video, ATTRS_VIDEO_EXCLUDE)


class PioneerAudioSensor(PioneerSensor):
    """Pioneer AVR global audio sensor."""

    _attr_name = "Audio"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.audio.get(ATTRS_AUDIO_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.audio, ATTRS_AUDIO_EXCLUDE)


class PioneerZoneVideoSensor(PioneerZoneSensor):
    """Pioneer AVR Zone video sensor."""

    _attr_name = "Video"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.video.get(self.zone, {}).get(ATTRS_ZONE_VIDEO_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(
            self.pioneer.video.get(self.zone, {}), ATTRS_ZONE_VIDEO_EXCLUDE
        )


class PioneerToneSensor(PioneerZoneSensor):
    """Pioneer AVR tone sensor."""

    _attr_name = "Tone"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.tone.get(self.zone, {}).get(ATTRS_TONE_PROMOTE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(self.pioneer.tone.get(self.zone, {}), ATTRS_TONE_EXCLUDE)


class PioneerChannelLevelSensor(PioneerZoneSensor):
    """Pioneer AVR channel level sensor."""

    _attr_name = "Channel Level"

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        return self.pioneer.channel_levels.get(self.zone, {}).get(
            ATTRS_CHANNEL_LEVEL_PROMOTE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return filter_dict(
            self.pioneer.video.get(self.zone, {}), ATTRS_CHANNEL_LEVEL_EXCLUDE
        )


def filter_dict(orig_dict: dict[str, Any], exclude_keys: list[str]) -> dict[str, Any]:
    """Filter keys from dict."""
    return {k: v for k, v in orig_dict.items() if k not in exclude_keys}
    # return orig_dict  ## TODO: testing
