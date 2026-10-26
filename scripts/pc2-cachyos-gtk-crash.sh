#!/usr/bin/env bash
# Private interactive CachyOS GTK crash backtrace for GameWeld PC2.
# No Steam launch-options edits, no game writes or trainer installation.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${GAMEWELD_PC2_OUT:-$ROOT/build/pc2-source}"
for command in gdb gcc go pkg-config; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required tool: $command (install through your system's package manager)." >&2
    exit 2
  fi
done
pkg-config --exists gtk+-3.0 || {
  echo "GTK3 development package is missing (gtk3 on CachyOS/Arch)." >&2
  exit 2
}
if [[ ! -x "$OUT/wand-native-backend" ]]; then
  echo "Backend missing. Run the normal source runner once first." >&2
  exit 2
fi
bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
mkdir -p "$OUT"
# Retain debug symbols and frame pointers while preserving the release -O2.
gcc -O2 -g3 -fno-omit-frame-pointer -pipe -pthread \
  -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" \
  -o "$OUT/gameweld-gtk-debug" \
  $(pkg-config --cflags --libs gtk+-3.0)
export APPDIR="$OUT/dev-AppDir"
export WAND_NATIVE_BACKEND="$OUT/wand-native-backend"
export PATH="$ROOT/scripts:${PATH:-/usr/bin:/bin}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$STATE"
chmod 700 "$STATE"
umask 077
REPORT="$STATE/pc2-gtk-crash-$(date +%Y%m%d-%H%M%S).txt"
echo "Running GameWeld under gdb. The report is saved only on your PC."
echo "Close the window if no crash occurs."
echo "Report: $REPORT"
set +e
gdb -q -batch \
  -ex 'set pagination off' \
  -ex 'set print thread-events off' \
  -ex 'handle SIGPIPE nostop noprint pass' \
  -ex run \
  -ex 'thread apply all bt 25' \
  --args "$OUT/gameweld-gtk-debug" "$@" >"$REPORT" 2>&1
STATUS=$?
set -e
chmod 600 "$REPORT"
echo "Debugger exited (status $STATUS). Report saved:"
printf '%s\n' "$REPORT"
if grep -qE 'Program received signal SIGSEGV|SIGABRT|AddressSanitizer|Segmentation fault' "$REPORT"; then
  echo "Crash captured. Review private paths before sharing this report."
elif grep -qE 'exited normally|Inferior .*exited' "$REPORT"; then
  echo "GUI exited without a captured crash."
else
  echo "No conclusive crash signature; review the report."
fi
