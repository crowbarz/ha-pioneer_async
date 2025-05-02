"""Pioneer AVR sensor entities."""

from __future__ import annotations

import logging
from typing import Any, Callable

from aiopioneer.const import Zone

from homeassistant.components.sensor import (
    # SensorDeviceClass,
    SensorEntity,
    # SensorStateClass,
)
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
    """Set up the sensor platform."""
    pioneer_data: PioneerData = hass.data[DOMAIN][config_entry.entry_id]
    pioneer = pioneer_data.pioneer
    _LOGGER.debug(">> async_setup_entry(entry_id=%s)", config_entry.entry_id)

    ## Add top level sensor entities
    entities = []
    entities.extend(
        [
            PioneerGenericSensor(
                pioneer_data,
                name="Display",
                icon="mdi:fullscreen",
                base_property="amp",
                promoted_property="display",
            ),
            PioneerGenericSensor(
                pioneer_data,
                name="Amp",
                icon="mdi:amplifier",
                base_property="amp",
                promoted_property="model",
                exclude_properties=["display", "dimmer"],
                enabled_default=True,
            ),
            PioneerGenericSensor(
                pioneer_data,
                name="DSP",
                icon="mdi:surround-sound",
                base_property="dsp",
                promoted_property="signal_select",
                exclude_properties=[],
                enabled_default=True,
            ),
            PioneerGenericSensor(
                pioneer_data,
                name="Video Parameters",
                icon="mdi:video-box",
                base_property="video",
                promoted_property="signal_output_resolution",
                exclude_properties=[Zone.Z1, Zone.Z2, Zone.Z3, Zone.HDZ],
                enabled_default=True,
            ),
            PioneerGenericSensor(
                pioneer_data,
                name="Audio Parameters",
                icon="mdi:speaker",
                base_property="audio",
                promoted_property="input_signal",
                exclude_properties=[
                    "input_multichannel",
                    Zone.Z1,
                    Zone.Z2,
                    Zone.Z3,
                    Zone.HDZ,
                ],
                enabled_default=True,
            ),
            PioneerGenericSensor(
                pioneer_data,
                name="System",
                icon="mdi:cog",
                base_property="system",
                promoted_property="osd_language",
                exclude_properties=[
                    "speaker_system",
                    "speaker_system_id",
                    "parental_lock_password",
                ],
            ),
        ]
    )

    ## Add zone specific sensor entities
    for zone in pioneer.properties.zones:
        if zone != Zone.HDZ:
            entities.extend(
                [
                    PioneerGenericSensor(
                        pioneer_data,
                        zone=zone,
                        name="Video Parameters",
                        icon="mdi:video-box",
                        base_property="video",
                        promoted_property="resolution",
                        exclude_properties=[],
                    ),
                    PioneerGenericSensor(
                        pioneer_data,
                        zone=zone,
                        name="Audio Parameters",
                        icon="mdi:speaker",
                        base_property="audio",
                        promoted_property="status",  # TODO: to identify
                        exclude_properties=[],
                    ),
                ]
            )

    async_add_entities(entities)


class PioneerSensor(PioneerEntityBase, SensorEntity, CoordinatorEntity):
    """Pioneer sensor entity base class."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, pioneer_data: PioneerData, zone: Zone = Zone.ALL) -> None:
        """Initialize the Pioneer sensor base class."""
        super().__init__(pioneer_data, zone=zone)
        CoordinatorEntity.__init__(self, pioneer_data.coordinators[zone])


class PioneerGenericSensor(PioneerSensor):
    """Pioneer generic sensor entity."""

    available_on_zones_off = True

    def __init__(
        self,
        pioneer_data: PioneerData,
        name: str,
        base_property: str,
        promoted_property: str | None = None,
        include_properties: list[str] | None = None,
        exclude_properties: list[str] | None = None,
        value_func: Callable[[str], str] | None = None,
        enabled_default: bool = False,
        zone: Zone = Zone.ALL,
        icon: str | None = None,
    ) -> None:
        """Initialize the Pioneer generic sensor."""
        super().__init__(pioneer_data, zone=zone)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self.base_property = base_property
        self.promoted_property = promoted_property
        self.include_properties = include_properties
        self.exclude_properties = exclude_properties
        self.value_func = value_func

        ## Exclude promoted_property from extra_attributes
        if (
            isinstance(exclude_properties, list)
            and promoted_property is not None
            and promoted_property not in exclude_properties
            and f"!{promoted_property}" not in exclude_properties
        ):
            self.exclude_properties.append(promoted_property)

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        base_property_value = getattr(self.pioneer.properties, self.base_property, {})
        if self.zone is not Zone.ALL:
            base_property_value = base_property_value.get(self.zone, {})
        if self.promoted_property is None:
            value = str(base_property_value)
        else:
            value = base_property_value.get(self.promoted_property)
        if value is not None and self.value_func is not None:
            value = str(self.value_func(value))
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        if self.include_properties is None and self.exclude_properties is None:
            return None
        base_attrs = getattr(self.pioneer.properties, self.base_property, {})
        attrs = base_attrs
        if self.zone is not Zone.ALL:
            attrs = base_attrs.get(self.zone, {})
        if not isinstance(attrs, dict):
            return None
        if self.include_properties:
            attrs = select_dict(attrs, self.include_properties)
        if self.exclude_properties:
            return reject_dict(attrs, self.exclude_properties)
        return attrs
