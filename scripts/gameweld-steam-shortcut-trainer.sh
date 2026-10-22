#!/usr/bin/env bash
set -Eeuo pipefail

APPID="${1:-}"
GAMEID="${2:-}"
COMPATDATA="${3:-}"
RESOLVED_TOOL="${4:-}"
TARGET="${5:-}"
TRAINER="${6:-}"
shift 6 || true

[[ "$APPID" =~ ^[0-9]+$ ]] || { echo "Usage: gameweld-steam-shortcut-trainer.sh APPID GAMEID COMPATDATA PROTON_TOOL TARGET TRAINER [args...]" >&2; exit 2; }
[[ "$GAMEID" =~ ^[0-9]+$ ]] || { echo "Invalid Steam shortcut rungameid: $GAMEID" >&2; exit 2; }
[[ -n "$COMPATDATA" ]] || { echo "Steam shortcut compatdata path is required." >&2; exit 2; }
[[ -f "$TRAINER" ]] || { echo "Local trainer not found: $TRAINER" >&2; exit 3; }

STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$STATE"
LOG="$STATE/steam-shortcut-trainer-${APPID}.log"
SESSION_STATE="$STATE/steam-shortcut-session-${APPID}.txt"
SESSION_PHASE="starting"
SESSION_RESULT="running"
SESSION_GAME_PID=""
SESSION_TRAINER_PID=""
write_session_state() {
  local phase="${1:-$SESSION_PHASE}" result="${2:-$SESSION_RESULT}" tmp="${SESSION_STATE}.tmp.$$"
  SESSION_PHASE="$phase"; SESSION_RESULT="$result"
  {
    printf 'format=gameweld-steam-shortcut-session-v1\n'
    printf 'updated_at=%s\n' "$(date --iso-8601=seconds)"
    printf 'phase=%s\n' "$SESSION_PHASE"
    printf 'result=%s\n' "$SESSION_RESULT"
    printf 'appid=%s\n' "$APPID"
    printf 'rungameid=%s\n' "$GAMEID"
    printf 'compatdata=%s\n' "$COMPATDATA"
    printf 'resolved_tool=%s\n' "$RESOLVED_TOOL"
    printf 'target=%s\n' "$TARGET"
    printf 'trainer=%s\n' "$TRAINER"
    printf 'game_pid=%s\n' "$SESSION_GAME_PID"
    printf 'trainer_launcher_pid=%s\n' "$SESSION_TRAINER_PID"
  } >"$tmp"
  mv -f "$tmp" "$SESSION_STATE"
}
on_exit() {
  local rc=$?
  if (( rc != 0 )); then write_session_state "failed" "exit-$rc" || true; fi
}
trap on_exit EXIT
write_session_state "starting" "running"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Steam non-Steam shortcut trainer launch: appid=%s gameid=%s trainer=%s\n' -1 "$APPID" "$GAMEID" "$TRAINER"
echo "Expected compatdata: $COMPATDATA"
echo "Resolved Steam Play tool: ${RESOLVED_TOOL:-<none>}"
echo "Shortcut target: ${TARGET:-<unknown>}"

PROC_ROOT="${GAMEWELD_PROC_ROOT:-/proc}"
STEAM_BIN="${GAMEWELD_STEAM_BIN:-steam}"
WAIT_SECONDS="${GAMEWELD_SHORTCUT_SESSION_WAIT:-120}"

canon_path() {
  local p="$1"
  [[ -n "$p" ]] || return 1
  readlink -f -- "$p" 2>/dev/null || printf '%s\n' "$p"
}

EXPECTED_COMPAT="$(canon_path "$COMPATDATA")"
TARGET_BASE="${TARGET##*/}"

read_proc_env() {
  local pid="$1"
  [[ -r "$PROC_ROOT/$pid/environ" ]] || return 1
  cat "$PROC_ROOT/$pid/environ" 2>/dev/null | tr '\0' '\n'
}

read_proc_cmd() {
  local pid="$1"
  [[ -r "$PROC_ROOT/$pid/cmdline" ]] || return 1
  cat "$PROC_ROOT/$pid/cmdline" 2>/dev/null | tr '\0' ' '
}

