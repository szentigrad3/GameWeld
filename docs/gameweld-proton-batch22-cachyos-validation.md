# GameWeld/DeckCheatz Batch 22 — CachyOS native validation and Windows observer smoke gate

**31 October 2026 · development only · PR #18 draft · no working WeMod trainer attachment claimed.**

## New user-provided acceptance evidence

On CachyOS, the user extracted the complete Batch 21 source package and ran `bash run-all-tests.sh`. It reported:

- **289/289 Python tests passed**.
- **14/14 Rust native tests passed**, compiling and running `deckcheatz-trainer-monitor-v2` on Linux.
- The guarded installer was invoked first in dry-run mode and then with `--apply`, staging the three MIT GameWeld modules `gameweld-wand-v2-driver.py`, `gameweld-wand-v2-runtime-plan.py` and `gameweld-wand-v2-configure.py` into the **local** PR #18 test worktree.
- No Git commit/push was performed, no Steam Launch Options were changed, and no game-prefix files were modified during staging.

This **does not establish** Windows target compilation, the disposable Wine `ObserveExisting` test, WeMod GUI/login, trainer attachment, or trainer shutdown in the actual Steam game. The `wine_runner_missing`/MinGW/monitor-release JSON visible during the Python suite was a synthetic test fixture, not proven system prerequisite status.

## Batch 22 source package, separate from the GitHub PR

The full-source development ZIP created in the conversation is named `GameWeld-DeckCheatz-Batch22-Complete-Source-DEV.zip`. The full source **has not yet been pushed to GitHub**.

1. Updated the MIT GameWeld driver `find_unique_game` to require the real Wine game-process `comm` name **even when there is only one matching runtime candidate**. A full-path Steam wrapper alone is never accepted as the game PID.
2. Added two negative process-selection tests.
3. Added `run-windows-observer-aio.sh` with read-only `--check`, Windows GNU monitor `--build` and disposable prefix `--smoke`. It never installs packages, modifies Steam Launch Options or launches the real Steam game.
4. Added four regression checks for the Windows smoke runner, bringing the complete Python source package to **295/295 passing tests**. Source ZIP CRC test, fresh-extraction rerun, Python compilation and shell syntax passed.
5. Added `apply-gameweld-pr18-batch22.sh`: a dry-run-first staging helper that accepts only the user's expected PR #18 branch and exactly the Batch 21 MIT file hashes. It modifies only the MIT driver and refuses unrelated local modifications. Tested against an isolated Git checkout, including successful staging and refusal of unrelated changes.

The separate AGPL Windows Rust observer and upstream DeckCheatz Python client were not modified. User-tested 14 native Rust tests are **not** evidence that the Windows target compiled.

## CachyOS next action: Windows observer first, not actual WeMod

Extract the complete Batch 22 ZIP into `~/Downloads`:

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch22-Complete-Source-DEV.zip
cd deckcheatz-batch22-full-integration
bash run-all-tests.sh
bash run-windows-observer-aio.sh --check
```

When the prerequisites are installed, build the standalone Windows observer and run the fixture-based smoke:

```bash
bash run-windows-observer-aio.sh --build
bash run-windows-observer-aio.sh --smoke |& tee "$HOME/Downloads/gameweld-win32-observer-smoke.log"
```

The Windows smoke runs harmless fixtures in an **isolated temporary Wine prefix**. It does not touch Steam or the Dying Light prefix. The user will need a Windows GNU Rust target, MinGW-w64 compiler, Wine/wineboot, and a local venv with grpcio/grpcio-tools. The `--check` JSON identifies missing requirements; no automatic installation.

## Update the user's already staged PR worktree (MIT files only)

```bash
cd ~/Downloads/deckcheatz-batch22-full-integration
bash apply-gameweld-pr18-batch22.sh /mnt/other/github/GameWeld-PR18-test
bash apply-gameweld-pr18-batch22.sh /mnt/other/github/GameWeld-PR18-test --apply
```

After reviewing/testing, the user can `git add` only the three MIT modules, commit and push their existing feature branch. PR #18's remote tests do **not** cover the complete Batch 22 source until these modules are pushed.

## Release gate remains closed

Win32 process handle and exact same Wine runtime must be confirmed on the actual live Steam game; WeMod GUI/attachment must be observed; trainer-owned process cleanup must be independently verified without terminating Steam, the game, the wineserver or unrelated processes. Keep PR #18 in draft, experimental GameWeld v2 GTK integration disabled, and never require manual Steam Launch Options changes.
