#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/wand/one-session"
PROTON_LOG="$STATE_ROOT/appid-$APPID-proton.log"
STAGE_LOG="$STATE_ROOT/appid-$APPID-stage.txt"

OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-tophat-diagnostics-${APPID}-${STAMP}.txt"

if [[ ! -f "$PROTON_LOG" ]]; then
  echo "Missing Proton log: $PROTON_LOG" >&2
  exit 1
fi

TOPHAT_MATCH="$(
  grep -nE 'trace:loaddll:build_module Loaded .*tophat_service_x64\.dll' \
    "$PROTON_LOG" | tail -1 || true
)"

TOPHAT_LINE=""
TOPHAT_TIME=""
GAME_WPID=""

if [[ -n "$TOPHAT_MATCH" ]]; then
  TOPHAT_LINE="${TOPHAT_MATCH%%:*}"
  TOPHAT_RECORD="${TOPHAT_MATCH#*:}"
  TOPHAT_TIME="$(printf '%s\n' "$TOPHAT_RECORD" | sed -nE 's/^([0-9.]+):.*/\1/p')"
  GAME_WPID="$(printf '%s\n' "$TOPHAT_RECORD" | sed -nE 's/^[0-9.]+:([0-9A-Fa-f]+):[0-9A-Fa-f]+:.*/\1/p')"
fi

AUX_MATCH="$(
  grep -nE 'NtCreateUserProcess .*WandAuxiliaryService\.exe.* pid [0-9A-Fa-f]+' \
    "$PROTON_LOG" | tail -1 || true
)"
AUX_WPID=""
if [[ -n "$AUX_MATCH" ]]; then
  AUX_RECORD="${AUX_MATCH#*:}"
  AUX_WPID="$(printf '%s\n' "$AUX_RECORD" | sed -nE 's/.* pid ([0-9A-Fa-f]+) tid .*/\1/p')"
fi

PLUGIN_MATCHES="$(
  grep -nF 'TrainerLibPlugin_x64.dll' "$PROTON_LOG" || true
)"

PLUGIN_FIRST_LINE=""
PLUGIN_FIRST_TIME=""
PLUGIN_LAST_LINE=""
PLUGIN_LAST_TIME=""

if [[ -n "$PLUGIN_MATCHES" ]]; then
  FIRST="$(printf '%s\n' "$PLUGIN_MATCHES" | head -1)"
  LAST="$(printf '%s\n' "$PLUGIN_MATCHES" | tail -1)"
  PLUGIN_FIRST_LINE="${FIRST%%:*}"
  PLUGIN_FIRST_RECORD="${FIRST#*:}"
  PLUGIN_FIRST_TIME="$(printf '%s\n' "$PLUGIN_FIRST_RECORD" | sed -nE 's/^([0-9.]+):.*/\1/p')"
  PLUGIN_LAST_LINE="${LAST%%:*}"
  PLUGIN_LAST_RECORD="${LAST#*:}"
  PLUGIN_LAST_TIME="$(printf '%s\n' "$PLUGIN_LAST_RECORD" | sed -nE 's/^([0-9.]+):.*/\1/p')"
fi

raw_window() {
  local center="$1"
  local before="${2:-250}"
  local after="${3:-650}"
  local start end

  start=$((center > before ? center - before : 1))
  end=$((center + after))
  sed -n "${start},${end}p" "$PROTON_LOG"
}

