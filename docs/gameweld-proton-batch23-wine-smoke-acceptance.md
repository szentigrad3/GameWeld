# GameWeld/DeckCheatz v2 — Windows-under-Wine observer smoke accepted

**31 October 2026 · Verified user-executed disposable-Wine smoke · Development only**

## Actual CachyOS outputs

The user ran the Batch 23 commands after the previous MinGW/Rust GNU Windows monitor cross-build:

```json
{"state":"grpc_venv_ready","mode":"--prepare-venv","steam_changed":false,"game_prefix_modified":false,"trainer_attachment_verified":false}
{"state":"windows_observer_smoke_prerequisites_ready","mode":"--check-smoke","steam_changed":false,"game_prefix_modified":false,"trainer_attachment_verified":false}
{"elapsed_seconds":17.75,"game_exit_code":0,"game_exited":true,"game_started_by_monitor":false,"monitor_exited":true,"state":"windows_wine_observer_smoke_passed","steam_changed":false,"trainer_attached":false,"trainer_cleanup_verified":true,"trainer_process_started":true,"win32_game_pid":516}
```

### What is genuinely verified

- gRPC dependencies and Windows smoke prerequisites were present.
- The Windows observer executed in a **disposable Wine prefix** with harmless Windows fixture game and trainer.
- The monitor observed the already-running fixture instead of launching a duplicate game (`game_started_by_monitor=false`).
- Observer reported **fixture** Win32 game PID **516**; it did not establish the actual Steam game Win32 PID.
- Fixture game exited with code 0; monitor-owned trainer fixture started and cleanup was verified; monitor exited.
- The test reported no Steam modifications.
- Test runtime approximately 17.75 seconds.

### Explicitly unverified

- Actual Dying Light: The Beast Steam AppID 3008130 **Win32 PID** and cross-boundary mapping to the already-verified Linux Wine game PID.
- Authenticated monitor executing in the **same live Steam-managed Proton Wine server**.
- Real WeMod UI rendering, login and **trainer attachment or functionality**.
- Independent GameWeld-owned *real trainer* cleanup after game exit, game crash or monitor crash. Fixture `trainer_cleanup_verified=true` **must not** be copied to live production acceptance.
- The complete Batch 22 MIT source staged in the user's local PR worktree is still not on the connected GitHub branch until specifically committed and pushed.

## Updated release gate / recommended next phase

1. Keep Steam Launch Options unchanged. Run the game normally through Steam.
2. Run the GameWeld Batch 22 driver in `--audit-only` mode **after configuring its private schema-1 XDG per-AppID settings**. Audit-only checks precise Proton/EXE/prefix evidence and does not launch the monitor or game.
3. Only after a positive audit, conduct an explicitly opted-in *read-only Windows observer identity check* in that same Proton session. Validate the returned Win32 PID and Windows full executable path, monitor session token, Wine server and Linux PID birth token before and after the probe. Do not spawn WeMod yet.
4. Test real WeMod GUI/login and attach in that verified session with the production feature toggle still off by default, after independent process-ownership and cleanup instrumentation has been added. Do not infer attachment from a trainer process starting.
5. Verify normal and abnormal close of owned monitor/trainer without affecting Steam, the game, wineserver, or unrelated processes. Do not declare a release before these are passed.

**CI test suites and the fixture observer prove useful components, not successful live attachment.** PR #18 must remain draft. Never instruct the user to paste custom Steam Launch Options.
