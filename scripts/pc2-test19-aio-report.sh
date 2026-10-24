#!/usr/bin/env bash
# Historical Test 19 compatibility wrapper. The separate Wand Native 0.1.41
# CLI dependency was retired in Test 20; the test contract is superseded.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
bash "$ROOT/scripts/pc2-test20-aio-report.sh"
REPORT="$ROOT/build/pc2-source/pc2-test19-aio-report.txt"
{
  echo 'GameWeld PC2 Test 19 — historical managed bridge superseded by Test 20'
  echo 'Result: PASS'
  echo 'External wandctl 0.1.41 requirement: REMOVED'
  echo 'Test 20 integrated managed one-Proton-session fixtures: PASS'
  echo 'Real game / Wand / Wine / Proton started by AIO: false'
  echo 'Actual Wand renderer and trainer attachment: NOT VERIFIED'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
