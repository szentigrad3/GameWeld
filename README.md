# GameWeld — Desktop 0.2.0 Alpha

A source-built **GTK4 desktop application** for Linux, developed as the clean GameWeld reboot.

## What works

- Read-only Steam game discovery across the primary and secondary Steam libraries, with bounded Valve KeyValues parsing.
- Search, favourites filtering, sorting by name/App ID/favourites, local per-game notes and copy App ID.
- Read-only on-disk checks for installation and compatdata folders, without claiming the game is running or compatible with trainers.
- A dedicated IPC Lab using **only the pinned GameWeld Batch77 Win64 v2 fixture** (SHA-256 checked before execution). The lab uses system Wine, fresh disposable prefixes, exact READY/PING/STATUS/STOP replies, bounded output, an explicit per-run consent checkbox and a background UI worker.
- Local XDG preferences, no network connections and a headless CLI for diagnostics.

**Not supported:** third-party trainer launching, arbitrary EXE execution, shared game Proton/Wine prefix execution, game memory access, Steam configuration changes or anti-cheat circumvention.

## CachyOS / Arch

```bash
sudo pacman -S --needed python python-gobject gtk4 wine
cd ~/Downloads/GameWeld
# After pulling the new code:
git pull --ff-only
python -m unittest discover -s tests -v
bash run.sh --smoke
bash run.sh
```

No Wine is needed to browse games or use read-only diagnostics. Wine is required **only** for the optional IPC Lab test.

## IPC Lab fixture prerequisite

The Win64 probe is a separate original 4,096-byte executable distributed in the earlier **GameWeld Batch77 Native Lab** standalone ZIP. This source-only desktop release does not bundle the PE binary. Extract that archive in Downloads so the fixture exists at:

```
~/Downloads/gameweld-b77-native-lab/fixtures/gameweld_sidecar_probe_v2.exe
```

The UI checks its exact fixed SHA-256 before allowing a test. You may choose a different fixture path in the IPC Lab entry, but **the filename, byte size, PE format and SHA-256 must all match**. The optional test runs with a new private prefix, and detached Wine helper cleanup is not fully verified. Do not use the game prefix or third-party binaries.

Read-only preflight:

```bash
bash run.sh --ipc-preflight
```

Single isolated test (must explicitly consent):

```bash
bash run.sh --ipc-test --consent-owned-fixture
```

Read-only per-game report:

```bash
bash run.sh --diagnose-appid 3008130
```

The IPC lab is a **controlled engineering fixture**, not a game trainer. All tests are written to avoid private process identifiers and raw paths in exported JSON.

## Test limitations

Offline tests validate parser correctness, preferences, safe paths, diagnostics and a simulated IPC lifecycle. **GTK4 GUI visual rendering and the new IPC integration still require host validation on CachyOS.** Previously successful Batch77 IPC tests were from a different integration context.
