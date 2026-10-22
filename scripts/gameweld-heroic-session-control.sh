#!/usr/bin/env bash
set -Eeuo pipefail
ACTION="${1:?action required}"; RUNNER="${2:-}"; APPID="${3:-}"; TITLE="${4:-$APPID}"; PREFIX="${5:-}"; WINE_TYPE="${6:-}"; WINE_BIN="${7:-}"; TRAINER="${8:-}"; INSTALL="${9:-}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"; mkdir -p "$STATE"
LOG="$STATE/heroic-session-control-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] action=%s runner=%s appid=%s title=%s prefix=%s\n' -1 "$ACTION" "$RUNNER" "$APPID" "$TITLE" "$PREFIX"

safe_cmdline(){ local p="$1"; [[ -r "/proc/$p/cmdline" ]] || return 1; tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true; }
managed_state_file(){
  local rr aa
  rr="$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')"
  aa="$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_')"
  printf '%s/heroic-managed-session-%s-%s.state\n' "$STATE" "$rr" "$aa"
}
clear_managed_state(){
  local f
  f="$(managed_state_file)"
  [[ -e "$f" ]] && echo "Removing GameWeld managed-session state: $f"
  rm -f -- "$f"
}
trainer_pids(){
  local base low p pid comm cmd all
  [[ -n "$TRAINER" ]] || return 0
  base="$(basename -- "$TRAINER")"; low="${base,,}"
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue; pid="${p##*/}"; [[ "$pid" != "$$" ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"; cmd="$(safe_cmdline "$pid")"; all="${comm,,} ${cmd,,}"
    case "${comm,,}" in bash|sh|dash|zsh|fish|python|python3|gameweld) continue;; esac
    case "$all" in *gameweld-heroic-session-control*) continue;; esac
    if [[ "$all" == *"$low"* ]]; then printf '%s\n' "$pid"; fi
  done | sort -u
}
stop_trainer(){
  local -a pids=(); local p
  while IFS= read -r p; do [[ -n "$p" ]] && pids+=("$p"); done < <(trainer_pids)
  if ((${#pids[@]}==0)); then echo "No running trainer process matched: ${TRAINER:-<none configured>}"; return 0; fi
  echo "Stopping trainer PIDs: ${pids[*]}"
  kill -TERM "${pids[@]}" 2>/dev/null || true; sleep 1
  local -a alive=(); for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive+=("$p") || true; done
  if ((${#alive[@]})); then echo "Trainer ignored TERM; forcing PIDs: ${alive[*]}"; kill -KILL "${alive[@]}" 2>/dev/null || true; fi
  echo "Trainer stop complete."
}
real_prefix(){
  if [[ -n "$PREFIX" && -d "$PREFIX/pfx/drive_c" && ! -d "$PREFIX/drive_c" ]]; then printf '%s\n' "$PREFIX/pfx"; else printf '%s\n' "$PREFIX"; fi
}
find_wineserver(){
  local root c
  if [[ -n "$WINE_BIN" ]]; then
    root="$(dirname -- "$WINE_BIN")"
    for c in "$root/files/bin/wineserver" "$root/files/share/wine/bin/wineserver" "$root/wineserver" "$(dirname -- "$root")/bin/wineserver"; do [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }; done
  fi
  command -v wineserver 2>/dev/null || true
}
target_process_match(){
  local pid="$1" rp="$2" envs cmd comm
  [[ -d "/proc/$pid" && "$pid" != "$$" ]] || return 1
  comm="$(cat "/proc/$pid/comm" 2>/dev/null || true)"
  cmd="$(safe_cmdline "$pid")"
  case "${comm,,}" in gameweld|gameforge|wand-native) return 1;; esac
  case "${cmd,,}" in *gameweld-heroic-session-control*) return 1;; esac
  envs="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null || true)"
  [[ -n "$rp" ]] && grep -Fqx "WINEPREFIX=$rp" <<<"$envs" && return 0
  [[ -n "$PREFIX" ]] && grep -Fqx "WINEPREFIX=$PREFIX" <<<"$envs" && return 0
  [[ -n "$PREFIX" ]] && grep -Fqx "STEAM_COMPAT_DATA_PATH=$PREFIX" <<<"$envs" && return 0
  [[ -n "$rp" ]] && grep -Fqx "STEAM_COMPAT_DATA_PATH=$rp" <<<"$envs" && return 0
  [[ -n "$APPID" && "$cmd" == *"$APPID"* ]] && return 0
  [[ -n "$INSTALL" && "$cmd" == *"$INSTALL"* ]] && return 0
  [[ -n "$PREFIX" && "$cmd" == *"$PREFIX"* ]] && return 0
  [[ -n "$rp" && "$cmd" == *"$rp"* ]] && return 0
  return 1
}
collect_target_pids(){
  local rp="$1" p pid ppid changed=1 item
  local -a hits=()
  declare -A seen=()
  for p in /proc/[0-9]*; do
    pid="${p##*/}"
    if target_process_match "$pid" "$rp"; then seen["$pid"]=1; hits+=("$pid"); fi
  done
  # Include descendants of any matched wrapper/session process even when a
  # child has dropped WINEPREFIX from its environment. This is important for
  # Legendary -> umu-run -> Proton/pressure-vessel process trees.
  while (( changed )); do
    changed=0
    for p in /proc/[0-9]*; do
      pid="${p##*/}"; [[ -n "${seen[$pid]:-}" || "$pid" == "$$" ]] && continue
      ppid="$(awk '/^PPid:/{print $2}' "$p/status" 2>/dev/null || true)"
      if [[ -n "$ppid" && -n "${seen[$ppid]:-}" ]]; then
        case "$(cat "$p/comm" 2>/dev/null || true)" in gameweld|gameforge|wand-native) continue;; esac
        seen["$pid"]=1; hits+=("$pid"); changed=1
      fi
    done
  done
  ((${#hits[@]})) && printf '%s\n' "${hits[@]}" | sort -n -u
}
kill_prefix_fallback(){
  local rp="$1" pid i
  local -a pids=() alive=()
  while IFS= read -r pid; do [[ -n "$pid" ]] && pids+=("$pid"); done < <(collect_target_pids "$rp")
  if ((${#pids[@]}==0)); then
    echo 'No remaining prefix/backend processes matched the selected Heroic game.'
    return 0
  fi
  echo "Targeted Heroic/UMU/Proton process set: ${pids[*]}"
  kill -TERM "${pids[@]}" 2>/dev/null || true
  for ((i=0;i<20;i++)); do
    alive=()
    for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null && alive+=("$pid") || true; done
    ((${#alive[@]}==0)) && break
    sleep 0.1
  done
  if ((${#alive[@]})); then
    echo "Processes ignored TERM (including possible Wine critical-section hang); forcing: ${alive[*]}"
    kill -KILL "${alive[@]}" 2>/dev/null || true
  fi
  sleep 1
  alive=()
  while IFS= read -r pid; do [[ -n "$pid" ]] && alive+=("$pid"); done < <(collect_target_pids "$rp")
  if ((${#alive[@]})); then
    echo "WARNING: target processes still remain after forced reset: ${alive[*]}"
    for pid in "${alive[@]}"; do printf '  pid=%s comm=%s cmd=%s\n' "$pid" "$(cat "/proc/$pid/comm" 2>/dev/null || true)" "$(safe_cmdline "$pid")"; done
    return 1
  fi
  echo 'Targeted Heroic/UMU/Proton process tree is fully stopped.'
}
reset_prefix(){
  stop_trainer || true
  local rp ws
  rp="$(real_prefix)"; ws="$(find_wineserver)"
  if [[ -n "$ws" && -x "$ws" && -n "$rp" ]]; then
    echo "Resetting Wine session with: $ws -k"
    echo "Effective WINEPREFIX: $rp"
    WINEPREFIX="$rp" "$ws" -k || true
    sleep 1
  else
    echo "No runner-local wineserver resolved; using prefix process fallback."
  fi
  if kill_prefix_fallback "$rp"; then
    clear_managed_state || true
    echo "Heroic prefix session reset complete. The game, Legendary/UMU wrappers and every Windows sidecar in this prefix are closed."
  else
    echo "Heroic prefix reset did not fully clear the process tree; see the PID diagnostics above."
    return 1
  fi
}
case "$ACTION" in
  stop-trainer) stop_trainer ;;
  reset-prefix) reset_prefix ;;
  *) echo "Unknown action: $ACTION"; exit 2;;
esac
