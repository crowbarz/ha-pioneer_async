""" Pioneer AVR API. """
# pylint: disable=logging-format-interpolation,broad-except,relative-beyond-top-level

import asyncio
import time
import logging
import re
from .util import sock_set_keepalive, get_backoff_delay, cancel_task

_LOGGER = logging.getLogger(__name__)

MAX_VOLUME = 185
MAX_VOLUME_ZONEX = 81
MAX_SOURCE_NUMBERS = 60

PIONEER_COMMANDS = {
    "turn_on": {
        "1": ["PO", "PWR"],
        "2": ["APO", "APR"],
        "3": ["BPO", "BPR"],
        "Z": ["ZEO", "ZEP"],
    },
    "turn_off": {
        "1": ["PF", "PWR"],
        "2": ["APF", "APR"],
        "3": ["BPF", "BPR"],
        "Z": ["ZEF", "ZEP"],
    },
    "select_source": {
        "1": ["FN", "FN"],
        "2": ["ZS", "Z2F"],
        "3": ["ZT", "Z3F"],
        "Z": ["ZEA", "ZEA"],
    },
    "volume_up": {
        "1": ["VU", "VOL"],
        "2": ["ZU", "ZV"],
        "3": ["YU", "YV"],
        "Z": ["HZU", "XV"],
    },
    "volume_down": {
        "1": ["VD", "VOL"],
        "2": ["ZD", "ZV"],
        "3": ["YD", "YV"],
        "Z": ["HZD", "XV"],
    },
    "set_volume_level": {
        "1": ["VL", "VOL"],
        "2": ["ZV", "ZV"],
        "3": ["YV", "YV"],
        "Z": ["HZV", "XV"],
    },
    "mute_on": {
        "1": ["MO", "MUT"],
        "2": ["Z2MO", "Z2MUT"],
        "3": ["Z3MO", "Z3MUT"],
        "Z": ["HZMO", "HZMUT"],
    },
    "mute_off": {
        "1": ["MF", "MUT"],
        "2": ["Z2MF", "Z2MUT"],
        "3": ["Z3MF", "Z3MUT"],
        "Z": ["HZMF", "HZMUT"],
    },
    "query_power": {
        "1": ["?P", "PWR"],
        "2": ["?AP", "APR"],
        "3": ["?BP", "BPR"],
        "Z": ["?ZEP", "ZEP"],
    },
    "query_volume": {
        "1": ["?V", "VOL"],
        "2": ["?ZV", "ZV"],
        "3": ["?YV", "YV"],
        "Z": ["?HZV", "XV"],
    },
    "query_mute": {
        "1": ["?M", "MUT"],
        "2": ["?Z2M", "Z2MUT"],
        "3": ["?Z3M", "Z3MUT"],
        "Z": ["?HZM", "HZMUT"],
    },
    "query_source_id": {
        "1": ["?F", "FN"],
        "2": ["?ZS", "Z2F"],
        "3": ["?ZT", "Z3F"],
        "Z": ["?ZEA", "ZEA"],
    },
    "query_mac_addr": {"1": ["?SVB", "SVB"]},
    "query_software_version": {"1": ["?SSI", "SSI"]},
    "query_model": {"1": ["?RGD", "RGD"]},
}


