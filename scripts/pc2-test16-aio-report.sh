#!/usr/bin/env bash
# PC2 Test 16 — live Steam Proton/Wand handoff contract, fixtures only.
# Does NOT start Steam, Wand, a real game, or modify compatibility settings.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test16-aio-report.txt"
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
grep -Fq 'Launch Wand in Running Steam Game (opt-in)' \
    "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
grep -Fq 'live-launch' "$ROOT/scripts/gameweld-wemod-enhancer.py"
{
  echo 'GameWeld PC2 Test 16 — Live Steam Proton Wand Handoff AIO'
  echo 'Result: PASS'
  echo 'Source GTK frontend syntax and APIs: PASS'
  echo 'Disposable Steam/Proton process fixture: PASS'
  echo 'Requires actual Windows game process: PASS'
  echo 'Three detected Wand installs with one uniquely patched client: PASS'
  echo 'Two patched clients remain ambiguous and blocked: PASS'
  echo 'Patch/Restore never auto-select among multiple clients: PASS'
  echo 'Rejects ambiguous live prefixes: PASS'
  echo 'Launches fake Proton with exact prefix and version DLL override: PASS'
  echo 'Explicit GUI and CLI confirmation gate: PRESENT'
  echo 'Patch/restore of real Wand client: NOT ATTEMPTED'
  echo 'Real game or Wand launched: false'
  echo 'Real in-game trainer attachment: NOT TESTED'
  echo 'Field check: Open real Astrometica through Steam, select its patched Wand client in GameWeld, then use Launch Wand in Running Steam Game (opt-in).'
} >"$REPORT"
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
