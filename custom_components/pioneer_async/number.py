"""Pioneer AVR number entities."""

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone, TunerBand
from aiopioneer.decoders.code_map import CodeFloatMap
from aiopioneer.decoders.tuner import FrequencyAM
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

DEFAULT_TUNER_AM_FREQ_STEP = 9
DEFAULT_TUNER_AM_FREQ_MIN, DEFAULT_TUNER_AM_FREQ_MAX = FrequencyAM.get_frequency_bounds(
    DEFAULT_TUNER_AM_FREQ_STEP
)
TUNER_FREQ_ATTRS = {
    TunerBand.AM: {
        "unit_of_measurement": "kHz",
        "min_value": DEFAULT_TUNER_AM_FREQ_MIN,
        "max_value": DEFAULT_TUNER_AM_FREQ_MAX,
        "step": 1,  # set once updated from AVR
    },
    TunerBand.FM: {
        "unit_of_measurement": "MHz",
        "min_value": 87.5,
        "max_value": 108.0,
        "step": 0.05,
    },
}


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

    ## Add top level numbers
    entities = []
    zone = Zone.ALL
    device_info = zone_device_info[zone]
    coordinator = coordinators[zone]
    entities.extend(
        [
            TunerFrequencyNumber(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                band=TunerBand.FM,
            ),
            TunerFrequencyNumber(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                band=TunerBand.AM,
            ),
        ]
    )
    for code_map in get_code_maps(CodeFloatMap, zone=Zone.ALL, is_ha_auto_entity=True):
        _LOGGER.critical(code_map.__name__)
        entities.append(
            PioneerGenericNumber(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(code_map),
            )
        )

    ## Add zone specific selects
    for zone in pioneer.properties.zones & {Zone.Z1, Zone.Z2}:
        device_info = zone_device_info[zone]
        coordinator = coordinators[zone]
        entities.extend(
            [
                ToneTrebleNumber(
                    pioneer,
                    options,
                    coordinator=coordinator,
                    device_info=device_info,
                    zone=zone,
                ),
                ToneBassNumber(
                    pioneer,
                    options,
                    coordinator=coordinator,
                    device_info=device_info,
                    zone=zone,
                ),
            ]
        )
        for code_map in get_code_maps(CodeFloatMap, zone=zone, is_ha_auto_entity=True):
            _LOGGER.critical(code_map.__name__)
            entities.append(
                PioneerGenericNumber(
                    pioneer,
                    options,
                    coordinator=coordinator,
                    device_info=device_info,
                    property_entry=get_property_entry(code_map),
                    zone=zone,
                )
            )

    async_add_entities(entities)


