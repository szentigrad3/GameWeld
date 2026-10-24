#!/usr/bin/env bash
# Test 20: self-contained GameWeld managed one-Proton-session source checks.
# Synthetic files/processes only; the real game, Wand and Proton are NEVER run.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test20-aio-report.txt"
mkdir -p "$OUT"
command -v python3 >/dev/null
command -v gcc >/dev/null
command -v pkg-config >/dev/null
pkg-config --exists gtk+-3.0
python3 -m py_compile \
    "$ROOT/scripts/gameweld-managed-wand.py" \
    "$ROOT/scripts/gameweld-wand-native-bridge.py" \
    "$ROOT/scripts/test_gameweld_wand_native_bridge.py" \
    "$ROOT/scripts/pc2-wand-crypt32-recovery-audit.py" \
    "$ROOT/scripts/test_pc2_wand_crypt32_recovery_audit.py"
python3 -m unittest discover -s "$ROOT/scripts" \
    -p 'test_gameweld_wand_native_bridge.py' -v
python3 -m unittest discover -s "$ROOT/scripts" \
    -p 'test_pc2_wand_crypt32_recovery_audit.py' -v
bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
test -L "$OUT/dev-AppDir/usr/libexec/gameweld-managed-wand.py"
gcc -fsyntax-only -Werror=implicit-function-declaration -pthread \
    -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
    $(pkg-config --cflags gtk+-3.0) \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'Check GameWeld Managed Wand (read-only)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'Play Game + Wand (managed Proton, opt-in)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'waitforexitandrun' "$ROOT/scripts/gameweld-managed-wand.py"
{
  echo 'GameWeld PC2 Test 20 — Integrated single Proton Wand + game session'
  echo 'Result: PASS'
  echo 'No separate Wand Native 0.1.41 CLI or daemon dependency: PASS'
  echo 'Native Steam game identity and executable validation: PASS (fixture)'
  echo 'GE Proton Wand SHA256 crypt32 release hash guard: PASS (synthetic fixture)'
  echo 'Test fixtures isolated from host Steam and /mnt/games installations: PASS'
  echo 'Read-only historical crypt32 archive / DLL recovery audit: PASS (synthetic fixtures)'
  echo 'Original one-Proton-session batch architecture: PASS (fixture)'
  echo 'Managed game process exclusivity guard: PASS (fixture)'
  echo 'Explicit opt-in and GTK source compilation: PASS'
  echo 'No unverified compatibility binary downloads or overwrites: PASS'
  echo 'Real game / Wand / Proton started by AIO: false'
  echo 'Real installed GE Proton Wand SHA256 availability: NOT TESTED'
  echo 'Actual white-window recovery and trainer attachment: NOT VERIFIED'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
