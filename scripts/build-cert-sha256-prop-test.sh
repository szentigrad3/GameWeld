#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CC="${MINGW_CC:-x86_64-w64-mingw32-gcc}"
OUT="${1:-$ROOT/tools/cert-sha256-prop.exe}"
command -v "$CC" >/dev/null 2>&1 || {
  echo "$CC not found. On Arch/CachyOS install the mingw-w64-gcc package, then rerun." >&2
  exit 2
}
"$CC" -O2 -Wall -Wextra -municode \
  -o "$OUT" "$ROOT/tools/cert-sha256-prop.c" \
  -lwintrust -lcrypt32
printf '%s\n' "$OUT"
