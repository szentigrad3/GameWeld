# Batch43 — real Batch42 failure and fail-closed transient wineserver /proc scan repair

**2026-11-01 · Dying Light: The Beast AppID 3008130 · draft PR #18 · documentation-only GitHub update**

## What the user's actual files establish

`gameweld-b42-gpu-after-rpc.json` reports:
- `state=wemod_gui_pilot_blocked`, `reason=launch_owned_loader_game_identity_recheck_unavailable`;
- `blocked_launch_phase=owned_loader_game_identity_recheck`, **`identity_check_subphase=wineserver_snapshot_first`**, **`identity_failure_code=wineserver_context_unreadable`**;
- `wine_loader_process_started=true`, `electron_gpu_fallback_arguments_submitted=true`, `wemod_same_prefix_candidate_count=5` / unattributed 0;
- `private_loader_log_saved=true`, `loader_output_bytes_seen=29853`, `loader_output_tail_truncated=true`;
- no trainer attachment, GUI, complete Wine child cleanup or Win32 production identity mapping verified; no Steam Launch Options change.

The separate uploaded `gameweld-b35-wine-loader-745h1ow1.log` is 311 lines with **307** repeated Electron GPU-process `error_code=43`, two Windows network lookup errors and no ASAR-integrity fatal. A submitted `--disable-gpu` flag is NOT proof Electron applied it. Neither GPU cause nor actual GUI startup is resolved.

Earlier actual `win32_identity_only_rpc_lifecycle_correlated` verified a short-lived authenticated Windows monitor, rejection of unauthenticated hello, and denial of trainer queue/finished. It DID NOT enable production trainer capability.

## Root-cause limitation and narrowly scoped Batch43 change

Batch42's `server-provenance.py` iterated `/proc` and mapped **every** `HandoffBlocked` or `OSError` while reading a wine-server-shaped process into `wineserver_context_unreadable`. The uploaded diagnostic proves it occurred during first postlaunch wineserver snapshot but **does not expose which Linux read failed**. A transient Wine-related process exiting between `/proc` enumeration and reading `comm`/`environ`/`exe`/`stat` is a plausible explanation, **not confirmed**.

Batch43's MIT-only provenance module now skips a candidate **only** if:
1. the operation failed with underlying Linux `ENOENT` or `ESRCH`, including an `HandoffBlocked` wrapping that exact OS error; **and**
2. a new `stat` confirms that task's `/proc/PID` entry is now ABSENT.

A still-present unreadable task, permission denial, missing live `exe`, ambiguous same-prefix wineserver, mismatched Proton binary or changed birth token **still blocks**. The genuine selected same-prefix wineserver must continue to be found exactly once and pass exact PID/birth/Proton binary checks twice; this never substitutes another or changes identity gates.

New focused tests verify the safe process-disappearance case, unknown errors, live-process non-skipping, permissions, executable mismatch, birth failures, duplicates, zero selected wineservers and no Steam/Wine side effects.

## Distribution and test gates

Complete source development ZIP in conversation: `GameWeld-DeckCheatz-Batch43-Complete-Source-DEV.zip`, 190 archive entries, 426153 bytes, SHA-256 `c4329531f52f6d083587c51376a741d7e98f1512b8dbfe4ce92e272e8d65e74c`; archive CRC PASS. Includes full Batch42 source plus the corrected provenance module, 21 Batch43 tests, README, and exact-hash guarded local update helper.

**Avoid another Windows observer rebuild:** the helper `apply-batch43-to-batch42.sh TARGET --check|--apply` only updates the exact previously verified Batch42 provenance Python file and adds the unit test, after checking fixed SHA-256 digests, refusing symlinks, unknown local edits and incorrect target directory. A real pristine Batch42 fixture was exercised: dry-run PASS, apply PASS and idempotent second apply PASS. No user's actual local folder was touched.

Working source suite **798/798 PASS** (before adding 7 helper tests), and final clean-extracted ZIP `bash run-all-tests.sh` **805/805 PASS** (exit code 0). All **21 Batch43 focused tests PASS**. Python compile, Bash syntax and ZIP integrity PASS. No Cargo/Rust execution here, no live Wine/WeMod/game. Trainer-capable production operations remain disabled.

**Next user check:** first read-only `bash run-wemod-gui-pilot.sh --inspect-existing` on the running game. The prior five process candidates were an historical finite observation and must not be assumed gone or owned. No new WeMod launch before a clean candidate scan, provenance and readiness and explicit user consent. Do not alter Steam Launch Options, disable Electron ASAR/TLS checks, kill unrelated Wine processes, or enable trainer queue.

**This is a plausible fix for a transient race, not a verified GPU fix or a live WeMod success.** GitHub receives documentation only; executable source delivered separately in user-facing ZIP; PR remains DRAFT.