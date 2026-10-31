# Batch 29 — Live authenticated identity-only RPC acceptance PASSED

**31 October 2026 · Dying Light: The Beast AppID 3008130 · development-only · draft PR #18**

## User-executed CachyOS acceptance (exact meaningful output)

- Preflight `state=identity_only_rpc_preflight_ready_not_executed`, no trainer or game launched.
- Explicit `--exercise`: `state=win32_identity_only_rpc_lifecycle_correlated`.
- `authenticated_hello_observed=true`, `unauthenticated_hello_rejected=true`.
- `trainer_queue_server_denied=true`, `finished_server_denied=true`. These demonstrate the **trainer-disabled** server guard was exercised.
- `observed_win32_game_pid=312`, `observed_win32_creation_filetime="134378829461334430"`, `windows_process_birth_stable=true`. Linux PID `185951` and start ticks `12945298` remained the selected candidate.
- `owned_monitor_exited=true`, no game or trainer launched, no Steam Launch Options or Steam configuration changed; `game_prefix_write_free_guaranteed=false` because Wine could perform incidental bookkeeping writes.

## Strongest conclusion warranted

The existing Steam-managed game was observed through an **authenticated, trainer-disabled, short-lived Windows RPC** with correct token denial and server-side trainer-queue denial, matching the previously observed Win32 process PID and creation token. The test-owned observer exited.

**Do not claim:** `win32_pid_verified=true` as an independent Linux↔Win32 PID translation, `monitor_session_authenticated=true` for the **production, trainer-capable monitor**, `monitor_launch_authorized=true`, real WeMod UI/login/attachment, or ownership-scoped real trainer cleanup. Every one of these was reported false by the actual test, and the result is not permission to enable trainer execution.

## Release-critical next batch

1. **Bridge exact lifecycle binding:** design a monitor authorization capability that cryptographically binds GameWeld's app ID, selected Proton/prefix, canonical game path, Win32 game PID + creation token, Linux candidate PID/start ticks, nonce, and validity period. Validate inside the Windows monitor *after* its own process open, not solely in Python. Keep session locked and all trainer methods disabled until all verifications pass; avoid claiming cross-namespace PID translation without an independent supported source.
2. **Prove provenance of Wine session:** revalidate that a newly started monitor joins the intended live Steam wineserver and not a separately initialized server. Use read-only Wine/proc identity observations where available, and fail closed on ambiguous/exited server.
3. **Ownership-safe cleanup:** track directly spawned monitor and (later) trainer process handles and birth identities; test game normal exit and crash without killing game, Steam, wineserver or unrelated processes.
4. Only after these gates: explicit opt-in real WeMod GUI/login and functional trainer attachment test. Do not infer attachment from a started process.
5. Keep MIT GameWeld and AGPL-only DeckCheatz source separated, and avoid replacing the user's locally staged Batch22/24/27/28 worktree modifications without reconciliation.

**Current repository:** this file records user validation, but complete Batch29 AGPL + MIT development source remains in the separate source ZIP, not yet necessarily committed to PR #18. PR must remain draft and the production WeMod GTK toggle off by default. No manual Steam Launch Options edits.
