"""Support for Pioneer AVR."""
import logging
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SCAN_INTERVAL,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_SOURCES,
    CONF_PARAMS,
    SUPPORT_PIONEER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_SOURCES,
    DEFAULT_SCAN_INTERVAL,
    PIONEER_OPTIONS_UPDATE,
    OPTIONS_DEFAULTS,
    OPTIONS_ALL,
)
from aiopioneer import PioneerAVR
from aiopioneer.param import PARAMS_ALL

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PARAM_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
        vol.Optional(CONF_PARAMS, default={}): PARAM_SCHEMA,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Pioneer AVR platform."""
    _LOGGER.debug(">> async_setup_platform(%s)", config)

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    timeout = config[CONF_TIMEOUT]
    scan_interval = config[CONF_SCAN_INTERVAL]
    sources = config[CONF_SOURCES]
    params = dict(config[CONF_PARAMS])

    device_unique_id = host + ":" + str(port)

    ## Check whether platform has already been set up via config entry
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if device_unique_id in hass.data[DOMAIN]:
        _LOGGER.error(
            'AVR "%s" is already set up via integration, ignoring configuration.yaml',
            name,
        )
        return False

    try:
        ## Open AVR connection
        pioneer = PioneerAVR(
            host,
            port,
            timeout,
            scan_interval=scan_interval.total_seconds(),
            params=params,
        )
        await pioneer.connect()
        await pioneer.query_device_info()
        await pioneer.query_zones()
        if sources:
            pioneer.set_source_dict(sources)
        else:
            await pioneer.build_source_dict()

    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error(
            "Could not open AVR connection: %s: %s", type(exc).__name__, str(exc)
        )
        raise PlatformNotReady  # pylint: disable=raise-missing-from

    await _pioneer_add_entities(
        hass, None, async_add_entities, pioneer, config, unique_id=device_unique_id
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Pioneer AVR media_player from config entry."""
    _LOGGER.debug(
        ">> async_setup_entry(data=%s, options=%s)",
        entry.data,
        entry.options,
    )
    pioneer = hass.data[DOMAIN][entry.entry_id]
    data = entry.data
    entry_options = entry.options if entry.options else {}
    options = {
        **OPTIONS_DEFAULTS,
        **{k: entry_options[k] for k in OPTIONS_ALL if k in entry_options},
    }
    config = {**data, **options}
    await _pioneer_add_entities(hass, entry, async_add_entities, pioneer, config)


