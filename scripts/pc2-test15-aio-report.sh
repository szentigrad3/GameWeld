#!/usr/bin/env bash
# Test 15 — Checked Steam launcher contract only. NEVER launches a real game.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test15-aio-report.txt"
APPID="2353250"
if [[ $# -gt 1 ]]; then
  echo 'Usage: pc2-test15-aio-report.sh [Steam app ID]' >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then APPID="$1"; fi
mkdir -p "$OUT"
python3 -m unittest discover -s "$ROOT/scripts" -p test_gameweld_steam_handoff.py -v
bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
test -L "$OUT/dev-AppDir/usr/libexec/gameweld-steam-handoff.py"
# Test 15 must also compile the actual source GTK UI: a helper-only PASS is
# misleading when GameWeld cannot start. Never execute the UI in this AIO.
command -v gcc >/dev/null
command -v pkg-config >/dev/null
pkg-config --exists gtk+-3.0
gcc -fsyntax-only -Werror=implicit-function-declaration -pthread \
  -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
  $(pkg-config --cflags gtk+-3.0) \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
# Run only the explicitly read-only status command.
STATUS="$OUT/pc2-test15-steam-status.txt"
python3 "$ROOT/scripts/gameweld-steam-handoff.py" status --appid "$APPID" >"$STATUS"
grep -Fq 'No Steam command or trainer was launched.' "$STATUS"
{
  echo 'GameWeld PC2 Test 15 — Checked Steam Handoff AIO'
  echo 'Result: PASS'
  echo "Target Steam app ID: $APPID"
  echo 'Source GUI checked Steam handoff helper: PRESENT'
  echo 'Source GTK frontend compile: PASS (syntax and declared GTK APIs)'
  echo 'Fake Steam nonzero-exit recognition: PASS'
  echo 'Fake Steam missing-executable recognition: PASS'
  echo 'Fake Steam zero-exit launch remains unconfirmed: PASS'
  echo 'Read-only same-user app-ID process observation fixture: PASS'
  echo 'Steam command launched by this diagnostic: false'
  echo 'Trainer/Proton configuration modified: false'
  echo 'Real Astrometica game startup: NOT TESTED'
  cat "$STATUS"
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
