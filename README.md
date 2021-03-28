<!-- markdownlint-disable MD033 -->
# Pioneer AVR (asyncio)

Home Assistant `media_player` custom integration for Pioneer AVRs.
Inspired by the [original Pioneer integration](https://www.home-assistant.io/integrations/pioneer/).
Tested on a VSX-930 (Main Zone and HDZone outputs).

Added support for the following features:

- Supports integration config flow (`Configuration` > `Integrations` > `+` to add) as well as configuration via `configuration.yaml`.
- Uses the [`aiopioneer`](http://github.com/crowbarz/aiopioneer) package to communicate with the AVR via its API.
- Auto-detect and create entities for Zones 1, 2, 3 and HDZONE.
- Automatically poll AVR for source names - no longer need to manually code them in your config any more if your AVR supports their retrieval.
- Create devices and populate with model, software version and MAC address queried from AVR (if supported).

## `configuration.yaml` options

Configure these settings under `media_player`:

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| `name` | string | `Pioneer AVR` | The friendly name that you would like to give to the receiver.
| `host` | string | **Required** | The DNS name or IP of the Pioneer device, eg., `192.168.0.10`.
| `port` | integer | `8102` | The port on which the Pioneer device listens. This may be `23` if your AVR doesn't respond on port `8102`.
| `scan_interval` | time_period | `60s` | Idle period between full polls of the AVR. Any response from the AVR (eg. to signal a power, volume or source change) will reset the idle timer. Some AVRs also send empty responses every 30 seconds, these also reset the idle timer and prevent a full poll from being performed.
| `timeout` | float | `2.0` | Number of seconds to wait for the initial connection and for responses to commands. Also used to set the TCP connection idle timeout.
| `sources` | list | `{}` | A mapping of source friendly-names to AVR source IDs, see [AVR sources](#avr-sources) below.
| `params` | object | `{}` | A mapping of parameters to pass to the Pioneer AVR API to modify its functionality, see [`params` object](#params-object) below.

**NOTE:** It is currently not possible to manually specify `sources` when the integration is added via the UI.

**NOTE:** See [Breaking Changes](#breaking-changes) if you are upgrading from version 0.2 or earlier as configuration options have changed.

## AVR sources

If the `sources` property is not specified, then the integration will attempt to query them from the AVR on startup and use the friendly names configured on the AVR. This functionality is not supported by all AVR models. If the integration does not detect sources, then a mapping can be manually configured in the `sources` property.

The mapping maps friendly names to IDs. Valid IDs are dependent on the receiver model, and are always two characters so must be defined as strings (ie. between quotation marks) so that `05` is not implicitly transformed to `5`, which is not a valid source ID.

Example source mapping: `{ TV: '05', Cable: '06' }`

## `params` object

The `params` object is passed onto the Pioneer AVR API to modify its functionality.

The default parameters listed below are for AVR models that do not match any custom profile. Custom profiles change the defaults based on the model identifier retrieved from the AVR, and are defined in [`aiopioneer/param.py`](https://github.com/crowbarz/aiopioneer/blob/main/aiopioneer/param.py).

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| `ignored_zones` | list | `[]` | List of zones to ignore even if they are auto-discovered.
| `command_delay` | float | `0.1` | Insert a delay between sequential commands that are sent to the AVR. This appears to make the AVR behave more reliably during status polls.
| `max_source_id` | int | `60` | Maximum source ID that the source discovery queries. Reduce this if your AVR returns errors.
| `max_volume` | int | `185` | Maximum volume for the Main Zone.
| `max_volume_zonex` | int | `185` | Maximum volume for zones other than the Main Zone.
| `power_on_volume_bounce` | bool | `false` | On some AVRs (eg. VSX-930) where a power-on is set, the initial volume is not reported by the AVR correctly until a volume change is made. This option enables a workaround that sends a volume up and down command to the AVR on power-on to correct the reported volume without affecting the power-on volume.
| `volume_step_only` | bool | `false` | On some AVRs (eg. VSX-S510), setting the volume level is not supported natively by the API. This option emulates setting the volume level using volume up and down commands.
| `volume_step_delta` | int | `1` | The number of units that each volume up/down commands changes the volume by. Used when `volume_step_only` is `true`.
| `debug_listener` | bool | `false` | Enables additional debug logging for the listener task. See [Enabling debugging](#enabling-debugging) for details.
| `debug_responder` | bool | `false` | Enables additional debug logging for the responder task. See [Enabling debugging](#enabling-debugging) for details.
| `debug_updater` | bool | `false` | Enables additional debug logging for the updater task. See [Enabling debugging](#enabling-debugging) for details.
| `debug_command` | bool | `false` | Enables additional debug logging for commands sent and responses received. See [Enabling debugging](#enabling-debugging) for details.

**NOTE:** It is currently not possible to manually specify `ignore_zones` when the integration is added via the UI.

## Breaking changes

- **0.3**\
  `command_delay`, `volume_workaround` and `volume_steps` have been moved into the [`params` object](#params-object). Additionally, `volume_steps` has been renamed `volume_step_only` and `volume_workaround` has been renamed to `power_on_volume_bounce`. You will need to update your `configuration.yaml` accordingly.

## Implementation details

- Implemented in asyncio.
- Maintain single continuous telnet session to AVR, with automatic reconnect.
- Eliminate polling where AVR sends keepalive responses (on port 8102).
- Uses [crowbarz/aiopioneer](https://github.com/crowbarz/aiopioneer) to communicate with the Pioneer API.

**NOTE:** On the VSX-930, the telnet API can become quite unstable when telnet connections are made to it repeatedly. The original integration established a new telnet connection for each command sent to the AVR, including the commands used to poll status. This integration establishes a single telnet connection when loaded, and re-connects automatically if it disconnects. The connection is used for sending commands, receiving responses, and receiving status updates which are reflected in Home Assistant in real time.

## Enabling debugging

The Home Assistant integration logs messages to the `custom_components.pioneer_async` namespace, and the underlying API logs messages to the `aiopioneer` namespace. See the [Logger integration documentation](https://www.home-assistant.io/integrations/logger/) for the procedure for enabling logging for these namespaces.

The [`debug_*`](#params-object) parameters can be set to enable additional debugging messages from the API. These debug options generate significant additional logging, so are turned off by default.