async def _pioneer_add_entities(
    hass, entry, async_add_entities, pioneer, config, unique_id=None
):
    """Add media_player entities for each zone."""
    _LOGGER.info("Adding entities for zones %s", pioneer.zones)
    entities = []
    if entry:
        ## Defer to entry if available
        unique_id = entry.unique_id
    for zone in pioneer.zones:
        name = config[CONF_NAME]
        if zone != "1":
            name += " HDZone" if zone == "Z" else f" Zone {zone}"
        entity = PioneerZone(entry, pioneer, zone, name, unique_id, config)
        if entity:
            _LOGGER.debug("Created entity %s for zone %s", name, zone)
            entities.append(entity)
        # if zone == "1":
        #     ## Set update callback to update Main Zone entity
        #     pioneer.set_update_callback(entity.update_callback)
    if entities:
        try:
            await pioneer.update()
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error(
                "Could not perform AVR initial update: %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise PlatformNotReady  # pylint: disable=raise-missing-from
        async_add_entities(entities, update_before_add=True)


class PioneerZone(MediaPlayerEntity):
    """Representation of a Pioneer zone."""

    def __init__(self, entry, pioneer, zone, name, unique_id, config):
        """Initialize the Pioneer zone."""
        _LOGGER.debug("PioneerZone.__init__(%s)", zone)
        self._entry = entry
        self._unique_id = unique_id
        self._pioneer = pioneer
        self._zone = zone
        self._name = name

        self._added_to_hass = False

    async def async_added_to_hass(self):
        """Complete the initialization."""
        # _LOGGER.debug(f">> async_added_to_hass({self._zone})")
        await super().async_added_to_hass()

        self._added_to_hass = True
        self._pioneer.set_zone_callback(self._zone, self.schedule_update_ha_state)
        if self._entry and self._zone == "1":
            ## Add update options dispatcher connection on Main Zone entity
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{PIONEER_OPTIONS_UPDATE}-{self._unique_id}",
                    self._async_update_options,
                )
            )

    async def shutdown(self):
        """Close connection on shutdown."""
        # _LOGGER.debug(f">> shutdown({self._zone}")
        ## Shutdown of PioneerAVR will be done at integration level

    async def _async_update_options(self, data):
        """Change options when the options flow does."""
        _LOGGER.debug(">> _async_update_options(data=%s)", data)
        pioneer = self._pioneer
        options = {**OPTIONS_DEFAULTS, **{k: data[k] for k in OPTIONS_ALL if k in data}}
        params = {k: data[k] for k in PARAMS_ALL if k in data}
        await pioneer.set_timeout(options[CONF_TIMEOUT])
        await pioneer.set_scan_interval(options[CONF_SCAN_INTERVAL])
        pioneer.set_user_params(params)

    @property
    def device_info(self):
        """Return device info."""
        name = self._name
        if self._zone == "1":
            name += " Main Zone"
        return {
            "identifiers": {(DOMAIN, self._unique_id, self._zone)},
            "manufacturer": "Pioneer",
            "sw_version": self._pioneer.software_version,
            "name": name,
            "model": self._pioneer.model,
            "via_device": (DOMAIN, self._unique_id),
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id + "/" + self._zone

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        state = self._pioneer.power.get(self._zone)
        if state is None:
            return STATE_UNKNOWN
        return STATE_ON if state else STATE_OFF

    @property
    def available(self):
        """Returns whether the device is available."""
        return self._pioneer.available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._pioneer.volume.get(self._zone)
        max_volume = self._pioneer.max_volume.get(self._zone)
        return volume / max_volume if (volume and max_volume) else 0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._pioneer.mute.get(self._zone, False)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_PIONEER

    @property
    def source(self):
        """Return the current input source."""
        source_id = self._pioneer.source.get(self._zone)
        if source_id:
            return self._pioneer.get_source_name(source_id)
        else:
            return None

    @property
    def source_list(self):
        """List of available input sources."""
        return self._pioneer.get_source_list()

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.source

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {}
        volume = self._pioneer.volume.get(self._zone)
        max_volume = self._pioneer.max_volume.get(self._zone)
        if volume is not None and max_volume is not None:
            if self._zone == "1":
                volume_db = volume / 2 - 80.5
            else:
                volume_db = volume - 81
            attrs = {
                "device_volume": volume,
                "device_max_volume": max_volume,
                "device_volume_db": volume_db,
            }
        return attrs

    @property
    def should_poll(self):
        """Polling not required: API will trigger refresh via callbacks."""
        return False

    async def async_turn_on(self):
        """Turn the media player on."""
        return await self._pioneer.turn_on(self._zone)

    async def async_turn_off(self):
        """Turn off media player."""
        return await self._pioneer.turn_off(self._zone)

    async def async_select_source(self, source):
        """Select input source."""
        return await self._pioneer.select_source(source, self._zone)

    async def async_volume_up(self):
        """Volume up media player."""
        return await self._pioneer.volume_up(self._zone)

    async def async_volume_down(self):
        """Volume down media player."""
        return await self._pioneer.volume_down(self._zone)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        max_volume = self._pioneer.max_volume.get(self._zone)
        return await self._pioneer.set_volume_level(
            round(volume * max_volume), self._zone
        )

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            return await self._pioneer.mute_on(self._zone)
        else:
            return await self._pioneer.mute_off(self._zone)

    async def async_update(self):
        """Poll properties periodically."""
        return await self._pioneer.update()

    ## HA polling disabled, TODO: to use asyncio for polling
    # def update_callback(self):
    #     """Schedule full properties update of all zones."""
    #     if self._zone == "1" and self._added_to_hass:
    #         self.schedule_update_ha_state(force_refresh=True)
