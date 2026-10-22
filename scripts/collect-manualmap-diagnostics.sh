#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/wand/one-session"
PROTON_LOG="$STATE_ROOT/appid-$APPID-proton.log"
OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"

LATEST_WATCH="$(
  find "$OUT_DIR" -maxdepth 1 -type f \
    -name "wand-manualmap-${APPID}-*.txt" \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr | head -1 | cut -d' ' -f2-
)"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-manualmap-summary-${APPID}-${STAMP}.txt"

{
  echo "Wand Native manual-map diagnostic summary"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "appid=$APPID"
  echo "watch_file=${LATEST_WATCH:-not-found}"
  echo "proton_log=$PROTON_LOG"
  echo

  echo "===== trainerlib file accesses ====="
  if [[ -n "$LATEST_WATCH" && -f "$LATEST_WATCH" ]]; then
    grep -Ei \
      'INOTIFY .* (TrainerLibPlugin_x64\.dll|TrainerLib_x64\.dll|ContractRuntimePlugin_x64\.dll|LuaExecutorPlugin_x64\.dll|CELib_x64\.dll|InputCapturePlugin_x64\.dll|tophat_service_x64\.dll)' \
      "$LATEST_WATCH" || true
  else
    echo "No manual-map watcher output found."
  fi
  echo

  echo "===== executable / Wand-related mapping changes ====="
  if [[ -n "$LATEST_WATCH" && -f "$LATEST_WATCH" ]]; then
    grep -E 'MAP_(ADD|CHANGE|REMOVE)|PROCESS_GONE|THREADS ' "$LATEST_WATCH" \
      | tail -12000 || true
  fi
  echo

  echo "===== watcher tail ====="
  if [[ -n "$LATEST_WATCH" && -f "$LATEST_WATCH" ]]; then
    tail -400 "$LATEST_WATCH"
  fi
  echo

  echo "===== Proton Tophat and downstream DLL summary ====="
  if [[ -f "$PROTON_LOG" ]]; then
    grep -nEi \
      'tophat_service_x64|TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64' \
      "$PROTON_LOG" | tail -2500 || true
  else
    echo "Proton log missing."
  fi
} > "$OUT"

echo "$OUT"