class PioneerAVR:
    """ Pioneer AVR interface. """

    def __init__(
        self,
        host,
        port=8102,
        timeout=2,
        scan_interval=60,
        command_delay=0.1,
        volume_workaround=False,
        volume_steps=False,
    ):
        """ Initialize the Pioneer AVR interface. """
        _LOGGER.debug(
            f'PioneerAVR.__init__(host="{host}", port={port}, timeout={timeout}, command_delay={command_delay}, volume_workaround={volume_workaround}, volume_steps={volume_steps})'
        )
        self._host = host
        self._port = port
        self._timeout = timeout
        self.scan_interval = scan_interval
        self.command_delay = command_delay
        self.volume_workaround = volume_workaround
        self.volume_steps = volume_steps

        ## Public properties
        self.model = None
        self.software_version = None
        self.mac_addr = None
        self.available = False
        self.zones = []
        self.power = {}
        self.volume = {}
        self.max_volume = {}
        self.mute = {}
        self.source = {}

        ## Internal state
        self._connect_lock = asyncio.Lock()
        self._disconnect_lock = asyncio.Lock()
        self._update_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._reconnect = True
        self._full_update = True
        self._last_updated = 0.0
        self._last_command = 0.0
        self._reader = None
        self._writer = None
        self._listener_task = None
        self._responder_task = None
        self._reconnect_task = None
        self._updater_task = None
        # self._response_commands = []
        self._source_name_to_id = {}
        self._source_id_to_name = {}
        self._zone_callback = {}
        self._update_callback = None

    def __del__(self):
        _LOGGER.debug("PioneerAVR.__del__()")

    ## Connection/disconnection
    async def connect(self, from_reconnect=False):
        """ Open connection to AVR and start listener thread. """
        # _LOGGER.debug(f">> PioneerAVR.connect(from_reconnect={from_reconnect})")
        if self._connect_lock.locked():
            _LOGGER.warning("AVR connection is already connecting, skipping connect")
            return
        if self.available:
            _LOGGER.warning("AVR is connected, skipping connect")
            return

        async with self._connect_lock:
            _LOGGER.debug("Opening AVR connection")
            if self._writer is not None:
                raise RuntimeError("AVR connection already established")

            ## Cancel any active reconnect task
            if not from_reconnect:
                await self.reconnect_cancel()

            ## Open new connection
            reader, writer = await asyncio.wait_for(  # pylint: disable=unused-variable
                asyncio.open_connection(self._host, self._port), timeout=self._timeout
            )
            _LOGGER.info("AVR connection established")
            self._reader = reader
            self._writer = writer
            self.available = True
            self._set_socket_options()

            await self.responder_cancel()
            await self.listener_schedule()
            await asyncio.sleep(0)  # yield to listener task
            await self.updater_schedule()

    def _set_socket_options(self):
        """ Set socket keepalive options. """
        sock_set_keepalive(
            self._writer.get_extra_info("socket"),
            after_idle_sec=int(self._timeout),
            interval_sec=int(self._timeout),
            max_fails=3,
        )

    async def set_timeout(self, timeout):
        """ Set timeout and update socket keepalive options. """
        self._timeout = timeout
        self._set_socket_options()

    async def set_scan_interval(self, scan_interval):
        """ Set scan interval and restart updater. """
        self.scan_interval = scan_interval
        await self.updater_schedule()

    async def disconnect(self):
        """ Shutdown and close telnet connection to AVR. """
        # _LOGGER.debug(">> PioneerAVR.disconnect()")

        if self._disconnect_lock.locked():
            _LOGGER.warning(
                "AVR connection is already disconnecting, skipping disconnect"
            )
            return
        if not self.available:
            _LOGGER.warning("AVR not connected, skipping disconnect")
            return

        async with self._disconnect_lock:
            _LOGGER.debug("Disconnecting AVR connection")
            self.available = False
            self.call_zone_callbacks()

            writer = self._writer
            if writer:
                ## Close AVR connection
                _LOGGER.debug("Closing AVR connection")
                self._writer.close()
                # TODO: await wait_closed() hangs the coroutine, skipping for now
                # try:
                #     await asyncio.wait_for(
                #         self._writer.wait_closed(), timeout=self._timeout
                #     )
                # except asyncio.TimeoutError:
                #     _LOGGER.debug("Timeout waiting for connection to close, continuing")
                # await self._writer.wait_closed()

            self._reader = None
            self._writer = None
            _LOGGER.info("AVR connection closed")

            await self.responder_cancel()
            await self.updater_cancel()
            await self.listener_cancel()
            await self.reconnect_schedule()

    async def shutdown(self):
        """ Shutdown the client. """
        # _LOGGER.debug(">> PioneerAVR.shutdown()")
        self._reconnect = False
        await self.disconnect()

    async def reconnect(self):
        """ Reconnect to an AVR. """
        # _LOGGER.debug(">> PioneerAVR.reconnect() started")
        retry = 0
        try:
            while True:
                delay = get_backoff_delay(retry)
                _LOGGER.debug(f"Waiting {delay}s before retrying connection")
                await asyncio.sleep(delay)

                retry += 1
                try:
                    await self.connect(from_reconnect=True)
                    _LOGGER.debug("Scheduling full AVR status update")
                    self._full_update = True
                    await self.update()
                    break
                except Exception as e:  # pylint: disable=invalid-name
                    _LOGGER.debug(
                        f"Could not reconnect to AVR: {type(e).__name__}: {e}"
                    )
                    if self.available:
                        await self.disconnect()
        except asyncio.CancelledError:
            _LOGGER.warning("AVR reconnection cancelled")

        # _LOGGER.debug(">> PioneerAVR.reconnect() completed")

    async def reconnect_schedule(self):
        """ Schedule reconnection to the AVR. """
        if self._reconnect:
            reconnect_task = self._reconnect_task
            if reconnect_task:
                if reconnect_task.done():
                    reconnect_task = None  ## trigger new task creation
            if reconnect_task is None:
                _LOGGER.info("Reconnecting to AVR")
                reconnect_task = asyncio.create_task(self.reconnect())
                self._reconnect_task = reconnect_task
            else:
                _LOGGER.warning("AVR listener reconnection already scheduled")

    async def reconnect_cancel(self):
        """ Cancel any active reconnect task. """
        # _LOGGER.debug(">> PioneerAVR.reconnect_cancel()")
        await cancel_task(self._reconnect_task, "reconnect")
        self._reconnect_task = None

    async def connection_listener(self):
        """ AVR connection listener. Parse responses and update state. """
        _LOGGER.debug(">> PioneerAVR.connection_listener() started")
        while self.available:
            response = await self.read_response()
            if response is None:
                ## Connection closed or exception, exit task
                break

            ## Check for empty response
            self._last_updated = time.time()  ## include empty responses
            if not response:
                _LOGGER.debug("Ignoring empty response")
                ## Skip processing empty responses (keepalives?)
                continue
            _LOGGER.debug(f"AVR listener received response: {response}")

            ## Parse response, update cached properties
            updated_zones = self.parse_response(response)

            ## NOTE: to avoid deadlocks, do not run any operations that
            ## depend on further responses (returned by the listener) within
            ## the listener loop.

            if updated_zones:
                ## Call zone callbacks for updated zones
                self.call_zone_callbacks(updated_zones)
                ## NOTE: updating zone 1 does not seem to reset its scan
                ## interval.

        if self.available:
            ## Trigger disconnection if not already disconnecting
            await self.disconnect()
        _LOGGER.debug(">> PioneerAVR.connection_listener() completed")

    async def listener_schedule(self):
        """ Schedule the listener task. """
        await self.listener_cancel()
        self._listener_task = asyncio.create_task(self.connection_listener())

    async def listener_cancel(self):
        """ Cancel the listener task. """
        # _LOGGER.debug(">> PioneerAVR.listener_cancel()")
        await cancel_task(self._listener_task, "listener")
        self._listener_task = None

    ## Read responses from AVR
    async def read_response(self, timeout=None):
        """ Wait for a response from AVR and return to all readers. """
        # _LOGGER.debug(f">> PioneerAVR.read_response(timeout={timeout})")

        ## Create responder task if not already created
        responder_task = self._responder_task
        if responder_task:
            if responder_task.done():
                responder_task = None  ## trigger new task creation
        if responder_task is None:
            responder_task = asyncio.create_task(self._reader.readuntil(b"\n"))
            self._responder_task = responder_task
            # _LOGGER.debug(f"Created responder task {responder_task}")
        else:
            ## Wait on existing responder task
            # _LOGGER.debug(f"Using existing responder task {responder_task}")
            pass

        ## Wait for result and process
        task_name = asyncio.current_task().get_name()
        try:
            if timeout:
                # _LOGGER.debug(f"{task_name}: waiting for data (timeout={timeout})")
                done, pending = await asyncio.wait(  # pylint: disable=unused-variable
                    [responder_task], timeout=timeout
                )
                if done:
                    raw_response = responder_task.result()
                else:
                    # _LOGGER.debug(f"{task_name}: timed out waiting for data")
                    return None
            else:
                # _LOGGER.debug(f"{task_name}: waiting for data")
                raw_response = await responder_task
        except (asyncio.CancelledError, EOFError, TimeoutError):
            ## Connection closed
            _LOGGER.debug(f"{task_name}: connection closed")
            return None
        response = raw_response.decode().strip()
        # _LOGGER.debug(f"{task_name}: received response: {response}")
        return response

    async def responder_cancel(self):
        """ Cancel any active responder task. """
        # _LOGGER.debug(">> PioneerAVR.responder_cancel()")
        await cancel_task(self._responder_task, "responder")
        self._responder_task = None

    ## Send commands and requests to AVR
    async def send_raw_command(self, command, rate_limit=True):
        """ Send a raw command to the AVR. """
        # _LOGGER.debug(
        #     f'>> PioneerAVR.send_raw_command("{command}", rate_limit={rate_limit})'
        # )
        if not self.available:
            raise RuntimeError("AVR connection not available")

        if rate_limit:
            ## Rate limit commands
            since_command = time.time() - self._last_command
            if since_command < self.command_delay:
                delay = self.command_delay - since_command
                _LOGGER.debug(f"Delaying command for {delay:.3f}s")
                await asyncio.sleep(self.command_delay - since_command)
        _LOGGER.debug(f"Sending AVR command: {command}")
        self._writer.write(command.encode("ASCII") + b"\r")
        await self._writer.drain()
        self._last_command = time.time()

    async def send_raw_request(
        self, command, response_prefix, ignore_error=None, rate_limit=True
    ):
        """ Send a raw command to the AVR and return the response. """
        # _LOGGER.debug(
        #     f'>> PioneerAVR.send_raw_request("{command}", {response_prefix}, ignore_error={ignore_error}, rate_limit={rate_limit})'
        # )
        async with self._request_lock:
            await self.send_raw_command(command, rate_limit=rate_limit)
            while True:
                response = await self.read_response(timeout=self._timeout)

                ## Check response
                if response is None:
                    _LOGGER.debug(f"AVR command {command} timed out")
                    return None
                elif response.startswith(response_prefix):
                    _LOGGER.debug(
                        f"AVR command {command} returned response: {response}"
                    )
                    return response
                elif response.startswith("E"):
                    err = f"AVR command {command} returned error: {response}"
                    if ignore_error is None:
                        raise RuntimeError(err)
                    elif not ignore_error:
                        _LOGGER.error(err)
                        return False
                    elif ignore_error:
                        _LOGGER.debug(err)
                        return False

    async def send_command(
        self, command, zone="1", prefix="", ignore_error=None, rate_limit=True
    ):
        """ Send a command or request to the device. """
        # pylint: disable=unidiomatic-typecheck
        # _LOGGER.debug(
        #     f'>> PioneerAVR.send_command("{command}", zone="{zone}", prefix="{prefix}", ignore_error={ignore_error}, rate_limit={rate_limit})'
        # )
        raw_command = PIONEER_COMMANDS.get(command, {}).get(zone)
        try:
            if type(raw_command) is list:
                if len(raw_command) == 2:
                    ## Handle command as request
                    expected_response = raw_command[1]
                    raw_command = raw_command[0]
                    response = await self.send_raw_request(
                        prefix + raw_command,
                        expected_response,
                        ignore_error,
                        rate_limit,
                    )
                    # _LOGGER.debug(f"send_command received response: {response}")
                    return response
                else:
                    _LOGGER.error(f"Invalid request {raw_command} for zone {zone}")
                    return None
            elif type(raw_command) is str:
                return await self.send_raw_command(prefix + raw_command, rate_limit)
            else:
                _LOGGER.warning(f"Invalid command {command} for zone {zone}")
                return None
        except RuntimeError:
            _LOGGER.error(f"Cannot execute {command} command: AVR not connected")
            return False

    ## Initialisation functions
    async def query_zones(self):
        """ Query zones on Pioneer AVR by querying power status. """
        if not self.zones:
            _LOGGER.info("Querying available zones on AVR")
            if await self.send_command("query_power", "1", ignore_error=True):
                _LOGGER.info("Zone 1 discovered")
                if "1" not in self.zones:
                    self.zones.append("1")
                    self.max_volume["1"] = MAX_VOLUME
            else:
                raise RuntimeError("Main Zone not found on AVR")
            if await self.send_command("query_power", "2", ignore_error=True):
                _LOGGER.info("Zone 2 discovered")
                if "2" not in self.zones:
                    self.zones.append("2")
                    self.max_volume["2"] = MAX_VOLUME_ZONEX
            if await self.send_command("query_power", "3", ignore_error=True):
                _LOGGER.info("Zone 3 discovered")
                if "3" not in self.zones:
                    self.zones.append("3")
                    self.max_volume["3"] = MAX_VOLUME_ZONEX
            if await self.send_command("query_power", "Z", ignore_error=True):
                _LOGGER.info("HDZone discovered")
                if "Z" not in self.zones:
                    self.zones.append("Z")
                    self.max_volume["Z"] = MAX_VOLUME_ZONEX

    def set_source_dict(self, sources):
        """ Manually set source id<->name translation tables. """
        self._source_name_to_id = sources
        self._source_id_to_name = {v: k for k, v in sources.items()}

    async def build_source_dict(self):
        """ Generate source id<->name translation tables. """
        timeouts = 0
        if not self._source_name_to_id:
            _LOGGER.info("Querying AVR source names")
            for src in range(MAX_SOURCE_NUMBERS):
                response = await self.send_raw_request(
                    "?RGB" + str(src).zfill(2),
                    "RGB",
                    ignore_error=True,
                    rate_limit=False,
                )
                if response is None:
                    timeouts += 1
                    _LOGGER.debug(f"Timeout {timeouts} retrieving source {src}")
                elif response is not False:
                    timeouts = 0
                    source_name = response[6:]
                    source_active = response[5] == "1"
                    source_number = str(src).zfill(2)
                    if source_active:
                        self._source_name_to_id[source_name] = source_number
                        self._source_id_to_name[source_number] = source_name
            _LOGGER.debug(f"Source name->id: {self._source_name_to_id}")
            _LOGGER.debug(f"Source id->name: {self._source_id_to_name}")
        if not self._source_name_to_id:
            _LOGGER.warning("no input sources found on AVR")

    def get_source_list(self):
        """ Return list of available input sources. """
        return list(self._source_name_to_id.keys())

    async def query_device_info(self):
        """ Query device information from Pioneer AVR. """
        if self.model or self.mac_addr or self.software_version:
            return

        _LOGGER.info("Querying device information from Pioneer AVR")
        model = None
        mac_addr = None
        software_version = None

        ## Query model via command
        data = await self.send_command("query_model", ignore_error=True)
        if data:
            matches = re.search(r"<([^>/]{5,})(/.[^>]*)?>", data)
            if matches:
                model = matches.group(1)

        ## Query MAC address via command
        data = await self.send_command("query_mac_addr", ignore_error=True)
        if data:
            mac_addr = data[0:2] + ":" + data[2:4] + ":" + data[4:6]
            mac_addr += ":" + data[6:8] + ":" + data[8:10] + ":" + data[10:12]

        ## Query software version via command
        data = await self.send_command("query_software_version", ignore_error=True)
        if data:
            matches = re.search(r'SSI"([^)]*)"', data)
            if matches:
                software_version = matches.group(1)

        self.model = model if model else "unknown"
        self.mac_addr = mac_addr if mac_addr else "unknown"
        self.software_version = software_version if software_version else "unknown"

        # TODO: Query via HTML page if all info is not available from command
        # http://avr/1000/system_information.asp
        # VSX-930 will report model and software version, but not MAC address.
        # Unknown how iControlAV5 determines this on a routed network.

    ## Callback functions
    def set_zone_callback(self, zone, callback):
        """ Register a callback for a zone. """
        if zone in self.zones:
            if callback:
                self._zone_callback[zone] = callback
            else:
                self._zone_callback.pop(zone)

    def call_zone_callbacks(self, zones=None):
        """ Call callbacks to signal updated zone(s). """
        if zones is None:
            zones = self.zones
        for zone in zones:
            if zone in self._zone_callback:
                callback = self._zone_callback[zone]
                if callback:
                    _LOGGER.debug(f"Calling callback for zone {zone}")
                    callback()

    def set_update_callback(self, callback):
        """ Register a callback to trigger update. """
        if callback:
            self._update_callback = callback
        else:
            self._update_callback = None

    def call_update_callback(self):
        """ Trigger update. """
        if self._update_callback:
            _LOGGER.debug("Calling update callback")
            self._update_callback()

    ## Update functions
    def parse_response(self, response):
        """ Parse response and update cached parameters. """
        updated_zones = set()
        if response.startswith("PWR"):
            value = response == "PWR0"
            if self.power.get("1") != value:
                self.power["1"] = value
                updated_zones.add("1")
                _LOGGER.info(f"Zone 1: Power: {value}")
        elif response.startswith("APR"):
            value = response == "APR0"
            if self.power.get("2") != value:
                self.power["2"] = value
                updated_zones.add("2")
                _LOGGER.info(f"Zone 2: Power: {value}")
        elif response.startswith("BPR"):
            value = response == "BPR0"
            if self.power.get("3") != value:
                self.power["3"] = value
                updated_zones.add("3")
                _LOGGER.info(f"Zone 3: Power: {value}")
        elif response.startswith("ZEP"):
            value = response == "ZEP0"
            if self.power.get("Z") != value:
                self.power["Z"] = value
                updated_zones.add("Z")
                _LOGGER.info(f"HDZone: Power: {value}")

        elif response.startswith("VOL"):
            value = int(response[3:])
            if self.volume.get("1") != value:
                self.volume["1"] = value
                updated_zones.add("1")
                _LOGGER.info(f"Zone 1: Volume: {value}")
        elif response.startswith("ZV"):
            value = int(response[2:])
            if self.volume.get("2") != value:
                self.volume["2"] = value
                updated_zones.add("2")
                _LOGGER.info(f"Zone 2: Volume: {value}")
        elif response.startswith("YV"):
            value = int(response[2:])
            if self.volume.get("3") != value:
                self.volume["3"] = value
                updated_zones.add("3")
                _LOGGER.info(f"Zone 3: Volume: {value}")
        elif response.startswith("XV"):
            value = int(response[2:])
            if self.volume.get("Z") != value:
                self.volume["Z"] = value
                updated_zones.add("Z")
                _LOGGER.info(f"HDZone: Volume: {value}")

        elif response.startswith("MUT"):
            value = response == "MUT0"
            if self.mute.get("1") != value:
                self.mute["1"] = value
                updated_zones.add("1")
                _LOGGER.info(f"Zone 1: Mute: {value}")
        elif response.startswith("Z2MUT"):
            value = response == "Z2MUT0"
            if self.mute.get("2") != value:
                self.mute["2"] = value
                updated_zones.add("2")
                _LOGGER.info(f"Zone 2: Mute: {value}")
        elif response.startswith("Z3MUT"):
            value = response == "Z3MUT0"
            if self.mute.get("3") != value:
                self.mute["3"] = value
                updated_zones.add("3")
                _LOGGER.info(f"Zone 3: Mute: {value}")
        elif response.startswith("HZMUT"):
            value = response == "HZMUT0"
            if self.mute.get("Z") != value:
                self.mute["Z"] = value
                updated_zones.add("Z")
                _LOGGER.info(f"HDZone: Mute: {value}")

        elif response.startswith("FN"):
            raw_id = response[2:]
            value = self._source_id_to_name.get(raw_id, raw_id)
            if self.source.get("1") != value:
                self.source["1"] = value
                updated_zones.add("1")
                _LOGGER.info(f"Zone 1: Source: {value}")
        elif response.startswith("Z2F"):
            raw_id = response[3:]
            value = self._source_id_to_name.get(raw_id, raw_id)
            if self.source.get("2") != value:
                self.source["2"] = value
                updated_zones.add("2")
                _LOGGER.info(f"Zone 2: Source: {value}")
        elif response.startswith("Z3F"):
            raw_id = response[3:]
            value = self._source_id_to_name.get(raw_id, raw_id)
            if self.source.get("3") != value:
                value = self.source["3"]
                updated_zones.add("3")
                _LOGGER.info(f"Zone 3: Source: {value}")
        elif response.startswith("ZEA"):
            raw_id = response[3:]
            value = self._source_id_to_name.get(raw_id, raw_id)
            if self.source.get("Z") != value:
                self.source["Z"] = value
                updated_zones.add("Z")
                _LOGGER.info(f"HDZone: Source: {value}")
        return updated_zones

    async def updater(self):
        """ Perform update every scan_interval. """
        while True:
            try:
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                return
            await self.update()

    async def updater_schedule(self):
        """ Schedule/reschedule the update task. """
        await self.updater_cancel()
        if self.scan_interval:
            self._updater_task = asyncio.create_task(self.updater())

    async def updater_cancel(self):
        """ Cancel the updater task. """
        updater_task = self._updater_task
        if updater_task:
            await cancel_task(self._updater_task, "updater")
            self._updater_task = None

    async def update_zone(self, zone):
        """ Update an AVR zone. """
        ## Check for timeouts, but ignore errors (eg. ?V will
        ## return E02 immediately after power on)
        if (
            await self.send_command("query_power", zone, ignore_error=True) is None
            or await self.send_command("query_volume", zone, ignore_error=True) is None
            or await self.send_command("query_mute", zone, ignore_error=True) is None
            or await self.send_command("query_source_id", zone, ignore_error=True)
            is None
        ):
            ## Timeout occurred, indicates AVR disconnected
            raise TimeoutError("Timeout waiting for data")

    async def update(self):
        """ Update AVR cached status. """
        if self._update_lock.locked():
            _LOGGER.warning("AVR update already running, skipping")
            return False
        if not self.available:
            _LOGGER.debug("AVR not connected, skipping update")
            return False

        async with self._update_lock:
            ## Update only if scan_interval has passed
            now = time.time()
            since_updated = now - self._last_updated
            full_update = self._full_update
            if full_update or since_updated > self.scan_interval:
                _LOGGER.info(
                    f"Updating AVR status (full={full_update}, last updated {since_updated:.3f}s ago)"
                )
                self._last_updated = now
                self._full_update = False
                try:
                    for zone in self.zones:
                        await self.update_zone(zone)
                    if full_update:
                        ## Trigger updates to all zones on full update
                        self.call_zone_callbacks()
                except Exception as e:  # pylint: disable=invalid-name
                    _LOGGER.error(
                        f"Could not update AVR status: {type(e).__name__}: {e}"
                    )
                    await self.disconnect()
                    return False
            else:
                ## NOTE: any response from the AVR received within
                ## scan_interval, including keepalives and responses triggered
                ## via the remote and by other clients, will cause the next
                ## update to be skipped if that update is scheduled to occur
                ## within scan_interval of the response.
                ##
                ## Keepalives may be sent by the AVR (every 30 seconds on the
                ## VSX-930) when connected to port 8102, but are not sent when
                ## connected to port 23.
                _LOGGER.debug(f"Skipping update: last updated {since_updated:.3f}s ago")
        return True

    ## State change functions
    async def turn_on(self, zone="1"):
        """ Turn on the Pioneer AVR. """
        response = await self.send_command("turn_on", zone)
        if self.volume_workaround and zone == "1" and response == "PWR0":
            await self.volume_up()
            await self.volume_down()

    async def turn_off(self, zone="1"):
        """ Turn off the Pioneer AVR. """
        await self.send_command("turn_off", zone)

    async def select_source(self, source, zone="1"):
        """ Select input source. """
        source_id = self._source_name_to_id.get(source)
        if source_id:
            return await self.send_command(
                "select_source", zone, prefix=source_id, ignore_error=False
            )
        else:
            _LOGGER.error(f"Invalid source {source} for zone {zone}")
            return False

    async def volume_up(self, zone="1"):
        """ Volume up media player. """
        return await self.send_command("volume_up", zone, ignore_error=False)

    async def volume_down(self, zone="1"):
        """ Volume down media player. """
        return await self.send_command("volume_down", zone, ignore_error=False)

    async def bounce_volume(self):
        """
        Send volume up/down to work around Main Zone reporting bug where
        an initial volume is set. This initial volume is not reported until
        the volume is changed.
        """
        if await self.volume_up():
            return await self.volume_down()
        else:
            return False

    async def set_volume_level(self, volume, zone="1"):
        """ Set volume level (0..185 for Zone 1, 0..81 for other Zones). """
        if (
            volume < 0
            or (zone == "1" and volume > MAX_VOLUME)
            or (zone != "1" and volume > MAX_VOLUME_ZONEX)
        ):
            raise ValueError(f"volume {volume} out of range for zone {zone}")
        if self.volume_steps:
            current_volume = self.volume.get(zone)
            steps = abs(round((volume - current_volume) / 2))
            for x in range(steps):
                if volume > current_volume:
                    await self.volume_up()
                elif volume < current_volume:
                    await self.volume_down()
        else:
            vol_len = 3 if zone == "1" else 2
            vol_prefix = str(volume).zfill(vol_len)
            return await self.send_command(
                "set_volume_level", zone, prefix=vol_prefix, ignore_error=False
            )

    async def mute_on(self, zone="1"):
        """ Mute AVR. """
        return await self.send_command("mute_on", zone, ignore_error=False)

    async def mute_off(self, zone="1"):
        """ Unmute AVR. """
        return await self.send_command("mute_off", zone, ignore_error=False)
