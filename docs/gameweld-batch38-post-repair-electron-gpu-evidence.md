# GameWeld Batch38 — Post-ASAR-repair Electron GPU subprocess failures

31 October 2026 — development only — Steam AppID 3008130 — PR #18 remains DRAFT.

## User-provided live artifacts and EXACT evidence

After successful Batch37 selected WeMod.exe/ASAR header recovery, the user uploaded **two separate files**:

1. `gameweld-b37-post-repair-gui-pilot.json` reports `state=wemod_gui_pilot_blocked`, `reason=pilot_environment_unavailable`, with Steam configuration and Launch Options untouched. **This pilot JSON does NOT prove any Wine or WeMod process was launched.** Because Batch37 caught different exceptions under one generic error reason, this JSON does not identify the missing preflight.
2. `gameweld-b35-wine-loader-5bfza3se.log`, **40,317 bytes, 420 lines**, includes a line reporting a capture tool's binary path (this private local path is omitted here), **416** lines of `gpu_process_host.cc(975): GPU process launch failed: error_code=43`, and **two** `WSALookupServiceBegin failed with: 8`. Visible GPU event timestamps span **7,790 ms**. No `Integrity check failed for asar archive` line is present in THIS supplied log.

**CRITICAL attribution limit:** the blocked JSON and separate Wine log have not been cryptographically associated with one launch; they might belong to different attempts. We may conclude only that an actual Wine/Electron logging session experienced repeated GPU subprocess failures. This is not yet a proven graphics-driver or DXVK root cause. The complete ASAR pair repair is separately established by the user's prior independent audit.

Relevant background: Electron has documented issues where `--disable-gpu` does not reliably prevent a GPU subprocess (`https://github.com/electron/electron/issues/28164`), and users of other Electron apps under Wine report the same `error_code=43` (`https://github.com/Kron4ek/Conty/issues/210`). These are contextual parallels, NOT confirmation that proposed flags will work for WeMod.

## Batch38 full source development ZIP

`GameWeld-DeckCheatz-Batch38-Complete-Source-DEV.zip`, 382540 bytes, 170 source entries, SHA256 `f607267379bac0d563f3f4e975920745735c7744f71b109dd9815055c9dfaffe`. ZIP CRC passed. Source is in the user's conversation artifact, NOT pushed into this MIT GitHub PR, preserving their local uncommitted checkout.

MIT-only features:

- Read-only offline `gameweld-wand-v2-gpu-log-audit.py` and wrapper `run-wemod-gpu-log-audit.sh`: reports only named error counts and bounded elapsed timestamp window; no raw logs, user paths or token-bearing lines. Marks `log_and_pilot_same_execution_verified=false`; recognizes and explicitly flags prelaunch-blocked pilot JSON.
- `gameweld-wand-v2-wemod-pilot.py` now returns `blocked_stage` (allowlisted, non-sensitive) with blocked outcomes, to separate a missing configured observer from selected game/wineserver checks.
- A **separate** `--gpu-fallback-with-private-log` wrapper mode is explicitly opt-in and requires THREE acknowledgments. It retains ALL previously verified game/wineserver Linux PID/birth checks, trainer-disabled Win32 authenticated RPC and server-side Execute denial, selected Proton loader, hash-pinned selected WeMod PE and owned Linux pidfd cleanup. It starts ONLY WeMod.exe with `--disable-gpu --disable-gpu-compositing` added to that process, NOT Steam/game. NO `--no-sandbox`, ASAR integrity bypass, manually edited Steam Launch Options, `pkill wine` or trainer queue. Child processes may remain after bounded 25-second observation, GUI/attachment/cleanup still UNVERIFIED.
- Diagnostic category matching now includes Electron GPU process failures and Windows network service lookup, without emitting raw private output.

Verification: **688/688 Python unittests passed** in source, including **23 new focused Batch38 tests**. Shell syntax, Python syntax and ZIP CRC passed. **688/688 Python tests also PASSED again from a clean extraction of the final ZIP (57.735 seconds)**; both complete runs passed independently. Rust/Wine GUI live tests were NOT executed in authoring environment.

## Safe user sequence

1. Extract ZIP and run `bash run-all-tests.sh`.
2. Without running Wine or Dying Light, analyze actual log: `bash run-wemod-gpu-log-audit.sh --log "$HOME/Downloads/gameweld-b35-wine-loader-5bfza3se.log" --pilot-json "$HOME/Downloads/gameweld-b37-post-repair-gui-pilot.json"`.
3. For any OPTIONAL real new WeMod startup, start game normally through Steam, then prepare local observer in new source directory and require successful `--provenance-check`, `--inspect-existing`, and `--check`.
4. If and only if user explicitly opts in, use `bash run-wemod-gui-pilot.sh --gpu-fallback-with-private-log --accept-unverified-cross-namespace-mapping --accept-private-loader-logging --accept-gpu-fallback-experiment`, capturing its structured JSON. It can cause Wine prefix writes and privately save raw logs under Downloads; review/redact before sharing.

The safest next question is whether the game was running at the moment the Batch37 `pilot_environment_unavailable` JSON was produced, and whether the new GPU-fallback pilot changes the GPU failure count or lets the GUI appear. No claimed WeMod GUI, login/game recognition, trainer attachment or owned-descendant cleanup until separately verified.