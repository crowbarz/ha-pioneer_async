# ha-pioneer_alt
Customised Home Assistant media_player custom component for Pioneer AVRs.
Tested on a VSX-930 (Main Zone and HDZone outputs).

Added support for the following features:
- Auto-detect and create entities for Zones 1, 2, 3 and HDZONE.
- Maintain single continuous telnet session to AVR, with automatic reconnect.
- Eliminate polling where AVR sends keepalive responses (on port 8102). 
- Separated Pioneer API into a separate class, ready to be moved into a
  separate module to follow current Home Assistant integration standards.
- Automatically poll AVR for source names - no need to manually code them
  any more.
- Uses source names instead of source IDs for selecting a new source.
- Added workaround for AVRs with an initial volume set on the Main Zone. The
  initial volume is not reported correctly until a volume change is made on
  the AVR. The workaround sends `volume_up`, `volume_down` commands to
  correct the reported volume without affecting the initial volume setting.

NOTE: On the VSX-930, the telnet API can become very unstable when telnet
connections are made to it repeatedly. The original component established a
new telnet connection for each command sent to the AVR, including the commands
used to poll status. This component reuses a single telnet connection,
established at component start and re-established automaticlly if it
disconnects, for both sending commands and receiving status updates that are
then reflected in Home Assistant in real time.
