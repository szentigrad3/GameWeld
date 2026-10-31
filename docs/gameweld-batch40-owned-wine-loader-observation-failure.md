# GameWeld Batch40: actual Batch39 spawn reached owned-loader observation, then blocked

31 October 2026. Steam AppID 3008130 (Dying Light: The Beast). PR #18 stays DRAFT. Actual post-repair GUI and trainer success remain UNVERIFIED.

## User-provided Batch39 evidence

Real CachyOS JSON `gameweld-b39-gpu-fallback-live.json`: `state=wemod_gui_pilot_blocked`, `blocked_stage=bounded_owned_wine_loader_launch`, `blocked_launch_phase=owned_loader_observation`, `reason=launch_owned_loader_observation_unavailable`, `wine_loader_process_started=true`. No production monitor authorization or trainer attachment; no manual Steam Launch Options change. This confirms the Wine-loader spawn returned and the Batch39 pilot entered the broad observation block, NOT which operation failed inside it. It does NOT establish that Electron honored the GPU flags or that a WeMod GUI appeared.

Separately uploaded `gameweld-b35-wine-loader-i9hm9hcj.log` has 87 lines, **83** `GPU process launch failed: error_code=43`, 2 `WSALookupServiceBegin failed with: 8`, **zero** `Integrity check failed for asar archive`. The JSON and log are not independently proven to be the exact same execution; never treat counts as proof the GPU fallback helped or hurt.

## Batch40 distinct MIT-only source changes

New development ZIP `GameWeld-DeckCheatz-Batch40-Complete-Source-DEV.zip` includes all Batch1–39 material and a revised MIT pilot. Exact final archive has 177 files, 396157 bytes, SHA-256 `101ac35c92b43580f6a57b8b0005ddb5d1ca854c8cf3b3db29fd34b7204910bf`; ZIP CRC passes.

* Break `owned_loader_observation` down into explicit allowlisted phases: `owned_loader_output_capture`, `owned_loader_proc_scan`, `owned_loader_process_poll`, `owned_loader_observation_sleep`, and `owned_loader_game_identity_recheck`. Only safe finite phase names are emitted, not raw exception strings, local paths or credentials.
* For unexpected post-spawn failure, preserve sanitized previously observed candidate counts, bounded captured-log categories/byte counts and, **only with explicit user consent**, an owner-only local private Wine log basename. Add `electron_gpu_fallback_arguments_submitted` to signal only that the Python subprocess call was made with GPU arguments; does NOT prove Electron accepted them.
* A Linux process already recognized by comm/cmdline as WeMod, whose environment becomes unreadable, is counted as UNATTRIBUTED. The pre-existing process guard then blocks another WeMod launch; unknown or unreadable data never proves process ownership. Root-level scan errors still block.
* Keep all prior trainer-disabled authenticated RPC denials and cross-namespace skepticism, exact game and wineserver PID/birth pins, configured WeMod PE identity, selected Proton Wine loader, per-AppID session lock, direct-owned Linux pidfd-only signalling and no Steam game/Launch Options edits. No `--no-sandbox`, Electron ASAR bypass, Wine-server kill, process-group kill or production trainer queue.
* Guarded dry-run-first `apply-gameweld-pr18-batch40.sh` stages only an exact MIT pilot, refusing user-modified source and unrelated changes. The AGPL Windows observer is unchanged and separate; this PR receives verification documentation only, NOT the new MIT source.

New focused tests cover private log redaction and retention, phase errors, process scan with malformed/unreadable WeMod candidates, safe PIDFD cleanup, non-faked GUI/attachment status, and guarded Git staging. They do not exercise live Dying Light or WeMod.

## Live acceptance gate

Extract the complete Batch40 ZIP; run `bash run-all-tests.sh`, prepare/build the local Windows monitor, and start Dying Light normally via Steam. Require successful `bash run-rpc-identity-only.sh --provenance-check`, `bash run-wemod-gui-pilot.sh --inspect-existing`, `--check`, and `--diagnose-launch-readiness`. STOP if any check blocks, especially if any same-prefix or unattributed WeMod candidate exists.

Only after the user **explicitly opts in again**, the same guarded GUI-only experiment with private logging may be used: `bash run-wemod-gui-pilot.sh --gpu-fallback-with-private-log --accept-unverified-cross-namespace-mapping --accept-private-loader-logging --accept-gpu-fallback-experiment`. It can write to the selected Wine prefix and leave Windows/Wine descendants; review raw logs privately/redact before sharing. No trainer attachment or complete cleanup is established. Production path remains disabled.

## Test honesty

First full-suite run on the Batch40 working tree completed **729 Python tests PASS** before one final fail-closed `/proc` attribution correction and two more tests. The **19 new focused tests PASS** against the final safety-corrected source and extracted final ZIP. Final full-suite clean extraction and any second final-tree full suite must be confirmed independently before they are labelled passed. Rust unavailable and unchanged; live Batch40 test NOT run.