# GameWeld / DeckCheatz Batch 26: live Win32 process lookup failed — diagnostic follow-up

**31 October 2026 · PR #18 remains draft.**

## Confirmed live output from user

The user's Batch25 `--check` passed with `win32_probe_ready_not_executed` (Linux PID 185951, start ticks 12945298, selected Proton correlated). Then, with Dying Light: The Beast (Steam App ID 3008130) already running, the explicit Windows observer `--probe` returned:

```json
{"appid":3008130,"state":"win32_probe_blocked","reason":"win32_process_lookup_failed","exact_runtime_verified":false,"monitor_launch_authorized":false,"monitor_session_authenticated":false,"trainer_attachment_verified":false,"trainer_cleanup_verified":false,"trainer_launched":false,"win32_pid_verified":false}
```

The process **was not identified in Win32 by strict exact image path**. Previous disposable-Wine fixture smoke passing does not override this failure. The failure could be exact DOS drive path versus a different Windows reported image path; Win32 process visibility, query access, loader/session mismatch or timing. **The underlying cause is not established.**

## Complete Batch 26 source ZIP, not pushed to MIT PR

The conversation's `GameWeld-DeckCheatz-Batch26-Complete-Source-DEV.zip` extends Batch25 with:

- AGPL Windows `process_win.rs`: on failed exact lookup only, read-only ToolHelp diagnostic scoped exclusively to the expected game's Win32 executable basename. Report numeric target candidate/queried/failed counts; at most one readable image for a single same-basename process. Unrelated processes are not enumerated into output.
- AGPL `main.rs`: emit bounded JSON `win32_probe_lookup_diagnostic` before exiting **nonzero**. No RPC session, trainer queue, game or trainer startup.
- MIT `gameweld-wand-v2-win32-probe.py`: strict allowlist parser, rejects malformed/unrelated paths and any trainer/game started claim. Even valid diagnostics keep `win32_probe_blocked`, `win32_pid_verified=false`, `monitor_launch_authorized=false`, `trainer_attachment_verified=false`, `monitor_session_authenticated=false`. Additional Linux PID/birth validation after the FAILED Win32 probe as well as after success.
- 16 new hermetic Python tests. Complete **397/397 tests passed**, also after clean ZIP extraction, Python syntax and Bash syntax passed. Archive CRC passed; SHA256 `eb529faac6d53dbc1b83061ca32b4696d6b9f5a89fc2691a15c77dc1a0256e07`.

**NOT tested here:** modified Rust Windows GNU compile; real Steam-managed Proton/Win32 probe; actual WeMod startup/attachment/cleanup. User needs to rebuild on CachyOS and return the diagnostic.

### Exact next user action

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch26-Complete-Source-DEV.zip
cd deckcheatz-batch26-full-integration
bash run-all-tests.sh
bash run-win32-identity-probe.sh --build
# With Dying Light already running normally through Steam:
bash run-win32-identity-probe.sh --check
bash -o pipefail -c 'bash run-win32-identity-probe.sh --probe 2>&1 | tee "$HOME/Downloads/gameweld-b26-win32-diagnostic.log"'
```

The new report should contain `observer_reason` and counts if the modified Windows monitor executed properly. On `win32_game_image_path_mismatch`, a single safe `observed_target_image` can show the Windows DOS alias to reconcile, **without automatically changing the acceptance rule**. On `win32_game_basename_not_visible`, investigate whether observer Wine server/process table matches Steam's actual one. On `win32_probe_diagnostic_unavailable`, investigate the Wine loader/cross-build process separately.

The real game remains untouched by a trainer launch; explicit `--probe` does start Wine and may result in incidental prefix bookkeeping writes. No Steam Launch Options modifications. Keep PR draft and production v2 disabled.

**The full source package is separate from GitHub.** The user has uncommitted MIT Batch22/24 adapters staged locally in `/mnt/other/github/GameWeld-PR18-test`; do not overwrite/rebase them or copy AGPL sources into MIT GameWeld without an explicit integration plan.