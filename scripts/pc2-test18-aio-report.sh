#!/usr/bin/env bash
# Test 18: recovered Wand Native 0.1.13/0.1.14 launch contracts.
# The fixtures NEVER start the user's real game, Wand, Wine or Proton.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test18-aio-report.txt"
mkdir -p "$OUT"
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
grep -Fq 'WINE_GRAPHICS_DRIVER' "$ROOT/scripts/gameweld-wemod-enhancer.py"
grep -Fq 'PROTON_USE_X11_EXCLUSIVE' "$ROOT/scripts/gameweld-wemod-enhancer.py"
grep -Fq 'direct active Proton wineserver join + Wand-only X11' \
    "$ROOT/scripts/gameweld-wemod-enhancer.py"
# This older approach remained in Settings as a diagnostic after its
# real-world white-window failure; it is intentionally no longer the default.
grep -Fq 'Launch Wand in Running Steam Game (opt-in)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
{
  echo 'GameWeld PC2 Test 18 — recovered Wand Native Wine/X11 integration'
  echo 'Result: PASS'
  echo 'Original Wand Native 0.1.13 direct existing wineserver join: PRESENT'
  echo 'Original Wand Native 0.1.14 Wand-only X11 graphics driver: PRESENT'
  echo 'Exact game-selected Proton Wine and wineserver paths: PASS (fixtures)'
  echo 'Original game Steam/Proton configuration changed: false'
  echo 'App-specific log and explicit consent: PRESENT'
  echo 'Legacy live X11 attempt is retained for diagnostics, not default: PASS'
  echo 'Actual Wand UI rendered or trainer attached: NOT VERIFIED'
  echo 'Real game/Wand launched by this test: false'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
