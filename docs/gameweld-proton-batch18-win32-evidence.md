# GameWeld Batch 18 — Windows observer evidence contract (untrusted, read-only)

Development only. This batch does **not** launch a Windows monitor, trainer, game or Steam and does not prove a working WeMod attachment.

## Live baseline supplied by the CachyOS tester

The previous Batch 17 App ID `3008130` report returned:

- `state=linux_runtime_anchor_stable`; 3 of 3 samples completed.
- Current Linux Wine game PID `185951`; process start ticks `12945298`.
- One Steam library, one matching installation manifest, one existing Proton compatdata prefix, one verified full game executable path.
- Exact game executable basename `DyingLightGame_TheBeast_x64_rwdi.exe` and one unique game-process candidate.
- Same-prefix wineserver observed; Steam launch options and configuration untouched.
- `win32_pid_verified=false`, `exact_runtime_verified=false`, `trainer_attachment_verified=false`.

The PID is historical evidence, **not** a durable authorization to attach to a process after a restart.

## New Batch 18 module

`scripts/gameweld-wand-v2-win32-evidence.py` compares a future Windows observer report with an already verified Linux-side anchor.

It requires exact Steam App ID, a unique reported Windows process candidate, evidence that the monitor observed rather than started the game, exact Linux PID and start ticks, and a nonzero integer Windows PID **reported by the observer**.

The reported Windows executable path is resolved through the selected existing Proton prefix's `dosdevices/<drive>:` mapping. The resolved file must match the selected installed game executable. UNC/device paths, traversal, missing drives, escape symlinks, ambiguous paths, and nonexistent files fail closed.

**Trust boundary:** The observer report is untrusted JSON. Even a fully matching report only yields `observer_candidate_evidence_correlated`, and the module explicitly retains:

```json
{"win32_pid_verified": false,
 "exact_runtime_verified": false,
 "monitor_authenticated": false,
 "monitor_attached": false,
 "trainer_attachment_verified": false,
 "trainer_cleanup_verified": false}
```

This is intentional: only a separate real, authenticated Windows-side observer that owns a protected Win32 process handle, verified to be in the selected Steam/Proton session, can establish Win32 PID identity and authorization. A claimed PID in JSON cannot.

## Regression suite

`scripts/test-gameweld-wand-v2-win32-evidence.py` contains **21** hermetic tests for matching file and Linux anchor, App ID mismatch, multiple Windows candidates, unexpected monitor game launch, changed PID and start ticks, invalid Windows PID, missing drive mapping, wrong executable, traversal/UNC/relative paths, symlink escape, stale Linux anchor, missing wineserver evidence, and all false-by-default attachment flags.

Run the entire branch suite:

```bash
cd /mnt/other/github/GameWeld-PR18-test
git pull --ff-only
python3 scripts/test-gameweld-wand-v2-live-context.py -v
python3 scripts/test-gameweld-wand-v2-live-anchor.py -v
python3 scripts/test-gameweld-wand-v2-session-gate.py -v
python3 scripts/test-gameweld-wand-v2-bounded-monitor.py -v
python3 scripts/test-gameweld-wand-v2-aio.py -v
python3 scripts/test-gameweld-wand-v2-win32-evidence.py -v
```

The Linux-side read-only AIO live test remains:

```bash
python3 scripts/gameweld-wand-v2-aio.py --appid 3008130 --steam-root /mnt/games/Steam
```

Do not execute Batch 18 against fabricated Windows observer output for a live attach: its synthetic test fixtures are validation examples, **not** proof.

## Critical next task

Import and integrate the actual `deckcheatz-rewrite-v2-gameweld-batch12_3` (or newer) **Windows ObserveExisting monitor** source. The accessible connected GameWeld repository holds the Python handoff contract but not the complete Windows observer implementation. Until that source is integrated and real on-machine Win32 identity plus authenticated monitor session and trainer attachment are demonstrated, leave the production Play with WeMod action disabled.

Complete a GameWeld-owned trainer PID/start-time registry and verify cleanup independently after exit or crash without touching the game, Steam, wineserver or unrelated trainer processes.

No Steam Launch Options or compatibility-tool changes are introduced.
