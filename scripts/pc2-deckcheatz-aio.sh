#!/usr/bin/env bash
# Complete OFFLINE DeckCheatz PC2 validation: no game start, no download,
# no real updater execution, no Wine prefix edits, no Steam config mutation.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/build/pc2-source"
mkdir -p "$OUT"
REPORT="$OUT/deckcheatz-aio-report.txt"

{
  printf '%s\n' 'GAMEWELD PC2 / DECKCHEATZ AIO'
  printf '%s\n' 'Scope: isolated offline installer/update fixtures, read-only Proton/launch preview, GTK syntax'
  printf '%s\n' 'Actual upstream downloads: NO'
  printf '%s\n' 'Real game / WeMod launched: NO'
  printf '%s\n' 'Real Steam Launch Options / Wine prefixes changed: NO'
  echo
  printf '%s\n' '=== Python source compilation ==='
  python3 -m py_compile scripts/gameweld-deckcheatz-direct.py \
      scripts/gameweld-deckcheatz-proton.py \
      scripts/gameweld-deckcheatz-install.py \
      scripts/gameweld-steam-game-exe.py
  printf '%s\n' '=== Automatic Steam game EXE resolution (no file picker) ==='
  python3 -m unittest scripts/test_gameweld_steam_game_exe.py -v
  printf '%s\n' '=== Steam game-process identity fixture tests ==='
  python3 -m unittest scripts/test_gameweld_platform_session.py -v
  printf '%s\n' '=== Steam-owned game then same-prefix WeMod offline fixtures ==='
  python3 -m unittest scripts/test_gameweld_steam_wemod_platform.py -v
  printf '%s\n' '=== Read-only WeMod/Electron client version metadata audit ==='
  python3 -m unittest scripts/test_gameweld_wemod_client_audit.py -v
  printf '%s\n' '=== Steam Proton .NET 4.8 readiness (offline registry fixtures) ==='
  python3 -m unittest scripts/test_gameweld_wemod_prefix_readiness.py -v
  printf '%s\n' '=== Read-only Steam vs WeMod runtime context comparison ==='
  python3 -m unittest scripts/test_gameweld_steam_wemod_runtime_audit.py -v
  printf '%s\n' '=== Managed install/update/adoption synthetic cases ==='
  python3 scripts/test_gameweld_deckcheatz_install.py -v
  printf '%s\n' '=== Per-game Proton resolution synthetic cases ==='
  python3 scripts/test_gameweld_deckcheatz_proton.py -v
  printf '%s\n' '=== Launch preview and consent synthetic cases ==='
  python3 scripts/test_gameweld_deckcheatz_direct.py -v
  printf '%s\n' '=== Game-first GUI layout + launch safeguards ==='
  python3 scripts/test_gameweld_deckcheatz_gui_layout.py -v
  printf '%s\n' '=== Native C monitor sizing across 8 resolutions ==='
  gcc -std=c11 -Wall -Wextra -Werror \
      scripts/test-pc2-window-policy.c -o "$OUT/pc2-window-policy-test"
  "$OUT/pc2-window-policy-test"
  printf '%s\n' '=== Native C window-state save / close / reopen roundtrip ==='
  gcc -std=gnu11 -Wall -Wextra -Werror \
      scripts/test-pc2-window-state.c -o "$OUT/pc2-window-state-test"
  "$OUT/pc2-window-state-test"
  printf '%s\n' '=== GTK GUI source syntax ==='
  if pkg-config --exists gtk+-3.0 && command -v gcc >/dev/null; then
      gcc -fsyntax-only -pthread -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
          crates/wand-ui/appimage-gtk3/gameweld-native-040.c \
          $(pkg-config --cflags gtk+-3.0)
  else
      printf '%s\n' 'FAIL: gcc and GTK3 development headers are needed for a complete GUI check'
      exit 3
  fi
  printf '%s\n' '=== Existing checkout status (read-only) ==='
  python3 scripts/gameweld-deckcheatz-install.py --status
  echo
  printf '%s\n' 'Result: PASS (OFFLINE FIXTURES + GUI SYNTAX ONLY)'
} 2>&1 | tee "$REPORT"
echo "Report: $REPORT"
