# GameWeld / DeckCheatz Batch 23 — Unblock disposable Wine observer smoke

**31 October 2026 · Development only · PR #18 remains draft**

## Real CachyOS evidence received

The user reported:

- `--check`: `windows_observer_build_prerequisites_ready`
- `--build`: `windows_monitor_compiled_not_tested`
- Batch 22 staging into the local PR worktree: **26/26 tests passed**, exactly the MIT v2 driver updated; planner/config helper retained.
- `--smoke`: blocked **solely by `grpc_venv_missing`**.
- No Steam settings or game prefixes changed. This was not a Windows observer execution failure.

## Short path with the already-extracted Batch 22 source

The source uses `.venv/bin/python` in the *extracted DeckCheatz root*. Its `upstream-overlay/requirements-rpc.txt` specifies bounded `grpcio`, `grpcio-tools` and `protobuf` dependencies. The user can provision only that isolated environment without any system packages or Steam configuration changes:

```bash
cd ~/Downloads/deckcheatz-batch22-full-integration
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r upstream-overlay/requirements-rpc.txt
.venv/bin/python -c 'import grpc, grpc_tools, google.protobuf; print("gRPC venv ready")'
bash run-windows-observer-aio.sh --smoke |& tee "$HOME/Downloads/gameweld-win32-observer-smoke.log"
```

No need to repeat `--build` unless the Windows monitor changed; Batch 22 `--smoke` compiles the target itself.

## Batch 23 convenience: complete source archive separate from GitHub

Produced `GameWeld-DeckCheatz-Batch23-Complete-Source-DEV.zip`, SHA256 `fb93ee8738b62818d04fb81109652f43d6a45be0c78fc3520421c0372a3a2076`. It includes all existing Batch 22 source, scripts and tests, with only the AGPL smoke AIO changed and 10 hermetic tests added.

- `--prepare-venv` creates the **local** `.venv` only on explicit opt-in and installs `upstream-overlay/requirements-rpc.txt` with its own pip, never system pip or sudo. Refuses symlinked/foreign-owned/incomplete environment paths.
- `--check-smoke` reads all smoke prerequisites (cargo/Rust Windows target, MinGW, Wine/wineboot, local gRPC environment) without executing monitor, Wine or Steam.
- Existing `--check`, `--build` and `--smoke` modes remain available.

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch23-Complete-Source-DEV.zip
cd deckcheatz-batch23-full-integration
bash run-all-tests.sh
bash run-windows-observer-aio.sh --prepare-venv
bash run-windows-observer-aio.sh --check-smoke
bash run-windows-observer-aio.sh --smoke |& tee "$HOME/Downloads/gameweld-win32-observer-smoke-b23.log"
```

**Verification in authoring container:** 305/305 Python tests passed in the source directory and again after clean ZIP extraction; Python syntax and ZIP integrity passed. Rust/Cargo and Windows/Wine tools were not installed in this environment, so no new native Rust/Win32/Wine smoke result is claimed. The user previously verified native Rust and Windows cross-compilation on CachyOS.

## Repository and licence boundaries

Batch 23 changes **only the separate AGPL-3.0-only source AIO, tests and README**; no MIT GameWeld adapters changed relative to Batch22. No staging or GitHub push is necessary for Batch23 itself. The user's three complete Batch21/22 MIT adapter changes remain *locally staged*, not yet committed to PR #18; do not overwrite or reset those automatically.

A passing disposable Wine `ObserveExisting` test establishes Windows observer behaviour only on harmless fixtures. It does **not** validate actual WeMod startup, UI/login, game trainer attachment or ownership-scoped cleanup on Dying Light. Keep production GTK experimental v2 disabled; never require manual Steam Launch Options edits.

**Next acceptance signal:** complete `--smoke` JSON, ideally `windows_wine_observer_smoke_passed`, or its exact error/trace. Then the next batch can address concrete runtime integration rather than hypothesizing the Windows observer status.
