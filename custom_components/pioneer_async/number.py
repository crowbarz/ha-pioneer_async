"""Pioneer AVR number entities."""

from __future__ import annotations

import logging
from typing import Any

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone, TunerBand

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
from .debug import Debug
from .entity_base import PioneerTunerEntity


_LOGGER = logging.getLogger(__name__)

TUNER_FREQ_ATTRS = {
    TunerBand.AM: {
        "unit_of_measurement": "kHz",
        "min_value": 530,  #  updated from aiopioneer
        "max_value": 1701,
        "step": 1,
    },
    TunerBand.FM: {
        "unit_of_measurement": "MHz",
        "min_value": 87.5,
        "max_value": 108.0,
        "step": 0.05,
    },
}
TUNER_AM_FREQ_MIN = {9: 531, 10: 530}
TUNER_AM_FREQ_MAX = {9: 1701, 10: 1700}


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
    if Debug.integration:
        _LOGGER.debug(
            ">> number.async_setup_entry(entry_id=%s, data=%s, options=%s)",
            config_entry.entry_id,
            config_entry.data,
            options,
        )

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

    async_add_entities(entities)


class TunerFrequencyNumber(
    PioneerTunerEntity, NumberEntity, CoordinatorEntity
):  # pylint: disable=abstract-method
    """Pioneer tuner frequency number entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.FREQUENCY
    _attr_icon = "mdi:radio-tower"
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
        self._attr_mode = NumberMode.BOX

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
            self._attr_native_min_value = TUNER_AM_FREQ_MIN[am_frequency_step]
            self._attr_native_max_value = TUNER_AM_FREQ_MAX[am_frequency_step]
        return attrs

    async def async_set_native_value(self, value: float) -> None:
        """Set the tuner frequency."""

        async def set_tuner_frequency() -> bool:
            return await self.pioneer.set_tuner_frequency(self.band, value)

        await self.pioneer_command(set_tuner_frequency, repeat=True)
