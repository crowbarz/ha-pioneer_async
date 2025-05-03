"""Pioneer AVR switch entities."""

# pylint: disable=abstract-method

from __future__ import annotations

import logging

from aiopioneer.const import Zone
from aiopioneer.property_entry import AVRPropertyEntry
from aiopioneer.property_registry import get_property_entry, get_code_maps
from aiopioneer.decoders.code_map import CodeBoolMap

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PioneerData
from .entity_base import PioneerEntityBase


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    pioneer_data: PioneerData = hass.data[DOMAIN][config_entry.entry_id]
    pioneer = pioneer_data.pioneer
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level switch entities
    entities = []
    zone = Zone.ALL
    for code_map in get_code_maps(CodeBoolMap, zone=Zone.ALL, is_ha_auto_entity=True):
        entities.append(
            PioneerGenericSwitch(
                pioneer_data, property_entry=get_property_entry(code_map)
            )
        )

    ## Add zone specific switch entities
    for zone in pioneer.properties.zones:
        for code_map in get_code_maps(CodeBoolMap, zone=zone, is_ha_auto_entity=True):
            entities.append(
                PioneerGenericSwitch(
                    pioneer_data, property_entry=get_property_entry(code_map), zone=zone
                )
            )

    async_add_entities(entities)


class PioneerSwitch(PioneerEntityBase, SwitchEntity, CoordinatorEntity):
    """Pioneer switch entity base class."""

    def __init__(self, pioneer_data: PioneerData, zone: Zone = Zone.ALL) -> None:
        """Initialize the Pioneer number base class."""
        super().__init__(pioneer_data, zone=zone)
        CoordinatorEntity.__init__(self, pioneer_data.coordinators[zone])

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        """Returns whether the AVR property is available."""
        return super().available and self.is_on is not None


class PioneerGenericSwitch(PioneerSwitch):
    """Pioneer generic switch entity."""

    def __init__(
        self,
        pioneer_data: PioneerData,
        property_entry: AVRPropertyEntry,
        zone: Zone = Zone.ALL,
        code_map: CodeBoolMap = None,
        name: str = None,
    ) -> None:
        """Initialize the Pioneer generic switch entity."""
        super().__init__(pioneer_data, zone=zone)
        self.property_entry = property_entry
        if code_map is None:
            code_map = property_entry.code_map
        self.code_map = code_map
        self._attr_name = name or code_map.get_ss_class_name()
        self._attr_icon = code_map.icon
        self._attr_entity_registry_enabled_default = code_map.ha_enable_default

        translation_key = code_map.base_property
        if property_name := code_map.property_name:
            translation_key += f"_{property_name}"
        self._attr_translation_key = translation_key

    @property
    def is_on(self) -> bool | None:
        """Return whether the AVR property is on."""
        return self.code_map.get_property_value(self.pioneer.properties, zone=self.zone)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the AVR property."""
        await self.pioneer_command(self.property_entry.set_command.name, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the AVR property."""
        await self.pioneer_command(self.property_entry.set_command.name, False)

    async def async_update(self) -> None:
        """Refresh the AVR property."""
        await self.pioneer_command(self.property_entry.query_command.name)
