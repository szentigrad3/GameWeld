# Batch42 real CachyOS Win32 lifetime probe: PASS, authenticated RPC not yet exercised

2026-11-01, Dying Light: The Beast, Steam AppID 3008130. This is a documentation-only update to draft PR #18; no executable code is changed.

## User-uploaded result

Exact uploaded artifact: `gameweld-b42-win32-sampled.json`.

```text
state = win32_existing_game_lifetime_correlated
independent_windows_observations = 2
samples_per_windows_observation = 3
observed_win32_game_pid = 316
observed_win32_creation_filetime = 134379833013255960
verified_windows_drive_alias = S:
win32_alias_retry_performed = true
win32_path_correlated = true
windows_process_birth_stable = true
linux_game_birth_stable = true
monitor_process_exited = true
candidate_linux_pid = 821144
candidate_start_time_ticks = 8807375
selected_proton_correlated = true
exact_runtime_verified = false
win32_pid_verified = false
monitor_session_authenticated = false
trainer_launched = false
trainer_attachment_verified = false
steam_launch_options_changed = false
```

This is genuine sampled, stable **Windows-side game PID + creation-time plus executable-path correlation** across two independent Windows observations; Win32 observer exited. These Linux and Windows PIDs are distinct namespace identifiers and MUST NOT be translated by equality or used as future live IDs.

The report intentionally has `win32_pid_verified=false` and `exact_runtime_verified=false`: these are stricter production/authenticated integration statuses than a standalone sampled Windows lifetime observation. `monitor_session_authenticated=false` because the token-authenticated RPC acceptance test has NOT run. No WeMod GUI, login, game recognition, trainer attachment or whole-descendant cleanup is established.

## Next already-implemented gate

Inspect Batch42 shipped `run-rpc-identity-only.sh` and `gameweld-wand-v2-auth-only-aio.py`: `--exercise` uses a fresh sampled Win32 baseline, reconstructs the exact verified game path under the `S:` alias, validates current Linux process birth + same-prefix wineserver, starts ONLY a directly owned short-lived Windows identity monitor with a random one-shot token, and exercises authenticated/unauthenticated hello + server-side denial of trainer queue / finished. It verifies Windows and Linux game lifetime again after RPC and owns cleanup only for the newly spawned monitor. Success state `win32_identity_only_rpc_lifecycle_correlated` with `win32_pid_verified=false` and `monitor_session_authenticated=false` still intentionally unchanged—do not claim production session authorization from the transient test.

Use with game started normally and no existing WeMod candidates, `bash run-rpc-identity-only.sh --check` (read-only) followed by **explicit user opt-in** `bash -o pipefail -c 'bash run-rpc-identity-only.sh --exercise 2>&1 | tee "$HOME/Downloads/gameweld-b42-identity-rpc-exercise.json"'`. This opt-in starts Wine inside the existing Proton prefix and may make incidental prefix writes. Never launch WeMod or queue trainer, never alter Steam Launch Options or kill Steam/game/wineserver. Stop on any failure and investigate structured denial reason; no new ZIP is necessary for this test.

PR remains draft.