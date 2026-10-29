# DeckCheatz rewrite/v2 integration (draft, batch 2)

GameWeld remains the sole user-facing GUI and launch/session owner. DeckCheatz's AGPL-licensed rewrite and Rust gRPC monitor are separate upstream components. This GameWeld branch supplies only MIT-licensed headless adapters. **Nothing in this draft changes Steam Launch Options or registered compatibility tools.**

Upstream design: https://github.com/DeckCheatz/wemod-launcher/tree/rewrite/v2 and https://github.com/DeckCheatz/wemod-launcher/issues/307.

GameWeld adapter stages:
1. `scripts/gameweld-wand-v2-preflight.py` checks a selected app's existing prefix and user-selected WeMod executable, without starting processes.
2. `scripts/gameweld-wand-v2-session.py` accepts --appid, --compatdata, --client, --game-exe, --monitor-endpoint and --rewrite-root **only when GameWeld has already created an authenticated monitor inside its selected live game Proton environment**. It passes these to the upstream headless entrypoint, never constructs another Proton command and never invokes a shell.
3. Neither script claims a WeMod trainer is attached just because processes are seen.

**Known blockers before enablement:** The standalone upstream monitor Rust source in the separate Batch 2 artifact is not yet compiled or field-tested. Steam's exact launch command/arguments and session startup by GameWeld are still incomplete; the GameWeld GTK Play with WeMod callback is not yet switched to this adapter. The published DeckCheatz Rust monitor is not yet its specified gRPC implementation. This is a development interface only, not a functioning WeMod launch integration.

Do not merge this draft until the upstream gRPC monitor builds, prefix/data safety review is complete, Steam’s original runtime command and game arguments are preserved, and the WeMod GUI, login, trainer attachment and cleanup pass live testing. Preserve AGPL/MIT attribution and distribution boundaries.

## Batch 5 safety checks (2026-10-29)

The development monitor's positive native gRPC smoke has been confirmed by its tester, including trainer cleanup. The new Batch 5 source adds stricter Rust process ownership and event sequencing, plus local gRPC failure tests. These changes are **not an installed GameWeld feature** and Rust Batch 5 compilation has not yet been verified.

The GameWeld bridge rejects out-of-range loopback ports and boolean game exit codes, requires both processes to start and requires explicit trainer cleanup evidence. This does **not** prove the WeMod UI rendered or that a trainer attached.

The GTK Play with WeMod callback must not be switched to this experimental bridge until GameWeld supplies a real monitor in the correct Steam Proton/Wine session, preserves the game's actual launch command, and verifies game identity and cleanup. Do not change Steam Launch Options or compatibility selection.

## Batch 6: read-only Steam context evidence

`scripts/gameweld-wand-v2-live-context.py` inspects only current user's /proc process environment, checking AppID, actual compatdata directory, and Wine prefix. The diagnostic result `steam_session_context_candidate` deliberately **does not** mean the Windows executable or trainer attachment was verified. No process is launched, stopped, injected, or reconfigured.

A positively matched Steam process is insufficient to enable the GameWeld button. Before live handoff, GameWeld must preserve Steam's real game launch and arguments, positively correlate the Windows process with the chosen installation, and start the separate monitor inside that same Wine server. Do not treat the experimental monitor's own direct-game spawn as a replacement for Steam's launch. Development session bridge stays fail-closed.

The external Batch 6 DeckCheatz monitor removes `WAND_MONITOR_SESSION_TOKEN` from its game/trainer child environments to avoid disclosing its control credential. The upstream client rejects WeMod exit or closure while the game is still active as a successful session, and requests monitor shutdown.

## Batch 7: Steam live runtime plan (source bundle only)

