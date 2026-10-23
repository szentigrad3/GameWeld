#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/publication-audit.py
python3 -m py_compile scripts/gameweld-trainer-updates.py scripts/gameweld-update-monitor.py scripts/gameweld-trainer-library.py scripts/gameweld-stability-preflight.py
# Self-contained, offline tests only. Avoid reaching real providers or running trainers.
for f in \
  scripts/regression-test-0.8.0-dev1-publisher-files.py \
  scripts/regression-test-0.8.0-dev1-ui.py \
  scripts/regression-test-0.7.0-rc6-signed-catalogs.py \
  scripts/regression-test-0.7.0-rc5-staging.py \
  scripts/regression-test-0.7.0-rc9.4-epoch.py; do
  echo "== $f =="
  python3 "$f"
done
echo "== scripts/test-audit-appimage-files.py =="
python3 scripts/test-audit-appimage-files.py
if command -v gcc >/dev/null 2>&1; then
  gcc -fsyntax-only -pthread crates/wand-ui/appimage-gtk3/gameweld-native-040.c
fi
printf 'Offline check suite passed.\n'
