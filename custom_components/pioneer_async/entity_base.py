"""Pioneer AVR entity base."""

import asyncio
import logging

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones, SOURCE_TUNER

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .debug import Debug

_LOGGER = logging.getLogger(__name__)


def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


class PioneerEntityBase(Entity):
    """Pioneer AVR base entity class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        pioneer: PioneerAVR,
        device_info: DeviceInfo,
        zone: Zones | None = None,
    ) -> None:
        """Initialize the Pioneer AVR display sensor."""
        if _debug_atlevel(9):
            _LOGGER.debug("%s.__init__()", type(self).__name__)
        self.pioneer = pioneer
        self.zone = zone
        self._attr_device_info = device_info

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        entry_id = self.platform.config_entry.entry_id
        name_suffix = "-" + slugify(self._attr_name) if self._attr_name else ""
        zone_suffix = "-" + str(self.zone) if self.zone is not None else ""
        return f"{entry_id}{zone_suffix}{name_suffix}"

    @property
    def available(self) -> bool:
        """Returns whether the device is available."""
        return self.pioneer.available and (
            self.zone is None or self.zone in self.pioneer.zones
        )

    async def pioneer_command(self, aw_f, max_count: int = 4) -> None:
        """Execute a PioneerAVR command, handle exceptions and optionally repeating."""
        try:
            count = 0
            while count < max_count and await aw_f() is False:
                await asyncio.sleep(1)
                count += 1
                if count < max_count:
                    _LOGGER.warning(
                        "repeating failed command (%d): %s", count, aw_f.__name__
                    )
            if count >= max_count:
                raise ServiceValidationError(f"AVR command {aw_f.__name__} unavailable")
        except Exception as exc:
            raise ServiceValidationError(
                f"AVR command {aw_f.__name__} failed: {exc}"
            ) from exc


class PioneerTunerEntity(PioneerEntityBase):
    """Pioneer AVR tuner entity."""

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and SOURCE_TUNER in self.pioneer.source.values()
