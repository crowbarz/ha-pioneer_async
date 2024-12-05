<!-- markdownlint-disable MD033 -->
# Pioneer AVR (asyncio)

Home Assistant `media_player` custom integration for Pioneer AVRs.
Inspired by the [original Pioneer integration](https://www.home-assistant.io/integrations/pioneer/).
Connects to a network capable AVR that supports the Pioneer API, typically used in pre-2016 Pioneer AVR models.
Developed and tested on a VSX-930 (with Main Zone and HDZone outputs), and [on other models by the community](https://github.com/crowbarz/ha-pioneer_async/issues/20).

This integration supports the following features (not all features are supported by all AVR models):

- Control power, volume and mute for zones available on the AVR
- Select the active input source for each available zone, which are detected from the AVR
- Set the tuner band and frequency, and select tuner presets
- Set audio parameters such as listening modes, tone and channel levels
- Set amp, DSP and video parameters

## Installation

This integration can be installed via HACS by adding this repository as a custom repository. See the [HACS documentation](https://hacs.xyz/docs/faq/custom_repositories/) for the procedure.

## AVR configuration

Some AVR models stop responding on the network when all zones are powered off to reduce the AVR's power consumption. On such models, Network Standby must be enabled in order for the integration to successfully power on any zone. Consult your AVR manual for the procedure to enable Network Standby.

## Adding an AVR instance to Home Assistant

> [!WARNING]
> As of 0.9.0, support for YAML configuration via `configuration.yaml` is no longer supported. The configuration is ignored and an error is logged if YAML configuration is detected.

This integration is configured via the UI. Once installed, add an instance for the AVR in Home Assistant by navigating to **Settings > Devices & Services > Integrations > Add Integration** and searching for **Pioneer AVR**. (Note that the **Pioneer** integration is the original integration built into Home Assistant)

The following options that configure the connection to the AVR are available from the initial setup page:

| Option | Default | Function
| --- | --- | ---
| Device name | Pioneer AVR | Default base name for the AVR
| Host | avr | DNS name/IP address for AVR to be added
| Port | 8102 | Port to be used to communicate with the AVR API. Use port `23` if your AVR doesn't respond on the default port
| Query sources from AVR | on | Query the list of available sources from the AVR when **Next** is clicked. See [AVR sources](#avr-sources)
| Maximum source ID | 60 | The highest source ID that will be queried when querying available sources from the AVR. See [AVR sources](#avr-sources)
| Don't check volume when querying AVR source | AVR default | Don't query zone volume when determining whether a zone is present on the AVR. Enable if zones on your AVR are not all detected

Once the integration is successfully added, devices representing the AVR and each supported zone are created, along with entities that are registered to the devices. The main entities are the `media_player` entities corresponding to each discovered zone that are used to control the basic functions for the zone: power, volume and mute.

Some AVRs have a maximum simultaneous connection limit, and will refuse to accept further connection requests once this limit is reached. Each instance of this integration uses one connection to the AVR, and each instance of the Pioneer **iControlAV5** application will use another connection. For example, if **iControlAV5** is open on two phones, then two connections will be in use.

**NOTE:** Some AVR device attributes (such as firmware version) are only available after the AVR main zone is powered on for the first time after the integration is added.

## AVR instance options

After an instance is added, options that modify how the integration operates can be changed by clicking **Configure** on the appropriate instance on the integration's **Hubs** page. The available options are described in the subsections below.

### Basic options

| Option | Default | Function
| --- | --- | ---
| Query sources from AVR | off | Query the list of available sources from the AVR when **Next** is clicked. See [AVR sources](#avr-sources)
| Maximum source ID | 60 | Highest source ID that will be queried when querying available sources from the AVR. See [AVR sources](#avr-sources)
| Manually configured sources | | List of all input sources available on the AVR. See [AVR sources](#avr-sources)
| Scan interval | 60s | Idle period between full polls of the AVR. Any response from the AVR (eg. to signal a power, volume or source change) will reset the idle timer. Some AVRs also send empty responses every 30 seconds, and these also reset the idle timer and prevent a full poll from being performed. Set this to `0` to disable polling
| Timeout | 5s | Number of seconds to wait for the initial connection and for responses to commands sent to the AVR. Also used to set the TCP connection idle timeout
| Command delay | 0.1s | Delay between commands sent to the AVR. Increase the delay if you are experiencing errors with basic commands that are sent to the AVR

### Zone options

| Option | Default | Function
| --- | --- | ---
| Available sources for _zone_ | all | List of sources available for selection as input for each zone. Use this option to limit the sources available for a zone in accordance with your AVR's capabilities. If no sources are specified, then all available sources as configured in [Basic options](#basic-options) are made available
| Don't create entities for _zone_ | off | Disable the creation of entities for a specific zone. Used when the integration detects a zone that does not exist for your AVR

### Advanced options

These options enable functionality and workarounds that are required for some AVR models. Some of these are enabled by default for specific AVR models when these are detected by the integration.

The Advanced options page is shown only if **Advanced Mode** is enabled in the user's Home Assistant profile.

| Option | Default | Function
| --- | --- | ---
| Query basic AVR parameters only | | Disable AVR queries for additional parameters (audio, video, amp, DSP, tuner, channel levels) which may not be supported on some AVR models
| Workaround for Zone 1 initial volume reporting | | Enable this workaround on AVRs that do not report the correct volume when the main zone is turned on and an initial volume is configured
| Don't check volume when querying AVR source | | Don't query zone volume when determining whether a zone is present on the AVR. Enable if zones on your AVR are not all detected
| Step volume up/down to set volume level | | Emulate volume level set by stepping volume up/down on AVR models that cannot set the volume level to a specific level
| Maximum volume units for Zone 1 | 185 | The highest volume unit for Zone 1
| Maximum volume units for other zones | 81 | The highest volume unit for other zones
| Extra aiopioneer parameters | | Additional config parameters to pass to the aiopioneer package. See [Extra `aiopioneer` params](#extra-aiopioneer-parameters)

### Debug options

These options enable additional debugging to be output to the Home Assistant log. Debug level logging must also be enabled in Home Assistant for the integration to generate debug.

The Debug options page is shown only if **Advanced Mode** is enabled in the user's Home Assistant profile.

| Option | Function
| --- |  ---
| Enable listener task debug logging | (`debug_responder` parameter) Enables additional debug messages in the listener task
| Enable responder task debug logging | (`debug_responder` parameter) Enables additional debug messages in the responder task
| Enable updater task debug logging | (`debug_responder` parameter) Enables additional debug messages in the updater task
| Enable command debug logging | (`debug_responder` parameter) Enables additional debug messages in the AVR command sending and command queue methods
| Integration debug | Enables additional per-module debug messages in this integration

## Enabling debugging

If the integration is not functioning as expected, then you will need to include the debug logging when logging an issue. See the [Debug logs and diagnostics section in the Home Assistant Troubleshooting page](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for instructions for enabling debug logging for the integration and downloading the log.

Further module level debug logging for the integration can be enabled by adding entries in **Integration debug configuration** on the [Debug options](#debug-options) configuration page. The entries are in the format: `_module_:_debug_level_`. For example, `config_flow:9` will enable full debugging output for the `config_flow` module. To enable full debugging for all modules, use `*:9`.

## AVR sources

The integration saves a master list of available sources on the AVR, and a subset of these sources can be made available for selection as the zone's input source. On some models of AVR, some zones do not support the use of certain sources for input, and also some sources may only be selected on one zone.

The master list of sources can be queried from the AVR when adding an integration instance by enabling **Query sources from AVR**. They can also be re-queried when reconfiguring the integration instance from the **Basic options** page. To do this, enable the **Query sources from AVR** option then click **Next**. Note that the current list of sources will be replaced by the list returned by the AVR.

Source mappings in the master source list can be edited in the **Basic options** screen by removing unwanted mappings and adding extra mappings via the **Manually configured sources** option. Additional mappings can be added if your AVR does not automatically detect them. Each source mapping is in the form `id:name`, where `id` is a 2 digit identifier for the source (including a leading zero for single digit source IDs), and `name` is the friendly name for the source. You can rename a source mapping by removing the mapping and adding a new mapping with the same `id`.

Source IDs can be found in the [`aiopioneer` documentation](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#source-list)

On the **Zone options** page, the available sources for each zone can be selected. If no sources are selected for a zone, then all sources are made available for selection.

### Extra `aiopioneer` parameters

Additional parameters can be configured in the Home Assistant integration and are passed to the `aiopioneer` packaged used by this integration for communication with the Pioneer AVR via its API. The parameters modify the package functionality to account for the operational differences between the various Pioneer AVR models.
See [aiopioneer documentation](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#params) for a list of parameters that can be set.

Most configuration parameters are configurable via UI settings. Other parameters can be added through entries in the **Extra `aiopioneer` parameters**. Each entry is in the format `parameter_name: value` with _value_ expressed in JSON format. For example, the `am_frequency_step` parameter can be set to 9 kHz by adding the entry `am_frequency_step: 9`.

### Tuner entities

The entities below show the current tuner settings, and can also be used to change the tuner settings. These entities are available only when the tuner is selected as the input for a powered on zone.

| Name | Type | Description
| --- | --- | ---
| Tuner Band | select | Current tuner band (`AM`, `FM`)
| Tuner AM Frequency | number | Current AM frequency (in kHz)
| Tuner FM Frequency | number | Current FM frequency (in MHz)
| Tuner Preset | select | Currently selected tuner preset, or `unknown` if no preset is. The preset is also reset to `unknown` when the frequency is changed

## Entity attributes

### `media_player` entity attributes

In addition to the standard `media_player` entity attributes, this integration exposes additional attributes for the Pioneer AVR:

| Entity attribute | Type | Description
| --- | --- | ---
| `sources_json` | JSON | JSON mapping of zone source names to source IDs
| `device_volume_db` | float | Current volume of zone (in dB)
| `device_volume` | int | Current volume of zone (in device units)
| `device_max_volume` | int | Maximum supported volume of zone (in device units)

### `tuner_am_frequency` entity attributes

The `tuner_am_frequency` number entity exposes the following additional attributes:

| Entity attribute | Type | Description
| --- | --- | ---
| `am_frequency_step` | int | The kHz step between valid AM frequencies. This value differs across regions. If not specified as a parameter, then this is calculated by stepping up and down the frequency when the band is first changed to `AM`

## AVR properties (>= 0.9)

The following AVR properties are available as entities where supported and reported by your AVR model.

> [!CAUTION]
> Property group entities are **beta** and may change in future releases as additional entities are created for individual properties.

### Global AVR properties

Sensor entities for global AVR properties and property groups are registered to the parent device created for the AVR.

| Property | Type | Description
| --- | --- | ---
| Display | sensor | Current value shown on AVR front panel display
| Speaker System | sensor | AVR speaker system currently in use
| Amp | sensor | Amp property group, main sensor property: `speakers`
| DSP | sensor | DSP property group, main sensor property: `signal_select`
| Video Parameters | sensor | Video parameters property group, main sensor property: `signal_output_resolution`
| Audio Parameters | sensor | Audio parameters property group, main sensor property: `input_signal`
| Input Multichannel | binary_sensor | **on** if current input audio source is a multi-channel source

**NOTE:** On supported AVRs, enabling the **Display** property may generate more recorder database update entries than expected. The sensor state changes every time the display changes. This includes every change when a long message is scrolled across the display, such as a long radio channel name.

To prevent these state changes from being recorded by the [Recorder integration](https://www.home-assistant.io/integrations/recorder/), add the following filter to `configuration.yaml`:

```yaml
# Example configuration.yaml entry
recorder:
  exclude:
    entities:
      - sensor.pioneer_avr_display
```

### Zone AVR properties

Zone entities are registered to the zone device.

| Property | Type | Description
| --- | --- | ---
| channel_levels | sensor | Surround channel levels
| tone | sensor | Tone setting, and bass and treble levels
| Video | sensor | Zone video parameters property group
| Audio | sensor |  Zone audio parameters property group

## Services (>= 0.7.3)

Service calls are used to invoke actions and change parameters on the AVR. They can be called from scripts, automations and UI elements, and can also be triggered via **Developer Tools > Services**.

### Service `set_tone_settings`

Set AVR tone settings for zone.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| tone | string | | Tone mode. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)
| treble | int | None | Tone treble value (-6dB -- 6dB)
| bass | int | None | Tone bass value (-6dB -- 6dB)

### Service `set_tuner_band`

Set AVR tuner band.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone to modify (required)
| band | string | | Tuner band: `AM` or `FM` (required)

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
| channel | str | | Tuner amp channel to modify. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)

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
| dimmer | string | | Dimmer mode. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)

### Service `set_video_settings`

To be implemented.

### Service `set_dsp_settings`

To be implemented.

### Service `media_control`

To be implemented.

### Service `send_command` (>= 0.9.1)

Send a command to the AVR.

| Service data attribute | Type | Default | Description
| --- | --- | --- | ---
| entity_id | entity ID | | Entity for AVR zone for command (required)
| command | string | | Name of command to send. See list of [available commands](https://github.com/crowbarz/aiopioneer/blob/dev/aiopioneer/commands.py) and the Pioneer documentation [linked from the aiopioneer references](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#references) for the arguments accepted by each command
| prefix | string | | Prefix argument for command
| suffix | string | | Suffix argument for command

## Breaking changes

### 0.9

- Integration configuration via `configuration.yaml` is no longer supported. [ADR10](https://github.com/home-assistant/architecture/blob/master/adr/0010-integration-configuration.md) outlines that integrations that communicate with devices, such as this one, must be configured via the UI. Also, several more recently added features, such as support for the HA device registry and dynamic integration loading/unloading, already do not work unless configured via the UI.

### 0.8

- The `zone_h_sources` and `zone_z_sources` params have been renamed to `hdzone_sources`, to be more consistent with the rest of the integration.

### 0.7

- The `device_class` for the zone entities has been updated to `receiver`. If any zone entities are exported to Google Assistant, this change currently (2023-01-08) removes the Google Home UI that was previously shown for this entity when using the default `device_class` of `tv`. You can restore the old behaviour by overriding `device_class` for the entity to `tv`, see [Customising Entities](https://www.home-assistant.io/docs/configuration/customizing-devices/) for details on how to do this.
- The `volume_step_delta` config property has been deprecated upstream in [crowbarz/aiopioneer](https://github.com/crowbarz/aiopioneer) and is no longer configurable from this integration.

### 0.6

- Zone entity unique IDs have changed to conform to [unique ID requirements](https://developers.home-assistant.io/docs/entity_registry_index/). Due to a bug with integration removal in previous versions, the entity IDs of your zones will probably change after upgrading to this version if you added the integration via the UI. To restore your entity IDs, perform the following steps:
  1. remove the integration via the UI (saving configuration settings).
  2. restart Home Assistant.
  3. in Home Assistant, navigate to `Configuration` > `Entities` and search for your Pioneer AVR zone entities. They should show a red exclamation mark in the `Status` column.
  4. select all the entities and click `Remove Entity`.
  5. reinstall the integration via the UI and restore configuration settings.

### 0.5

- `volume_step_only` logic has been rewritten to step the volume until the actual volume reaches (or exceeds) the desired volume. It will stop stepping and log a warning if after the step command the volume does not change or changes in the wrong direction.

### 0.4

- The AVR source query no longer skips source names that have not been renamed. This will result in additional sources being selectable. Specify sources manually to only allow certain sources to be selected.

### 0.3

- `command_delay`, `volume_workaround` and `volume_steps` have been moved into the [`params` object](#params-object). Additionally, `volume_steps` has been renamed `volume_step_only` and `volume_workaround` has been renamed to `power_on_volume_bounce`. You will need to update your `configuration.yaml` accordingly.

## Implementation details

Under the hood, this integration uses [crowbarz/aiopioneer](https://github.com/crowbarz/aiopioneer) to communicate with the Pioneer AVR via its API. Briefly, the features of this package are:

- Implemented in asyncio
- Maintain single continuous command connection with the AVR, with automatic reconnect
- Eliminate polling where AVR sends keepalive responses (on port 8102)

**NOTE:** On the VSX-930, the telnet API can become quite unstable when telnet connections are made to it repeatedly. The original integration established a new telnet connection for each command sent to the AVR, including the commands used to poll status. This integration establishes a single telnet connection when loaded, and re-connects automatically if it disconnects. The connection is used for sending commands, receiving responses, and receiving status updates which are reflected in Home Assistant in real time.
