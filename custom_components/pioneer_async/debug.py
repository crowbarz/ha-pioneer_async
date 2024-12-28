"""Integration debugging."""

import logging
from .const import (
    CONF_DEBUG_ACTION,
    CONF_DEBUG_CONFIG_FLOW,
    CONF_DEBUG_INTEGRATION,
)

_LOGGER = logging.getLogger(__name__)


class Debug:
    """Global debug."""

    ## Debug classes
    integration: bool = None
    config_flow: bool = None
    action: bool = None

    @staticmethod
    def setconfig(options: dict[str, int] | None) -> None:
        """Set debug model config."""
        _LOGGER.debug(
            ">> Debug.setconfig(%s)",
            {k: v for k, v in options.items() if k.startswith("debug_")},
        )
        Debug.integration = options.get(CONF_DEBUG_INTEGRATION, False)
        Debug.config_flow = options.get(CONF_DEBUG_CONFIG_FLOW, False)
        Debug.action = options.get(CONF_DEBUG_ACTION, False)