{
  echo "Wand Native Tophat/plugin trust diagnostic"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "appid=$APPID"
  echo "tophat_raw_line=${TOPHAT_LINE:-not-found}"
  echo "tophat_time=${TOPHAT_TIME:-not-found}"
  echo "game_wine_pid=${GAME_WPID:-not-found}"
  echo "aux_wine_pid=${AUX_WPID:-not-found}"
  echo "plugin_first_raw_line=${PLUGIN_FIRST_LINE:-not-found}"
  echo "plugin_first_time=${PLUGIN_FIRST_TIME:-not-found}"
  echo "plugin_last_raw_line=${PLUGIN_LAST_LINE:-not-found}"
  echo "plugin_last_time=${PLUGIN_LAST_TIME:-not-found}"
  echo

  echo "===== session stage ====="
  [[ -f "$STAGE_LOG" ]] && cat "$STAGE_LOG" || echo "missing: $STAGE_LOG"
  echo

  echo "===== current relevant processes ====="
  pgrep -afi \
    'Wand\.exe|WandAuxiliaryService|TrainerHost|GameLauncher|Resonance\.exe|tophat|ACE: WinMain' \
    || true
  echo

  echo "===== Proton/Wine header ====="
  sed -n '1,45p' "$PROTON_LOG"
  echo

  echo "===== exact Tophat load window ====="
  if [[ -n "$TOPHAT_LINE" ]]; then
    raw_window "$TOPHAT_LINE" 100 300
  else
    echo "tophat_service_x64.dll load not found"
  fi
  echo

  echo "===== all TrainerLibPlugin references ====="
  if [[ -n "$PLUGIN_MATCHES" ]]; then
    printf '%s\n' "$PLUGIN_MATCHES"
  else
    echo "No TrainerLibPlugin_x64.dll references found"
  fi
  echo

  echo "===== exact first plugin-trust raw window ====="
  if [[ -n "$PLUGIN_FIRST_LINE" ]]; then
    raw_window "$PLUGIN_FIRST_LINE" 300 1200
  else
    echo "first plugin event not found"
  fi
  echo

  if [[ -n "$PLUGIN_LAST_LINE" && "$PLUGIN_LAST_LINE" != "$PLUGIN_FIRST_LINE" ]]; then
    echo "===== exact last plugin-trust raw window ====="
    raw_window "$PLUGIN_LAST_LINE" 300 1600
    echo
  fi

  echo "===== plugin trust/result filter ====="
  if [[ -n "$PLUGIN_FIRST_LINE" ]]; then
    START=$((PLUGIN_FIRST_LINE > 1500 ? PLUGIN_FIRST_LINE - 1500 : 1))
    END=$(( (PLUGIN_LAST_LINE > 0 ? PLUGIN_LAST_LINE : PLUGIN_FIRST_LINE) + 8000 ))
    sed -n "${START},${END}p" "$PROTON_LOG" \
      | grep -Ei \
        'TrainerLibPlugin_x64|TrainerLib_x64|ContractRuntimePlugin|LuaExecutorPlugin|CELib_x64|InputCapturePlugin|wintrust|WinVerifyTrust|WTHelper|CryptSIP|CryptQueryObject|CryptMsg|Cert(Get|Verify|Enum|Open|Close)|TRUST_E_|CERT_E_|0x800b|status=|returned|returning|error|failed|failure|success' \
      | head -12000 || true
  else
    echo "plugin trust range unavailable"
  fi
  echo

  echo "===== game PID after first plugin trust ====="
  if [[ -n "$GAME_WPID" && -n "$PLUGIN_FIRST_LINE" ]]; then
    START=$((PLUGIN_FIRST_LINE > 300 ? PLUGIN_FIRST_LINE - 300 : 1))
    END=$((PLUGIN_FIRST_LINE + 30000))
    sed -n "${START},${END}p" "$PROTON_LOG" \
      | grep -E ":${GAME_WPID}:" \
      | grep -Ei \
        'loaddll|wintrust|crypt|process:|thread:|seh:|NtTerminateProcess|exit_code|dispatch_exception|unhandled|fault|crash|abort|err:' \
      | head -12000 || true
  else
    echo "game PID/plugin range unavailable"
  fi
  echo

  echo "===== AuxiliaryService around plugin trust ====="
  if [[ -n "$AUX_WPID" && -n "$PLUGIN_FIRST_LINE" ]]; then
    START=$((PLUGIN_FIRST_LINE > 300 ? PLUGIN_FIRST_LINE - 300 : 1))
    END=$((PLUGIN_FIRST_LINE + 30000))
    sed -n "${START},${END}p" "$PROTON_LOG" \
      | grep -E ":${AUX_WPID}:" \
      | grep -Ei \
        'process:|thread:|seh:|loaddll|wintrust|crypt|NtTerminateProcess|exit_code|dispatch_exception|error|failed|err:' \
      | head -10000 || true
  else
    echo "AuxiliaryService PID/plugin range unavailable"
  fi
  echo

  echo "===== post-plugin global termination/crash signals ====="
  if [[ -n "$PLUGIN_FIRST_LINE" ]]; then
    START=$((PLUGIN_FIRST_LINE > 100 ? PLUGIN_FIRST_LINE - 100 : 1))
    END=$((PLUGIN_FIRST_LINE + 60000))
    sed -n "${START},${END}p" "$PROTON_LOG" \
      | grep -Ei \
        'NtTerminateProcess|exit_code|process_exiting|dispatch_exception|unhandled|access violation|illegal instruction|stack overflow|fault|crash|abort|terminate|STATUS_|err:' \
      | head -12000 || true
  else
    echo "plugin range unavailable"
  fi
  echo

  echo "===== final plugin/load summary ====="
  grep -nEi \
    'tophat_service_x64|TrainerLib_x64|TrainerLibPlugin_x64|ContractRuntimePlugin_x64|LuaExecutorPlugin_x64|CELib_x64|InputCapturePlugin_x64' \
    "$PROTON_LOG" \
    | tail -1000 || true
} > "$OUT"

echo "$OUT"