The separately distributed **Batch 7** source package adds the read-only GameWeld helper `gameweld-wand-v2-runtime-plan.py`. It requires full game executable-path correlation and exact selected Steam/Proton/WINEPREFIX/WINEDSERVER identity before producing a **non-executable** Windows-monitor launch plan. Cumulative package Python tests: 125/125, no errors. This helper is **not yet committed to this PR**; the ZIP is the source review artifact.

A verified Linux PID does not establish Win32 PID identity. The published gRPC monitor's current launch protocol starts a new game process, which must not replace a Steam-managed game. GameWeld's existing Play with WeMod action remains unchanged. Do not merge or ship as functional until the monitor can observe the already-running Windows game, preserve Steam's original game startup/arguments, and verify WeMod GUI/attachment and cleanup.

## Batch 8: experimental Windows observe-existing-game protocol

The separate DeckCheatz AGPL source package now includes a Windows-only `ObserveExisting` gRPC call. Its read-only process snapshot finds an **unambiguous full executable-path match**, returns the Win32 PID, holds an OS wait handle, and reports game exit without launching or terminating the game. The monitor owns and closes the separately spawned trainer. The GameWeld session bridge now requests `--observe-existing-game`, **not** the monitor's old direct-game-spawn mode.

Cumulative Batch 8 source tests: 140 Python tests passed from a clean extracted package. The changed Rust/Windows code **has not yet been cross-compiled or field-tested**, and WeMod GUI/attachment are unverified. The current GameWeld GUI Play-with-WeMod button remains unchanged, and the internal bridge is not invoked by a production path. Do not merge or deploy this draft before exact-game Wine testing and Steam session handoff validation.

## Batch 9: isolated Win32 observation smoke before GTK handoff

The independent AGPL DeckCheatz source package **Batch 9** adds a disposable Wine prefix test for the actual Windows monitor executable. It compiles harmless Windows game/trainer fixtures, starts a real monitor under Wine, checks authenticated full-path and exact Win32 PID observation, and verifies that only the monitor-owned fixture trainer is closed after the observed fixture game exits. Python client also supports optional bounded gRPC Events deadline for this smoke.

Source tests: 158/158 Python tests passed locally. **The Windows-under-Wine test has not yet been executed on CachyOS.** The prior Batch 8.3 Windows compilation and Rust tests were reported passing by the tester. Do not report the new Win32 observation smoke as passed until run.

The GameWeld GTK `on_launch_with_wemod` callback still calls `ensure_proton_gate` / `arm_wand_launch` / `steam -applaunch`. It is **not** connected to a verified Windows observer. Do not remove or switch the production callback based on the disposable Wine smoke alone; Steam/Proton live session ownership, WeMod GUI and actual trainer attachment remain open. Nothing in Batch 9 changes Steam options, prefixes or GameWeld production installation.

## Batch 9 Windows-under-Wine acceptance evidence (2026-10-29)

A tester has now executed the disposable Windows-under-Wine observer smoke and reported:
- `state=windows_wine_observer_smoke_passed`, `win32_game_pid=528`
- `game_started_by_monitor=false`, `game_exited=true`, `game_exit_code=0`
- `trainer_process_started=true`, `trainer_cleanup_verified=true`, `monitor_exited=true`
- `steam_changed=false`, `trainer_attached=false`
- elapsed time 58.7 seconds

The prerequisite probe also reported `observer_wine_prerequisites_ready`. This validates the independent monitor's process discovery/exit tracking under a **disposable Wine prefix** only; it does not validate the actual Steam game, WeMod renderer, trainer attachment, or that GameWeld launched the monitor. Do not report one-click launch complete.

**Next integration gate:** replace the legacy GTK `JOB_WEMOD`/Proton gate implementation with a GameWeld-owned, normal Steam launch followed by authenticated monitor startup in the game's exact existing Wine server and `ObserveExisting` handoff. That requires Steam session/process identity and compatible GUI/trainer operation checks. Keep the production path unchanged until this gate passes; retain unrelated game/trainer provider flows.

