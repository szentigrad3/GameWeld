#!/usr/bin/env bash
# Private headless GTK launch smoke test. Does not launch Steam or a game.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APPDIR="${GAMEWELD_PC2_STAGE:-$ROOT/build/pc2-source/private-AppDir}"
[[ -x "$APPDIR/AppRun" ]] || { echo "FAIL: missing private AppRun" >&2; exit 2; }
for tool in xvfb-run timeout mktemp; do
  command -v "$tool" >/dev/null || { echo "FAIL: missing $tool" >&2; exit 2; }
done
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/config" "$TMP/data" "$TMP/cache"
LOG="$TMP/gui.log"
set +e
timeout 8s xvfb-run -a env \
  HOME="$TMP/home" \
  XDG_CONFIG_HOME="$TMP/config" \
  XDG_DATA_HOME="$TMP/data" \
  XDG_CACHE_HOME="$TMP/cache" \
  GDK_BACKEND=x11 \
  GAMEWELD_PC2_DISCOVERY_ONLY=1 \
  "$APPDIR/AppRun" > "$LOG" 2>&1
status=$?
set -e
if [[ "$status" -eq 124 ]]; then
  echo "PASS: private GTK GUI remained running for 8 seconds under Xvfb."
  echo "LIMITATION: no interactive GUI, Steam, WeMod, clean distro, or bundled-library verification."
  exit 0
fi
echo "FAIL: private GTK GUI exited early (status $status)" >&2
tail -80 "$LOG" >&2
exit 1
