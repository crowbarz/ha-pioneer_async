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
