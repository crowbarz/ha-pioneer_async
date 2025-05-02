"""Pioneer AVR select entities."""

# pylint: disable=abstract-method

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone, TunerBand
from aiopioneer.params import PARAM_SPEAKER_SYSTEM_MODES
from aiopioneer.property_entry import AVRPropertyEntry
from aiopioneer.property_registry import get_property_entry, get_code_maps
from aiopioneer.decoders.amp import Dimmer
from aiopioneer.decoders.code_map import CodeDictStrMap
from aiopioneer.decoders.system import SpeakerSystem
from aiopioneer.decoders.tuner import TunerPreset

from homeassistant.components.select import SelectEntity
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
)
from .coordinator import PioneerAVRZoneCoordinator
from .entity_base import PioneerEntityBase, PioneerTunerEntity


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    options: dict[str, Any] = pioneer_data[ATTR_OPTIONS]
    coordinators: list[PioneerAVRZoneCoordinator] = pioneer_data[ATTR_COORDINATORS]
    zone_device_info: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level select entities
    entities = []
    zone = Zone.ALL
    device_info = zone_device_info[zone]
    coordinator = coordinators[zone]
    entities.extend(
        [
            TunerPresetSelect(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(TunerPreset),
            ),
            TunerBandSelect(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
            ),
            SpeakerSystemSelect(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(SpeakerSystem),
            ),
            DimmerSelect(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(Dimmer),
            ),
        ]
    )
    for code_map in get_code_maps(
        CodeDictStrMap, zone=Zone.ALL, is_ha_auto_entity=True
    ):
        entities.append(
            PioneerGenericSelect(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(code_map),
            )
        )

    ## Add zone specific select entities
    for zone in pioneer.properties.zones:
        for code_map in get_code_maps(
            CodeDictStrMap, zone=zone, is_ha_auto_entity=True
        ):
            entities.append(
                PioneerGenericSelect(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(code_map),
                    zone=zone,
                )
            )

    async_add_entities(entities)


class PioneerSelect(PioneerEntityBase, SelectEntity, CoordinatorEntity):
    """Pioneer select entity base class."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer select base class."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.current_option is not None


class PioneerGenericSelect(PioneerSelect):
    """Pioneer generic select entity."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        property_entry: AVRPropertyEntry,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer generic select entity."""
        super().__init__(
            pioneer,
            options,
            coordinator=coordinator,
            device_info=device_info,
            zone=zone,
        )
        self.property_entry = property_entry
        self.code_map: type[CodeDictStrMap] = property_entry.code_map
        self._attr_name = self.code_map.get_ss_class_name()
        self._attr_icon = self.code_map.icon
        self._attr_entity_registry_enabled_default = self.code_map.ha_enable_default

        translation_key = self.code_map.base_property
        if property_name := self.code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

    @property
    def current_option(self) -> str | None:
        """Return the selected option for the AVR property."""
        return self.code_map.get_property_value(self.pioneer.properties, zone=self.zone)

    @property
    def options(self) -> list[str]:
        """Return the available set of AVR property options."""
        return list(self.code_map.code_map.values())

    async def async_select_option(self, option: str) -> None:
        """Change the selected option for the AVR property."""
        await self.pioneer_command(self.property_entry.set_command.name, option)

    async def async_update(self) -> None:
        """Refresh the AVR property."""
        await self.pioneer_command(self.property_entry.query_command.name)


class TunerPresetSelect(PioneerTunerEntity, PioneerGenericSelect):
    """Pioneer tuner preset select entity."""

    @property
    def options(self) -> list[str]:
        """Return the available tuner presets."""
        return [
            c + str(n)
            for c in ["A", "B", "C", "D", "E", "F", "G"]
            for n in range(1, 10)
        ]

    @property
    def current_option(self) -> str | None:
        """Return the selected tuner preset."""
        tuner_class = self.pioneer.properties.tuner.get("class")
        tuner_preset = self.pioneer.properties.tuner.get("preset")
        if tuner_preset is None or tuner_class is None:
            return None
        return tuner_class + str(tuner_preset)

    async def async_select_option(self, option: str) -> None:
        """Change the tuner preset."""
        tuner_class = option[0]
        tuner_preset = int(option[1])
        await self.pioneer_command(
            self.pioneer.select_tuner_preset,
            tuner_class=tuner_class,
            tuner_preset=tuner_preset,
        )


class TunerBandSelect(PioneerTunerEntity, PioneerSelect):
    """Pioneer tuner frequency band select entity."""

    _attr_name = "Tuner Band"
    _attr_icon = "mdi:radio"
    _attr_options = [b.value for b in TunerBand]

    @property
    def current_option(self) -> str | None:
        """Return the current tuner band."""
        band = self.pioneer.properties.tuner.get("band")
        return band.value if isinstance(band, TunerBand) else None

    async def async_select_option(self, option: str) -> None:
        """Change the tuner band."""
        await self.pioneer_command(
            self.pioneer.select_tuner_band, band=TunerBand(option)
        )

    async def async_update(self) -> None:
        """Refresh the tuner frequency band property (encoded in frequency)."""
        await self.pioneer_command("query_tuner_frequency")


class SpeakerSystemSelect(PioneerGenericSelect):
    """Pioneer speaker system select entity."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "speaker_system_id": self.pioneer.properties.system.get("speaker_system_id")
        }

    @property
    def options(self) -> list[str]:
        """Return the available set of speaker system options."""
        return list(
            self.pioneer.params.get_param(PARAM_SPEAKER_SYSTEM_MODES, {}).values()
        )


class DimmerSelect(PioneerGenericSelect):
    """Pioneer dimmer select entity."""

    @property
    def available(self) -> bool:
        """Returns whether the dimmer property is available."""
        return PioneerEntityBase.is_available(self)

    async def async_update(self) -> None:
        """Don't refresh dimmer property as AVR command does not exist."""
