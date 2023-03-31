<!-- markdownlint-disable MD033 -->
# Pioneer AVR (asyncio)

Home Assistant `media_player` custom integration for Pioneer AVRs.
Inspired by the [original Pioneer integration](https://www.home-assistant.io/integrations/pioneer/).
Tested on a VSX-930 (Main Zone and HDZone outputs).

Added support for the following features:

- Supports integration config flow (`Configuration` > `Integrations` > `+` to add) as well as configuration via `configuration.yaml`.
- Uses the [`aiopioneer`](http://github.com/crowbarz/aiopioneer) package to communicate with the AVR via its API.
- Auto-detect and create entities for Zones 1, 2, 3 and HDZone.
- Automatically poll AVR for source names - no longer need to manually code them in your config any more if your AVR supports their retrieval.
- Create devices and populate with model, software version and MAC address queried from AVR (if supported) when configured via the UI.

## Installation

This integration can be installed via HACS by adding this repository as a custom repository. See the [HACS documentation](https://hacs.xyz/docs/faq/custom_repositories/) for the procedure.

## Configuration

This integration may be configured via the UI (`Configuration > Integrations > Add Integration`) or through YAML in `configuration.yaml`. It is recommended that all AVRs are configured using the same configuration method.

Unlike other similar integrations, this integration will create `media_player` entities for all zones that are discovered on an AVR. It is not necessary to configure separate instances of the integration for each zone.

Be aware that some AVRs have a maximum simultaneous connection limit, and will refuse to accept further connection requests once this limit is reached. This integration uses a single connection, and each instance of the Pioneer iControlAV5 application will use another connection. (eg. if iControlAV5 is open on two phones, then two connections will be used.)

## `configuration.yaml` options

Configure these settings under `media_player`:

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| `platform` | string | | Set to `pioneer_async` to use this integration for the `media_player` entity.
| `name` | string | `Pioneer AVR` | The friendly name that you would like to give to the receiver.
| `host` | string | **Required** | The DNS name or IP of the Pioneer device, eg., `192.168.0.10`.
| `port` | integer | `8102` | The port on which the Pioneer device listens. This may be `23` if your AVR doesn't respond on port `8102`.
| `scan_interval` | time_period | `60s` | Idle period between full polls of the AVR. Any response from the AVR (eg. to signal a power, volume or source change) will reset the idle timer. Some AVRs also send empty responses every 30 seconds, these also reset the idle timer and prevent a full poll from being performed. Set this to `0` to disable polling.
| `timeout` | float | `5.0` | Number of seconds to wait for the initial connection and for responses to commands. Also used to set the TCP connection idle timeout.
| `sources` | list | `{}` | A mapping of source friendly-names to AVR source IDs, see [AVR sources](#avr-sources) below. To remove custom sources in the UI and query them from the AVR instead, enter `{}`.
| `params` | object | `{}` | A mapping of configuration parameters to pass to the Pioneer AVR API to modify its functionality, see [`params` object](#params-object) below.

**NOTE:** See [Breaking Changes](#breaking-changes) if you are upgrading from version 0.2 or earlier as configuration options have changed.

### AVR sources

If the `sources` property is not specified, then the integration will attempt to query them from the AVR on startup and when options are updated, and use the friendly names configured on the AVR. This functionality is not supported by all AVR models. If the integration does not detect sources, or only a subset of sources should be selectable, then a mapping can be manually configured via the `sources` property.

The configured mapping maps friendly names to IDs. Valid IDs are dependent on the receiver model, and are always two characters in length. The IDs must be defined as YAML strings (ie. between single or double quotes) so that `05` is not implicitly transformed to `5`, which is not a valid source ID.

Example source mapping (`configuration.yaml`): `{ TV: '05', Cable: '06' }`

**NOTE:** Remember to use JSON syntax when entering sources in the UI, for example: `{ "TV": "05", "Cable": "06" }`

### `params` object

The `params` object contains configuration parameters that are passed onto the Pioneer AVR API to modify its functionality. Configuration parameters can be configured via the `Configure` button when the integration is added via the UI, or in `configuration.yaml` if the integration is configured there. See the [`aiopioneer` documentation](https://github.com/crowbarz/aiopioneer/blob/main/README.md) for the configuration parameters that can be set.

Most configuration parameters are configurable from the UI.

**NOTE**: Changing `ignored_zones` or `ignore_volume_check` via the UI requires Home Assistant to be restarted before fully taking effect.

### Example YAML configuration

```yaml
# Example configuration.yaml entry
media_player:
  - platform: pioneer_async
    name: Pioneer AVR
    host: avr
    port: 8102
    scan_interval: 60
    timeout: 5.0
    sources: { TV: '05', Cable: '06' }
    params:
      ignore_volume_check: true
```

## Services (>= 0.7.3)

A number of service calls are supported by the integration to invoke functions and change parameters on the AVR. These can be called from scripts and automations, and can also be triggered via Developer Tools > Services.

### Service `set_tone_settings`

Set AVR tone settings for zone.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| tone | string | | Tone mode. See [`services.yaml`](blob/main/custom_components/pioneer_async/services.yaml) for valid values (required)
| treble | int | None | Tone treble value (-6dB -- 6dB)
| bass | int | None | Tone bass value (-6dB -- 6dB)

### Service `set_fm_tuner_frequency`

Set AVR FM tuner frequency.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| frequency | float | | Tuner frequency (87.5 MHz -- 108.0 MHz) (required)

### Service `set_am_tuner_frequency`

Set AVR AM tuner frequency.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| frequency | float | | Tuner frequency (530 -- 1700KHz) (required)

### Service `set_tuner_preset`

Set AVR tuner preset.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| class | str | | Tuner preset class (A -- G) (required)
| preset | int | | Tuner preset ID (1 -- 9) (required)

### Service `set_channel_levels`

Set AVR level (gain) for an amplifier channel.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| channel | str | | Tuner amp channel to modify. See [`services.yaml`](blob/main/custom_components/pioneer_async/services.yaml) for valid values (required)

### Service `set_panel_lock`

Set AVR panel lock.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| panel_lock | bool | | Panel lock setting (required)

### Service `set_remote_lock`

Set AVR remote lock.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| remote_lock | bool | | Enable remote lock (required)

### Service `set_dimmer`

Set AVR display dimmer.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| dimmer | string | | Dimmer mode. See [`services.yaml`](blob/main/custom_components/pioneer_async/services.yaml) for valid values (required)

### Service `set_video_settings`

To be implemented.

### Service `set_dsp_settings`

To be implemented.

### Service `media_control`

To be implemented.

## Breaking changes

- **0.7**\
  The `device_class` for the zone entities has been updated to `receiver`. If any zone entities are exported to Google Assistant, this change currently (2023-01-08) removes the Google Home UI that was previously shown for this entity when using the default `device_class` of `tv`. You can restore the old behaviour by overriding `device_class` for the entity to `tv`, see [Customising Entities](https://www.home-assistant.io/docs/configuration/customizing-devices/) for details on how to do this.

  The `volume_step_delta` config property has been deprecated upstream in [crowbarz/aiopioneer](https://github.com/crowbarz/aiopioneer) and is no longer configurable from this integration.

- **0.6**\
  Zone entity unique IDs have changed to conform to [unique ID requirements](https://developers.home-assistant.io/docs/entity_registry_index/). Due to a bug with integration removal in previous versions, the entity IDs of your zones will probably change after upgrading to this version if you added the integration via the UI. To restore your entity IDs, perform the following steps:
  1. remove the integration via the UI (saving configuration settings).
  2. restart Home Assistant.
  3. in Home Assistant, navigate to `Configuration` > `Entities` and search for your Pioneer AVR zone entities. They should show a red exclamation mark in the `Status` column.
  4. select all the entities and click `Remove Entity`.
  5. reinstall the integration via the UI and restore configuration settings.

- **0.5**\
  `volume_step_only` logic has been rewritten to step the volume until the actual volume reaches (or exceeds) the desired volume. It will stop stepping and log a warning if after the step command the volume does not change or changes in the wrong direction.
- **0.4**\
  The AVR source query no longer skips source names that have not been renamed. This will result in additional sources being selectable. Specify sources manually to only allow certain sources to be selected.
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

The [`debug_*`](#params-object) configuration parameters can be set to enable additional debugging messages from the API. These debug options generate significant additional logging, so are turned off by default.
