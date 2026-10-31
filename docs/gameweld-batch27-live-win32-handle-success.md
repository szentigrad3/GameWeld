# GameWeld — Batch 27 REAL live Win32 handle/path correlation succeeded

**31 October 2026 · Dying Light: The Beast AppID 3008130 · Development-only · Keep PR #18 draft**

## User-reported exact results

The user ran the Batch 27 script while the existing Steam game was running, with no manually changed Steam Launch Options:

```json
{"appid":3008130,"candidate_linux_pid":185951,"candidate_start_time_ticks":12945298,"exact_runtime_verified":false,"game_launched":false,"game_prefix_write_free_guaranteed":false,"monitor_session_authenticated":false,"monitor_started":false,"selected_proton_correlated":true,"state":"win32_probe_ready_not_executed","steam_configuration_written":false,"steam_launch_options_changed":false,"trainer_attachment_verified":false,"trainer_cleanup_verified":false,"trainer_launched":false,"win32_pid_verified":false}
```

```json
{"appid":3008130,"candidate_linux_pid":185951,"candidate_start_time_ticks":12945298,"exact_runtime_verified":false,"game_launched":false,"game_prefix_write_free_guaranteed":false,"monitor_launch_authorized":false,"monitor_process_exited":true,"monitor_session_authenticated":false,"observed_win32_game_pid":312,"selected_proton_correlated":true,"state":"win32_existing_game_handle_correlated","steam_configuration_written":false,"steam_launch_options_changed":false,"trainer_attachment_verified":false,"trainer_cleanup_verified":false,"trainer_launched":false,"verified_windows_drive_alias":"S:","win32_alias_retry_performed":true,"win32_path_correlated":true,"win32_pid_verified":false}
```

### Verified boundary

- Selected Steam AppID, game executable, Linux Wine game PID and birth ticks remained correlated.
- The Windows observer used the actual `S:` drive image alias from the exact prefix DOS-drive mapping and reported Win32 **PID 312**, through a query-only held Win32 process handle.
- The query-only process exited. No game/trainer was launched; Steam launch options and configuration remained unchanged.
- The full Windows image path was correlated with the exact configured Linux game EXE.

### Still NOT verified

- A protected, independent mapping of Win32 PID 312 to Linux PID 185951. These **are different PID namespaces**; do not equate them. See Wine's process model and avoid translating by appearance or proximity.
- A live authenticated/persistent monitor connection in the same Steam-managed Wine server; standalone query-only probe was not that connection.
- Real WeMod GUI/login/functional trainer attachment and real ownership-scoped exit/crash cleanup.
- `exact_runtime_verified=false`, `win32_pid_verified=false`, `monitor_session_authenticated=false` and `monitor_launch_authorized=false` intentionally remain false.

## Next development gate

1. Add a **read-only paired identity observation** that pins Linux PID and birth ticks **before/after** Windows inquiry and captures a Win32 process creation-time token through the same held process handle. Repeat over an interval to detect Windows PID reuse/relaunch. A Windows process creation timestamp must come from a documented process-time API and is not itself a Unix↔Windows PID mapping.
2. Determine whether a trustworthy Wine-specific API or Steam prefix/server identity can independently link the selected Unix and Windows process identities; if not, preserve `win32_pid_verified=false`.
3. Once the exact same runtime is independently authenticated, bind the monitor session token, intended Win32 process identity, and GameWeld-owned child process lifetime. Retain explicit opt-in, fail-closed startup, bounded stdout and session lock. Do NOT queue WeMod merely because a query-only probe passed.
4. Test real WeMod startup/GUI/attachment on the live game only after the security gates, then normal/game-exit/crash cleanup of owned children. No Steam launch option edits.

## Code deployment status

The **Batch27 MIT** probe source is in the complete downloadable source ZIP and the user's local `~/Downloads/deckcheatz-batch27-full-integration`. It is not yet necessarily staged into their `/mnt/other/github/GameWeld-PR18-test` Git worktree or committed to PR #18. AGPL Windows observer stays in its separate source tree. Keep the current PR draft and its experimental production path disabled.

**Do not confuse this observed Win32 PID with verified WeMod attachment or real monitor cleanup.**
