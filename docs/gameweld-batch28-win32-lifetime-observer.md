# GameWeld Batch 28 — Windows process creation-time / held-HANDLE sampling

**31 October 2026 · Development only · PR #18 draft**

## Real user evidence carried into Batch 28

Dying Light: The Beast Steam AppID 3008130, Linux PID 185951 and Linux process start ticks 12945298, Proton Experimental. The user-executed Batch27 query-only Rust observer successfully reported `win32_existing_game_handle_correlated` with candidate Win32 PID **312**, verified canonical `S:` Wine DOS drive mapping, `win32_path_correlated=true`, and no game/trainer launches or Steam Launch Options changes. That was Windows full-image-path correlation, **not a verified Linux↔Win32 PID mapping**, authenticated monitor, or working WeMod attachment.

## Batch28 complete source package (not in GitHub branch)

The conversation's `GameWeld-DeckCheatz-Batch28-Complete-Source-DEV.zip` contains full source (248,800 bytes; 124 files; SHA-256 `1ee96e192bd7c4fdc1b78404878ed47dc1af14bcd7e2cc2a332047450a89d218`).

**AGPL-only Rust monitor additions**:
- Explicit, standalone `--probe-existing-game-sampled <full DOS EXE>`, separate from gRPC monitor and trainer queue.
- Pin one query+synchronize Win32 game process HANDLE through 3 samples approximately 350 ms apart. Each checks `GetProcessId`, `GetProcessTimes` creation FILETIME, full `QueryFullProcessImageNameW` and process non-exit.
- Return `win32_existing_game_sampled_handle_correlated` only with stable Win32 PID, **decimal-string** 64-bit creation FILETIME and `samples_completed=3`. No game/trainer spawn or RPC session.

**MIT GameWeld helper additions**:
- Opt-in `--sampled` mode; preserve original read-only `--check` and old explicit `--probe`.
- Verify exact selected Steam game Linux PID/birth and same Proton; canonical `Z:` query with strict `S:` alias fallback as in Batch27. If a Windows HANDLE lifetime report passes, run an **independent second** sampled observer subprocess and require exactly matching Win32 PID + process FILETIME. Linux birth and DOS symlink mappings are verified before/after; session lock retained.
- All observer runs bounded to 15s / 4096 bytes; invalid or trainer-capable-looking JSON fails closed. Success is candidate `win32_existing_game_lifetime_correlated`, not independent Linux↔Windows mapping.
- SHA-bound, dry-run-first `apply-gameweld-pr18-batch28.sh` stages only updated MIT Python helper into the existing user PR test checkout. It preserves the user-staged Batch22/24 files and refuses unexpected edits. Older Batch27 stager uses frozen Batch27 source fixture.

**Validation**: **462/462 Python tests passed** in the source tree and again from fresh ZIP extraction (34 added). Shell syntax, Python compilation, archive CRC, isolated Git tests passed. `GetProcessTimes` Windows-sys 0.61 signature was checked against API docs. **Modified Rust code was NOT compiled or live-tested in the authoring environment.** The user must build it on CachyOS and run the explicit sampled mode. The Batch27 live success cannot be used as a passing result for new Batch28 sampling.

### CachyOS acceptance procedure

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch28-Complete-Source-DEV.zip
cd deckcheatz-batch28-full-integration
bash run-all-tests.sh
bash run-win32-identity-probe.sh --build
# Dying Light already running normally through Steam:
bash run-win32-identity-probe.sh --check
bash -o pipefail -c 'bash run-win32-identity-probe.sh --sampled 2>&1 | tee "$HOME/Downloads/gameweld-b28-live-win32-lifetime.log"'
```

`--check` is read-only. `--sampled` starts ONLY query-only Win32 observer processes inside the current Proton Wine prefix, potentially causing Wine bookkeeping writes. No trainer, game, or Steam setting changes are made by the application. Optional dry-run+apply of `apply-gameweld-pr18-batch28.sh` into the user's local checkout; no GitHub push.

**Security/release boundary**: Even success must retain `win32_pid_verified=false`, `exact_runtime_verified=false`, `monitor_launch_authorized=false`, `monitor_session_authenticated=false`, `trainer_attachment_verified=false`, `trainer_cleanup_verified=false`. Windows process FILETIME is not a Unix PID mapping. Future work: independent cross-runtime identity, authenticated monitor session, real WeMod GUI/trainer functionality and GameWeld-owned normal/crash cleanup. Keep production feature disabled and PR draft.