#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/wand/one-session"
PROTON_LOG="$STATE_ROOT/appid-$APPID-proton.log"
STAGE_LOG="$STATE_ROOT/appid-$APPID-stage.txt"

OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-plugin-loader-${APPID}-${STAMP}.txt"

if [[ ! -f "$PROTON_LOG" ]]; then
  echo "Missing Proton log: $PROTON_LOG" >&2
  exit 1
fi

TOPHAT_MATCH="$(
  grep -nE 'trace:loaddll:build_module Loaded .*tophat_service_x64\.dll' \
    "$PROTON_LOG" | tail -1 || true
)"

if [[ -z "$TOPHAT_MATCH" ]]; then
  echo "No tophat_service_x64.dll load found in $PROTON_LOG" >&2
  exit 2
fi

TOPHAT_LINE="${TOPHAT_MATCH%%:*}"
TOPHAT_RECORD="${TOPHAT_MATCH#*:}"
TOPHAT_TIME="$(printf '%s\n' "$TOPHAT_RECORD" | sed -nE 's/^([0-9.]+):.*/\1/p')"
GAME_WPID="$(printf '%s\n' "$TOPHAT_RECORD" \
  | sed -nE 's/^[0-9.]+:([0-9A-Fa-f]+):[0-9A-Fa-f]+:.*/\1/p')"

if [[ -z "$GAME_WPID" ]]; then
  echo "Unable to derive game Wine PID from Tophat load: $TOPHAT_RECORD" >&2
  exit 3
fi

TOTAL_LINES="$(wc -l < "$PROTON_LOG")"
WINDOW_START=$((TOPHAT_LINE > 750 ? TOPHAT_LINE - 750 : 1))
WINDOW_END=$((TOPHAT_LINE + 180000))
(( WINDOW_END > TOTAL_LINES )) && WINDOW_END="$TOTAL_LINES"

TOPHAT_ATTACH_END="$(
  awk -v start="$TOPHAT_LINE" -v pid="$GAME_WPID" '
    NR < start { next }
    index($0, ":" pid ":") &&
    /process_attach \(L"tophat_service_x64\.dll"/ &&
    / - END/ { print NR ":" $0; exit }
  ' "$PROTON_LOG"
)"

FIRST_TOPHAT_UNLOAD="$(
  awk -v start="$TOPHAT_LINE" -v pid="$GAME_WPID" '
    NR < start { next }
    index($0, ":" pid ":") &&
    /LdrUnloadDll \(L"tophat_service_x64\.dll"\) - START/ {
      print NR ":" $0; exit
    }
  ' "$PROTON_LOG"
)"
FIRST_UNLOAD_LINE=""
FIRST_UNLOAD_TIME=""
if [[ -n "$FIRST_TOPHAT_UNLOAD" ]]; then
  FIRST_UNLOAD_LINE="${FIRST_TOPHAT_UNLOAD%%:*}"
  FIRST_UNLOAD_REC="${FIRST_TOPHAT_UNLOAD#*:}"
  FIRST_UNLOAD_TIME="$(printf '%s\n' "$FIRST_UNLOAD_REC" \
    | sed -nE 's/^([0-9.]+):.*/\1/p')"
fi

FIRST_GAME_CLR="$(
  awk -v start="$TOPHAT_LINE" -v pid="$GAME_WPID" '
    NR < start { next }
    index($0, ":" pid ":") &&
    $0 ~ /(TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64|mscoree\.dll|clr\.dll|CLRCreateInstance|ICLRMetaHost|ICLRRuntime)/ {
      print NR ":" $0
      exit
    }
  ' "$PROTON_LOG"
)"

FIRST_DOWNSTREAM_LOAD="$(
  awk -v start="$TOPHAT_LINE" -v pid="$GAME_WPID" '
    NR < start { next }
    index($0, ":" pid ":") &&
    /trace:loaddll:build_module Loaded/ &&
    $0 ~ /(TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64)/ {
      print NR ":" $0
      exit
    }
  ' "$PROTON_LOG"
)"

raw_window() {
  local center="$1"
  local before="${2:-180}"
  local after="${3:-350}"
  local start end
  start=$((center > before ? center - before : 1))
  end=$((center + after))
  (( end > TOTAL_LINES )) && end="$TOTAL_LINES"
  sed -n "${start},${end}p" "$PROTON_LOG"
}

