"""Pioneer AVR select entities."""

from __future__ import annotations

import logging

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones, TunerBand

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_PIONEER,
    ATTR_COORDINATORS,
    ATTR_DEVICE_INFO,
)
from .coordinator import PioneerAVRZoneCoordinator
from .debug import Debug
from .entity_base import PioneerTunerEntity


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
            ">> select.async_setup_entry(entry_id=%s, data=%s, options=%s)",
            config_entry.entry_id,
            config_entry.data,
            config_entry.options,
        )
    pioneer_data = hass.data[DOMAIN][config_entry.entry_id]
    pioneer: PioneerAVR = pioneer_data[ATTR_PIONEER]
    coordinator_list = pioneer_data[ATTR_COORDINATORS]
    device_info_dict: dict[str, DeviceInfo] = pioneer_data[ATTR_DEVICE_INFO]

    entities = []

    ## Add top level selects
    zone = str(Zones.Z1)  ## TODO: move to Zones.ALL
    device_info = device_info_dict.get("top")
    coordinator = coordinator_list[zone]
    entities.extend(
        [
            TunerPresetSelect(
                pioneer,
                coordinator,
                device_info,
            ),
            TunerBandSelect(
                pioneer,
                coordinator,
                device_info,
            ),
        ]
    )

    async_add_entities(entities)


class TunerPresetSelect(
    PioneerTunerEntity, SelectEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer tuner preset select entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Tuner Preset"
    _attr_icon = "mdi:radio"
    _attr_options = [
        c + str(n) for c in ["A", "B", "C", "D", "E", "F", "G"] for n in range(1, 10)
    ]

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
        self._attr_current_option = None
        self.preset_frequency = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        tuner_class = self.pioneer.tuner.get("class")
        tuner_preset = self.pioneer.tuner.get("preset")
        tuner_frequency = self.pioneer.tuner.get("frequency")
        if tuner_class and tuner_preset:
            preset = tuner_class + str(tuner_preset)
            if self._attr_current_option != preset:
                self._attr_current_option = preset
                self.preset_frequency = tuner_frequency
                ## TODO: need to wait for next frequency update
            ## TODO: clear state if frequency changes from preset

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        tuner_class = option[0]
        tuner_preset = int(option[1])

        async def select_tuner_preset() -> bool:
            return await self.pioneer.select_tuner_preset(tuner_class, tuner_preset)

        await self.pioneer_command(select_tuner_preset, max_count=1)


class TunerBandSelect(
    PioneerTunerEntity, SelectEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer tuner frequency band select entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Tuner Band"
    _attr_icon = "mdi:radio"
    _attr_options = [b.value for b in TunerBand]

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

    @property
    def current_option(self) -> str | None:
        """Return the current tuner band."""
        band = self.pioneer.tuner.get("band")
        return band.value if isinstance(band, TunerBand) else None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        async def select_tuner_band() -> bool:
            return await self.pioneer.select_tuner_band(TunerBand(option))

        await self.pioneer_command(select_tuner_band, max_count=1)
