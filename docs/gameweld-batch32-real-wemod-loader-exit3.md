# Batch32 — first real WeMod loader exited with code 3; bounded diagnostic fix

31 October 2026. Dying Light: The Beast / Steam AppID 3008130. PR #18 must remain DRAFT.

## User-executed Batch31 acceptance (actual, not simulated)

Read-only provenance and GUI pilot preflight returned `same_prefix_wineserver_candidate_stable` and `wemod_gui_pilot_preflight_ready_not_executed` in the existing Steam Proton session. Selected game candidate Linux PID 185951/birth 12945298 and wineserver PID 185869/birth 12945222 matched.

The user explicitly opted into a first real `WeMod.exe` GUI launch pilot. Its authenticated trainer-disabled RPC passed and observed Win32 game PID 312 / creation FILETIME 134378829461334430. The directly owned Proton Wine loader did start and subsequently EXITED WITH CODE 3; 0 same-prefix WeMod candidates and 0 unattributed WeMod candidates were observed. JSON: `reason=wine_loader_exited`, `state=wemod_gui_pilot_observation_complete`, `gui_visible_verified=false`, `trainer_attachment_verified=false`. **This did NOT demonstrate a successful WeMod GUI.** No Steam Launch Options changes or game/trainer startup.

Batch31 discarded the Wine loader stdout/stderr (`DEVNULL`). Therefore code 3's actual cause cannot be established from the existing output. It may be Wine startup, loader invocation, dependencies, WeMod runtime, or other causes. Do not assert one cause without diagnostics.

## Batch32 full source development ZIP, separate from GitHub source

`GameWeld-DeckCheatz-Batch32-Complete-Source-DEV.zip`: 306679 bytes; 145 entries; SHA256 `a56ee68c01dbe4deac1c51b3ec861c9f0aa0d91ba7f3b97d8bc4dee65e512af3`.

Updated MIT `gameweld/scripts/gameweld-wand-v2-wemod-pilot.py`: for *explicit opt-in* real WeMod launch, capture combined owned Wine-loader stdout/stderr to nonblocking pipe, drain at most 128KiB per polling tick, retain only the last 16KiB in memory and return only allowlisted `loader_diagnostic_categories` (missing Windows module, bad EXE format, load failure, Wine prefix/server, no display, graphics, permissions, runtime exception). No raw error lines, home paths, usernames or tokens are emitted or persisted by this tool. Outputs also include byte count and truncation/read-error flags. Categories are lexical clues, not root-cause proof.

Nonzero loader exit now has `state=wemod_gui_pilot_launch_failed`, `reason=wine_loader_nonzero_exit` and nonzero shell exit, instead of misleading `observation_complete`. The initial process scan happens before checking for exit. A pidfd-open failure is accepted only if directly owned `Popen` already reports the child exited, otherwise the tool fails closed without PID-only signalling. Final Linux game/wineserver identity changes outrank the loader failure classification.

New SHA-guarded `apply-gameweld-pr18-batch32.sh` stages ONLY this MIT pilot, replacing only the exact hash-pinned original Batch31 or exact already-staged Batch32. Protects user's other local uncommitted MIT files. No AGPL sources added to the MIT repository; no Git push/commit performed.

**574/574 Python tests PASS twice (working source and clean ZIP extraction); 27 new tests**. Python syntax, shell syntax, ZIP CRC pass; missing private configuration fails closed. The AGPL Windows monitor is unchanged. Rust build not run here. New diagnostic mode has not been exercised against the user's live Proton game and the first live WeMod launch failure is NOT fixed yet.

## Exact next user actions

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch32-Complete-Source-DEV.zip
cd deckcheatz-batch32-full-integration
bash run-all-tests.sh
bash run-rpc-identity-only.sh --prepare-venv
bash run-rpc-identity-only.sh --build
# Start Dying Light normally through Steam, preferably offline/singleplayer
bash run-rpc-identity-only.sh --provenance-check
bash run-wemod-gui-pilot.sh --check
# Only if explicitly opting in to REPEAT the real WeMod GUI launch:
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --launch --accept-unverified-cross-namespace-mapping 2>&1 | tee "$HOME/Downloads/gameweld-b32-live-wemod-diagnostic.json"'
```

Expected failed-launch report includes `wine_loader_exit_code`, `loader_diagnostic_categories`, `loader_output_bytes_seen`, `loader_output_tail_truncated`, and `state=wemod_gui_pilot_launch_failed`. If categories are empty, investigate alternative startup evidence without inventing a cause. No manual Steam Launch Options edits or blanket Wine process kills.

Even if the Wine process starts successfully, GUI visibility/login, game recognition, trainer attaching/working and real owned-descendant cleanup are still UNVERIFIED. Independent Linux↔Windows PID translation not proven. Keep production WeMod feature OFF and PR draft.