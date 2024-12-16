"""Pioneer AVR data update coordinator."""

import logging

from collections.abc import Callable

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones
from aiopioneer.param import PARAM_ZONES_INITIAL_REFRESH

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
    ) -> None:
        """Initialise Pioneer AVR coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.pioneer = pioneer
        self.zone = zone
        self._initial_refresh_callback = None
        self._initial_refresh = False

    async def _async_update_data(self) -> None:
        """Update Pioneer AVR."""

    def set_initial_refresh_callback(
        self, initial_refresh_callback: Callable[[], None]
    ) -> None:
        """Set callback when zone is first updated."""
        self._initial_refresh_callback = initial_refresh_callback

    def set_zone_callback(self) -> None:
        """Set aiopioneer zone callback to trigger HA zone update."""

        def callback_zone_update() -> None:
            zones_initial_refresh: set[Zones] = self.pioneer.params.get_system_param(
                PARAM_ZONES_INITIAL_REFRESH, set()
            )
            if (
                self._initial_refresh_callback is not None
                and not self._initial_refresh
                and self.zone in zones_initial_refresh
            ):
                self._initial_refresh = True
                self._initial_refresh_callback()
            self.async_set_updated_data(None)

        self.pioneer.set_zone_callback(self.zone, callback_zone_update)
