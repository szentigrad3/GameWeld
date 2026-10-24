#!/usr/bin/env bash
# Test 19: Read-only fixtures for recovery of the verified Wand Native 0.1.41
# managed one-Proton-session architecture. Never launches the real game or Wand.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test19-aio-report.txt"
mkdir -p "$OUT"
command -v python3 >/dev/null
command -v gcc >/dev/null
command -v pkg-config >/dev/null
pkg-config --exists gtk+-3.0
python3 -m py_compile "$ROOT/scripts/gameweld-wand-native-bridge.py" \
    "$ROOT/scripts/test_gameweld_wand_native_bridge.py"
python3 -m unittest discover -s "$ROOT/scripts" \
    -p 'test_gameweld_wand_native_bridge.py' -v
bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
gcc -fsyntax-only -Werror=implicit-function-declaration -pthread \
    -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
    $(pkg-config --cflags gtk+-3.0) \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'Play with Wand Native 0.1.41 (opt-in)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'Check Wand Native 0.1.41 (read-only)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
{
 echo 'GameWeld PC2 Test 19 — Proven Wand Native 0.1.41 managed-session bridge'
 echo 'Result: PASS'
 echo 'Old Wand Native version and daemon readiness guard: PASS (fixture)'
 echo 'Isolated GE Proton Wand SHA256 and DWriteCore guards: PASS (fixture)'
 echo 'Already-running game blocks second session: PASS (fixture)'
 echo 'Explicit confirmation required before game + Wand request: PASS (fixture)'
 echo 'GTK frontend compiles with managed-session actions: PASS'
 echo 'PC1 and Steam launch options modified: false'
 echo 'Real game / Wand / Wine / Proton started by AIO: false'
 echo 'Real Wand Native 0.1.41 installed on user machine: NOT TESTED'
 echo 'Actual Wand renderer and trainer attachment: NOT VERIFIED'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