## Batch 10: opt-in GTK -> Steam -> existing Wine server -> Windows observer

The development GTK frontend now has a feature-gated JOB_WEMOD_V2 branch behind GAMEWELD_ENABLE_WAND_V2=1. The worker passes the selected Steam AppID, installation path and executable to the GameWeld session driver supplied in the separate complete Batch 10 source ZIP. The driver must be copied into the GameWeld checkout / AppImage before opting in: this GitHub branch does NOT yet include that file by itself. The branch remains a non-mergeable development PR until the entire source bundle, build script and live acceptance checks are integrated.

The driver calls Steam normally with an argv-only steam -applaunch <AppID> when no matching game already exists, or joins the already-running game. It validates the full game executable path against the live Linux process, exact Proton Wine loader and wineserver, Steam AppID and compatdata. It launches the Windows monitor via that Wine loader with an ephemeral local bearer token, then delegates to DeckCheatz's observe-existing-game gRPC path. Only the monitor is ever GameWeld-owned and reaped; the Steam game is never terminated by this adapter. Per-game paths live in the private XDG gameweld/wand-v2.json settings, not Steam config. A private per-AppID flock blocks duplicate sessions.

Cumulative source bundle tests: 184 Python tests passed locally. GTK source in the PR has not yet been compiled with GameWeld's native build, and the driver has not been run against the user's real Proton environment. The successful disposable Windows-under-Wine observer smoke (Batch 9) is independent evidence, not acceptance of the live GameWeld path. Trainer attachment and WeMod rendering are unverified. Do not merge, distribute or enable this route until build and live acceptance criteria pass. The legacy GTK path remains the default.

## Batch 10 packaged regression and developer status

Complete cumulative source ZIP (194 passing Python tests from a clean extraction) includes GameWeld's full experimental session driver, private per-game XDG config writer, guarded GTK hook source transformer, updated DeckCheatz Python gRPC client, existing Windows monitor source and tests. The opt-in GTK C hook itself has been committed in this draft branch; driver/config/helper source still requires the ZIP overlay into a clean feature worktree. The GTK hook transformer was checked against all 13 exact anchors in GameWeld main. GTK compilation has NOT been executed here.

User-executed Batch 9 disposable Wine observer test passed. Next required live validation: selected Dying Light/Steam game identity in running Proton, exact Wine loader monitor startup, actual WeMod GUI/rendering/login, trainer attachment and lifecycle. The experimental route is off by default and never edits Steam Launch Options or compatibility tools; real Wine activity may modify prefix state. Do not merge or deploy this draft yet.

## Batch 11: GTK C syntax regression fix and long-session safety

Review of the draft branch found that the Batch 10 JOB_WEMOD_V2 worker route contained a literal backslash-n (`\\n`) outside a C string. This is invalid C and was **fixed directly in the draft branch**. Existing GameWeld CI includes `gcc -fsyntax-only -pthread crates/wand-ui/appimage-gtk3/gameweld-native-040.c`, but an actual CI success on this updated branch has **not** yet been confirmed.

The development session bridge timeout is now 86,400 seconds (24 hours), matching the GameWeld controller instead of incorrectly killing a valid one-hour-plus game session. The separate complete Batch 11 source bundle also tightens the controller's own result verification: both game and trainer start evidence, a non-boolean integer game-exit code, and verified trainer cleanup are required. Its `check-gameweld-gtk.sh` prepares an isolated temporary worktree of this draft branch, stages the MIT-side adapters, performs a real GCC **syntax-only** check, then cleans up without touching the user's active branch or Steam. Package Python regression tests: 205 passed here.

These tests do **not** establish a linked GameWeld AppImage, a live Steam/Proton handoff, a working WeMod window or actual trainer attachment. The GTK feature gate remains disabled by default, and the draft PR must not be merged until end-to-end field testing.

## Batch 12: live Steam context discovery (source ZIP) and Linux PID lifetime safety

