"""Pioneer AVR data update coordinator."""

import logging

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PioneerAVRZoneCoordinator(DataUpdateCoordinator):
    """Pioneer AVR Zone coordinator."""

    def __init__(self, hass: HomeAssistant, pioneer: PioneerAVR, zone: Zones) -> None:
        """Initialise Pioneer AVR coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.pioneer = pioneer
        self.zone = zone

    async def _async_update_data(self) -> None:
        """Update Pioneer AVR."""

    def set_zone_callback(self) -> None:
        """Set aiopioneer zone callback to trigger HA zone update."""

        def callback_zone_update() -> None:
            self.async_set_updated_data(None)

        self.pioneer.set_zone_callback(Zones(self.zone), callback_zone_update)
        if self.zone == "1":
            self.pioneer.set_zone_callback(Zones.ALL, callback_zone_update)