proton_from_tools() {
  local tools="$1" item
  IFS=':' read -r -a parts <<< "$tools"
  for item in "${parts[@]}"; do
    [[ -x "$item/proton" ]] && { printf '%s\n' "$item/proton"; return 0; }
    [[ -x "$item" && "${item##*/}" == proton ]] && { printf '%s\n' "$item"; return 0; }
  done
  return 1
}

proton_from_parent_chain() {
  local pid="$1" q="$1" parent cmd candidate
  for _ in {1..16}; do
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    cmd="$(read_proc_cmd "$q" || true)"
    if [[ "$cmd" =~ (^|[[:space:]])([^[:space:]]*/proton)([[:space:]]|$) ]]; then
      candidate="${BASH_REMATCH[2]}"
      [[ -x "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
    fi
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
    q="$parent"
  done
  return 1
}

session_identity_matches() {
  local env="$1" cmd="$2" compat="$3" compat_canon appid gameid install
  compat_canon="$(canon_path "$compat")"
  [[ "$compat_canon" == "$EXPECTED_COMPAT" ]] || return 1

  appid="$(printf '%s\n' "$env" | sed -n 's/^SteamAppId=//p;s/^STEAM_COMPAT_APP_ID=//p' | head -1)"
  gameid="$(printf '%s\n' "$env" | sed -n 's/^SteamGameId=//p;s/^SteamGameId64=//p' | head -1)"
  install="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_INSTALL_PATH=//p' | head -1)"

  [[ "$appid" == "$APPID" || "$gameid" == "$APPID" || "$gameid" == "$GAMEID" ]] && return 0
  [[ -n "$TARGET" && -n "$install" && "$(canon_path "$install")" == "$(canon_path "${TARGET%/*}")" ]] && return 0
  [[ -n "$TARGET_BASE" && "$cmd" == *"$TARGET_BASE"* ]] && return 0
  return 1
}

find_session() {
  local p pid env compat tools proton steamroot cmd
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -e "$p" ]] || continue
    pid="${p##*/}"
    env="$(read_proc_env "$pid" || true)"
    [[ -n "$env" ]] || continue
    compat="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' | head -1)"
    [[ -n "$compat" ]] || continue
    cmd="$(read_proc_cmd "$pid" || true)"
    session_identity_matches "$env" "$cmd" "$compat" || continue

    tools="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' | head -1)"
    steamroot="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_CLIENT_INSTALL_PATH=//p' | head -1)"
    proton="$(proton_from_tools "$tools" || true)"
    [[ -n "$proton" ]] || proton="$(proton_from_parent_chain "$pid" || true)"
    if [[ -z "$proton" && -n "$RESOLVED_TOOL" && -x "$RESOLVED_TOOL/proton" ]]; then
      proton="$RESOLVED_TOOL/proton"
      echo "Live shortcut session found; using the pre-resolved Steam Play tool because the process environment did not expose its proton path."
    fi
    [[ -n "$proton" && -x "$proton" ]] || continue
    printf '%s\t%s\t%s\t%s\n' "$pid" "$compat" "$proton" "$steamroot"
    return 0
  done
  return 1
}

proc_or_parent_in_expected_session() {
  local pid="$1" q="$1" env compat parent
  for _ in {1..16}; do
    [[ -d "$PROC_ROOT/$q" ]] || break
    env="$(read_proc_env "$q" || true)"
    if [[ -n "$env" ]]; then
      compat="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' | head -1)"
      if [[ -n "$compat" && "$(canon_path "$compat")" == "$EXPECTED_COMPAT" ]]; then
        return 0
      fi
    fi
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 && "$parent" != "$q" ]] || break
    q="$parent"
  done
  return 1
}

find_actual_game_process() {
  local p pid cmd low base_low comm
  [[ -n "$TARGET_BASE" ]] || return 1
  base_low="${TARGET_BASE,,}"
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    cmd="$(read_proc_cmd "$pid" || true)"
    [[ -n "$cmd" ]] || continue
    low="${cmd,,}"
    [[ "$low" == *"$base_low"* ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    case "${comm,,}" in
      bash|sh|dash|zsh|fish|python|python3|steam|steamwebhelper|xdg-open|gio|flatpak|bwrap|timeout|proton|wineserver|steam-runtime-launch-client|steam-runtime-supervisor|steam-launch-wrapper|reaper|pv-bwrap) continue ;;
      pressure-vessel*) continue ;;
    esac
    # A Steam/pressure-vessel wrapper often includes the target EXE path in its
    # argv.  Do not mistake that command line for the actual Windows game.
    case "$low" in
      *gameweld-steam-shortcut-trainer*|*steam://rungameid/*|*steam-runtime-launch-client*|*steam-runtime-supervisor*|*steam-launch-wrapper*|*pressure-vessel*|*/reaper\ steamlaunch*|*wineboot.exe*|*wineserver*|*steamwebhelper*|*crashpad*|*crashreport*) continue ;;
    esac
    proc_or_parent_in_expected_session "$pid" || continue
    printf '%s\t%s\n' "$pid" "$cmd"
    return 0
  done
  return 1
}



window_process_is_game_candidate() {
  local pid="$1" gamepid="$2" q="$1" parent comm cmd
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [[ -d "$PROC_ROOT/$pid" ]] || return 1

  # The window may belong to the configured target itself or to a render/game
  # child spawned by it.  Accept descendants first.
  for _ in {1..24}; do
    [[ "$q" == "$gamepid" ]] && return 0
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 && "$parent" != "$q" ]] || break
    q="$parent"
  done

  # Wine can expose the top-level window from a sibling process.  It must still
  # belong to the exact compatdata session and not be a known bootstrap/helper.
  proc_or_parent_in_expected_session "$pid" || return 1
  comm="$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null || true)"
  cmd="$(read_proc_cmd "$pid" || true)"
  case "${comm,,}" in
    steam|steamwebhelper|pressure-vessel*|proton|wineserver|services.exe|explorer.exe|rpcss.exe|plugplay.exe|svchost.exe) return 1 ;;
  esac
  case "${cmd,,}" in
    *steamwebhelper*|*pressure-vessel*|*wineboot.exe*|*wineserver*|*crashpad*|*crashreport*) return 1 ;;
  esac
  return 0
}

