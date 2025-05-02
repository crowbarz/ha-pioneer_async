"""Pioneer AVR binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from aiopioneer.const import Zone

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import select_dict, reject_dict
from .const import DOMAIN, PioneerData
from .entity_base import PioneerEntityBase


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    pioneer_data: PioneerData = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level binary_sensors
    entities = []
    entities.extend(
        [
            PioneerGenericBinarySensor(
                pioneer_data,
                name="Input Multichannel",
                icon="mdi:surround-sound",
                base_property="audio",
                promoted_property="input_multichannel",
                enabled_default=True,
            ),
        ]
    )

    async_add_entities(entities)


class PioneerBinarySensor(PioneerEntityBase, BinarySensorEntity, CoordinatorEntity):
    """Pioneer binary sensor class."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_entity_registry_visible_default = True

    def __init__(self, pioneer_data: PioneerData, zone: Zone = Zone.ALL) -> None:
        """Initialize the Pioneer AVR binary sensor."""
        super().__init__(pioneer_data, zone=zone)
        CoordinatorEntity.__init__(self, pioneer_data.coordinators[zone])


class PioneerGenericBinarySensor(PioneerBinarySensor):
    """Pioneer AVR generic sensor."""

    available_on_zones_off = True

    def __init__(
        self,
        pioneer_data: PioneerData,
        name: str,
        base_property: str,
        promoted_property: str | None,
        include_properties: list[str] | None = None,
        exclude_properties: list[str] | None = None,
        enabled_default: bool = False,
        zone: Zone = Zone.ALL,
        icon: str | None = None,
    ) -> None:
        """Initialize the Pioneer AVR sensor."""
        super().__init__(pioneer_data, zone=zone)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self.base_property = base_property
        self.promoted_property = promoted_property
        self.include_properties = include_properties
        self.exclude_properties = exclude_properties

        ## Exclude promoted_property from extra_attributes
        if (
            isinstance(exclude_properties, list)
            and promoted_property is not None
            and promoted_property not in exclude_properties
            and f"!{promoted_property}" not in exclude_properties
        ):
            self.exclude_properties.append(promoted_property)

    @property
    def is_on(self) -> bool:
        """Retrieve boolean state."""
        base_property_value = getattr(self.pioneer.properties, self.base_property, {})
        if self.zone is not Zone.ALL:
            base_property_value = base_property_value.get(self.zone, {})
        if self.promoted_property is None:
            value = base_property_value
        else:
            value = base_property_value.get(self.promoted_property)
        if value is None:
            return None
        return True if value else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        if self.include_properties is None and self.exclude_properties is None:
            return None
        attrs = getattr(self.pioneer.properties, self.base_property, {})
        if self.zone is not Zone.ALL:
            attrs = attrs.get(self.zone, {})
        if not isinstance(attrs, dict):
            return None
        if self.include_properties:
            attrs = select_dict(attrs, self.include_properties)
        if self.exclude_properties:
            return reject_dict(attrs, self.exclude_properties)
        return attrs
