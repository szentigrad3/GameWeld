#!/usr/bin/env bash
# Verify private functional AppImage packaging cannot proceed by accident.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
APP="$TMP/Functional.AppDir"
mkdir -p "$APP"
printf 'NOT APPROVED FOR DISTRIBUTION\nBuild mode: functional\n' > "$APP/NOT-FOR-DISTRIBUTION.txt"
printf '#!/bin/sh\nexit 0\n' > "$APP/AppRun"
chmod +x "$APP/AppRun"
set +e
GAMEWELD_PC2_STAGE="$APP" GAMEWELD_APPIMAGETOOL=/bin/true \
  bash "$ROOT/scripts/pc2-build-private-appimage.sh" >"$TMP/no-optin.log" 2>&1
first=$?
GAMEWELD_PC2_STAGE="$APP" GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST=I_UNDERSTAND_PRIVATE_TEST_ONLY GAMEWELD_APPIMAGETOOL=/bin/true \
  bash "$ROOT/scripts/pc2-build-private-appimage.sh" >"$TMP/no-output.log" 2>&1
second=$?
set -e
[[ "$first" -eq 2 ]] || { cat "$TMP/no-optin.log"; exit 1; }
[[ "$second" -eq 2 ]] || { cat "$TMP/no-output.log"; exit 1; }
grep -q 'explicit private-test opt-in' "$TMP/no-optin.log"
grep -q 'explicit GAMEWELD_PC2_IMAGE_OUT' "$TMP/no-output.log"
echo 'PASS: private functional AppImage cannot be accidentally packaged'