x11_window_ready_for_game() {
  local gamepid="$1" root_out wid pid info geom width height state
  [[ "${GAMEWELD_SHORTCUT_X11_WINDOW_BARRIER:-auto}" != 0 ]] || return 1
  [[ -n "${DISPLAY:-}" ]] || return 1
  command -v xprop >/dev/null 2>&1 || return 1
  command -v xwininfo >/dev/null 2>&1 || return 1

  root_out="$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null || xprop -root _NET_CLIENT_LIST 2>/dev/null || true)"
  [[ -n "$root_out" ]] || return 1
  while read -r wid; do
    [[ -n "$wid" ]] || continue
    info="$(xprop -id "$wid" _NET_WM_PID 2>/dev/null || true)"
    pid="$(sed -n 's/.*= *\([0-9][0-9]*\).*/\1/p' <<< "$info" | head -1)"
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    window_process_is_game_candidate "$pid" "$gamepid" || continue
    geom="$(xwininfo -id "$wid" 2>/dev/null || true)"
    width="$(sed -n 's/^ *Width: *\([0-9][0-9]*\).*/\1/p' <<< "$geom" | head -1)"
    height="$(sed -n 's/^ *Height: *\([0-9][0-9]*\).*/\1/p' <<< "$geom" | head -1)"
    state="$(sed -n 's/^ *Map State: *//p' <<< "$geom" | head -1)"
    [[ "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]] || continue
    [[ "$width" -ge "${GAMEWELD_SHORTCUT_MIN_WINDOW_WIDTH:-320}" && "$height" -ge "${GAMEWELD_SHORTCUT_MIN_WINDOW_HEIGHT:-200}" ]] || continue
    [[ -z "$state" || "$state" == "IsViewable" ]] || continue
    printf '%s\t%s\t%s\t%s\n' "$wid" "$pid" "$width" "$height"
    return 0
  done < <(grep -oE '0x[0-9a-fA-F]+' <<< "$root_out" | awk '!seen[$0]++')
  return 1
}

wait_for_game_visible_or_stable() {
  local gamepid="$1" gcmd="$2" second ready stable_seconds window_wait render_settle
  local winid winpid winw winh key current_key="" stable_window_seconds=0
  stable_seconds="${GAMEWELD_SHORTCUT_GAME_READY_STABLE_SECONDS:-12}"
  window_wait="${GAMEWELD_SHORTCUT_GAME_WINDOW_WAIT_SECONDS:-60}"
  render_settle="${GAMEWELD_SHORTCUT_GAME_WINDOW_RENDER_SETTLE_SECONDS:-12}"

  # A mapped fullscreen window is not necessarily a rendered/ready game.  Some
  # Proton titles create a black bootstrap surface first.  Require the same
  # exact game-window owner to remain mapped for a sustained grace period; if
  # the bootstrap window is replaced, restart the grace period for the new one.
  if [[ "${GAMEWELD_SHORTCUT_X11_WINDOW_BARRIER:-auto}" != 0 && -n "${DISPLAY:-}" ]] && command -v xprop >/dev/null 2>&1 && command -v xwininfo >/dev/null 2>&1; then
    [[ "$render_settle" =~ ^[0-9]+$ ]] || render_settle=12
    (( render_settle > 0 )) || render_settle=1
    for ((second=0; second<window_wait; second++)); do
      [[ -d "$PROC_ROOT/$gamepid" ]] || return 1
      ready="$(x11_window_ready_for_game "$gamepid" || true)"
      if [[ -n "$ready" ]]; then
        IFS=$'\t' read -r winid winpid winw winh <<< "$ready"
        key="$winid:$winpid"
        if [[ "$key" != "$current_key" ]]; then
          current_key="$key"
          stable_window_seconds=0
          echo "Visible Steam shortcut game window detected: window=$winid pid=$winpid size=${winw}x${winh}; requiring ${render_settle}s stable render-settle before trainer handoff." >&2
        fi
        stable_window_seconds=$((stable_window_seconds+1))
        if (( stable_window_seconds >= render_settle )); then
          echo "Steam shortcut game window remained mapped with the same owner for ${render_settle}s; render-settle barrier passed." >&2
          return 0
        fi
      else
        if (( stable_window_seconds > 0 )); then
          echo "Startup game window disappeared or changed before render-settle completed; waiting for the final game window." >&2
        fi
        current_key=""
        stable_window_seconds=0
      fi
      if (( second > 0 && second % 10 == 0 )); then
        echo "Waiting for the final stable Steam shortcut game window (${second}s/${window_wait}s; stable=${stable_window_seconds}s/${render_settle}s)..." >&2
      fi
      sleep 1
    done
    echo "No stable mapped X11/XWayland game window completed the render-settle barrier. Falling back to a continuous game-process readiness grace period." >&2
  fi

  [[ "$stable_seconds" =~ ^[0-9]+$ ]] || stable_seconds=12
  for ((second=0; second<stable_seconds; second++)); do
    [[ -d "$PROC_ROOT/$gamepid" ]] || return 1
    sleep 1
  done
  echo "Game process remained alive for ${stable_seconds}s readiness grace period." >&2
  return 0
}
wait_for_actual_game_process() {
  local second found settled settle_seconds="${GAMEWELD_SHORTCUT_GAME_SETTLE_SECONDS:-3}"
  for ((second=0; second<WAIT_SECONDS; second++)); do
    found="$(find_actual_game_process || true)"
    if [[ -n "$found" ]]; then
      IFS=$'\t' read -r gp gcmd <<< "$found"
      echo "Actual Steam shortcut game process detected: PID=$gp target=$TARGET_BASE" >&2
      # Steam/Proton bootstrap processes can appear before the Windows game is
      # actually established.  Require the configured shortcut target first,
      # then give it a short settle window before the trainer is started.
      if [[ "$settle_seconds" =~ ^[0-9]+$ && "$settle_seconds" -gt 0 ]]; then
        sleep "$settle_seconds"
        settled="$(find_actual_game_process || true)"
        if [[ -n "$settled" ]]; then
          found="$settled"
        elif [[ -d "$PROC_ROOT/$gp" ]]; then
          # The exact process is still alive even if /proc enumeration raced.
          found="$gp"$'\t'"$gcmd"
        else
          # A bootstrap EXE vanished during settling.  Keep waiting rather than
          # launching the trainer ahead of the eventual gameplay process.
          continue
        fi
      fi
      printf '%s\n' "$found"
      return 0
    fi
    if (( second > 0 && second % 10 == 0 )); then
      echo "Steam shortcut Proton session is live, but the actual Windows target '$TARGET_BASE' is not visible yet (${second}s/${WAIT_SECONDS}s)..." >&2
    fi
    sleep 1
  done
  return 1
}

session="$(find_session || true)"
if [[ -z "$session" ]]; then
  echo "No live shortcut Proton session found. Asking Steam to launch rungameid $GAMEID..."
  if [[ "${GAMEWELD_SKIP_STEAM_LAUNCH:-0}" != 1 ]]; then
    env -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN -u GIO_LAUNCHED_DESKTOP_FILE -u GIO_LAUNCHED_DESKTOP_FILE_PID \
      "$STEAM_BIN" "steam://rungameid/$GAMEID" >/dev/null 2>&1 &
  fi
  for ((i=0;i<WAIT_SECONDS;i++)); do
    sleep 1
    session="$(find_session || true)"
    [[ -n "$session" ]] && break
  done
fi

[[ -n "$session" ]] || { echo "Timed out waiting for the live Steam non-Steam shortcut Proton session (AppID $APPID / rungameid $GAMEID)."; exit 4; }
IFS=$'\t' read -r GAMEPID LIVE_COMPAT PROTON STEAMROOT <<< "$session"

LIVE_COMPAT_CANON="$(canon_path "$LIVE_COMPAT")"
[[ "$LIVE_COMPAT_CANON" == "$EXPECTED_COMPAT" ]] || { echo "Refusing trainer handoff: live compatdata '$LIVE_COMPAT' does not match resolved shortcut compatdata '$COMPATDATA'."; exit 5; }

echo "Validated live shortcut session PID=$GAMEPID"
SESSION_GAME_PID="$GAMEPID"
write_session_state "live-session-validated" "running"
echo "Live compatdata: $LIVE_COMPAT"
echo "Live Proton: $PROTON"
echo "Handoff mode: same live Steam shortcut Proton prefix via runinprefix"

echo "Live Proton session validated. Waiting for the actual shortcut game executable before trainer handoff..."
GAME_TARGET="$(wait_for_actual_game_process || true)"
[[ -n "$GAME_TARGET" ]] || { echo "Timed out waiting for the actual Steam shortcut Windows game executable '$TARGET_BASE'. Trainer was not launched early."; exit 6; }
IFS=$'\t' read -r ACTUAL_GAME_PID ACTUAL_GAME_CMD <<< "$GAME_TARGET"
echo "Actual game executable barrier passed: PID=$ACTUAL_GAME_PID cmd=$ACTUAL_GAME_CMD"
SESSION_GAME_PID="$ACTUAL_GAME_PID"
write_session_state "game-executable-detected" "running"
echo "Waiting for visible/settled game readiness before trainer handoff..."
wait_for_game_visible_or_stable "$ACTUAL_GAME_PID" "$ACTUAL_GAME_CMD" || { echo "Game process disappeared before it reached the visible/settled readiness barrier. Trainer was not launched early."; exit 7; }
echo "Game-visible readiness barrier passed: PID=$ACTUAL_GAME_PID"
write_session_state "game-visible-ready" "running"

env_args=("STEAM_COMPAT_DATA_PATH=$LIVE_COMPAT")
[[ -n "$STEAMROOT" ]] && env_args+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAMROOT")
env_args+=("GAMEWELD_STEAM_SHORTCUT_APPID=$APPID" "GAMEWELD_STEAM_SHORTCUT_GAMEID=$GAMEID")

nohup env "${env_args[@]}" "$PROTON" runinprefix "$TRAINER" "$@" >>"$LOG" 2>&1 &
TPID=$!
SESSION_TRAINER_PID="$TPID"
write_session_state "trainer-launched" "success"
echo "Steam shortcut trainer launched through the validated live prefix (launcher PID $TPID)."
echo "No second compatdata prefix or alternate Proton runtime was created by GameWeld."
