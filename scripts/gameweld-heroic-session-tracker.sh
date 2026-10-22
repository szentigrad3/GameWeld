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
LAUNCH_PATH="${9:-unknown}"
PROTON="${10:-}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=gameweld-heroic-common.sh
source "$script_dir/gameweld-heroic-common.sh"

safe="$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID")"
STATE_FILE="$GAMEWELD_STATE/heroic-managed-session-$safe.state"
LOG="$GAMEWELD_STATE/heroic-managed-session-$safe.log"
mkdir -p "$GAMEWELD_STATE"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] tracker start runner=%s appid=%s title=%s initial_game_pid=%s launch=%s\n' -1 "$RUNNER" "$APPID" "$TITLE" "$INITIAL_GAME_PID" "$LAUNCH_PATH"

HINTS="$(build_game_exe_hints "$INSTALL" "$EXE" || true)"
STARTED_EPOCH="$(date +%s)"

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

write_state() {
  local state="$1" gpid="$2" tpid="$3" gexe="$4" tmp
  tmp="$STATE_FILE.tmp.$$"
  {
    printf 'version=1\n'
    printf 'state=%s\n' "$state"
    printf 'runner=%s\n' "$RUNNER"
    printf 'appid=%s\n' "$APPID"
    printf 'title=%s\n' "$TITLE"
    printf 'game_pid=%s\n' "$gpid"
    printf 'trainer_pid=%s\n' "$tpid"
    printf 'game_exe=%s\n' "$gexe"
    printf 'install=%s\n' "$INSTALL"
    printf 'prefix=%s\n' "$PREFIX"
    printf 'trainer=%s\n' "$TRAINER"
    printf 'launch_path=%s\n' "$LAUNCH_PATH"
    printf 'proton=%s\n' "$PROTON"
    printf 'started_epoch=%s\n' "$STARTED_EPOCH"
    printf 'updated_epoch=%s\n' "$(date +%s)"
    printf 'tracker_pid=%s\n' "$$"
  } >"$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv -f "$tmp" "$STATE_FILE"
}

# Publish immediately so the UI can stop relying on Heroic's PLAY/PLAYING badge
# as soon as GameWeld owns a direct Legendary compatibility launch.
initial_exe="${EXE##*/}"
write_state running "$INITIAL_GAME_PID" 0 "$initial_exe"

missing_game=0
empty_both=0
while :; do
  # Resolve the trainer first so the generic install-path fallback can never
  # mistake a trainer stored next to the game (or whose pathname begins with
  # the game install directory) for the gameplay process after the game exits.
  tpid="$(trainer_pid || true)"; [[ -n "$tpid" ]] || tpid=0
  target="$(find_live_game_target "$INSTALL" "$HINTS" || true)"
  gpid=0; gexe=""
  if [[ -n "$target" ]]; then
    IFS=$'\t' read -r gpid gexe gcmd <<<"$target"
    trainer_base="${TRAINER##*/}"; trainer_base="${trainer_base,,}"
    if [[ "$tpid" != 0 && "$gpid" == "$tpid" ]] || [[ -n "$trainer_base" && "${gcmd,,}" == *"$trainer_base"* ]]; then
      gpid=0; gexe=""; target=""
    fi
  fi
  if [[ -n "$target" && "$gpid" != 0 ]]; then
    missing_game=0
  else
    ((missing_game+=1))
    # Avoid flickering to stopped during short bootstrap/process handoffs.
    if (( missing_game < 3 )) && [[ "$INITIAL_GAME_PID" =~ ^[0-9]+$ ]] && kill -0 "$INITIAL_GAME_PID" 2>/dev/null; then
      if [[ "$tpid" == 0 || "$INITIAL_GAME_PID" != "$tpid" ]]; then
        gpid="$INITIAL_GAME_PID"; gexe="$initial_exe"
      fi
    fi
  fi

  if [[ "$gpid" != 0 ]]; then
    write_state running "$gpid" "$tpid" "$gexe"
    empty_both=0
  elif [[ "$tpid" != 0 ]]; then
    write_state trainer-only 0 "$tpid" ""
    empty_both=0
  else
    ((empty_both+=1))
    if (( empty_both >= 3 )); then
      rm -f "$STATE_FILE"
      printf '[%(%F %T)T] game and trainer exited; tracker stopping\n' -1
      exit 0
    fi
  fi
  sleep 2
done
