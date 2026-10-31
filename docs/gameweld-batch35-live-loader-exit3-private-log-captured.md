# Batch35 LIVE acceptance: loader code 3 repeated and 297-byte private log captured

31 October 2026 — Dying Light: The Beast, Steam AppID 3008130. PR #18 remains draft and production WeMod path remains disabled.

## User's actual CachyOS observations

First read-only checks after changing to the Batch35 extracted source were blocked: `identity_only_preflight_blocked`, `pilot_environment_unavailable`, `windows_probe_preflight_not_ready`. No launch took place during that first blocked set. Reason for unavailable game environment was not demonstrated by these JSON fields.

The user repeated the checks with a new live Linux game PID **16370** / birth ticks **70063**, matching selected game and Proton wineserver PID **16286** / birth ticks **69989**. The read-only provenance returned `same_prefix_wineserver_candidate_stable`, existing WeMod inspection returned `wemod_no_existing_candidate_visible` (three samples, zero candidate processes), and the pilot returned `wemod_gui_pilot_preflight_ready_not_executed`.

User explicitly opted in to REAL WeMod launch and private loader output capture. The live trainer-disabled identity-only RPC PASSED, observing Win32 game PID **320** / creation FILETIME **134378959282149090**. The Wine loader was started; it exited with code **3**, resulting in `state=wemod_gui_pilot_launch_failed`, `reason=wine_loader_nonzero_exit`. One same-prefix WeMod candidate was observed during the launch window; no unattributed candidates. `gui_visible_verified=false`, `trainer_attachment_verified=false`, `trainer_cleanup_verified=false`, `win32_pid_verified=false`, `production_monitor_authenticated=false`, `monitor_launch_authorized=false`. No Steam configuration or Launch Options were changed.

**New decisive artifact:** the pilot captured **297 bytes** of directly owned Wine loader stdout/stderr and saved it locally under `~/Downloads/gameweld-b35-wine-loader-83_t8_6g.log` (mode 0600 by design). `private_loader_log_saved=true`, `private_loader_log_write_error=false`, `private_loader_log_truncated=false`, `loader_output_read_error=false`; `loader_diagnostic_categories=[]`. This is not an empty log; the narrow classifier simply matched none of its known signatures. We have NOT read its actual contents. The log exists on the user's CachyOS computer, not inside this assistant's current filesystem. Do not guess the meaning of exit code 3.

## Next action

**Do NOT rerun the real WeMod launch blindly.** Examine the **existing** 297-byte local log, redact any paths, account names, email addresses, tokens, URLs or other sensitive data, and provide only its sanitized diagnostic lines. The bounded log itself may include sensitive information; never upload it unreviewed. Source inspection shows Batch35 captured stdout/stderr from the direct Wine-loader subprocess and has no other live error details. Check whether a Windows handoff process appeared and exited, but do not treat one candidate snapshot as a visible GUI.

After identifying the actual Wine error message, build the next targeted source fix; then rerun with the authenticated identity-only and same-prefix gameserver guards. The historical PIDs above MUST NOT be hard-coded as active PIDs after another game restart. Do not change Steam Launch Options, kill Wine/wineserver/game, or enable real trainer RPC. Keep full AGPL observer source separate from MIT GameWeld.