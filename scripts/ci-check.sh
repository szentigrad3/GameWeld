#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/publication-audit.py
python3 -m py_compile scripts/gameweld-trainer-updates.py scripts/gameweld-update-monitor.py scripts/gameweld-trainer-library.py scripts/gameweld-stability-preflight.py
echo "== Steam Bridge offline regression tests =="
python3 -m unittest discover -s scripts -p 'test_gameweld_steam_compat_bridge.py' -v
echo "== Prepared WeMod prefix catalog offline regression tests =="
python3 -m unittest discover -s scripts -p 'test_gameweld_deckcheatz_prefix_catalog.py' -v
echo "== Shared WeMod prepared prefix archive safety checks =="
python3 -m unittest discover -s scripts -p 'test_gameweld_prepared_prefix_audit.py' -v
echo "== Explicit-opt-in WeMod prefix cache-only download security tests =="
python3 -m unittest discover -s scripts -p 'test_gameweld_prepared_prefix_cache.py' -v
echo "== Isolated prepared WeMod archive staging and no-game-write regression =="
python3 -m unittest discover -s scripts -p 'test_gameweld_prepared_prefix_stage.py' -v
echo "== Independent per-game prefix backup dry-run and safe-snapshot regression =="
python3 -m unittest discover -s scripts -p 'test_gameweld_prefix_backup.py' -v
echo "== Isolated prefix restore rehearsal and adversarial rollback fixture tests =="
python3 -m unittest discover -s scripts -p 'test_gameweld_prefix_restore_rehearsal.py' -v
echo "== Provider-native WeMod route / no mandatory Steam Bridge =="
python3 -m unittest discover -s scripts -p 'test_gameweld_wemod_native_route.py' -v
for f in scripts/regression-test-0.7.0-rc6-signed-catalogs.py scripts/regression-test-0.7.0-rc5-staging.py scripts/regression-test-0.7.0-rc9.4-epoch.py scripts/regression-test-0.7.0-stable.py scripts/regression-test-0.7.0-pc1-distribution.py; do
  echo "== $f =="
  python3 "$f"
done
echo "== PC1 AppDir packaging audit fixtures =="
python3 scripts/test-audit-appimage-files.py
if command -v gcc >/dev/null 2>&1; then
 gcc -fsyntax-only -pthread crates/wand-ui/appimage-gtk3/gameweld-native-040.c
fi
