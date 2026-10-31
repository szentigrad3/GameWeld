# GameWeld / DeckCheatz — Batch 24: live identity AIO and bounded bridge

Development-only source package created on 31 October 2026. **PR #18 remains draft**; no production WeMod integration is claimed.

## Grounded prerequisite progress

On CachyOS, user verified the Windows GNU monitor compiled; the isolated gRPC environment and disposable-Wine smoke prerequisites passed; and the **harmless Win32 fixture** returned `windows_wine_observer_smoke_passed`, fixture PID 516, game exit 0, monitor exit and verified cleanup of the *owned trainer fixture*. No real Dying Light Win32 PID or WeMod attachment was thereby verified.

The user also staged the three complete MIT Batch22 GameWeld adapters **locally** in `/mnt/other/github/GameWeld-PR18-test`. These source files remain uncommitted/unpushed from that local checkout.

## Batch 24 complete development archive

The conversation's `GameWeld-DeckCheatz-Batch24-Complete-Source-DEV.zip` is a complete source successor to Batch23, including the unchanged separate AGPL Windows Rust monitor and Python RPC client.

Changes in MIT GameWeld code:

- **Strict read-only live AIO:** `gameweld-wand-v2-live-aio.py`, using existing private schema-1 GameWeld settings. Validates exact installed game and selected Proton runtime, samples the current Wine Linux PID and kernel process-birth token three times by default, and rejects wrong game App ID, unsafe config permissions, missing executable, ambiguous/missing game process, wrong Proton runtime, changed PID or PID reuse. Safe report never claims a verified Win32 PID or attached WeMod.
- **Bounded bridge:** `gameweld-wand-v2-bounded-bridge.py`, used by the complete Batch22 controller for the default bridge subprocess path. Replaces an unbounded up-to-24-hour `subprocess.run(capture_output=True)` with a 128 KiB output limit, strict UTF-8, bounded timeout and direct-child-only termination; no shell, secrets or Steam processes are signalled.
- **Private session-lock hardening:** Full controller validates mode/ownership of runtime directory and file, `O_NOFOLLOW` and inode correlation; never unlinks stale locks. Still respects different App IDs.
- **Guarded staging:** `apply-gameweld-pr18-batch24.sh` is dry-run by default, allows only the exact existing user-staged Batch22 MIT driver + planner + config-helper SHA values, refuses unknown files and edits, then stages only three MIT files: replacement driver and new live-aio/bounded-bridge helpers. No Git commit or push, no Steam/prefix writes.

## Tests

- Full **361/361 Python tests passed** in source tree and again after clean extraction of the ZIP.
- New 56 tests: 22 live-AIO checks, 12 bounded-bridge subprocess tests, 4 driver/default-bridge wiring tests, 11 private-lock checks and 7 guarded staging tests.
- Python compilation, archive CRC and shell syntax checks passed.
- Windows Rust observer's two source files were SHA-identical to Batch23; it was **not rebuilt or live-tested** again in this authoring container.

## CachyOS: safe next step

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch24-Complete-Source-DEV.zip
cd deckcheatz-batch24-full-integration
bash run-all-tests.sh
bash apply-gameweld-pr18-batch24.sh /mnt/other/github/GameWeld-PR18-test
bash apply-gameweld-pr18-batch24.sh /mnt/other/github/GameWeld-PR18-test --apply
```

Then in the test checkout:

```bash
cd /mnt/other/github/GameWeld-PR18-test
python3 scripts/gameweld-wand-v2-live-aio.py --appid 3008130 --config-only

# With Dying Light running normally through Steam:
python3 scripts/gameweld-wand-v2-live-aio.py --appid 3008130 |
  tee "$HOME/Downloads/gameweld-b24-live-audit-3008130.json"
```

If the private schema-1 config has not been created, this *read-only* audit reports `private_gameweld_v2_config_missing_or_unsafe`; inspect `python3 scripts/gameweld-wand-v2-configure.py --help` and configure only exact verified paths. The settings helper writes only private GameWeld XDG config when `--write` is explicitly supplied, never Steam.

A passing outcome `gameweld_v2_linux_runtime_audit_stable` proves repeated Linux-side correlation. It **does not authorize** Win32 monitor attachment or a trainer.

## Blockers

Exact authenticated live Dying Light Windows PID, verified same Steam-managed Proton wineserver, real WeMod interface/login/trainer attachment, ownership-scoped normal/crash cleanup, native GTK acceptance. No Steam Launch Options edits or automatic feature enablement. **PR #18 is not ready to merge.**

The three Batch24 MIT updates are presently in the development ZIP; they have **not** yet been pushed to GitHub PR #18, preserving the user's intentionally modified local checkout.
