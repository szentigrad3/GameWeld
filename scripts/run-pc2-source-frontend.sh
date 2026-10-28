#!/usr/bin/env bash
# Source-only PC2 test runner. Does not install/mutate game compatibility tools.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${GAMEWELD_PC2_OUT:-$ROOT/build/pc2-source}"
for tool in go gcc pkg-config; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
pkg-config --exists gtk+-3.0 || { echo "Missing GTK3 development libraries" >&2; exit 1; }
# The legacy GTK frontend resolves its helper paths relative to APPDIR.
# A source checkout has helpers in scripts/, not at the repository root.
# Build a private, unbundled development AppDir with links to those sources.
# This avoids copying inherited PC1 binaries or modifying installed games.
APPDIR_DEV="$OUT/dev-AppDir"
LIBEXEC="$APPDIR_DEV/usr/libexec"
mkdir -p "$LIBEXEC"
for helper in "$ROOT"/scripts/gameweld-*.py "$ROOT"/scripts/gameweld-*.sh \
              "$ROOT"/scripts/gameforge-*.sh "$ROOT"/scripts/wand-*.sh; do
  [[ -f "$helper" ]] || continue
  ln -sfn -- "$helper" "$LIBEXEC/${helper##*/}"
done
for required in gameweld-wand-discovery.py gameweld-wand-compat-audit.py \
                gameweld-wand-native-bridge.py gameweld-managed-wand.py \
                gameweld-trainer-library.py gameweld-wand-patcher.py \
                gameweld-steam-shortcuts.py gameweld-heroic-provider.py \
                gameweld-lutris-provider.py; do
  [[ -f "$LIBEXEC/$required" ]] || { echo "Missing PC2 helper: $required" >&2; exit 1; }
done
export APPDIR="$APPDIR_DEV"
# Steam game-only launch is opt-in for this ONE invocation, never inherited
# accidentally from the shell. The normal source runner stays discovery-only.
unset GAMEWELD_PC2_ENABLE_STEAM_LAUNCH
unset GAMEWELD_PC2_ENABLE_NATIVE_WRAPPER
unset GAMEWELD_PC2_ENABLE_STEAM_WEMOD
unset GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON
unset GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS
unset GAMEWELD_PC2_USE_WAND_V2
unset GAMEWELD_PC2_WEMOD_SOFTWARE_RENDERING
if [[ "${1:-}" == "--enable-deckcheatz-onebutton-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON=1
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  printf '%s\n' 'PC2 Steam-managed DeckCheatz experiment: automatic consented Steam shutdown/restart registers one-shot wrapper with protected backup; no manual Launch Options paste.'
  set --
fi
# One initial in-app consent; no Steam shutdown, no per-game Launch Options
# editing, and no fallback to the legacy one-shot wrapper registration.
if [[ "${1:-}" == "--enable-no-steam-options-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  export GAMEWELD_PC2_ENABLE_STEAM_WEMOD=1
  export GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS=1
  printf '%s\n' 'PC2 NO-STEAM-OPTIONS experiment: normal Steam game launch then consented live-prefix WeMod client handoff. Never restarts Steam or edits its Launch Options. Attachment still needs verification.'
  set --
fi
# Separate diagnostic trial: disable GPU acceleration for the WeMod Electron
# client only. Not a Steam/Game/Proton GPU setting, and no automatic fallback.
if [[ "${1:-}" == "--enable-v2-wemod-gpu-safe-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  export GAMEWELD_PC2_ENABLE_STEAM_WEMOD=1
  export GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS=1
  export GAMEWELD_PC2_USE_WAND_V2=1
  export GAMEWELD_PC2_WEMOD_SOFTWARE_RENDERING=1
  printf '%s\n' 'PC2 Wand v2 GPU-safe test: Electron software rendering for WeMod.exe only. Steam/game graphics and Launch Options unchanged. No duplicate launch or auto fallback.'
  set --
fi
# Explicit v2 development route. Requires an independently installed, user-owned
# v2 source tree. No automatic fallback to the old live helper or Steam wrapper.
if [[ "${1:-}" == "--enable-v2-wemod-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  export GAMEWELD_PC2_ENABLE_STEAM_WEMOD=1
  export GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS=1
  export GAMEWELD_PC2_USE_WAND_V2=1
  printf '%s\n' 'PC2 V2 development mode: Steam owns Launch Options; GameWeld invokes installed Wand v2 separately after exact-game evidence. No silent fallback or prefix overwrite.'
  set --
fi
if [[ "${1:-}" == "--enable-steam-wemod-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  export GAMEWELD_PC2_ENABLE_STEAM_WEMOD=1
  printf '%s\n' 'PC2 STEAM-MANAGED WeMod test: Steam launches game, then optional client-only live attach; no Steam Launch Options or Bridge edits.'
  set --
fi
unset GAMEWELD_NATIVE_WRAPPER_CLI
if [[ "${1:-}" == "--enable-native-wrapper-test" && "$#" -eq 1 ]]; then
  command -v cargo >/dev/null || { echo "Rust cargo is required for native wrapper test mode." >&2; exit 1; }
  ( cd "$ROOT" && cargo build -p wand-runtime --bin gameweld-native-wrapper )
  export GAMEWELD_PC2_ENABLE_NATIVE_WRAPPER=1
  export GAMEWELD_NATIVE_WRAPPER_CLI="$ROOT/target/debug/gameweld-native-wrapper"
  printf '%s\n' 'PC2 experimental direct Rust wrapper enabled. Steam options unchanged; consent required for launch.'
  set --
fi
if [[ "${1:-}" == "--enable-steam-game-launch" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  printf '%s\n' 'PC2 explicit Steam GAME-ONLY launch gate enabled (still requires per-game confirmation).'
  set --
fi
if [[ "${1:-}" == "--check-layout" && "$#" -eq 1 ]]; then
  printf 'PC2 source helper layout verified: %s\n' "$LIBEXEC"
  exit 0
fi
(
  cd "$ROOT/cmd/gameweld-backend"
  go test ./...
  go build -trimpath -o "$OUT/wand-native-backend" .
)
gcc -O2 -pipe -pthread -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" \
  -o "$OUT/gameweld" \
  $(pkg-config --cflags --libs gtk+-3.0)
printf '%s\n' 'PC2 development: Steam discovery + read-only HTTP only; setup and mapping return 501.'
printf '%s\n' 'Do not use PC2 dev to install compatibility tools or trainers. PC1 remains stable.'
export WAND_NATIVE_BACKEND="$OUT/wand-native-backend"
export PATH="$ROOT/scripts:${PATH:-/usr/bin:/bin}"
exec "$OUT/gameweld" "$@"
