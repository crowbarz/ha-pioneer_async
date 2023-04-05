"""Integration debugging."""

import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Debug:
    """Global debug."""

    level = 0  # deprecated
    config = {}

    def setconfig(self, config: dict[str, int] | None) -> None:
        """Set debug model config."""
        _LOGGER.debug(">> Debug.setconfig(%s)", config)
        Debug.config = config

    def atlevel(self, level: int, category_raw: str) -> bool:
        """Determine if debug is at a level"""
        if not Debug.config:
            return False
        category = category_raw.partition(DOMAIN + ".")[2] or DOMAIN
        try:
            debug_level_str = Debug.config.get(category, 0)
            debug_level = int(debug_level_str)
        except ValueError:
            _LOGGER.error(
                "invalid debug level for category %s: %s", category, debug_level_str
            )
            return None
        return debug_level >= level
