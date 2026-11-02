# GameWeld — Desktop 0.3.0 Alpha

A source-built **GTK4 desktop application** for Linux, developed as the clean GameWeld reboot.

## What works

- Read-only Steam game discovery across the primary and secondary Steam libraries, with bounded Valve KeyValues parsing.
- Search, favourites filtering, sorting by name/App ID/favourites, local per-game notes and copy App ID.
- Read-only on-disk checks for installation and compatdata folders, without claiming the game is running or compatible with trainers.
- A dedicated IPC Lab using **only the pinned GameWeld Batch77 Win64 v2 fixture** (SHA-256 checked before execution). The lab uses system Wine, fresh disposable prefixes, exact READY/PING/STATUS/STOP replies, bounded output, an explicit per-test consent checkbox and a background UI worker.
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

Repeatable diagnostic benchmark (1–3 separate, fresh Wine sessions; explicit consent):

```bash
bash run.sh --ipc-benchmark --consent-owned-fixture --runs 2 --timeout 75
```

The benchmark reports each session's cold-start time separately from PING, STATUS and STOP round-trip times. The desktop can cancel a benchmark, terminating only its own launched process group and waiting for cleanup. It also observes previously identified same-prefix Linux process identities after exit, while always reporting complete detached helper cleanup as unverified. It reads only bounded, same-user /proc metadata and does not disclose environment strings or PIDs in JSON. Each session uses a new prefix; this **measures** startup variability but does not claim to accelerate Wine.

Read-only per-game report:

```bash
bash run.sh --diagnose-appid 3008130
```

The IPC lab is a **controlled engineering fixture**, not a game trainer. All tests are written to avoid private process identifiers and raw paths in exported JSON.

## Test limitations

Offline tests validate parser correctness, preferences, safe paths, diagnostics and a simulated IPC lifecycle. **GTK4 interface changes and the new multi-session benchmark require host validation on CachyOS.** The 0.2.0 desktop IPC integration was validated in one real CachyOS session, but that does not verify the 0.3.0 benchmark or helper observer.
