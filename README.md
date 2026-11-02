# GameWeld — Desktop 0.7.0 Alpha

A source-built **GTK4 desktop application** for Linux, developed as the clean GameWeld reboot.

## What works

- Read-only Steam game discovery across the primary and secondary Steam libraries, with bounded Valve KeyValues parsing.
- Search, favourites filtering, sorting by name/App ID/favourites, local per-game notes and copy App ID.
- Read-only on-disk checks for installation and compatdata folders, without claiming the game is running or compatible with trainers.
- A dedicated IPC Lab using **only the pinned GameWeld Batch77 Win64 v2 fixture** (SHA-256 checked before execution). The lab uses system Wine, fresh disposable prefixes, exact READY/PING/STATUS/STOP replies, bounded output, an explicit per-test consent checkbox and a background UI worker.
- Local XDG preferences, no network connections and a headless CLI for diagnostics.

**New in 0.7:** explicitly consented user-supplied Windows trainer testing; this is experimental and is not evidence of working in-game cheats. No game memory inspection, automatic trainer discovery/download, Steam launch-option changes, or anti-cheat circumvention are provided.

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

## Batch 0.5: startup performance diagnostics

The successful IPC protocol is unchanged; future runs now report Wine launcher spawn
time separately from waiting for READY. The new read-only commands:


```bash
bash run.sh --startup-compare ~/Downloads/gameweld-desktop-030-benchmark.json ~/Downloads/gameweld-desktop-040-benchmark.json
bash run.sh --startup-trend
```

Startup differences are observations only. One slow run cannot establish a Wine regression or its cause.
The history schema remains compatible with 0.4.0. Do not share raw Wine logs or alter Proton settings to troubleshoot this dashboard.


## 0.6.0-alpha: user-observed Wine component installation

The host reported that a single 35.247-second READY wait coincided with a
**Wine Mono installer**. GameWeld does not pretend to detect the installer from
the timing or verify its cause. Instead, you can label that **existing saved
benchmark** with a strictly allowlisted, user-supplied startup context:

```bash
# Safe, read-only history before any change
bash run.sh --history

# Labels only the most recently recorded benchmark; no Wine process is started
bash run.sh --annotate-latest --startup-context mono_setup

# View separate routine/unclassified and setup-tagged timing statistics
bash run.sh --startup-trend
```

If you need to label a specific older report instead, use the original JSON
file (it must already have been imported into history):

```bash
bash run.sh --annotate-benchmark /path/to/benchmark.json --startup-context mono_setup
```

Accepted context values: `unclassified`, `routine`, `mono_setup`,
`gecko_setup`, `other_setup`. Import a new benchmark with `--record-benchmark`
and `--startup-context` to label it immediately. Setup sessions remain visible
in all-session statistics but are **excluded from routine/unclassified
comparisons**, and the UI displays the exclusion. Contexts are user-supplied
and **never proof** of the actual installer root cause.

Historical history entries without a context remain readable; no migration is
required and no stored measurements, hashes, personal notes or favourites are
rewritten by the label. The IPC protocol, pinned Win64 fixture and consent
boundary are unchanged.

## 0.6.0-alpha: native Linux desktop installation (optional)

A pure-Python user-level installer now creates a normal application launcher
and `GameWeld` desktop menu entry without sudo and without copying any third-
party executables. It copies allowlisted Python sources into the current user's
XDG data directory, and refuses to replace unrecognised existing files.

```bash
# Inspect intended action (no writes)
python3 -m gameweld.installer install --dry-run
# Install into ~/.local/share/gameweld and ~/.local/bin
python3 -m gameweld.installer install
# Launch from terminal, or find GameWeld in your KDE app launcher
~/.local/bin/gameweld
# Optional user-level removal (keeps all settings, notes and history)
python3 -m gameweld.installer uninstall
```

On CachyOS: `sudo pacman -S --needed python python-gobject gtk4`
(plus `wine` only for the optional IPC Lab). After installing a newer source
checkout, rerun `python3 -m gameweld.installer install` to update its copy.
Only `~/.local/bin` may need adding to your `PATH` if launching by name rather
than through the desktop menu. The installer never changes Steam, a game prefix
or system applications and will not overwrite an unrelated user launcher.

## 0.6.0-alpha verification limits

The expanded history, CLI and user-level installer are covered by offline
regression tests. GTK4 appearance and actual desktop-menu integration still
require a CachyOS host test. A reported Wine Mono installation is user-provided
context, not a mechanically confirmed explanation. A single additional slow
startup does not establish a performance regression. Complete detached Wine
helper cleanup and commercial trainer compatibility remain unverified.

