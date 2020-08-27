# Pioneer AVR (asyncio)

Customised Home Assistant media_player custom component for Pioneer AVRs.
Inspired by the [original Pioneer integation](https://www.home-assistant.io/integrations/pioneer/).
Tested on a VSX-930 (Main Zone and HDZone outputs).

Added support for the following features:

- Rewritten to support integration config flow (`Configuration` > `Integrations` > `+` to add) as well as retained `configuration.yaml` support.
- Auto-detect and create entities for Zones 1, 2, 3 and HDZONE.
- Automatically poll AVR for source names - no longer need to manually code them in your config any more if your AVR supports their retrieval.

`configuration.yaml` options:

- `name` _string_ (optional, default: `Pioneer AVR`): The name you would like to give to the receiver.
- `host` _string_ REQUIRED: The IP of the Pioneer device, e.g., 192.168.0.10.
- `port` _integer_ (optional, default: `8102`): The port on which the Pioneer device listens, e.g., 23 or 8102.
- `scan_interval` _integer_ (optional, default: `60`): Idle period (in seconds) between full polls of the AVR. Any response from the AVR (eg. to signal a power, volume or source change) will reset the idle timer. Some AVRs send empty responses every 30 seconds, these also reset the idle timer and prevent a full poll from being performed.
- `timeout` _float_ (optional): Number of seconds (float) to wait for the initial connection and for responses to commands. Also used to set the TCP connection idle timeout.
- `sources` _list_ (optional, default: `{}`): A mapping of source friendly-names to AVR source IDs (e.g., `{ TV: '05', Cable: '06' }`). Valid source IDs are dependent on the receiver. Codes must be defined as strings (ie. between single or double quotation marks) so that `05` is not implicitly transformed to `5`, which is not a valid source ID.

  If not specified, the integration will attempt to query them from the AVR on startup if this is supported by the AVR. If no sources are specified or found, then the integration will not be able to switch sources.

  **NOTE:** it is currently not possible to manually specify `sources` when the integration is added via the UI.
- `command_delay` _float_ (optional, default: `0.1`): Insert a delay between sequential commands that are sent to the AVR. This appears to make the AVR behave more reliably during status polls.
- `volume_workaround` _bool_ (optional, default: `False`): On some AVRs (notably the VSX-930) where a power-on is set, the initial volume is not reported by the AVR correctly until a volume change is made. This option enables a workaround that sends `volume_up`, `volume_down` commands to the AVR on power-on to correct the reported volume without affecting the power-on volume.

Additional technical details on the changes:

- Maintain single continuous telnet session to AVR, with automatic reconnect.
- Eliminate polling where AVR sends keepalive responses (on port 8102).
- Added workaround (`volume_workaround`) for AVRs with an initial volume set on the Main Zone.
- Rewrote [pioneer_alt](https://github.com/crowbarz/ha-pioneer_alt), this integration's predecessor, to support asyncio in both the HA integration and the API.
- Extracted the Pioneer API components into a separate class, ready to be moved into a separate module to follow current Home Assistant integration standards.

**NOTE:** On the VSX-930, the telnet API can become quite unstable when telnet connections are made to it repeatedly. The original integration established a new telnet connection for each command sent to the AVR, including the commands used to poll status. This integration establishes a single telnet connection at component start and re-connects automatically if it disconnects. The connection is used for sending commands, receiving responses, and receiving status updates that are then reflected in Home Assistant in real time.
