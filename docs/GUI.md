# Wand Native GUI — 0.0.6

The native client is built with GTK4 and libadwaita.

GTK 4.10+ is intentionally required because `gtk::FileDialog` provides the
modern asynchronous native file chooser.

## Current UI

- Steam game library and filter
- daemon status/reconnect indicator
- provider dropdown
- Proton dropdown
- native trainer file chooser
- saved per-game profile
- Play with Trainer
- Stop Trainer
- live session event timeline
- recent sessions
- diagnostic export

## UI/runtime boundary

The GUI is not a launcher implementation.

It only talks to `wandd` through `wand-client`.

The daemon and provider crates remain responsible for Steam, Proton, compatdata,
session state and trainer lifecycle.
