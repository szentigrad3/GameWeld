#!/usr/bin/env bash
# Fast, source-only GameWeld PC2 checks. No GTK apt installs, Go build, network,
# game launches, Wine/Proton execution, or writes to installed prefixes.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
start=$SECONDS
export PYTHONDONTWRITEBYTECODE=1
echo "GameWeld PC2 — FAST offline feedback (NOT a release qualification)"
bash -n scripts/pc2-cachyos-gtk-crash.sh
echo "Crash-diagnostic helper syntax: PASS"
python3 -m py_compile \
  scripts/gameweld-wemod-native-route.py \
  scripts/gameweld-wemod-live-attach.py \
  scripts/gameweld-prepared-prefix-import.py \
  scripts/gameweld-prepared-prefix-activate.py \
  scripts/gameweld-prefix-runtime-preflight.py \
  scripts/gameweld-deckcheatz-prefix-catalog.py \
  scripts/gameweld-prepared-prefix-audit.py \
  scripts/gameweld-prepared-prefix-cache.py \
  scripts/gameweld-rejected-zip-integrity.py \
  scripts/gameweld-prepared-prefix-case-preflight.py \
  scripts/gameweld-remote-zip-directory.py \
  scripts/gameweld-prepared-prefix-stage.py \
  scripts/gameweld-prefix-backup.py \
  scripts/gameweld-prefix-restore-rehearsal.py \
  scripts/gameweld-transaction-rehearsal.py

# The same PC2 safety suites used by full CI, without GTK/Ubuntu
# dependency installation or private binary packaging.
suites=(
  test_gameweld_steam_compat_bridge.py
  test_gameweld_deckcheatz_prefix_catalog.py
  test_gameweld_prepared_prefix_audit.py
  test_gameweld_prepared_prefix_cache.py
  test_gameweld_rejected_zip_integrity.py
  test_gameweld_prepared_prefix_case_preflight.py
  test_gameweld_remote_zip_directory.py
  test_gameweld_prepared_prefix_stage.py
  test_gameweld_prefix_backup.py
  test_gameweld_prefix_restore_rehearsal.py
  test_gameweld_transaction_rehearsal.py
  test_gameweld_prefix_runtime_preflight.py
  test_gameweld_wemod_native_route.py
  test_gameweld_wemod_live_attach.py
  test_gameweld_prepared_prefix_import.py
  test_gameweld_prepared_prefix_activate.py
)
for suite in "${suites[@]}"; do
  echo "== $suite =="
  timeout --signal=TERM --kill-after=5s 30s python3 -m unittest discover -s scripts -p "$suite" -q
done
echo "PASS: ${#suites[@]} PC2 safety suites in $((SECONDS-start))s."
echo "NOT TESTED HERE: native GTK build, Ubuntu AppDir audit, live Steam/Heroic/Lutris integration, real WeMod trainer."
