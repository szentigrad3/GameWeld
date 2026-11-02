# GameWeld — Desktop 0.4.0 Alpha

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

The benchmark reports each session's cold-start time separately from PING, STATUS and STOP round-trip times. The desktop can cancel a benchmark, terminating only its own launched process group and waiting for cleanup. It also observes previously identified same-prefix Linux process identities within the owned launcher process group after exit, while always reporting complete detached helper cleanup as unverified. It opens process environment data only for the newly created, owned launcher process group, after a bounded same-user process-group check. It reads bounded /proc metadata and does not disclose environment strings or PIDs in JSON. Each session uses a new prefix; this **measures** startup variability but does not claim to accelerate Wine.

Read-only per-game report:

```bash
bash run.sh --diagnose-appid 3008130
```

The IPC lab is a **controlled engineering fixture**, not a game trainer. All tests are written to avoid private process identifiers and raw paths in exported JSON.

## Test limitations

Offline tests validate parser correctness, preferences, safe paths, diagnostics and a simulated IPC lifecycle. **GTK4 interface changes and the new multi-session benchmark require host validation on CachyOS.** Desktop 0.3.0 was subsequently validated with two real CachyOS sessions (startup 9.025 s and 6.824 s). The new 0.4.0 History tab and persistence workflow still require CachyOS graphical testing.

## New in 0.4.0: local history and comparison

After a successful fixture benchmark you can **opt in** to saving a small summary
at `$XDG_STATE_HOME/gameweld/benchmarks.json` (fallback
`~/.local/state/gameweld/benchmarks.json`). A new History tab shows the last
30 entries, supports importing prior benchmark JSON reports and never stores
raw stderr, Wine prefixes, PIDs or challenges.

`bash run.sh --history` — read the summaries, no Wine execution.

`bash run.sh --review-benchmark ~/Downloads/gameweld-desktop-030-benchmark.json` —
validate and redact the existing test, without saving.

`bash run.sh --record-benchmark ~/Downloads/gameweld-desktop-030-benchmark.json` —
explicitly import this earlier host benchmark.

`bash run.sh --compare-benchmarks OLD.json NEW.json` — read-only mean READY
comparison, with a warning that differences are not causal evidence.

`bash run.sh --ipc-benchmark --consent-owned-fixture --runs 2 --save-history`
— opt in to saving a successful live-run summary. The existing fixture hash
and game-memory prohibitions remain unchanged. The history log is strictly
local, 0600, symlink-resistant and capped at 64 records.
