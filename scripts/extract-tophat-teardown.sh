#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/wand/one-session/appid-$APPID-proton.log"

[[ -f "$LOG" ]] || { echo "Missing $LOG" >&2; exit 1; }

MATCH="$(grep -nE 'trace:loaddll:build_module Loaded .*tophat_service_x64\.dll' "$LOG" | tail -1 || true)"
[[ -n "$MATCH" ]] || { echo "No Tophat load found." >&2; exit 2; }

LINE="${MATCH%%:*}"
REC="${MATCH#*:}"
PID="$(printf '%s\n' "$REC" | sed -nE 's/^[0-9.]+:([0-9A-Fa-f]+):[0-9A-Fa-f]+:.*/\1/p')"
END=$((LINE + 30000))

echo "Tophat load: $MATCH"
echo "Game Wine PID: $PID"
echo
echo "First Tophat unload:"
awk -v start="$LINE" -v pid="$PID" '
  NR < start { next }
  index($0, ":" pid ":") &&
  /LdrUnloadDll \(L"tophat_service_x64\.dll"\) - START/ { print NR ":" $0; exit }
' "$LOG"
echo
echo "Game-process CLR/TrainerLib refs after Tophat:"
sed -n "${LINE},${END}p" "$LOG" \
  | grep -E ":${PID}:" \
  | grep -Ei 'TrainerLib|mscoree\.dll|clr\.dll|CLRCreateInstance|ICLR|CorBind' \
  | head -200 || true
