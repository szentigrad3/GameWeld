#!/usr/bin/env bash
# Test 17: disposable fixture checks + GTK syntax. Does not launch a real game or Wand.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
mkdir -p "$OUT"
REPORT="$OUT/pc2-test17-aio-report.txt"
command -v python3 >/dev/null
command -v gcc >/dev/null
command -v pkg-config >/dev/null
pkg-config --exists gtk+-3.0
python3 -m py_compile "$ROOT/scripts/gameweld-wemod-enhancer.py"
python3 -m unittest discover -s "$ROOT/scripts" -p 'test_gameweld_wemod_enhancer.py' -v
bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
gcc -fsyntax-only -Werror=implicit-function-declaration -pthread \
    -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
    $(pkg-config --cflags gtk+-3.0) \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq '"live-render"' "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
! grep -Fq 'GtkWidget*live_render=button(' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'wand-live-' "$ROOT/scripts/gameweld-wemod-enhancer.py"
{
  echo 'GameWeld PC2 Test 17 — White Wand Window Recovery'
  echo 'Result: PASS'
  echo 'GTK source syntax and declared APIs: PASS'
  echo 'Wand helper unit tests (including software-render launch): PASS'
  echo 'Legacy CLI software-render confirmation preserved; obsolete GUI retry removed: PASS'
  echo 'Same live Proton runtime and prefix preserved: PASS (fixtures only)'
  echo 'Chromium --disable-gpu and --disable-gpu-compositing sent: PASS (fixtures only)'
  echo 'Steam game launch options modified: false'
  echo 'Real game or Wand started by test: false'
  echo 'Wand renderer visible / login / trainer attached: NOT VERIFIED'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
