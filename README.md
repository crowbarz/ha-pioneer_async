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

Internally, the integration uses the [aiopioneer](https://github.com/crowbarz/aiopioneer) package to interface with Pioneer AVRs. This package is installed automatically by HA on integration startup.

> [!NOTE]
> To install pre-release versions of the integration, follow [these steps](https://www.hacs.xyz/docs/use/repositories/dashboard/#downloading-a-specific-version-of-a-repository).

## AVR configuration

Some AVR models stop responding on the network when all zones are powered off to reduce the AVR's power consumption. On such models, Network Standby must be enabled in order for the integration to successfully power on any zone. Consult your AVR manual for the procedure to enable Network Standby.

## Adding an AVR instance to Home Assistant

This integration is configured via the UI. Once installed, add an instance for the AVR in Home Assistant by navigating to **Settings > Devices & Services > Integrations > Add Integration** and searching for **Pioneer AVR**. (Note that the **Pioneer** integration is the original integration built into Home Assistant)

The following options that configure the connection to the AVR are available from the initial setup page:

| Option | Default | Function
| --- | --- | ---
| Device name | Pioneer AVR | Default base name for the AVR
| Host | avr | DNS name/IP address for AVR to be added
| Port | 8102 | Port to be used to communicate with the AVR API. Try port `23` if your AVR doesn't respond on the default port
| Query sources from AVR | on | Query the list of available sources from the AVR when **Next** is clicked. See [AVR sources](#avr-sources)
| Maximum source ID | 60 | The highest source ID that will be queried when querying available sources from the AVR. See [AVR sources](#avr-sources)
| Don't check volume when querying AVR source | AVR default | Don't query zone volume when determining whether a zone is present on the AVR. Enable if zones on your AVR are not all detected

Once the integration is successfully added, [devices](#devices) and [entities](#entities) representing the AVR are created as described in the respective sections below.

### Troubleshooting

Some steps to try if you are unable to add an instance of the integration for your AVR:

- On many AVRs, the network API is not very robust and can occasionally enter an unresponsive state. This can be fixed by powering off the AVR at the outlet, powering it back on after some time, then waiting until it starts responding on the network again.
- Some AVRs have a maximum simultaneous connection limit, and will refuse to accept further connection requests once this limit is reached. Each instance of this integration uses one connection to the AVR, and each instance of the Pioneer **iControlAV5** application will use another connection. For example, if **iControlAV5** is open on two phones, then two connections will be in use.
- Pioneer AVRs released from 2016 onwards use the Onkyo API, and will not work with this integration. This integration will report `AVR not responding to Pioneer API commands` when used with such AVRs. Try the [Onkyo integration](https://www.home-assistant.io/integrations/onkyo/) instead with the AVR.

## AVR instance options

After an instance is added, options that modify how the integration operates can be changed by clicking **Configure** on the appropriate instance on the integration's **Hubs** page. The available options are described in the subsections below.

### Basic options

| Option | Default | Function
| --- | --- | ---
| Query sources from AVR | off | Query the list of available sources from the AVR when **Next** is clicked. See [AVR sources](#avr-sources)
| Maximum source ID | 60 | Highest source ID that will be queried when querying available sources from the AVR. See [AVR sources](#avr-sources)
| Manually configured sources | | List of all input sources available on the AVR. See [AVR sources](#avr-sources)
| Scan interval | 60s | Idle period between full refreshes of the AVR. If the **Always poll the AVR every scan interval** option in [Advanced options](#advanced-options) is not enabled, then any response from the AVR (eg. indicating a power, volume or source change) will reset the idle timer. Some AVRs also send empty responses every 30 seconds, and these also reset the idle timer and prevent a full refresh from being performed. Set this option to `0` to disable polling
| Timeout | 5s | Number of seconds to wait for the initial connection and for responses to commands sent to the AVR. Also used to set the TCP connection idle timeout
| Command delay | 0.1s | Delay between commands sent to the AVR. Increase the delay if you are experiencing errors with basic commands that are sent to the AVR

### Zone options

| Option | Default | Function
| --- | --- | ---
| Available sources for _zone_ | all | List of sources available for selection as input for each zone. Use this option to limit the sources available for a zone in accordance with your AVR's capabilities. If no sources are specified, then all available sources as configured in [Basic options](#basic-options) are made available
| Don't create entities for _zone_ | off | Disable the creation of entities for a specific zone. Used when the integration detects a zone that does not exist for your AVR

### Advanced options

These options enable functionality and workarounds that are required for some AVR models. Some of these are enabled by default for specific AVR models when these are detected by the integration.

> [!IMPORTANT]
> The Advanced options page is shown only if **Advanced Mode** is enabled in the user's Home Assistant profile.

| Option | Default | Function
| --- | --- | ---
| Query basic AVR parameters only | | Disable AVR queries for additional parameters (audio, video, amp, DSP, tuner, channel levels) which may not be supported on some AVR models
| Workaround for Zone 1 initial volume reporting | | Enable this workaround on AVRs that do not report the correct volume when the main zone is turned on and an initial volume is configured
| Don't check volume when querying AVR source | | Don't query zone volume when determining whether a zone is present on the AVR. Enable if zones on your AVR are not all detected
| Step volume up/down to set volume level | | Emulate volume level set by stepping volume up/down on AVR models that cannot set the volume level to a specific level
| Always poll the AVR every scan interval | | Enable for AVRs that do not reliably report state changes and needs a full refresh to be performed every scan interval. Otherwise, the integration will perform a full refresh only if the AVR does not send a response to the integration for the scan interval period
| Maximum volume units for Zone 1 | 185 | The highest volume unit for Zone 1
| Maximum volume units for other zones | 81 | The highest volume unit for other zones
| Extra aiopioneer parameters | | Additional config parameters to pass to the aiopioneer package. See [Extra `aiopioneer` params](#extra-aiopioneer-parameters)

### Debug options

These options enable additional debugging to be output to the Home Assistant log. Debug level logging must also be enabled in Home Assistant for the integration to generate debug.

> [!IMPORTANT]
> The Debug options page is shown only if **Advanced Mode** is enabled in the user's Home Assistant profile.

| Option | Function
| --- |  ---
| Enable listener task debug logging | (`debug_listener` parameter) Enables additional debug messages in the listener task
| Enable updater task debug logging | (`debug_updater` parameter) Enables additional debug messages in the updater task
| Enable command debug logging | (`debug_command` parameter) Enables additional debug messages in the AVR command sending and command queue methods
| Enable command queue debug logging | (`debug_command_queue` parameter) Enables additional debug messages in the AVR command queue methods and task
| Integration load/unload debug logging | Enables additional integration load/unload debug messages
| Integration config flow debug logging | Enables additional integration config flow debug messages
| Integration action debug logging | Enables additional integration debug messages on running integration specific actions

## Enabling debugging

If the integration is not functioning as expected, then you will need to include the debug logging when logging an issue. See the [Debug logs and diagnostics section in the Home Assistant Troubleshooting page](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for instructions for enabling debug logging for the integration and downloading the log.

Additional debug logging for both the underlying aiopioneer package and the integration can be enabled from the [Debug options](#debug-options) page.

## AVR sources

The integration saves a master list of available sources on the AVR, and a subset of these sources can be made available for selection as the zone's input source. On some models of AVR, some zones do not support the use of certain sources for input, and also some sources may only be selected on one zone.

The master list of sources can be queried from the AVR when adding an integration instance by enabling **Query sources from AVR**. They can also be re-queried when reconfiguring the integration instance from the **Basic options** page. To do this, enable the **Query sources from AVR** option then click **Next**. Note that the current list of sources will be replaced by the list returned by the AVR.

Source mappings in the master source list can be edited in the **Basic options** screen by removing unwanted mappings and adding extra mappings via the **Manually configured sources** option. Additional mappings can be added if your AVR does not automatically detect them. Each source mapping is in the form `id:name`, where `id` is a 2 digit identifier for the source (including a leading zero for single digit source IDs), and `name` is the friendly name for the source. You can rename a source mapping by removing the mapping and adding a new mapping with the same `id`.

Source IDs can be found in the [`aiopioneer` documentation](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#source-list)

On the **Zone options** page, the available sources for each zone can be selected. If no sources are selected for a zone, then all sources are made available for selection.

### Extra `aiopioneer` parameters

Additional parameters can be configured in the Home Assistant integration and are passed to the `aiopioneer` package used by this integration for communication with the Pioneer AVR via its API. The parameters modify the package functionality to account for the operational differences between the various Pioneer AVR models.
See [aiopioneer documentation](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#params) for a list of parameters that can be set.

Most configuration parameters are configurable via UI settings. Other parameters can be added through entries in the **Extra `aiopioneer` parameters**. Each entry is in the format `parameter_name: value` with _value_ expressed in JSON format. For example, the `am_frequency_step` parameter can be set to 9 kHz by adding the entry `am_frequency_step: 9`.

## Devices

The integration creates a device representing the AVR, and a child device for each discovered zone on the AVR.

The devices created for each instance of the integration can be viewed via integration's **Hubs** page. The details page for each device shows all entities registered to the device, and provides options to enable entities that are disabled by default.

> [!NOTE]
> Some AVR device information (such as firmware version) are only available after the AVR main zone is powered on for the first time after the integration is started.

## Entities

Entities representing various features and properties of the AVR are created and registered with a device. Global AVR entities are registered to the AVR device, and zone entities are registered to the zone device.

### Media player entities

`media_player` entities are created for each discovered zone. These entities are used to control the basic functions for the zone: power, volume, mute, and sound mode (referred to as listening mode on the Pioneer AVRs). Other media player actions, such as play and pause, become available when specific sources are selected: tuner, MHL, iPod, Spotify, etc.

#### `media_player` entity attributes

In addition to the standard `media_player` entity attributes, this integration exposes additional attributes for the Pioneer AVR:

| Entity attribute | Type | Description
| --- | --- | ---
| `sources_json` | JSON | JSON mapping of zone source names to source IDs
| `device_volume_db` | float | Current volume of zone (in dB)
| `device_volume` | int | Current volume of zone (in device units)
| `device_max_volume` | int | Maximum supported volume of zone (in device units)

### Tuner entities

The entities below show the current tuner settings, and can also be used to change the tuner settings. These entities are available only when the tuner is selected as the input for a powered on zone.

| Name | Platform | Description
| --- | --- | ---
| Tuner Band | select | Current tuner band (`AM`, `FM`)
| Tuner AM Frequency | number | Current AM frequency (in kHz)
| Tuner FM Frequency | number | Current FM frequency (in MHz)
| Tuner Preset | select | Currently selected tuner preset, or `unknown` if no preset is. The preset is also reset to `unknown` when the frequency is changed

#### `tuner_am_frequency` entity attributes

The `tuner_am_frequency` number entity exposes the following additional attributes:

| Entity attribute | Type | Description
| --- | --- | ---
| `am_frequency_step` | int | The kHz step between valid AM frequencies. This value differs across regions. If not specified as a parameter, then this is calculated by stepping up and down the frequency when the band is first changed to `AM`

### AVR property entities

The following AVR properties and property groups are available as entities where supported and reported by your AVR model. These entities can be used to display the current AVR state in dashboards, as well as be used in automation triggers and/or conditions to perform an action when an AVR property changes.

> [!CAUTION]
> Property group entities are **beta** and may change in future releases as additional entities are created for individual properties.

#### Global AVR properties

Sensor entities for global AVR properties and property groups are registered to the parent device created for the AVR.

| Property | Platform | Description
| --- | --- | ---
| Display | sensor | Current value shown on AVR front panel display
| Speaker System | sensor | AVR speaker system currently in use
| Amp | sensor | Amp property group, main sensor property: `speakers`
| DSP | sensor | DSP property group, main sensor property: `signal_select`
| Video Parameters | sensor | Video parameters property group, main sensor property: `signal_output_resolution`
| Audio Parameters | sensor | Audio parameters property group, main sensor property: `input_signal`
| Input Multichannel | binary_sensor | **on** if current input audio source is a multi-channel source
| System | sensor | System property group

> [!CAUTION]
> On supported AVRs, enabling the **Display** sensor may generate more recorder database update entries than expected. The sensor state changes every time the display changes. This includes every change when a long message is scrolled across the display, such as a long radio channel name.
>
> To prevent these state changes from being recorded by the [Recorder integration](https://www.home-assistant.io/integrations/recorder/), add the following filter to `configuration.yaml`:

```yaml
# Example configuration.yaml entry
recorder:
  exclude:
    entities:
      - sensor.pioneer_avr_display
```

#### Zone AVR properties

Zone entities are registered to the zone device.

| Property | Platform | Description
| --- | --- | ---
| channel_levels | sensor | Surround channel levels
| tone | sensor | Tone setting, and bass and treble levels
| Video | sensor | Zone video parameters property group
| Audio | sensor |  Zone audio parameters property group

## Actions

Actions are used to perform an activity or change parameters on the AVR. They can be called from scripts, automations and UI elements, and can also be triggered via **Developer Tools > Actions**. Standard `media_player` actions are supported where the AVR provides equivalent functionality. Integration specific actions are also available to expose additional activities available on Pioneer AVRs.

All of the integration specific actions described below require a target to be specified. The zone device or the `media_player` entity for the zone can be used.

> [!NOTE]
> Prior to Home Assistant 2024.8, actions were referred to as service calls. See the [2024.8 release post](https://www.home-assistant.io/blog/2024/08/07/release-20248/#goodbye-service-calls-hello-actions-) for more details on this change in terminology.

### Action `set_tone_settings`

Set AVR tone settings for zone.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| tone | string | | Tone mode. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)
| treble | int | None | Tone treble value (-6dB -- 6dB)
| bass | int | None | Tone bass value (-6dB -- 6dB)

### Action `set_tuner_band`

Set AVR tuner band.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| band | string | | Tuner band: `AM` or `FM` (required)

### Action `set_fm_tuner_frequency`

Set AVR FM tuner frequency.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| frequency | float | | Tuner frequency (87.5 MHz -- 108.0 MHz) (required)

### Action `set_am_tuner_frequency`

Set AVR AM tuner frequency.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| frequency | float | | Tuner frequency (530 -- 1700KHz) (required)

### Action `set_tuner_preset`

Set AVR tuner preset.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| class | str | | Tuner preset class (A -- G) (required)
| preset | int | | Tuner preset ID (1 -- 9) (required)

### Action `set_channel_levels`

Set AVR level (gain) for an amplifier channel.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| channel | str | | Tuner amp channel to modify. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)

### Action `set_panel_lock`

Set AVR panel lock.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| panel_lock | bool | | Panel lock setting (required)

### Action `set_remote_lock`

Set AVR remote lock.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| remote_lock | bool | | Enable remote lock (required)

### Action `set_dimmer`

Set AVR display dimmer.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| dimmer | string | | Dimmer mode. See [`services.yaml`](custom_components/pioneer_async/services.yaml) for valid values (required)

### Action `set_video_settings`

To be implemented.

### Action `set_dsp_settings`

To be implemented.

### Action `media_control`

To be implemented.

### Action `send_command` (>= 0.9.1)

Send a command to the AVR.

| Action data | Type | Default | Description
| --- | --- | --- | ---
| command | string | | Name of command to send. See list of [available commands](https://github.com/crowbarz/aiopioneer/blob/dev/aiopioneer/commands.py) and the Pioneer documentation [linked from the aiopioneer references](https://github.com/crowbarz/aiopioneer?tab=readme-ov-file#references) for the arguments accepted by each command
| prefix | string | | Prefix argument for command
| suffix | string | | Suffix argument for command

## Breaking changes

### 0.10

- From 0.10.0 onwards, it will no longer be possible to downgrade the integration to a version that uses an older config entry major version (currently 4). If this is encountered, the integration will refuse to start with a config entry migration error. You will need to either restore your HA configuration from a backup, or remove and re-add all instances of the integration to create a new config entry.
- The HA integration debug options have changed - the free-form `debug_config` has been deprecated and replaced with discrete debug options for integration load/unload, config flow and actions that are configurable from the UI. The deprecated debug config is not migrated.
- The [recently introduced config_entry warning](https://developers.home-assistant.io/blog/2024/11/12/options-flow/) that appears when you reconfigure an integration instance has been fixed, but the fix may break reconfiguration on HA versions older than 2024.12.

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

- `command_delay`, `volume_workaround` and `volume_steps` have been moved into the `params` object. Additionally, `volume_steps` has been renamed `volume_step_only` and `volume_workaround` has been renamed to `power_on_volume_bounce`. You will need to update your `configuration.yaml` accordingly.

## Implementation details

Under the hood, this integration uses [crowbarz/aiopioneer](https://github.com/crowbarz/aiopioneer) to communicate with the Pioneer AVR via its API. Briefly, the features of this package are:

- Implemented in asyncio
- Maintain single continuous command connection with the AVR, with automatic reconnect
- Eliminate polling where AVR sends keepalive responses (on port 8102)

**NOTE:** On the VSX-930, the telnet API can become quite unstable when telnet connections are made to it repeatedly. The original integration established a new telnet connection for each command sent to the AVR, including the commands used to poll status. This integration establishes a single telnet connection when loaded, and re-connects automatically if it disconnects. The connection is used for sending commands, receiving responses, and receiving status updates which are reflected in Home Assistant in real time.
