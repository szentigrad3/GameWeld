#!/usr/bin/env bash
# Source-only PC2 test runner. Does not install/mutate game compatibility tools.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${GAMEWELD_PC2_OUT:-$ROOT/build/pc2-source}"
for tool in go gcc pkg-config; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
pkg-config --exists gtk+-3.0 || { echo "Missing GTK3 development libraries" >&2; exit 1; }
mkdir -p "$OUT"
(
  cd "$ROOT/cmd/gameweld-backend"
  go test ./...
  go build -trimpath -o "$OUT/wand-native-backend" .
)
gcc -O2 -pipe -pthread \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" \
  -o "$OUT/gameweld" \
  $(pkg-config --cflags --libs gtk+-3.0)
printf '%s\n' 'PC2 development: Steam discovery + read-only HTTP only; setup and mapping return 501.'
printf '%s\n' 'Do not use PC2 dev to install compatibility tools or trainers. PC1 remains stable.'
export WAND_NATIVE_BACKEND="$OUT/wand-native-backend"
export PATH="$ROOT/scripts:${PATH:-/usr/bin:/bin}"
exec "$OUT/gameweld" "$@"
