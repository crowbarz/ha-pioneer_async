"""Pioneer AVR text entities."""

# pylint: disable=abstract-method

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone
from aiopioneer.property_entry import AVRPropertyEntry
from aiopioneer.property_registry import get_property_entry, get_code_maps
from aiopioneer.decoders.code_map import CodeStrMap

from homeassistant.components.text import TextEntity
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
from .entity_base import PioneerEntityBase


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the text platform."""
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    options: dict[str, Any] = pioneer_data[ATTR_OPTIONS]
    coordinators: list[PioneerAVRZoneCoordinator] = pioneer_data[ATTR_COORDINATORS]
    zone_device_info: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level text entities
    entities = []
    zone = Zone.ALL
    device_info = zone_device_info[zone]
    coordinator = coordinators[zone]
    for code_map in get_code_maps(CodeStrMap, zone=Zone.ALL, is_ha_auto_entity=True):
        entities.append(
            PioneerGenericText(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(code_map),
            )
        )

    ## Add zone specific text entities
    for zone in pioneer.properties.zones:
        for code_map in get_code_maps(CodeStrMap, zone=zone, is_ha_auto_entity=True):
            entities.append(
                PioneerGenericText(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(code_map),
                    zone=zone,
                )
            )

    async_add_entities(entities)


class PioneerText(PioneerEntityBase, TextEntity, CoordinatorEntity):
    """Pioneer text entity base class."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer text base class."""
        super().__init__(pioneer, options, device_info=device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.native_value is not None


class PioneerGenericText(PioneerText):
    """Pioneer generic text entity."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        property_entry: AVRPropertyEntry,
        zone: Zone | None = None,
        code_map: CodeStrMap = None,
        name: str = None,
    ) -> None:
        """Initialize the Pioneer generic text entity."""
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
        self._attr_native_min = code_map.value_min_len
        self._attr_native_max = code_map.value_max_len
        self._attr_mode = code_map.ha_text_mode
        self._attr_pattern = code_map.ha_pattern

        translation_key = self.code_map.base_property
        if property_name := self.code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

    @property
    def native_value(self) -> str | None:
        """Return the current value for the AVR property."""
        return self.code_map.get_property_value(self.pioneer.properties, zone=self.zone)

    async def async_set_value(self, value: str) -> None:
        """Set the AVR property."""
        await self.pioneer_command(self.property_entry.set_command.name, value)

    async def async_update(self) -> None:
        """Refresh the AVR property."""
        await self.pioneer_command(self.property_entry.query_command.name)
