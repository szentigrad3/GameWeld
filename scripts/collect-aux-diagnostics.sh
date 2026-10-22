#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/wand/one-session"
PROTON_LOG="$STATE_ROOT/appid-$APPID-proton.log"
STAGE_LOG="$STATE_ROOT/appid-$APPID-stage.txt"
BATCH="$STATE_ROOT/appid-$APPID-launch.bat"

OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-aux-diagnostics-${APPID}-${STAMP}.txt"

{
  echo "Wand Native auxiliary-service diagnostic"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "appid=$APPID"
  echo

  echo "===== system ====="
  uname -a || true
  echo

  echo "===== wandd environment ====="
  systemctl --user show wandd \
    -p Environment -p MainPID -p ActiveState -p SubState 2>/dev/null || true
  echo

  echo "===== current relevant processes ====="
  pgrep -af \
    'Wand.exe|WeMod.exe|WandAuxiliaryService|TrainerHost|GameLauncher|resonance.exe|proton|wineserver' \
    || true
  echo
  echo "===== Wand Electron profile paths ====="
  pgrep -af 'Wand.exe' 2>/dev/null \
    | grep -oE -- '--user-data-dir=[^ ]+' \
    | sort -u || true
  echo

  echo "===== one-session stage ====="
  if [[ -f "$STAGE_LOG" ]]; then
    cat "$STAGE_LOG"
  else
    echo "missing: $STAGE_LOG"
  fi
  echo

  echo "===== generated one-session batch ====="
  if [[ -f "$BATCH" ]]; then
    sed -n '1,120p' "$BATCH"
  else
    echo "missing: $BATCH"
  fi
  echo

  echo "===== Proton/Wine log header ====="
  if [[ -f "$PROTON_LOG" ]]; then
    sed -n '1,40p' "$PROTON_LOG"
  else
    echo "missing: $PROTON_LOG"
  fi
  echo

  echo "===== filtered Proton/Wine auxiliary/injection trace ====="
  if [[ -f "$PROTON_LOG" ]]; then
    grep -nEi \
      'WandAuxiliary|TrainerHost|GameLauncher|tophat_service|TrainerLib|ContractRuntime|LuaExecutor|resonance|CreateRemoteThread|VirtualAllocEx|VirtualProtectEx|WriteProcessMemory|ReadProcessMemory|OpenProcess|named.?pipe|\\\\\\\\\\.\\\\pipe|pipe|mscoree|clr|seh|exception|access.denied|err:' \
      "$PROTON_LOG" \
      | tail -1500 || true
  fi
  echo

  echo "===== tail of Proton/Wine log ====="
  if [[ -f "$PROTON_LOG" ]]; then
    tail -500 "$PROTON_LOG"
  fi
  echo

  echo "===== recent wandd journal ====="
  journalctl --user -u wandd --since "-15 min" --no-pager 2>/dev/null \
    | tail -600 || true
} > "$OUT"

echo "$OUT"
