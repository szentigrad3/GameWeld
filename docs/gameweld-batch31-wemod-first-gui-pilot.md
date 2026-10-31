# Batch31 — first opt-in real WeMod GUI launch pilot

31 October 2026. Development-only. Draft PR #18 must remain draft; production trainer launch disabled.

## Live prerequisites actually passed

The user's CachyOS Batch30 test returned same_prefix_wineserver_candidate_stable and win32_identity_only_rpc_lifecycle_correlated, with same_prefix_wineserver_stable=true, authenticated Hello, unauthenticated rejection, trainer Execute/Finished denied at server, and owned test monitor exit. Selected game Linux PID 185951 (birth 12945298), wineserver PID 185869 (birth 12945222), Win32 candidate game PID 312 and creation FILETIME 134378829461334430 were user-observed historical values. New tests never hardcode those as the active process.

## Development full source ZIP

GameWeld-DeckCheatz-Batch31-Complete-Source-DEV.zip (292386 bytes; 140 entries; SHA256 a068929d478ed00ffabd6fccc7c876d4ded680612a7d2e8aaca2005334702675). The full source is supplied in the conversation, not committed here. New MIT pilot module: gameweld/scripts/gameweld-wand-v2-wemod-pilot.py, wrapper run-wemod-gui-pilot.sh; tests and staging script. Existing AGPL Rust unchanged.

Read-only --check validates configured PE, game PID/birth, selected Proton loader, same-prefix wineserver and no preexisting WeMod task, without starting Wine. Real --launch REQUIRES explicit --accept-unverified-cross-namespace-mapping. Before WeMod execution it repeats a complete trainer-disabled authenticated RPC session (including negative trainer-queue tests), revalidates the process and prefix/wineserver identities and hashes selected WeMod.exe. It launches only the configured WeMod.exe via selected Proton WINELOADER in the existing prefix. No production monitor, trainer queue, Steam game relaunch or Steam Launch Options changes.

Observation is bounded to 25 seconds. Signals only the directly owned Wine loader via Linux pidfd; no PID-only or process-group kill, never game/Steam/wineserver. Read-only same-prefix WeMod candidate counts are observational only. Any Wine/WeMod descendants can survive and are never signalled without proof of ownership. The pilot does not independently prove GUI visibility, login, game detection, trainer attachment, cleanup or the Linux↔Win32 PID mapping. Success state wemod_gui_pilot_observation_complete proves only a bounded loader process observation. All unsupported verification flags remain false.

## Verification

547/547 Python tests passed twice, including 40 new Batch31 tests and clean ZIP extraction. Python syntax, Bash syntax and ZIP integrity pass. Rust native/Windows build and real GUI launch NOT tested here; user's live test required.

## CachyOS acceptance

1. Extract the complete ZIP into ~/Downloads and enter deckcheatz-batch31-full-integration.
2. Run bash run-all-tests.sh, bash run-rpc-identity-only.sh --prepare-venv, then bash run-rpc-identity-only.sh --build.
3. Start Dying Light normally through Steam, preferably offline/single player.
4. Run bash run-rpc-identity-only.sh --provenance-check and bash run-wemod-gui-pilot.sh --check. Target preflight state wemod_gui_pilot_preflight_ready_not_executed.
5. ONLY on explicit opt-in: bash run-wemod-gui-pilot.sh --launch --accept-unverified-cross-namespace-mapping. This executes REAL WeMod.exe, may modify prefix files, and may leave GUI children open for manual closure.

Optional guarded local staging: bash apply-gameweld-pr18-batch31.sh /mnt/other/github/GameWeld-PR18-test, then the same with --apply. Only NEW MIT pilot staged; no commit/push or overwrite of existing staged files.

Keep PR draft and production launch disabled. After the live pilot, evaluate actual WeMod GUI/login/game detection and then independently verify real trainer functionality and owned-descendant cleanup before release.