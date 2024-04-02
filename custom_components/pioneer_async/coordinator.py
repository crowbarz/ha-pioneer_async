"""Pioneer AVR data update coordinator."""

import logging

from collections.abc import Callable

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PioneerAVRZoneCoordinator(DataUpdateCoordinator):
    """Pioneer AVR Zone coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        pioneer: PioneerAVR,
        zone: Zones,
        initial_update_callback: Callable[[], None] = None,
    ) -> None:
        """Initialise Pioneer AVR coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.pioneer = pioneer
        self.zone = zone
        self._initial_update_callback = initial_update_callback
        self._initial_update = False

    async def _async_update_data(self) -> None:
        """Update Pioneer AVR."""

    def set_zone_callback(self) -> None:
        """Set aiopioneer zone callback to trigger HA zone update."""

        def callback_zone_update() -> None:
            if (
                self._initial_update_callback is not None
                and not self._initial_update
                and self.pioneer.initial_update
            ):
                self._initial_update = True
                self._initial_update_callback()
            self.async_set_updated_data(None)

        self.pioneer.set_zone_callback(self.zone, callback_zone_update)