class PioneerGenericNumber(
    PioneerEntityBase, NumberEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer generic number entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        property_entry: AVRPropertyEntry,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer generic number entity."""
        self.property_entry = property_entry
        self.code_map: type[CodeFloatMap] = property_entry.code_map
        self._attr_name = self.code_map.get_ss_class_name()
        self._attr_icon = self.code_map.icon
        self._attr_entity_registry_enabled_default = self.code_map.ha_enable_default
        self._attr_native_unit_of_measurement = self.code_map.unit_of_measurement
        self._attr_native_min_value = self.code_map.value_min
        self._attr_native_max_value = self.code_map.value_max
        self._attr_native_step = self.code_map.value_step
        self._attr_device_class = self.code_map.ha_device_class
        self._attr_mode = self.code_map.ha_number_mode

        translation_key = self.code_map.base_property
        if property_name := self.code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        """Return the current value for the AVR property."""
        base_value = getattr(self.pioneer.properties, self.code_map.base_property, {})
        if self.zone is not None:
            base_value = base_value.get(self.zone, {})
        if self.code_map.property_name is None:
            return base_value or None
        return base_value.get(self.code_map.property_name)

    async def async_set_native_value(self, value: float) -> None:
        """Set the AVR property."""

        async def set_property() -> bool:
            command = self.property_entry.set_command.name
            return await self.pioneer.send_command(command, value)

        await self.pioneer_command(set_property)

    async def async_update(self) -> None:
        """Refresh the AVR property."""

        async def query_property() -> bool:
            command = self.property_entry.query_command.name
            return await self.pioneer.send_command(command)

        await self.pioneer_command(query_property)


class TunerFrequencyNumber(
    PioneerTunerEntity, NumberEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer tuner frequency number entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.FREQUENCY
    _attr_icon = "mdi:radio-tower"
    _attr_mode = NumberMode.BOX
    _unrecorded_attributes = frozenset({ATTR_TUNER_AM_FREQUENCY_STEP})

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        band: TunerBand,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer tuner frequency number entity."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)
        self.band = band
        tuner_freq_attrs = TUNER_FREQ_ATTRS[band]
        self._attr_name = f"Tuner {band} Frequency"
        self._attr_native_unit_of_measurement = tuner_freq_attrs["unit_of_measurement"]
        self._attr_native_min_value = tuner_freq_attrs["min_value"]
        self._attr_native_max_value = tuner_freq_attrs["max_value"]
        self._attr_native_step = tuner_freq_attrs["step"]

    @property
    def available(self) -> bool:
        """Returns whether the tuner is available and band is selected."""
        return (
            super().available and self.pioneer.properties.tuner.get("band") == self.band
        )

    @property
    def native_value(self) -> float | None:
        """Return the tuner frequency."""
        return self.pioneer.properties.tuner.get("frequency")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        if self.band != TunerBand.AM:
            return None

        attrs = super().extra_state_attributes or {}
        am_frequency_step = self.pioneer.properties.tuner.get("am_frequency_step")
        if self.band is TunerBand.AM and am_frequency_step:
            attrs |= {ATTR_TUNER_AM_FREQUENCY_STEP: am_frequency_step}
            self._attr_native_step = am_frequency_step
            value_min, value_max = FrequencyAM.get_frequency_bounds(am_frequency_step)
            self._attr_native_min_value = value_min
            self._attr_native_max_value = value_max
        return attrs

    async def async_set_native_value(self, value: float) -> None:
        """Set the tuner frequency."""

        async def set_tuner_frequency() -> bool:
            return await self.pioneer.set_tuner_frequency(self.band, value)

        await self.pioneer_command(set_tuner_frequency)


class ToneNumber(PioneerEntityBase, NumberEntity):  # pylint: disable=abstract-method
    """Pioneer tone number entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.SIGNAL_STRENGTH
    _attr_native_min_value = -6
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    @property
    def available(self) -> bool:
        """Returns whether the tone number is available."""
        tone_status = self.pioneer.properties.tone.get(self.zone, {}).get("status")
        return super().available and tone_status == "on"


class ToneTrebleNumber(
    ToneNumber, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer tone treble number entity."""

    _attr_icon = "mdi:music-clef-treble"
    _attr_name = "Tone Treble"

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer tone treble number entity."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the tone treble value."""
        return self.pioneer.properties.tone.get(self.zone, {}).get("treble")

    async def async_set_native_value(self, value: int) -> None:
        """Set the tone treble value."""

        async def set_tone_treble() -> bool:
            return await self.pioneer.set_tone_settings(zone=self.zone, treble=value)

        await self.pioneer_command(set_tone_treble)


class ToneBassNumber(ToneNumber, CoordinatorEntity):  # pylint: disable=abstract-method
    """Pioneer tone bass number entity."""

    _attr_icon = "mdi:music-clef-bass"
    _attr_name = "Tone Bass"

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer tone bass number entity."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the tone bass value."""
        return self.pioneer.properties.tone.get(self.zone, {}).get("bass")

    async def async_set_native_value(self, value: int) -> None:
        """Set the tone bass value."""

        async def set_tone_treble() -> bool:
            return await self.pioneer.set_tone_settings(zone=self.zone, bass=value)

        await self.pioneer_command(set_tone_treble)
