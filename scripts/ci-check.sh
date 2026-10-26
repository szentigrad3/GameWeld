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
for f in scripts/regression-test-0.7.0-rc6-signed-catalogs.py scripts/regression-test-0.7.0-rc5-staging.py scripts/regression-test-0.7.0-rc9.4-epoch.py scripts/regression-test-0.7.0-stable.py scripts/regression-test-0.7.0-pc1-distribution.py; do
  echo "== $f =="
  python3 "$f"
done
echo "== PC1 AppDir packaging audit fixtures =="
python3 scripts/test-audit-appimage-files.py
if command -v gcc >/dev/null 2>&1; then
 gcc -fsyntax-only -pthread crates/wand-ui/appimage-gtk3/gameweld-native-040.c
fi
