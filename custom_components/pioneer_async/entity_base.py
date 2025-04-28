"""Pioneer AVR entity base."""

from typing import Any, Callable, Awaitable

import logging

from aiopioneer import PioneerAVR
from aiopioneer.const import Zone
from aiopioneer.exceptions import AVRError

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PioneerEntityBase(Entity):
    """Pioneer AVR entity base class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        pioneer: PioneerAVR,
        options: dict[str, Any],
        device_info: DeviceInfo,
        zone: Zone | None = None,
    ) -> None:
        """Initialize the Pioneer AVR entity base class."""
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
            or (
                self.zone in self.pioneer.properties.zones
                and self.pioneer.properties.power.get(self.zone)
            )
        )

    async def pioneer_command(
        self, aw_f: Callable[..., Awaitable], command: str = None
    ):
        """Execute a PioneerAVR command and handle exceptions."""
        if command is None:
            command = aw_f.__name__
        try:
            return await aw_f()
        except AVRError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={
                    "command": command,
                    "exc": str(exc),
                },
            ) from exc
        except Exception as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=getattr(exc, "translation_key", "unknown_exception"),
                translation_placeholders={
                    "command": command,
                    "zone": self.zone,
                    "exc": repr(exc),
                },
            ) from exc


class PioneerTunerEntity(PioneerEntityBase):
    """Pioneer AVR tuner entity."""

    @property
    def available(self) -> bool:
        """Returns whether the AVR is available and source is set to tuner."""
        if not super().available:
            return False
        return self.pioneer.properties.is_source_tuner()
