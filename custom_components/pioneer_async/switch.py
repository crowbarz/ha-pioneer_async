"""Pioneer AVR switch entities."""

# pylint: disable=abstract-method

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone
from aiopioneer.property_entry import AVRPropertyEntry
from aiopioneer.property_registry import get_property_entry, get_code_maps
from aiopioneer.decoders.code_map import CodeBoolMap

from homeassistant.components.switch import SwitchEntity
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
    """Set up the switch platform."""
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    options: dict[str, Any] = pioneer_data[ATTR_OPTIONS]
    coordinators: list[PioneerAVRZoneCoordinator] = pioneer_data[ATTR_COORDINATORS]
    zone_device_info: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level switch entities
    entities = []
    zone = Zone.ALL
    device_info = zone_device_info[zone]
    coordinator = coordinators[zone]
    for code_map in get_code_maps(CodeBoolMap, zone=Zone.ALL, is_ha_auto_entity=True):
        entities.append(
            PioneerGenericSwitch(
                pioneer,
                options,
                coordinator=coordinator,
                device_info=device_info,
                property_entry=get_property_entry(code_map),
            )
        )

    ## Add zone specific switch entities
    for zone in pioneer.properties.zones:
        for code_map in get_code_maps(CodeBoolMap, zone=zone, is_ha_auto_entity=True):
            entities.append(
                PioneerGenericSwitch(
                    pioneer,
                    options,
                    coordinator=coordinators[zone],
                    device_info=zone_device_info[zone],
                    property_entry=get_property_entry(code_map),
                    zone=zone,
                )
            )

    async_add_entities(entities)


class PioneerSwitch(PioneerEntityBase, SwitchEntity, CoordinatorEntity):
    """Pioneer switch entity base class."""

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

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.is_on is not None


class PioneerGenericSwitch(PioneerSwitch):
    """Pioneer generic switch entity."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        property_entry: AVRPropertyEntry,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer generic switch entity."""
        super().__init__(
            pioneer,
            options,
            coordinator=coordinator,
            device_info=device_info,
            zone=zone,
        )
        self.property_entry = property_entry
        self.code_map: type[CodeBoolMap] = property_entry.code_map
        self._attr_name = self.code_map.get_ss_class_name()
        self._attr_icon = self.code_map.icon
        self._attr_entity_registry_enabled_default = self.code_map.ha_enable_default

        translation_key = self.code_map.base_property
        if property_name := self.code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

    @property
    def is_on(self) -> bool | None:
        """Return whether the AVR property is on."""
        base_value = getattr(self.pioneer.properties, self.code_map.base_property, {})
        if self.zone is not None:
            base_value = base_value.get(self.zone, {})
        if self.code_map.property_name is None:
            return base_value or None
        return base_value.get(self.code_map.property_name)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the AVR property."""

        async def turn_on_property() -> None:
            command = self.property_entry.set_command.name
            await self.pioneer.send_command(command, True)

        await self.pioneer_command(turn_on_property)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the AVR property."""

        async def turn_off_property() -> None:
            command = self.property_entry.set_command.name
            await self.pioneer.send_command(command, False)

        await self.pioneer_command(turn_off_property)

    async def async_update(self) -> None:
        """Refresh the AVR property."""

        async def query_property() -> None:
            command = self.property_entry.query_command.name
            await self.pioneer.send_command(command)

        await self.pioneer_command(query_property)
