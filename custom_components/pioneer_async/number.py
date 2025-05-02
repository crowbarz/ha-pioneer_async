"""Pioneer AVR number entities."""

# pylint: disable=abstract-method

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone, TunerBand
from aiopioneer.decoders.audio import (
    ToneDb,
    ToneTreble,
    ToneBass,
    ChannelLevel,
    SpeakerChannel,
    SpeakerChannelLevel,
)
from aiopioneer.decoders.code_map import CodeFloatMap
from aiopioneer.decoders.tuner import TunerAMFrequency, TunerFMFrequency
from aiopioneer.property_entry import AVRPropertyEntry
from aiopioneer.property_registry import get_property_entry, get_code_maps

from homeassistant.components.number import NumberEntity, NumberMode, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
    ATTR_OPTIONS,
    ATTR_TUNER_AM_FREQUENCY_STEP,
)
from .coordinator import PioneerAVRZoneCoordinator
from .entity_base import PioneerEntityBase, PioneerTunerEntity


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    options: dict[str, Any] = pioneer_data[ATTR_OPTIONS]
    coordinators: list[PioneerAVRZoneCoordinator] = pioneer_data[ATTR_COORDINATORS]
    zone_device_info: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level number entities
    entities = []
    zone = Zone.ALL
    device_info = zone_device_info[zone]
    coordinator = coordinators[zone]
    entities.extend(
        [
            TunerFMFrequencyNumber(
                pioneer, options, coordinator=coordinator, device_info=device_info
            ),
            TunerAMFrequencyNumber(
                pioneer, options, coordinator=coordinator, device_info=device_info
            ),
        ]
    )
    for code_map in get_code_maps(CodeFloatMap, zone=Zone.ALL, is_ha_auto_entity=True):
        entities.append(
            PioneerGenericNumber(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(code_map),
            )
        )

    ## Add zone specific number entities
    for zone in pioneer.properties.zones & ChannelLevel.supported_zones:
        for channel in SpeakerChannel.CHANNELS_ALL:
            entities.append(
                ChannelLevelNumber(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    channel=channel,
                    zone=zone,
                )
            )
    for zone in pioneer.properties.zones & ToneDb.supported_zones:
        entities.extend(
            [
                ToneTrebleNumber(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(ToneTreble),
                    zone=zone,
                ),
                ToneBassNumber(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(ToneBass),
                    zone=zone,
                ),
            ]
        )
    for zone in pioneer.properties.zones:
        for code_map in get_code_maps(CodeFloatMap, zone=zone, is_ha_auto_entity=True):
            entities.append(
                PioneerGenericNumber(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(code_map),
                    zone=zone,
                )
            )

    async_add_entities(entities)


class PioneerNumber(PioneerEntityBase, NumberEntity, CoordinatorEntity):
    """Pioneer number entity base class."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer number base class."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.native_value is not None


class PioneerGenericNumber(PioneerNumber):
    """Pioneer generic number entity."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        property_entry: AVRPropertyEntry,
        zone: Zone | None = None,
        code_map: CodeFloatMap = None,
        name: str = None,
    ) -> None:
        """Initialize the Pioneer generic number entity."""
        super().__init__(
            pioneer,
            options,
            coordinator=coordinator,
            device_info=device_info,
            zone=zone,
        )
        self.property_entry = property_entry
        if code_map is None:
            code_map = property_entry.code_map
        self.code_map = code_map
        self._attr_name = name or code_map.get_ss_class_name()
        self._attr_icon = code_map.icon
        self._attr_entity_registry_enabled_default = code_map.ha_enable_default
        self._attr_native_unit_of_measurement = code_map.unit_of_measurement
        self._attr_native_min_value = code_map.value_min
        self._attr_native_max_value = code_map.value_max
        self._attr_native_step = code_map.value_step
        self._attr_device_class = code_map.ha_device_class
        self._attr_mode = code_map.ha_number_mode

        translation_key = self.code_map.base_property
        if property_name := self.code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

    @property
    def native_value(self) -> float | None:
        """Return the current value for the AVR property."""
        return self.code_map.get_property_value(self.pioneer.properties, zone=self.zone)

    async def async_set_native_value(self, value: float) -> None:
        """Set the AVR property."""
        await self.pioneer_command(self.property_entry.set_command.name, value)

    async def async_update(self) -> None:
        """Refresh the AVR property."""
        await self.pioneer_command(self.property_entry.query_command.name)


