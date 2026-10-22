#!/usr/bin/env bash
set -Eeuo pipefail

APPID="${1:-}"
TRAINER="${2:-}"
shift 2 || true

[[ "$APPID" =~ ^[0-9]+$ ]] || { echo "Usage: gameweld-local-trainer.sh APPID /path/to/trainer.exe [args...]" >&2; exit 2; }
[[ -f "$TRAINER" ]] || { echo "Local trainer not found: $TRAINER" >&2; exit 3; }

STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$STATE"
LOG="$STATE/local-trainer-${APPID}.log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Local trainer launch: appid=%s trainer=%s\n' -1 "$APPID" "$TRAINER"

read_proc_env() {
  local pid="$1"
  [[ -r "/proc/$pid/environ" ]] || return 1
  cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n'
}

find_session() {
  local pid env compat tools proton item steamroot
  for p in /proc/[0-9]*; do
    pid="${p##*/}"
    env="$(read_proc_env "$pid" || true)"
    [[ "$env" == *"SteamAppId=$APPID"* || "$env" == *"SteamGameId=$APPID"* ]] || continue
    compat="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' | head -1)"
    [[ -n "$compat" ]] || continue
    tools="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' | head -1)"
    steamroot="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_CLIENT_INSTALL_PATH=//p' | head -1)"
    proton=""
    IFS=':' read -r -a parts <<< "$tools"
    for item in "${parts[@]}"; do
      [[ -x "$item/proton" ]] && { proton="$item/proton"; break; }
    done
    if [[ -z "$proton" ]]; then
      local q parent cmd
      q="$pid"
      for _ in {1..12}; do
        [[ -r "/proc/$q/stat" ]] || break
        cmd="$(tr '\0' ' ' < "/proc/$q/cmdline" 2>/dev/null || true)"
        if [[ "$cmd" =~ (^|[[:space:]])([^[:space:]]*/proton)([[:space:]]|$) ]]; then
          [[ -x "${BASH_REMATCH[2]}" ]] && proton="${BASH_REMATCH[2]}" && break
        fi
        parent="$(awk '{print $4}' "/proc/$q/stat" 2>/dev/null || true)"
        [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
        q="$parent"
      done
    fi
    [[ -n "$proton" && -x "$proton" ]] || continue
    printf '%s\t%s\t%s\t%s\n' "$pid" "$compat" "$proton" "$steamroot"
    return 0
  done
  return 1
}

session="$(find_session || true)"
if [[ -z "$session" ]]; then
  echo "Starting game normally through Steam..."
  env -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN -u GIO_LAUNCHED_DESKTOP_FILE -u GIO_LAUNCHED_DESKTOP_FILE_PID steam -applaunch "$APPID" >/dev/null 2>&1 &
  for _ in {1..120}; do
    sleep 1
    session="$(find_session || true)"
    [[ -n "$session" ]] && break
  done
fi

[[ -n "$session" ]] || { echo "Timed out waiting for an active Proton session for Steam AppID $APPID"; exit 4; }
IFS=$'\t' read -r GAMEPID COMPAT PROTON STEAMROOT <<< "$session"
echo "Detected game session PID=$GAMEPID"
echo "Compatdata: $COMPAT"
echo "Proton: $PROTON"

env_args=("STEAM_COMPAT_DATA_PATH=$COMPAT")
[[ -n "$STEAMROOT" ]] && env_args+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAMROOT")

# runinprefix joins the already-active compatdata/wineserver context without
# modifying Steam's launch options or starting Wand.
nohup env "${env_args[@]}" "$PROTON" runinprefix "$TRAINER" "$@" >>"$LOG" 2>&1 &
TPID=$!
echo "Local trainer launched (PID $TPID)."
echo "This provider is independent of Wand account/session limits."
