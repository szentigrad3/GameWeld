#!/usr/bin/env bash
set -Eeuo pipefail
RUNNER="${1:?runner required}"
APPID="${2:?app id required}"
TITLE="${3:-$APPID}"
INSTALL="${4:-}"
EXE="${5:-}"
PREFIX="${6:-}"
INITIAL_GAME_PID="${7:-0}"
TRAINER="${8:-}"
REOPEN_GUI="${9:-0}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=gameweld-heroic-common.sh
source "$script_dir/gameweld-heroic-common.sh"
LOG="$GAMEWELD_STATE/heroic-session-finalizer-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] finalizer start runner=%s appid=%s title=%s initial_game_pid=%s reopen_gui=%s\n' -1 "$RUNNER" "$APPID" "$TITLE" "$INITIAL_GAME_PID" "$REOPEN_GUI"
HINTS="$(build_game_exe_hints "$INSTALL" "$EXE" || true)"

trainer_pid() {
  [[ -n "$TRAINER" ]] || return 1
  local needle p pid comm cmd low
  needle="${TRAINER##*/}"; needle="${needle,,}"
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$comm$cmd" ]] || continue
    case "${comm,,}" in bash|sh|dash|zsh|fish|python|python3|proton|umu-run|timeout|bwrap|pv-bwrap|pressure-vessel*) continue ;; esac
    low="${cmd,,} ${comm,,}"
    [[ "$low" == *"$needle"* ]] && { printf '%s\n' "$pid"; return 0; }
  done
  return 1
}

# Wait until the actual gameplay process and trainer have both been absent for
# three consecutive checks. The first few seconds can contain bootstrap handoffs.
empty=0
while :; do
  target="$(find_live_game_target "$INSTALL" "$HINTS" || true)"
  tpid="$(trainer_pid || true)"
  if [[ -n "$target" || -n "$tpid" ]]; then
    empty=0
  else
    ((empty+=1))
    if (( empty >= 3 )); then break; fi
  fi
  sleep 2
done

printf '[%(%F %T)T] game and trainer exited; clearing Heroic in-memory compatibility cache\n' -1
# Recover the original on-disk config if the launcher script exited before its
# normal byte-exact restore point.
python3 "$HEROIC_PROVIDER" session-runner-restore "$APPID" || true

# Heroic caches GameConfig in memory. Stop the now-idle Heroic process so the
# next normal launch cannot accidentally reuse GE-Proton10-34 from this session.
heroic_stop_main_for_reload || true
if [[ "$REOPEN_GUI" == "1" ]]; then
  echo 'Heroic was open before GameWeld started the compatibility session; reopening it with the restored user configuration.'
  heroic_open_gui || true
fi
printf '[%(%F %T)T] Heroic compatibility-session finalizer complete\n' -1
