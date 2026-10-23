#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:?Usage: ./MAKE-APPIMAGE.sh /path/to/GameWeld-0.7.0-rc11-x86_64.AppImage [output.AppImage]}"
OUT="${2:-$ROOT/GameWeld-0.7.0-x86_64.AppImage}"
exec "$ROOT/scripts/build-gameweld-0.7.0-appimage.sh" "$BASE" "$OUT"
