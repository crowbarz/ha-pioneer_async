"""Pioneer AVR entity base."""

from typing import Callable, Awaitable

import logging

from aiopioneer.const import Zone
from aiopioneer.exceptions import AVRError

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN, PioneerData

_LOGGER = logging.getLogger(__name__)


class PioneerEntityBase(Entity):
    """Pioneer AVR entity base class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    available_on_zones_off = False

    def __init__(self, pioneer_data: PioneerData, zone: Zone) -> None:
        """Initialize the Pioneer AVR entity base class."""
        self.pioneer_data = pioneer_data
        self.pioneer = pioneer_data.pioneer
        self.entry_options = pioneer_data.options
        self.zone = zone
        self._attr_device_info = pioneer_data.zone_device_info[zone]

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        entry_id = self.platform.config_entry.entry_id
        name_suffix = "-" + slugify(self._attr_name) if self._attr_name else ""
        zone_suffix = "-" + str(self.zone) if self.zone is not Zone.ALL else ""
        return f"{entry_id}{zone_suffix}{name_suffix}"

    @property
    def available(self) -> bool:
        """Returns whether the AVR is available and the zone is on."""
        return self.pioneer.available and (
            (
                self.zone is Zone.ALL
                and (
                    self.available_on_zones_off
                    or any(self.pioneer.properties.power.values())
                )
            )
            or (
                self.zone in self.pioneer.properties.zones
                and self.pioneer.properties.power.get(self.zone)
            )
        )

    async def pioneer_command(
        self, command: str | Callable[..., Awaitable], *args, **kwargs
    ):
        """Execute a PioneerAVR command and handle exceptions."""
        command_name = "(unknown)"
        try:
            if isinstance(command, str):
                command_name = command
                return await self.pioneer.send_command(command, *args, **kwargs)
            command_name = command.__name__
            return await command(*args, **kwargs)
        except AVRError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={
                    "command": command_name,
                    "exc": str(exc),
                },
            ) from exc
        except Exception as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=getattr(exc, "translation_key", "unknown_exception"),
                translation_placeholders={
                    "command": command_name,
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
