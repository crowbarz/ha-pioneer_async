# Pioneer AVR (asyncio)

Customised Home Assistant media_player custom component for Pioneer AVRs.
Inspired by the [original Pioneer integation](https://www.home-assistant.io/integrations/pioneer/).
Tested on a VSX-930 (Main Zone and HDZone outputs).

Added support for the following features:

- Rewritten to support integration config flow (`Configuration` > `Integrations` > `+` to add) as well as retained `configuration.yaml` support.
- Auto-detect and create entities for Zones 1, 2, 3 and HDZONE.
- Automatically poll AVR for source names - no longer need to manually code them in your config any more.
- Uses source names instead of IDs for selecting a new source.

Technical details:

- Maintain single continuous telnet session to AVR, with automatic reconnect.
- Eliminate polling where AVR sends keepalive responses (on port 8102).
- Added workaround (`volume_workaround`) for AVRs with an initial volume set on the Main Zone. The initial volume is not reported correctly until a volume change is made on the AVR. The workaround sends `volume_up`, `volume_down` commands to correct the reported volume without affecting the initial volume setting.
- Rewrote [pioneer_alt](https://github.com/crowbarz/ha-pioneer_alt), this integration's predecessor, to support asyncio in both the HA integration and the API.
- Extracted the Pioneer API components into a separate class, ready to be moved into a separate module to follow current Home Assistant integration standards.

**NOTE:** On the VSX-930, the telnet API can become quite unstable when telnet connections are made to it repeatedly. The original integration established a new telnet connection for each command sent to the AVR, including the commands used to poll status. This integration establishes a single telnet connection at component start and re-connects automatically if it disconnects. The connection is used for sending commands, receiving responses, and receiving status updates that are then reflected in Home Assistant in real time.
