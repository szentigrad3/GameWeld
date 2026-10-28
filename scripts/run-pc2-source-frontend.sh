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
if [[ "${1:-}" == "--enable-deckcheatz-onebutton-test" && "$#" -eq 1 ]]; then
  export GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON=1
  export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1
  printf '%s\n' 'PC2 Steam-managed DeckCheatz experiment: read existing saved launch options automatically, use verified DeckCheatz wrapper through steam -applaunch; first-time Steam wrapper setup may be required.'
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