## New in 0.7.0-alpha — Test your own local Windows trainer

This is GameWeld's first **real local Windows trainer launch path**, not just the original GameWeld IPC fixture. **Only execute EXEs from sources you personally trust.** SHA-256 pinning and Windows PE validation protect integrity; they do **not** make unknown trainers safe, guarantee compatibility, or detect malware. No executables are downloaded, bundled, patched or modified by GameWeld. Use offline, single-player games and avoid anticheat-protected games or online play.

The GTK4 **Trainer Lab** offers a Steam-game selector, EXE path, a separate *Find installed Proton versions* helper, a checksum inspection/review screen, isolation/advanced mode selector, separate consent checkboxes, a Launch button and a Stop button. GameWeld does not read or write live-game memory itself.

Two modes are available:

- **Isolated system Wine:** starts a private, temporary Wine prefix. This is useful for determining whether the Windows trainer's own window starts, but is **not expected to attach to a Steam Proton game**. Wine Mono setup can take time on fresh prefixes.
- **Existing Steam Proton game prefix (advanced):** attempts `proton run` with the **pre-existing** selected game's Steam compatdata directory and a user-selected Proton launcher. **May change the game's compatibility prefix, registry and save state. Back up your prefix and game saves before using.** This is an experimental compatibility attempt, not evidence that Steam's existing wineserver, pressure-vessel container or a running game are shared correctly. If Proton refuses to start, don't assume the trainer is broken. GameWeld never runs `wineserver -k`, changes Steam launch options or kills a game.

The source trainer is checked as a regular user-owned PE32/PE32+ `.exe` (not a symlink), hashed, and **copied and reverified** in a short-lived private staging directory before Wine/Proton sees it. Only single-EXE trainers are supported: tools that require adjacent DLLs or files may fail. The original EXE is not modified. Staged files are removed when the tracked launcher exits. Spawned grandchildren and trainer effects are **not verified**.

### Commands (first do a read-only review)

```bash
cd ~/Downloads/GameWeld
bash run.sh --trainer-list-proton
bash run.sh --trainer-inspect "$HOME/Downloads/MyTrustedTrainer.exe"
bash run.sh --trainer-preview "$HOME/Downloads/MyTrustedTrainer.exe" --trainer-appid 3008130
```

Copy the `sha256` value from inspection, and **only after personally reviewing the file**, test the isolated launch:

```bash
bash run.sh --trainer-launch "$HOME/Downloads/MyTrustedTrainer.exe" \
  --trainer-appid 3008130 --trainer-mode isolated \
  --trainer-sha256 'PASTE_INSPECTED_SHA256_HERE' \
  --consent-trainer-launch --trainer-timeout 180
```

For **advanced existing-game Proton mode**, first launch that game at least once in Steam, shut it down, back up its compatdata and saves, identify the *exact* Proton version the game uses, and then:

```bash
bash run.sh --trainer-preview "$HOME/Downloads/MyTrustedTrainer.exe" \
  --trainer-appid 3008130 --trainer-mode proton \
  --trainer-proton "$HOME/.local/share/Steam/steamapps/common/Proton - Experimental/proton"
# Only after reviewing the prefix warning and checksum:
bash run.sh --trainer-launch "$HOME/Downloads/MyTrustedTrainer.exe" \
  --trainer-appid 3008130 --trainer-mode proton \
  --trainer-proton "$HOME/.local/share/Steam/steamapps/common/Proton - Experimental/proton" \
  --trainer-sha256 'PASTE_INSPECTED_SHA256_HERE' \
  --consent-trainer-launch --consent-game-prefix --trainer-timeout 900
```

`--trainer-proton` is an example; use the **installed Proton executable for that game**. The command only launches a trainer, **not** the game. If you wish to test in-game effects, start the appropriate offline single-player game separately through Steam. All reports avoid raw file paths and trainer names, and never claim that in-game effects were verified. The trainer itself might make changes to a game's memory or files once started, outside GameWeld's control.

### Updating a previous user-level installation

```bash
cd ~/Downloads/GameWeld
git pull --ff-only
python -m unittest discover -s tests -v
python -m gameweld.installer install --dry-run
python -m gameweld.installer install
~/.local/bin/gameweld
```

The installed launcher copies the new `gameweld/trainer.py` module as well. No external trainer files are installed by GameWeld.
