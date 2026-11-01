# Batch43 CachyOS acceptance test: false-negative on a properly configured host, fixed in test-only hotfix

On 2026-11-01, user applied `apply-batch43-to-batch42.sh --check` (PASS) and `--apply` (PASS) to their existing Batch42 directory with compiled Windows monitor. Running `bash run-all-tests.sh` yielded **798 Python tests, 1 failure**:

```text
test_batch29_auth_only.PolicyTests.test_check_does_not_launch_monitor_with_missing_config
AssertionError: 0 != 2
```

This was **not** a production GameWeld regression or proof that the Batch43 provenance patch failed. The legacy test invoked the `auth-only-aio.py --check` subprocess with **no explicit `--config`** and incorrectly assumed the user's global GameWeld configuration or compiled observer was absent. On this genuinely configured machine, a successful exit code **0** was legitimate. A negative test must never rely on host setup.

### Minimal test-only correction

The replacement `tests/test_batch29_auth_only.py` runs `--check --config <fresh temporary directory>/missing-gameweld-config.json` and asserts the JSON's `gameweld_v2_auth_only_blocked` state, `identity_only_preflight_blocked` reason, exit code 2 and all key no-launch/no-Steam-change flags. It creates no configuration file. **Only this test file changes**; the upgraded MIT provenance scanner, compiled Windows monitor, `.venv`, real config and all runtime files remain unchanged.

A guarded helper `apply-b43-host-test-fix.sh` accepts exact Batch42/43 test SHA-256 `59c10d41856ea03bdbf25fae0de6e279d300520c17af1e47bc78d3429f3f4441`, writes only patched SHA `6c53ab5c75ab6eec5c6e1c41f79145774411cbbb1f538a09fa8c9cf2b2152a7a`, refuses edited tests/symlinks and supports `--check`, `--apply` and safe repeat apply.

**User-facing hotfix artifact:** `GameWeld-Batch43-Host-Test-Fix.zip`, SHA-256 `c75efdeadfca624dcbedf787556a24fef376917d70c9a9883f0a3669b896e704`. ZIP includes README, guarded installer and one corrected test. **This source artifact is delivered in conversation, not pushed to GitHub.** Downloadable verification report `GameWeld-Batch43-Host-Test-Fix-Verification.md`.

### Independent verification

- Extract pristine Batch42 full ZIP, apply existing Batch43 provenance update, then hotfix helper check/apply/apply again: **all PASS**.
- Batch29 tests: **13/13 PASS**.
- Exact updated Batch42 full suite: **798/798 Python tests PASS**, `bash run-all-tests.sh` exit 0; Python compile + Bash syntax PASS.
- Changed test file refusal PASS; hotfix ZIP CRC/clean extract PASS.
- Rust/Cargo unavailable: Rust tests SKIPPED; live Proton/WeMod GUI not exercised here.

The actual postspawn wineserver recheck and separate Electron GPU `error_code=43` remain live blockers. **Do not** claim successful GUI, game recognition, trainer attachment or entire Wine child cleanup. PR remains **DRAFT**, no Steam Launch Options changes.