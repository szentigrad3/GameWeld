# Batch41 development research — isolated Steam runtime, recheck diagnostics and trainer guides

31 October 2026 · Dying Light: The Beast, AppID 3008130 · PR #18 stays **draft**.

## Confirmed live evidence carried forward

The user supplied Batch40 JSON: `wine_loader_process_started=true`, `electron_gpu_fallback_arguments_submitted=true`, `wemod_same_prefix_candidate_count=4`, `blocked_launch_phase=owned_loader_game_identity_recheck`, `reason=launch_owned_loader_game_identity_recheck_unavailable`. Repeated Electron GPU subprocess error 43 was independently observed in an uploaded Wine log, with no repeat Electron ASAR integrity fatal. **Caution:** the logged Wine process and structured JSON are not cryptographically proven to be the same execution. No GUI, trainer attachment or descendant cleanup is verified. Previous ASAR pair repair remains proven from an independent local audit.

## What Batch41 source implements (development ZIP, not pushed here)

1. **Specific game identity subphases** for a later post-spawn failure: game process discovery/birth, first and second selected same-prefix wineserver snapshots, snapshot comparison, game revalidation/birth comparison. All diagnostic codes are finite/allowlisted; raw exception messages, local paths, Steam authentication and tokens never leave the process. The existing identity checks are unchanged in security significance: a failure still blocks startup.
2. `--diagnose-running-identity`: three repeated read-only Linux game PID/start-token plus wineserver PID/start-token snapshots, works even with an existing WeMod candidate, returns step and a safe failure code; never launches or signals Wine, Windows observer, game, trainer or WeMod. Stable read-only snapshots **never authorize trainer launch**.
3. `--diagnose-container-parity`: reads the game, wineserver and GameWeld launcher **mount/PID namespace inodes** from procfs, checks identity stability again, and compares relations. Does NOT enter a namespace, run protonhax, use ptrace, change Steam configuration, or treat namespace parity as Windows↔Linux PID mapping or Wine-socket connectivity proof.
4. Guarded local MIT-only pilot stager: dry run first, exact known source hashes, protects unrecognized local edits and unrelated changes. AGPL Windows observer remains separate and unchanged.

## External references reviewed and explicitly evaluated

* [zehelh/proton-trainer-launcher](https://github.com/zehelh/proton-trainer-launcher) is MIT Rust/Tauri. Its Steam mode uses `protonhax` when the game's Steam Linux Runtime pressure-vessel container requires the trainer to be inside the same environment; its README requires the Steam `protonhax init %command%` Launch Options hook for that path. **Do not implement** because the user requires no manual/automatic Steam Launch Options changes. An uninjected direct-prefix fallback is explicitly warned as potentially unable to share the game's container. Its child environment sanitation for AppImage/IDE leaks is useful context; GameWeld already starts from a narrow inherited environment and must not blindly remove the selected Proton runtime's required libraries.
* [DeckCheatz/meta issue #1](https://github.com/DeckCheatz/meta/issues/1) reports one user's WeMod v11.6.0 login screen working under Wine while newer Wand 12.x showed a black window. Comments mention TLS/certificate failures, crypt32 and Squirrel update logic; their causal explanations are **speculative**, NOT a documented fix or safe excuse to bypass certificate/security verification. Our selected 11.6.0 executable/ASAR integrity mismatch was separately repaired and audited; the outstanding GPU and game-identity checks remain.
* [SteamDeck WeMod guide](https://www.reddit.com/r/SteamDeck/comments/18u80ym/installing_wemod_on_steamos_the_proper_way/) describes a separate-prefix/older Windows compatibility strategy with changes to `drive_c/windows`, Win7 compatibility and .NET setup. **Do not** copy those potentially destructive steps into the user's currently running game prefix or claim that a displayed login means game detection works.
* [2026 Linux trainer guide](https://www.reddit.com/r/linux_gaming/comments/1s6qpdr/game_trainers_on_linux_tutorialguide_2026_proton/) recommends `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW` as Steam **Launch Options** or SteamTinkerLaunch custom/injected commands, with adjustable delays for launching before/after the game. Both approaches change Steam settings (launch options or selected compatibility tool) and **are NOT incorporated into GameWeld**. The *timing concept* is a future design reference only; any future in-GameWeld timing must occur after fresh game+wineserver identity and authentic trainer-disabled RPC checks, with a separately opted-in trainer launch. Community advice about Aurora and FLiNG is anecdotal, not a verified solution to Electron GPU error 43.

## Batch41 next live gate (NO launches)

Extract the complete Batch41 ZIP and run tests. With Dying Light already started normally through Steam, run:
```bash
bash run-rpc-identity-only.sh --provenance-check
bash run-wemod-gui-pilot.sh --inspect-existing
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --diagnose-running-identity 2>&1 | tee "$HOME/Downloads/gameweld-b41-running-identity.json"'
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --diagnose-container-parity 2>&1 | tee "$HOME/Downloads/gameweld-b41-container-parity.json"'
```

Even if existing WeMod processes are present, the new diagnostics can be used read-only. DO NOT run the real GPU fallback again merely to get these results. Do not kill the game, Steam, wineserver or unknown Wine descendants, change Launch Options or switch compatibility tools. Keep production trainer disabled and PR draft.

## Authoring/test honesty

Complete source ZIP is produced in the conversation, not committed to this GitHub PR. **FINAL ZIP verified:** `GameWeld-DeckCheatz-Batch41-Complete-Source-DEV.zip`, **411073 bytes**, **183 entries**, SHA-256 `a4b4a5a77a750e85022d1c699ba5afb8c49a976a68b1bcc296cc7bebd7f38f70`. **771/771 Python tests PASSED** from a fresh extraction of the FINAL ZIP in 73.108 seconds, exit 0. Python compilation, Bash syntax and ZIP CRC PASSED. Batch41-focused tests: **40 PASSED**. Rust/Cargo unavailable, SKIPPED; no actual Wine/WeMod/GPU/live game tests performed here. Windows/Rust native build and live Proton integration have NOT been performed in the authoring environment.
