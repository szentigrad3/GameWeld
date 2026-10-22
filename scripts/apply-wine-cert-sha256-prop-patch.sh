#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/wine-source-tree" >&2
  exit 2
fi
ROOT="$(realpath "$1")"
TARGET="$ROOT/dlls/crypt32/cert.c"
[[ -f "$TARGET" ]] || { echo "Not a Wine source tree: $TARGET missing" >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="$SCRIPT_DIR/../patches/wine-crypt32-cert-sha256-prop.patch"

if grep -A18 'case CERT_SHA1_HASH_PROP_ID:' "$TARGET" | grep -q 'case CERT_SHA256_HASH_PROP_ID:'; then
  echo "CERT_SHA256_HASH_PROP_ID getter already present; nothing to patch."
  exit 0
fi

cd "$ROOT"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git apply --check "$PATCH_FILE"
  git apply "$PATCH_FILE"
else
  patch --dry-run -p1 < "$PATCH_FILE"
  patch -p1 < "$PATCH_FILE"
fi

echo "Applied CERT_SHA256_HASH_PROP_ID compatibility patch to $TARGET"
echo "Rebuild Wine/Proton normally; this script does not modify an installed Proton build."
