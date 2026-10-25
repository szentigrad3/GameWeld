#!/usr/bin/env bash
# Private AppDir integrity/portability audit; never starts GameWeld or publishes artifacts.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${GAMEWELD_PC2_STAGE:-$ROOT/build/pc2-source/private-AppDir}"
REPORT="${GAMEWELD_PC2_AUDIT_REPORT:-$ROOT/build/pc2-source/private-appdir-audit.txt}"
mkdir -p "$(dirname "$REPORT")"
fail=0
{
  echo 'GAMEWELD PRIVATE APPDIR AUDIT — NOT RELEASE APPROVAL'
  echo "AppDir: $OUT"
  for file in AppRun usr/bin/gameweld usr/bin/wand-native-backend \
      usr/libexec/gameweld-steam-compat-bridge.py \
      usr/libexec/gameweld-deckcheatz-direct.py \
      usr/libexec/gameweld-deckcheatz-proton.py \
      usr/libexec/gameweld-deckcheatz-install.py NOT-FOR-DISTRIBUTION.txt; do
    if [[ -f "$OUT/$file" && ! -L "$OUT/$file" ]]; then echo "PASS file: $file"
    else echo "FAIL missing, linked or invalid: $file"; fail=1; fi
  done
  if [[ -x "$OUT/AppRun" && -x "$OUT/usr/bin/gameweld" && -x "$OUT/usr/bin/wand-native-backend" ]]; then
    echo 'PASS: launcher and both binaries executable'
  else echo 'FAIL: launcher or binary not executable'; fail=1; fi
  if [[ -d "$OUT" ]] && find "$OUT" -type l -print -quit | grep -q .; then
    echo 'FAIL: symlinks in private AppDir (may escape bundle)'; fail=1
  else echo 'PASS: no symlinks found'; fi
  if command -v ldd >/dev/null 2>&1; then
    for name in gameweld wand-native-backend; do
      if [[ -f "$OUT/usr/bin/$name" ]]; then
        echo "=== dynamic dependencies: $name ==="
        deps="$(ldd "$OUT/usr/bin/$name" 2>&1)" || { echo "$deps"; echo "FAIL: ldd $name"; fail=1; continue; }
        echo "$deps"
        if grep -q 'not found' <<<"$deps"; then echo "FAIL: unresolved dependency: $name"; fail=1; fi
      fi
    done
  else echo 'FAIL: ldd unavailable'; fail=1; fi
  if [[ -f "$OUT/usr/bin/gameweld" && -f "$OUT/usr/bin/wand-native-backend" ]]; then
    echo '=== SHA256 ==='
    sha256sum "$OUT/usr/bin/gameweld" "$OUT/usr/bin/wand-native-backend"
  fi
  echo 'NOT TESTED: launch, GUI behaviour, clean OS, portable dependency bundling, licenses'
  if (( fail )); then echo 'RESULT: FAIL — do not package'; else echo 'RESULT: PASS — local AppDir structure only; publication BLOCKED'; fi
} 2>&1 | tee "$REPORT"
exit "$fail"
