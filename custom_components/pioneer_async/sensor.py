"""Pioneer AVR sensors."""

from __future__ import annotations

import logging

from typing import Any, Callable

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import PARAM_TUNER_AM_FREQ_STEP


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

from . import select_dict, reject_dict
from .const import (
    DOMAIN,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
)
from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug
from .entity_base import PioneerEntityBase, PioneerTunerEntity


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
    entities.extend(
        [
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="Display",
                icon="mdi:fullscreen",
                base_property="amp",
                promoted_property="display",
                value_func=lambda x: x.strip(),
                enabled_default=True,
                include_properties=["dimmer"],
            ),
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="System",
                icon="mdi:audio-video",
                base_property="system",
                promoted_property="speaker_system",
                exclude_properties=[],
            ),
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="Amp",
                icon="mdi:amplifier",
                base_property="amp",
                promoted_property="speakers",
                exclude_properties=["display", "dimmer"],
            ),
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="DSP",
                icon="mdi:surround-sound",
                base_property="dsp",
                promoted_property="signal_select",
                exclude_properties=[],
            ),
            PioneerTunerSensor(
                pioneer,
                coordinator,
                device_info,
                name="Tuner",
                icon="mdi:radio",
                base_property="tuner",
                promoted_property="frequency",
                exclude_properties=[],
            ),
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="Video Parameters",
                icon="mdi:video-box",
                base_property="video",
                promoted_property="signal_output_resolution",
                exclude_properties=["1", "2", "3", "Z"],
            ),
            PioneerGenericSensor(
                pioneer,
                coordinator,
                device_info,
                name="Audio Parameters",
                icon="mdi:speaker",
                base_property="audio",
                promoted_property="input_signal",
                exclude_properties=["1", "2", "3", "Z"],
            ),
        ]
    )

    ## Add zone specific sensors
    for zone in pioneer.zones:
        device_info = device_info_dict.get(zone)
        coordinator = coordinator_list[zone]
        if zone != "Z":
            entities.extend(
                [
                    PioneerGenericSensor(
                        pioneer,
                        coordinator,
                        device_info,
                        zone=zone,
                        name="Video Parameters",
                        icon="mdi:video-box",
                        base_property="video",
                        promoted_property="status",  # TODO: to identify
                        exclude_properties=[],
                    ),
                    PioneerGenericSensor(
                        pioneer,
                        coordinator,
                        device_info,
                        zone=zone,
                        name="Audio Parameters",
                        icon="mdi:speaker",
                        base_property="audio",
                        promoted_property="status",  # TODO: to identify
                        exclude_properties=[],
                    ),
                    PioneerGenericSensor(
                        pioneer,
                        coordinator,
                        device_info,
                        zone=zone,
                        name="Tone",
                        icon="mdi:circle-half-full",
                        base_property="tone",
                        promoted_property="status",
                        exclude_properties=[],
                    ),
                    PioneerGenericSensor(
                        pioneer,
                        coordinator,
                        device_info,
                        zone=zone,
                        name="Channel Level",
                        icon="mdi:surround-sound",
                        base_property="channel_levels",
                        promoted_property="C",
                        exclude_properties=["!C"],
                    ),
                ]
            )

    async_add_entities(entities)


class PioneerSensor(PioneerEntityBase, SensorEntity, CoordinatorEntity):
    """Pioneer sensor base class."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # _attr_entity_registry_enabled_default = False  ## TODO: disable when debug over

    def __init__(
        self,
        pioneer: PioneerAVR,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        zone: Zones | None = None,
    ) -> None:
        """Initialize the Pioneer AVR sensor."""
        super().__init__(pioneer, device_info, zone=zone)
        CoordinatorEntity.__init__(self, coordinator)


class PioneerGenericSensor(PioneerSensor):
    """Pioneer AVR generic sensor."""

    def __init__(
        self,
        pioneer: PioneerAVR,
        coordinator: PioneerAVRZoneCoordinator,
        device_info: DeviceInfo,
        name: str,
        base_property: str,
        promoted_property: str | None,
        include_properties: list[str] | None = None,
        exclude_properties: list[str] | None = None,
        value_func: Callable[[str], str] | None = None,
        enabled_default: bool = True,  ## TODO: disable when debug over
        zone: Zones | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize the Pioneer AVR sensor."""
        super().__init__(pioneer, coordinator, device_info, zone=zone)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self.base_property = base_property
        self.promoted_property = promoted_property
        self.include_properties = include_properties
        self.exclude_properties = exclude_properties
        self.value_func = value_func

        ## Exclude promoted_property from extra_attributes
        # if (
        #     isinstance(exclude_properties, list)
        #     and promoted_property is not None
        #     and promoted_property not in exclude_properties
        #     and f"!{promoted_property}" not in exclude_properties
        # ):
        #     self.exclude_properties.append(promoted_property)

    @property
    def native_value(self) -> str:
        """Retrieve sensor value."""
        base_property_value = getattr(self.pioneer, self.base_property, {})
        if self.zone is not None:
            base_property_value = base_property_value.get(self.zone, {})
        if not self.promoted_property:
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
            return []
        attrs = getattr(self.pioneer, self.base_property, {})
        if self.zone is not None:
            attrs = attrs.get(self.zone, {})
        if not isinstance(attrs, dict):
            return []
        if self.include_properties:
            attrs = select_dict(attrs, self.include_properties)
        if self.exclude_properties:
            return reject_dict(attrs, self.exclude_properties)
        return attrs


class PioneerTunerSensor(PioneerTunerEntity, PioneerGenericSensor):
    """Pioneer AVR tuner sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attrs = super().extra_state_attributes
        attrs |= {
            PARAM_TUNER_AM_FREQ_STEP: self.pioneer.get_param(PARAM_TUNER_AM_FREQ_STEP),
        }
        return attrs