class TunerFrequencyNumber(PioneerTunerEntity, PioneerNumber):
    """Pioneer tuner frequency number entity."""

    _attr_device_class = NumberDeviceClass.FREQUENCY
    _attr_icon = "mdi:radio-tower"
    _attr_mode = NumberMode.BOX

    @property
    def band(self) -> TunerBand:
        """Return frequency band for entity."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        """Returns whether the tuner is available and band is selected."""
        return (
            super().available and self.pioneer.properties.tuner.get("band") == self.band
        )

    @property
    def native_value(self) -> float | None:
        """Return the tuner frequency."""
        if self.pioneer.properties.tuner.get("band") != self.band:
            return None
        return self.pioneer.properties.tuner.get("frequency")

    async def async_set_native_value(self, value: float) -> None:
        """Set the tuner frequency."""

        await self.pioneer_command(
            self.pioneer.set_tuner_frequency, band=self.band, frequency=value
        )


class TunerFMFrequencyNumber(TunerFrequencyNumber):
    """Pioneer tuner FM frequency number entity."""

    _attr_name = "Tuner FM Frequency"
    _attr_native_unit_of_measurement = TunerFMFrequency.unit_of_measurement
    _attr_native_min_value = TunerFMFrequency.value_min
    _attr_native_max_value = TunerFMFrequency.value_max
    _attr_native_step = TunerFMFrequency.value_step

    @property
    def band(self) -> TunerBand:
        """Return frequency band for entity."""
        return TunerBand.FM


class TunerAMFrequencyNumber(TunerFrequencyNumber):
    """Pioneer tuner AM frequency number entity."""

    _attr_name = "Tuner AM Frequency"
    _attr_native_unit_of_measurement = TunerAMFrequency.unit_of_measurement
    _unrecorded_attributes = frozenset({ATTR_TUNER_AM_FREQUENCY_STEP})

    @property
    def band(self) -> TunerBand:
        """Return frequency band for entity."""
        return TunerBand.AM

    @property
    def native_min_value(self) -> float:
        return TunerAMFrequency.get_frequency_bounds(self.native_step)[0]

    @property
    def native_max_value(self) -> float:
        return TunerAMFrequency.get_frequency_bounds(self.native_step)[1]

    @property
    def native_step(self) -> float:
        return self.pioneer.properties.tuner.get("am_frequency_step")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attrs = super().extra_state_attributes or {}

        if am_frequency_step := self.native_step:
            attrs |= {ATTR_TUNER_AM_FREQUENCY_STEP: am_frequency_step}
        return attrs


class ChannelLevelNumber(PioneerGenericNumber):
    """Pioneer channel level number entity."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        channel: str,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer channel level number entity."""
        super().__init__(
            pioneer,
            options,
            coordinator=coordinator,
            device_info=device_info,
            property_entry=get_property_entry(SpeakerChannelLevel),
            zone=zone,
            code_map=ChannelLevel,
            name=f"Channel {channel}",
        )
        self.channel = channel

    @property
    def native_value(self) -> float | None:
        """Return the level for the configured channel."""
        return self.pioneer.properties.channel_level.get(self.zone, {}).get(
            self.channel
        )

    async def async_set_native_value(self, value: int) -> None:
        """Set the channel level."""
        await self.pioneer_command(
            self.pioneer.set_channel_level,
            channel=self.channel,
            level=value,
            zone=self.zone,
        )

    async def async_update(self) -> None:
        """Refresh the channel level."""
        await self.pioneer_command("query_channel_level", self.channel)


class ToneNumber(PioneerGenericNumber):
    """Pioneer tone number entity."""

    @property
    def available(self) -> bool:
        """Returns whether the tone number is available."""
        tone_status = self.pioneer.properties.tone.get(self.zone, {}).get("status")
        return super().available and tone_status == "on"


class ToneTrebleNumber(ToneNumber):
    """Pioneer tone treble number entity."""

    async def async_set_native_value(self, value: int) -> None:
        """Set the tone treble value."""
        await self.pioneer_command(
            self.pioneer.set_tone_settings, zone=self.zone, treble=value
        )


class ToneBassNumber(ToneNumber):
    """Pioneer tone bass number entity."""

    async def async_set_native_value(self, value: int) -> None:
        """Set the tone bass value."""
        await self.pioneer_command(
            self.pioneer.set_tone_settings, zone=self.zone, bass=value
        )
