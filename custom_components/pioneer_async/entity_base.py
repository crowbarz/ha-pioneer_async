"""Pioneer AVR entity base."""

from typing import Any

import asyncio
import logging

from aiopioneer import PioneerAVR
from aiopioneer.const import Zones, SOURCE_TUNER

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import CONF_REPEAT_COUNT
from .debug import Debug

_LOGGER = logging.getLogger(__name__)


def _debug_atlevel(level: int, category: str = __name__):
    return Debug.atlevel(None, level, category)


class PioneerEntityBase(Entity):
    """Pioneer AVR entity base class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        device_info: DeviceInfo,
        zone: Zones | None = None,
    ) -> None:
        """Initialize the Pioneer AVR entity base class."""
        if _debug_atlevel(9):
            _LOGGER.debug("%s.__init__()", type(self).__name__)
        self.pioneer = pioneer
        self.entry_options = options
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
        """Returns whether the AVR is available and the zone is on."""
        return self.pioneer.available and (
            self.zone is None
            or (self.zone in self.pioneer.zones and self.pioneer.power.get(self.zone))
        )

    async def pioneer_command(self, aw_f, repeat: bool = False) -> None:
        """Execute a PioneerAVR command, handle exceptions and optionally repeating."""
        options = self.entry_options
        repeat_count = options[CONF_REPEAT_COUNT] if repeat else 1

        try:
            count = 0
            while count < repeat_count and await aw_f() is False:
                await asyncio.sleep(1)
                count += 1
                if count < repeat_count:
                    _LOGGER.warning(
                        "repeating failed command (%d): %s", count, aw_f.__name__
                    )
            if count >= repeat_count:
                raise ServiceValidationError(f"AVR command {aw_f.__name__} unavailable")
        except Exception as exc:
            raise ServiceValidationError(
                f"AVR command {aw_f.__name__} failed: {exc}"
            ) from exc


class PioneerTunerEntity(PioneerEntityBase):
    """Pioneer AVR tuner entity."""

    @property
    def available(self) -> bool:
        """Returns whether the AVR is available and source is set to tuner."""
        if not super().available:
            return False
        return bool(
            [
                z
                for z, s in self.pioneer.source.items()
                if s == SOURCE_TUNER and self.pioneer.power.get(Zones(z))
            ]
        )
