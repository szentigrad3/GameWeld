# GameWeld Batch39 — bounded Wine launch failure stage isolation

31 October 2026 | Dying Light: The Beast / Steam AppID 3008130 | development only, PR #18 remains DRAFT.

## Actual user-provided Batch38 result

Uploaded `gameweld-b38-gpu-fallback-pilot.json` returned `state=wemod_gui_pilot_blocked`, `blocked_stage=bounded_owned_wine_loader_launch`, `reason=pilot_environment_unavailable`. **This does not confirm that GPU fallback args were passed to WeMod or that Wine started.** The Batch38 outer handler converted different unexpected exceptions from the entire launch routine into one generic string.

Uploaded `gameweld-b35-wine-loader-o87hn6je.log` contains 85 lines, including 81 `GPU process launch failed: error_code=43`, 2 `WSALookupServiceBegin failed with: 8`, no ASAR integrity fatal. The uploaded `gameweld-b38-gpu-log-audit.json` describes a DIFFERENT prior 420-line log with 416 GPU errors. Neither log has been proven to belong to the blocked Batch38 pilot, so the 416 vs 81 counts are **NOT a verified GPU fallback comparison**. The user's full WeMod.exe/ASAR pair repair was previously confirmed; do not undo it.

## Batch39 MIT development changes (full source ZIP, NOT pushed into PR)

`gameweld-wand-v2-wemod-pilot.py` now tracks a finite set of allowed operation names and converts unexpected runtime exceptions into `reason=launch_<safe_phase>_unavailable`, with `blocked_launch_phase` in blocked JSON. Phase coverage includes selected game/wineserver identity, configured PE identity, trainer-disabled authenticated RPC, existing WeMod guard, GameWeld per-AppID exclusive session lock, locked game identity, selected Proton Wine loader environment, private log creation, direct owned Wine loader spawn, pidfd acquisition, bounded observation, direct-loader cleanup and postlaunch identity. Raw exception text, Wine stdout, local paths, credentials, process environment and tokens are never serialized. Direct pidfd-only loader safety, failure-closed trainer-disabled RPC, exact game/wineserver PID/birth pins and Steam Launch Options non-modification remain unchanged.

New `--diagnose-launch-readiness` wrapper mode checks the running game, selected wineserver, exclusive per-AppID GameWeld lock, configured WeMod PE and selected Proton Wine loader. It starts **no Wine, no WeMod and no Windows RPC**. Its session lock can create a 0600 file in the user's XDG runtime directory, but it doesn't edit the game prefix or Steam. It retains the installed Windows monitor's static preflight. Target state `wemod_launch_runtime_preflight_ready_no_wine_started`; if blocked, report finite safe reason.

The explicit GPU fallback mode from Batch38 is unchanged. A GPU launch retry remains user-opted-in and should not occur until the new launch-readiness mode passes. A separate guarded `apply-gameweld-pr18-batch39.sh` stages only exact MIT pilot code from unmodified known Batch37/38 files; it does not alter GitHub or the user's local PR unless they explicitly execute `--apply`.

## Development verification

**712/712 Python unittests passed in working tree**, including 24 new tests. Python compilation, Bash syntax, ZIP integrity passed. ZIP `GameWeld-DeckCheatz-Batch39-Complete-Source-DEV.zip` SHA256 `b699254b6c3a439b5bfde2652c616d0dadd497584ac50a2da23cfd264af62bb3`, 173 entries, 391708 bytes. **712/712 Python tests also PASSED again from a clean extraction of the FINAL ZIP, in 73.614s; independent full-suite double pass confirmed.** Rust/Windows builds and any live CachyOS execution not performed here; AGPL Rust observer unchanged.

## Exact next user gate

Unzip Batch39 complete source; from its root run `bash run-all-tests.sh`, then with Dying Light running normally under Steam (single-player/offline recommended), prepare the local observer via `bash run-rpc-identity-only.sh --prepare-venv` and `--build`, run `--provenance-check`, `bash run-wemod-gui-pilot.sh --inspect-existing`, `--check`, and finally **non-launching** `bash run-wemod-gui-pilot.sh --diagnose-launch-readiness` to save structured JSON. Stop if any check blocks. No need to launch WeMod just to obtain this new diagnostic.

If all checks pass and user separately opts into actual GUI launch, the existing three-acknowledgment GPU fallback still exists; it may write to the Wine prefix and save a private log, and can leave Wine descendants. It never starts a production trainer, edits Steam Launch Options, or asserts GUI/game recognition/attachment/cleanup. PR #18 stays draft; full source remains in development ZIP, GitHub changes documentation-only.