{
  echo "Wand Native Tophat teardown / plugin-loader diagnostic"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "appid=$APPID"
  echo "raw_log=$PROTON_LOG"
  echo "raw_total_lines=$TOTAL_LINES"
  echo "tophat_raw_line=$TOPHAT_LINE"
  echo "tophat_time=${TOPHAT_TIME:-unknown}"
  echo "game_wine_pid=$GAME_WPID"
  echo "trainer_window_start=$WINDOW_START"
  echo "trainer_window_end=$WINDOW_END"
  echo "first_tophat_unload_raw_line=${FIRST_UNLOAD_LINE:-not-found}"
  echo "first_tophat_unload_time=${FIRST_UNLOAD_TIME:-not-found}"
  echo

  echo "===== session stage ====="
  [[ -f "$STAGE_LOG" ]] && cat "$STAGE_LOG" || echo "missing: $STAGE_LOG"
  echo

  echo "===== Tophat load ====="
  printf '%s\n' "$TOPHAT_MATCH"
  echo

  echo "===== Tophat process_attach completion ====="
  if [[ -n "$TOPHAT_ATTACH_END" ]]; then
    printf '%s\n' "$TOPHAT_ATTACH_END"
  else
    echo "No Tophat process_attach END found after load."
  fi
  echo

  echo "===== first Tophat unload/thread-teardown request ====="
  if [[ -n "$FIRST_TOPHAT_UNLOAD" ]]; then
    printf '%s\n' "$FIRST_TOPHAT_UNLOAD"
  else
    echo "No Tophat LdrUnloadDll request found after load."
  fi
  echo

  echo "===== raw window around first Tophat teardown ====="
  if [[ -n "$FIRST_UNLOAD_LINE" ]]; then
    raw_window "$FIRST_UNLOAD_LINE" 250 500
  else
    echo "No first teardown window available."
  fi
  echo

  echo "===== Tophat thread lifecycle after injection ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -E ":${GAME_WPID}:" \
    | grep -E \
      'tophat_service_x64\.dll.*(THREAD_ATTACH|THREAD_DETACH|PROCESS_ATTACH|PROCESS_DETACH)|LdrUnloadDll \(L"tophat_service_x64\.dll"\)|LdrAddRefDll \(L"tophat_service_x64\.dll"\)' \
    | head -12000 || true
  echo

  echo "===== first game-process TrainerLib / CLR reference after Tophat ====="
  if [[ -n "$FIRST_GAME_CLR" ]]; then
    printf '%s\n' "$FIRST_GAME_CLR"
  else
    echo "NONE: no game-process TrainerLib/mscoree/CLR reference was observed after Tophat load."
  fi
  echo

  echo "===== first successful downstream trainer DLL load ====="
  if [[ -n "$FIRST_DOWNSTREAM_LOAD" ]]; then
    printf '%s\n' "$FIRST_DOWNSTREAM_LOAD"
  else
    echo "NONE: no downstream TrainerLib/plugin DLL was observed as a successful Wine DLL load."
  fi
  echo

  echo "===== all game-process TrainerLib / CLR activity after Tophat ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -E ":${GAME_WPID}:" \
    | grep -Ei \
      'TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64|mscoree\.dll|clr\.dll|CLRCreateInstance|ICLRMetaHost|ICLRRuntime|CorBind|MetaHost|fusion\.dll' \
    | head -12000 || true
  echo

  echo "===== game-process module loader after Tophat ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -E ":${GAME_WPID}:" \
    | grep -Ei \
      'module:(load_dll|find_dll_file|find_builtin_dll|build_module|process_attach|LdrLoadDll|LdrGetDllHandleEx|LdrGetProcedureAddress|LdrUnloadDll|LdrAddRefDll)|loaddll:build_module' \
    | head -18000 || true
  echo

  echo "===== game-process exceptions/termination after Tophat ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -E ":${GAME_WPID}:" \
    | grep -Ei \
      'dispatch_exception|NtTerminateProcess|exit_code|process_exiting|Unhandled|access violation|illegal instruction|stack overflow|fault|crash|abort|STATUS_|c0000135|c0000139|c000007b|err:' \
    | head -14000 || true
  echo

  echo "===== game-process debug strings after Tophat ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -E ":${GAME_WPID}:" \
    | grep -Ei 'debugstr|OutputDebugString' \
    | head -8000 || true
  echo

  echo "===== global TrainerLib / CLR references after Tophat ====="
  sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
    | grep -nEi \
      'TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64|mscoree\.dll|clr\.dll|CLRCreateInstance|ICLRMetaHost|ICLRRuntime|CorBind' \
    | head -14000 || true
  echo

  echo "===== concise lifecycle summary ====="
  ATTACHES="$(
    sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
      | grep -E ":${GAME_WPID}:" \
      | grep -c 'tophat_service_x64\.dll",THREAD_ATTACH' || true
  )"
  DETACHES="$(
    sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
      | grep -E ":${GAME_WPID}:" \
      | grep -c 'tophat_service_x64\.dll",THREAD_DETACH' || true
  )"
  UNLOADS="$(
    sed -n "${TOPHAT_LINE},${WINDOW_END}p" "$PROTON_LOG" \
      | grep -E ":${GAME_WPID}:" \
      | grep -c 'LdrUnloadDll (L"tophat_service_x64.dll") - START' || true
  )"
  echo "Tophat THREAD_ATTACH callbacks: $ATTACHES"
  echo "Tophat THREAD_DETACH callbacks: $DETACHES"
  echo "Tophat LdrUnloadDll requests: $UNLOADS"
  echo "First teardown time: ${FIRST_UNLOAD_TIME:-not-found}"
  echo "First game CLR/TrainerLib event: ${FIRST_GAME_CLR:-none}"
  echo "First downstream successful load: ${FIRST_DOWNSTREAM_LOAD:-none}"
} > "$OUT"

echo "$OUT"
