# GameWeld / DeckCheatz Batch 25 — query-only live Win32 identity experiment

**31 October 2026 · Development source package · draft PR #18**

## User-confirmed prerequisite acceptance

Dying Light: The Beast Steam AppID `3008130` now passes both:
- `gameweld_v2_private_config_written`, with exact selected Proton, game EXE, compiled Batch23 observer and managed WeMod path.
- `gameweld_v2_static_config_ready` and `gameweld_v2_linux_runtime_audit_stable`, reporting a real Linux Wine game PID `185951` with birth ticks `12945298`, **3/3 stable samples**, `verified_live_proton_process_executable`, game path and selected Proton correlated.

Those PIDs are historical observations; Batch25 reacquires the process. `exact_runtime_verified=false` and `monitor_launch_authorized=false` in the live JSON correctly denote the missing Windows-side proof.

The user previously validated the Windows observer's **disposable-Wine fixture**, including a fixture Win32 PID 516 and owned fixture cleanup. That is not the actual Dying Light Windows PID.

## Batch25 complete development archive — separate from PR

Produced `GameWeld-DeckCheatz-Batch25-Complete-Source-DEV.zip` with:
- **AGPL Rust Windows observer**: a new standalone `--probe-existing-game <absolute DOS EXE path>` option, using the existing kernel read-only Win32 handle + exact full Windows image path lookup. No RPC server, no trainer queue or game launch.
- **MIT Python GameWeld helper**: `gameweld-wand-v2-win32-probe.py`. `--check` makes only read-only filesystem and /proc calls; `--probe` runs only the rebuilt Windows identity-query monitor through the previously verified live Proton Wine loader and exact existing Wine prefix. It revalidates Linux PID and birth token before and after, using private per-AppID locking, bounded output (4 KiB) and a 15-second timeout.
- **Conservative trust boundary**: a positive report says `win32_existing_game_handle_correlated` and includes an **observed Win32 PID**, but retains `win32_pid_verified=false`, `exact_runtime_verified=false`, `monitor_session_authenticated=false`, `trainer_attachment_verified=false`, `trainer_cleanup_verified=false`. It does not independently map the Linux↔Win32 process IDs, authenticate a future monitor connection, or authorize real WeMod.
- Wine can write incidental prefix files when launched. **Do not claim this explicit `--probe` mode is write-free**; only `--check` is read-only. No Steam Launch Options edits or user game relaunches are required.
- A small opt-in `run-win32-identity-probe.sh` wrapper with `--build`, `--check` and `--probe` modes.

## Verification, no overclaims

**381/381 Python tests passed**, including 20 new probe safety cases, both in the working source tree and from a clean ZIP extraction. Syntax, Bash syntax and archive CRC checks passed. SHA256 of the ZIP: `248d2a51e7975936d7584ca6917321ddff560c04a78f36fe130b3eac4d81d622`.

**NOT tested here**: the modified Rust Windows target was not compiled (authoring environment lacks Rust GNU Windows toolchain), and the probe was not executed against the user's live Steam game. The Batch23 disposable Wine smoke cannot be used to claim that the NEW probe-only mode works.

## Exact CachyOS instructions

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch25-Complete-Source-DEV.zip
cd deckcheatz-batch25-full-integration
bash run-all-tests.sh
bash run-win32-identity-probe.sh --build
```

Start Dying Light normally through Steam (no custom Launch Options), and while it is already running:

```bash
bash run-win32-identity-probe.sh --check
```

If `win32_probe_ready_not_executed`, explicitly opt into a short identity query using the same selected Proton prefix:

```bash
bash run-win32-identity-probe.sh --probe | tee "$HOME/Downloads/gameweld-b25-live-win32-probe.json"
```

The positive outcome `win32_existing_game_handle_correlated` is **candidate evidence only**. On failure, report the exact JSON or Windows build error. Do not use an old fixture PID and never change Steam Launch Options to force success.

## License / checkout boundaries

The Rust modifications are **AGPL-3.0-only** and live separately in the full source ZIP; the Python helper is MIT. Batch 25 is **not automatically applied to the local Git checkout** and no partial source files were pushed to PR #18; its local three staged MIT Batch22/24 edits remain untouched. Do not merge this PR or enable the production WeMod button until authenticated real Windows session and actual WeMod trainer attachment/cleanup pass.