The user's Batch 11 CachyOS checks passed: **14/14 Rust unit tests** and real GameWeld GTK3 `gcc -fsyntax-only` with `gtk_c_compiled=true`, `v2_driver_deployed=true`, `game_started=false` in a disposable worktree. These confirm native unit tests and C syntax, not a linked application or WeMod attachment.

The independent complete Batch 12 source ZIP now adds `gameweld-wand-v2-steam-audit.py` (read-only `/proc` inspection using the selected Steam AppID) and `read_process_birth_token` (Linux `/proc/PID/stat` starttime verification) in the GameWeld runtime planner. The experimental controller checks that birth token again before it launches **only** the Windows monitor. Changed or reused PIDs block the handoff.

**Important: new Batch 12 Python files are only in the ZIP; the draft PR does not yet contain those files.** The bundle's 222 Python unit tests passed against synthetic data. A real Steam/Proton audit has **not** been run; no actual game was launched or modified. The intended next command while the Steam game is already running is `python3 gameweld/scripts/gameweld-wand-v2-steam-audit.py --appid 3008130` from the Batch 12 ZIP root. Its result is runtime *candidate* evidence, not verified Win32 process identity or trainer attachment.

The GameWeld GTK feature gate remains off in production. Do not merge PR #17 until the complete source, full GameWeld build, Steam handoff and actual WeMod GUI/attachment are verified.

## Batch 12.2: missing Wine runtime exports — kernel-linked Proton evidence

The user's live read-only Steam audit for AppID 3008130 saw 15 processes exposing the requested AppID, of which 12 correlated with the selected compatdata/prefix, but **all 12 lacked exported WINELOADER/WINESERVER**. This identifies an overly restrictive runtime-export assumption in the previous source, not proof that the game is absent.

The separate complete Batch 12.2 ZIP updates the GameWeld MIT runtime plan, audit, diagnostic tool, and experimental session driver. When those variables are absent, they can independently verify that the kernel's **/proc/PID/exe symlink** resolves to a Wine executable under the selected Proton installation's `files/bin` directory. The Steam AppID, prefix, exact game executable and selected Proton identity must still match; conflicting exports still fail closed. The resulting runtime values are derived from that verified Proton tool, not a command-line basename.

The source package passed **252 Python tests** (15 new tests), Python syntax, shell syntax, ZIP integrity and clean extraction. **The new live audit has not yet been executed on the user's Steam session**. Source modifications are distributed in the ZIP and not yet imported into the draft GitHub branch. Do not enable production WeMod launch from this diagnostic alone, and do not claim trainer attachment or Win32 game PID verification.

## Batch 12.3: real-game AppID/prefix found, but no kernel Wine loader executable

Second real audit (AppID 3008130) still found 15 AppID-labelled processes, 12 prefix-correlated, and now 11 visible .exe command-line **hints**, but zero verified Proton loader executable symlinks and zero strict monitor launch candidates. This is not evidence that Steam or the game failed to launch; it is a detector evidence limitation.

The separately packaged **Batch 12.3** ZIP adds read-only Linux `/proc/PID/maps` Wine-module evidence diagnostics and categorized executable symlink reporting to distinguish container/runtime remapping, mapped libraries under the selected Proton tool and missing permissions. It handles octal-escaped spaces in maps, reports conflicting mapped Proton roots, and does not expose paths/secrets by default. A mapped library is **not** sufficient for launching the monitor, and strict monitor handoff code remains unchanged.

**267/267** cumulative Python tests passed after clean ZIP extraction. The new code is bundled separately and not yet copied into the GameWeld draft branch. No actual Steam/Proton monitor launch, WeMod GUI rendering or trainer attachment has been verified. Next field check: run `gameweld-wand-v2-steam-audit.py --appid 3008130 --diagnose` from Batch 12.3 while Dying Light runs normally in Steam; no Launch Options or prefix modification.
