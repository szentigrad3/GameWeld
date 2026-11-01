# GameWeld Batch42 — ACTUAL CachyOS identity-only authenticated RPC lifecycle PASS

2026-11-01 · Dying Light: The Beast / AppID 3008130 · PR #18 remains DRAFT, production WeMod integration disabled.

The user's uploaded `gameweld-b42-identity-rpc-exercise.json` reported:

- `state=win32_identity_only_rpc_lifecycle_correlated`
- `authenticated_hello_observed=true`
- `unauthenticated_hello_rejected=true`
- `trainer_queue_server_denied=true`
- `finished_server_denied=true`
- `owned_monitor_exited=true`
- `same_prefix_wineserver_stable=true`, `windows_process_birth_stable=true`
- Windows game PID `316`, creation FILETIME `134379833013255960`
- Linux game PID `821144`, Linux birth ticks `8807375`
- Linux wineserver PID `821061`, birth ticks `8807300`

The sampled Linux/Win32 PIDs are **historical, not permanent**; PID equality is not cross-namespace identity proof. The one-shot, trainer-disabled RPC test verified a successful authenticated hello, rejection of unauthenticated hello, and DENIAL (not execution) of trainer-queue and finished RPC. Its directly owned observer exited, and game+selected wineserver identity remained stable.

The result intentionally retains `monitor_session_authenticated=false`, `win32_pid_verified=false`, `monitor_launch_authorized=false`, `trainer_attachment_verified=false`, and `trainer_cleanup_verified=false`, because this acceptance exercise is NOT full production authorization, Windows↔Linux process identity proof, trainer execution or Wine child cleanup. `steam_configuration_written=false`, `steam_launch_options_changed=false`; `game_prefix_write_free_guaranteed=false` because a Wine observer was actually started.

The Batch42 complete source ZIP has the new Batch41 finer-grained postspawn identity error fields `identity_check_subphase` and `identity_failure_code` in the real GUI-only pilot. **No Batch43 patch is required solely to obtain those failure codes.** The next action is a *fresh* no-candidate inspection and full provenance + GUI preflight + runtime readiness (not replay historical PIDs). Only after all pass, and with user explicit opt-in, run a SINGLE bounded `--gpu-fallback-with-private-log` WeMod **GUI-only** experiment with all three existing acknowledgement flags. This experiment can modify the selected Wine prefix and leave Windows/Wine descendants. Previous live WeMod logs still contained repeated Electron GPU subprocess `error_code=43`; mere submission of flags is not evidence that Electron honored them, nor that a window/login/game detection works. Capture safe structured JSON, and only share user-reviewed private Wine log if needed.

Do NOT change Steam Launch Options, use protonhax/SteamTinkerLaunch hooks, disable ASAR/TLS integrity, kill Steam/game/wineserver, infer descendant cleanup or enable production trainer requests. Development executable source remains in conversation ZIP only; this GitHub update documents acceptance evidence, PR remains DRAFT.