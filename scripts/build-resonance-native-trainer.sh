#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="${1:-$ROOT/prebuilt/resonance-native-trainer.exe}"
CLANG="${CLANG:-$(command -v clang || true)}"
LLD="${LLD_LINK:-$(command -v lld-link || true)}"
[[ -n "$CLANG" && -x "$CLANG" ]] || { echo "clang is required" >&2; exit 2; }
[[ -n "$LLD" && -x "$LLD" ]] || { echo "lld-link is required" >&2; exit 3; }
mkdir -p "$(dirname -- "$OUT")"
OBJ="${TMPDIR:-/tmp}/resonance-native-trainer-$$.obj"
trap 'rm -f "$OBJ"' EXIT
"$CLANG" -target x86_64-pc-windows-msvc -O2 -ffreestanding -fno-builtin \
  -fno-stack-protector -mno-stack-arg-probe \
  -c "$ROOT/tools/resonance-native-trainer.c" -o "$OBJ"
"$LLD" /entry:entry /subsystem:windows /nodefaultlib /machine:x64 \
  "/out:$OUT" "$OBJ"
printf 'Built %s\n' "$OUT"
