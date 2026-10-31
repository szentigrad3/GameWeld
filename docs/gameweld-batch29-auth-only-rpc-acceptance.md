# GameWeld / DeckCheatz Batch 29 — live Win32 lifetime passed; auth-only RPC development

**31 October 2026 · AppID 3008130 · development only · PR #18 remains draft**

## Actual user-executed Batch 28 acceptance

With Dying Light running normally in Steam, the user's read-only preflight `--check` returned `win32_probe_ready_not_executed`. The explicit `--sampled` returned:

```json
{"appid":3008130,"candidate_linux_pid":185951,"candidate_start_time_ticks":12945298,"exact_runtime_verified":false,"game_launched":false,"game_prefix_write_free_guaranteed":false,"independent_windows_observations":2,"linux_game_birth_stable":true,"monitor_launch_authorized":false,"monitor_process_exited":true,"monitor_session_authenticated":false,"observed_win32_creation_filetime":"134378829461334430","observed_win32_game_pid":312,"samples_per_windows_observation":3,"selected_proton_correlated":true,"state":"win32_existing_game_lifetime_correlated","steam_configuration_written":false,"steam_launch_options_changed":false,"trainer_attachment_verified":false,"trainer_cleanup_verified":false,"trainer_launched":false,"verified_windows_drive_alias":"S:","win32_alias_retry_performed":true,"win32_path_correlated":true,"win32_pid_verified":false,"windows_process_birth_stable":true}
```

This proves two independent query-only Windows observations × three HELD HANDLE PID/image/creation-time samples, plus a stable separate Linux PID/birth and a canonical Wine drive alias. The **cross-namespace Linux↔Win32 PID mapping was not independently authenticated**, nor was any real WeMod trainer/GUI tested. Keep `win32_pid_verified=false`.

## Batch29 complete development source package (not yet committed to PR)

Downloadable artifact in conversation: `GameWeld-DeckCheatz-Batch29-Complete-Source-DEV.zip` (260,546 bytes; 129 entries; SHA-256 `a1961f1371ac4d6bb9be3d0754a300f2ea8007227d4e9700d4a3cc07dc2c5077`).

**AGPL Rust monitor (separate source tree)**: opt-in `--identity-only --port` server setting. Regardless of correct bearer token, authenticated `Execute`, `Finished`, `Stop`, `Restart` RPC methods return `FAILED_PRECONDITION` before side effects. `Hello`, `ObserveExisting`, `Shutdown` are available. A Rust test checks the restrictions, but this Rust change is **not yet compiled or tested on CachyOS**.

**AGPL Python client**: Test unauthenticated Hello is denied, valid one-time token accepted, ObserveExisting returns the exact expected Win32 PID, and even an authenticated invalid/inert `Execute` is rejected by the identity-only server (not merely invalid argument). Deny `Finished`, request `Shutdown`. No real trainer spec or queue sent; token passed in private environment, never exposed in stdout.

**MIT GameWeld experimental orchestrator**: Opt-in only. Reacquire Batch28 sampled Windows PID/FILETIME and Linux PID/birth before and after the identity-only RPC; hold per-AppID lock and verify selected Proton + DOS mapping during the session. Spawn and, when needed, stop only the *directly owned* monitor child, not the Steam game or wineserver. Enforce bounded gRPC client output and exact JSON types; reject any trainer/game/authorization claims. Success would be `win32_identity_only_rpc_lifecycle_correlated`, still with `monitor_session_authenticated=false` for the *production* monitor, `monitor_launch_authorized=false`, `win32_pid_verified=false`, `trainer_attachment_verified=false`.

## Validation performed here

- **475/475 Python tests passed**, including 13 new Batch29 cases, in the source directory and after a clean ZIP extraction.
- Python compilation, Bash syntax and ZIP CRC checks passed.
- **Rust native tests and Windows cross-build were unavailable in this authoring environment and are NOT claimed as passed.** No live RPC test in the real game was performed here.

## CachyOS acceptance commands

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch29-Complete-Source-DEV.zip
cd deckcheatz-batch29-full-integration
bash run-all-tests.sh
bash run-rpc-identity-only.sh --prepare-venv
bash run-rpc-identity-only.sh --build
# With Dying Light already running normally through Steam:
bash run-rpc-identity-only.sh --check
bash -o pipefail -c 'bash run-rpc-identity-only.sh --exercise 2>&1 | tee "$HOME/Downloads/gameweld-b29-auth-only-rpc.log"'
```

**Important**: `--check` is read-only. Explicit `--exercise` launches query-only Windows observer processes and an identity-only gRPC monitor in the **already-existing Proton prefix**, which may make incidental Wine prefix writes. No Steam Launch Options changes and no game/trainer starts. The random token authenticates the one-off localhost RPC caller but does not independently prove Wine Linux↔Win32 PID translation or an authorized production trainer session.

## Release gate

Only after the identity-only RPC passes should development proceed toward authenticated game/process binding, production monitor ownership, real WeMod GUI/login and verified trainer functionality, plus safe normal/crash cleanup of genuinely owned processes. **PR #18 remains draft, with production v2 GTK feature disabled**. The full Batch29 AGPL/MIT source is only in the separate downloadable ZIP; no conflicting local PR files were overwritten.