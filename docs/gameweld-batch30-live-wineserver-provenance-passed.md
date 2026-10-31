# Batch30 live acceptance: same-prefix wineserver + trainer-disabled authenticated RPC passed

**31 October 2026 — Dying Light: The Beast, Steam AppID 3008130 — development-only**

User executed on CachyOS with the existing Steam game running, without modifying Steam Launch Options.

## 1. Read-only preflight

`bash run-rpc-identity-only.sh --check` returned `identity_only_rpc_preflight_ready_not_executed`, no game/trainer launched.

`bash run-rpc-identity-only.sh --provenance-check` returned `same_prefix_wineserver_candidate_stable`, with:

| Field | User-observed result |
|---|---|
| candidate_linux_pid | 185951 |
| candidate_start_time_ticks | 12945298 |
| wineserver_linux_pid | 185869 |
| wineserver_start_time_ticks | 12945222 |
| selected_prefix_correlated | true |
| selected_proton_wineserver_binary_correlated | true |
| monitor_launch_authorized | false |
| win32_pid_verified | false |

## 2. Explicit trainer-disabled identity-only RPC

`bash run-rpc-identity-only.sh --exercise` returned `win32_identity_only_rpc_lifecycle_correlated`, with:

- `authenticated_hello_observed=true`, `unauthenticated_hello_rejected=true`.
- `trainer_queue_server_denied=true`, `finished_server_denied=true`.
- `same_prefix_wineserver_stable=true`.
- `owned_monitor_exited=true`.
- Win32 game PID 312, creation FILETIME `134378829461334430`, `windows_process_birth_stable=true`.
- Same Linux game PID/birth and wineserver PID/birth as read-only preflight.
- `game_launched=false`, `trainer_launched=false`, `steam_launch_options_changed=false`, `steam_configuration_written=false`.

## What this does and does not mean

**Confirmed by the user's live output:** the experimental same-prefix wineserver check passed and the authenticated trainer-disabled monitor RPC completed while preserving the selected wineserver identity. The direct owned monitor exited.

**Still not proven:** an independent Linux PID ↔ Win32 PID mapping (`win32_pid_verified=false`), authorization of any production trainer-capable monitor (`monitor_launch_authorized=false`, `monitor_session_authenticated=false`), actual WeMod GUI/login, trainer attaching and functioning, and cleanup of *all* monitor/trainer-owned descendants after normal exit or a crash (`trainer_cleanup_verified=false`).

The Linux and Win32 PIDs are different namespaces. The fact that both observations share the same Steam prefix and stable wineserver is evidence of the intended environment, but not mathematical proof of a one-to-one process identity mapping. No production/real trainer capability is granted by this result.

## Next concrete release gate

1. Put a **separate, explicitly opt-in development-only WeMod launch test** behind the proven prefix/provenance/Win32 creation-time check, bounded owner/session locks, no user Steam Launch Options edits and a clear failure report. Avoid implying that real attachment is guaranteed; this would be the **first** actual WeMod launch.
2. Add verifiable ownership-scoped monitor/WeMod child-process tracking, non-destructive stop/normal-exit/crash tests. Never signal the Steam game, wineserver, user processes, or unrelated Wine descendants.
3. Require fresh identity rechecks, a server-enforced capability gate, and human opt-in before any trainer-capable RPC method. If Windows/Unix cross-namespace mapping cannot be independently proven with the available API, do not set `win32_pid_verified=true`.
4. Only mark real trainer attachment/cleanup passed after game-detection and functionality checks, not from RPC authentication or a process launching.

**PR #18 remains draft; this GitHub commit is verification documentation only.** The Batch30 complete AGPL+MIT source is in the user's development ZIP and may not be present in the remote branch. Do not overwrite their local uncommitted MIT changes.
