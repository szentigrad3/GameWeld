#!/usr/bin/env bash
set -Eeuo pipefail

# GameWeld 0.5.0 Test 49
# Start one resolved Steam non-Steam Windows shortcut through Steam's already-live
# LaunchAlongsideSteam pressure-vessel service, while injecting Proton's
# command-launcher service for this one launch only. Steam itself is never
# restarted and shortcuts.vdf is never modified.

APPID="${1:-}"
GAMEID="${2:-}"
COMPATDATA="${3:-}"
RESOLVED_TOOL="${4:-}"
TARGET="${5:-}"
STARTDIR="${6:-}"
STEAM_ROOT="${7:-}"
LAUNCH_OPTIONS="${8:-}"

[[ "$APPID" =~ ^[0-9]+$ ]] || { echo -e 'STATUS\terror\tInvalid shortcut AppID.'; exit 2; }
[[ "$GAMEID" =~ ^[0-9]+$ ]] || { echo -e 'STATUS\terror\tInvalid shortcut rungameid.'; exit 2; }
[[ -d "$COMPATDATA" ]] || { echo -e 'STATUS\terror\tResolved compatdata directory is missing.'; exit 3; }
COMPAT_ID="${COMPATDATA%/}"; COMPAT_ID="${COMPAT_ID##*/}"
[[ "$COMPAT_ID" == "$APPID" ]] || { echo -e 'STATUS\terror\tResolved compatdata does not belong to the selected Steam shortcut.'; exit 3; }
[[ -f "$TARGET" ]] || { echo -e 'STATUS\terror\tResolved shortcut target is missing.'; exit 3; }
[[ -n "$STARTDIR" && -d "$STARTDIR" ]] || STARTDIR="$(dirname -- "$TARGET")"

PROC_ROOT="${GAMEWELD_PROC_ROOT:-/proc}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$STATE"
LOG="$STATE/steam-shortcut-live-launch-${APPID}.log"
RESULT="$STATE/steam-shortcut-live-launch-${APPID}.result"

canon(){ readlink -f -- "$1" 2>/dev/null || printf '%s\n' "$1"; }
write_result(){ local tmp="$RESULT.tmp.$$"; printf '%s\n' "$@" >"$tmp"; mv -f -- "$tmp" "$RESULT"; }

proton_path(){
  local p="$RESOLVED_TOOL"
  [[ -x "$p/proton" ]] && { printf '%s\n' "$p/proton"; return 0; }
  [[ -x "$p" && "${p##*/}" == proton ]] && { printf '%s\n' "$p"; return 0; }
  return 1
}

read_proc_cmd(){
  local pid="$1"
  [[ -r "$PROC_ROOT/$pid/cmdline" ]] || return 1
  tr '\0' ' ' <"$PROC_ROOT/$pid/cmdline" 2>/dev/null
}

read_proc_env(){
  local pid="$1"
  [[ -r "$PROC_ROOT/$pid/environ" ]] || return 1
  tr '\0' '\n' <"$PROC_ROOT/$pid/environ" 2>/dev/null
}

global_bus_from_processes(){
  local p pid cmd envs bus
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/cmdline" ]] || continue
    pid="${p##*/}"; cmd="$(read_proc_cmd "$pid" || true)"
    [[ "$cmd" == *steam-runtime-launcher-service* ]] || continue
    [[ "$cmd" == *--alongside-steam* || "$cmd" == *LaunchAlongsideSteam* ]] || continue
    if [[ "$cmd" =~ --bus-name=([^[:space:]]+) ]]; then
      bus="${BASH_REMATCH[1]}"
      [[ "$bus" == com.steampowered.PressureVessel.LaunchAlongsideSteam.Instance* ]] && { printf '%s\n' "$bus"; return 0; }
    fi
    envs="$(read_proc_env "$pid" || true)"
    bus="$(sed -n 's/^SRT_LAUNCHER_SERVICE_ALONGSIDE_STEAM=//p' <<<"$envs" | head -1)"
    [[ "$bus" == com.steampowered.PressureVessel.LaunchAlongsideSteam.Instance* ]] && { printf '%s\n' "$bus"; return 0; }
  done
  return 1
}

global_bus(){
  local bus
  if [[ -n "${GAMEWELD_STEAM_GLOBAL_BUS:-}" ]]; then printf '%s\n' "$GAMEWELD_STEAM_GLOBAL_BUS"; return 0; fi
  bus="$(global_bus_from_processes || true)"
  [[ -n "$bus" ]] && { printf '%s\n' "$bus"; return 0; }
  if command -v busctl >/dev/null 2>&1; then
    bus="$(busctl --user --list --no-legend 2>/dev/null | awk '$1 ~ /^com\.steampowered\.PressureVessel\.LaunchAlongsideSteam\.Instance/ {print $1; exit}')"
    [[ -n "$bus" ]] && { printf '%s\n' "$bus"; return 0; }
  fi
  return 1
}

runtime_client(){
  local c root="$STEAM_ROOT"
  [[ -n "${GAMEWELD_STEAM_RUNTIME_CLIENT:-}" && -x "${GAMEWELD_STEAM_RUNTIME_CLIENT}" ]] && { printf '%s\n' "$GAMEWELD_STEAM_RUNTIME_CLIENT"; return 0; }
  local -a candidates=()
  [[ -n "$root" ]] && candidates+=(
    "$root/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt64/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt3/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt4/pressure-vessel/bin/steam-runtime-launch-client"
  )
  candidates+=(
    "$HOME/.local/share/Steam/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME/.steam/root/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
  )
  for c in "${candidates[@]}"; do [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }; done
  if [[ -n "$root" && -d "$root" ]]; then
    c="$(find "$root" -maxdepth 8 -type f -name steam-runtime-launch-client -perm -u+x -print -quit 2>/dev/null || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  fi
  return 1
}

extract_game_args(){
  # Preserve only arguments after %command%. Prefix wrappers/environment are not
  # replayed by the managed path because GameWeld is already replacing Steam's
  # launch wrapper. Never eval the user's Launch Options.
  python3 - "$LAUNCH_OPTIONS" <<'PY'
import shlex,sys
s=sys.argv[1]
if '%command%' not in s:
    raise SystemExit(0)
s=s.split('%command%',1)[1].strip()
if not s:
    raise SystemExit(0)
try: parts=shlex.split(s,posix=True)
except ValueError: parts=[]
for x in parts:
    print(x)
PY
}

PROTON="$(proton_path || true)"
BUS="$(global_bus || true)"
CLIENT="$(runtime_client || true)"
[[ -n "$PROTON" ]] || { write_result 'state=error' 'reason=proton-unresolved'; echo -e 'STATUS\terror\tResolved Proton executable is unavailable.'; exit 4; }
[[ -n "$BUS" ]] || { write_result 'state=error' 'reason=global-steam-runtime-bus-missing'; echo -e 'STATUS\tbus-missing\tSteam is running without a discoverable LaunchAlongsideSteam runtime service.'; exit 5; }
[[ -n "$CLIENT" ]] || { write_result 'state=error' 'reason=runtime-client-missing'; echo -e 'STATUS\tclient-missing\tsteam-runtime-launch-client could not be found.'; exit 6; }

mapfile -t GAME_ARGS < <(extract_game_args)
TOOL_ROOT="$(cd -- "$(dirname -- "$PROTON")" && pwd -P)"
LIBRARY_ROOT=""
case "$(canon "$COMPATDATA")" in
  */steamapps/compatdata/*) LIBRARY_ROOT="${COMPATDATA%/steamapps/compatdata/*}" ;;
esac

{
  printf '\n[%(%F %T)T] restart-free Steam shortcut launch\n' -1
  printf 'appid=%s\nrungameid=%s\ncompatdata=%s\nproton=%s\ntarget=%s\nstartdir=%s\nsteam_root=%s\n' "$APPID" "$GAMEID" "$COMPATDATA" "$PROTON" "$TARGET" "$STARTDIR" "$STEAM_ROOT"
  printf 'runtime_bus=%s\nruntime_client=%s\n' "$BUS" "$CLIENT"
  printf 'launch_mode=restart-free-live-runtime\nlauncher_service=proton\nsteam_restart=disabled\nshortcut_file_edit=disabled\n'
  printf 'stabilization_contract=exact-session-restart-free\n'
  if ((${#GAME_ARGS[@]})); then printf 'forwarded_game_args='; printf '%q ' "${GAME_ARGS[@]}"; printf '\n'; fi
  [[ -n "$LAUNCH_OPTIONS" ]] && printf 'source_launch_options=%s\n' "$LAUNCH_OPTIONS"
} >>"$LOG"

# Remove AppImage/runtime pollution before entering Steam's own live runtime.
# The game is launched through the already-running global pressure-vessel service,
# then Proton creates its per-app command-launcher service for this launch only.
ENVV=(
  "STEAM_COMPAT_LAUNCHER_SERVICE=proton"
  "STEAM_COMPAT_DATA_PATH=$COMPATDATA"
  "STEAM_COMPAT_TOOL_PATHS=$TOOL_ROOT"
  "STEAM_COMPAT_INSTALL_PATH=$STARTDIR"
  "SteamAppId=0"
  "SteamGameId=0"
  "STEAM_COMPAT_APP_ID=0"
  "GAMEWELD_MANAGED_STEAM_SHORTCUT=1"
  "GAMEWELD_STEAM_SHORTCUT_APPID=$APPID"
  "GAMEWELD_STEAM_SHORTCUT_GAMEID=$GAMEID"
)
[[ -n "$STEAM_ROOT" ]] && ENVV+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_ROOT")
[[ -n "$LIBRARY_ROOT" ]] && ENVV+=("STEAM_COMPAT_LIBRARY_PATHS=$LIBRARY_ROOT")

nohup env -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
  -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH \
  -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH \
  -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \
  "$CLIENT" --bus-name="$BUS" --directory "$STARTDIR" -- \
  env "${ENVV[@]}" "$PROTON" waitforexitandrun "$TARGET" "${GAME_ARGS[@]}" >>"$LOG" 2>&1 &
LAUNCH_PID=$!

write_result \
  'state=starting' \
  "appid=$APPID" \
  "rungameid=$GAMEID" \
  "compatdata=$COMPATDATA" \
  "runtime_bus=$BUS" \
  'launch_mode=restart-free-live-runtime' \
  "launcher_pid=$LAUNCH_PID" \
  "log=$LOG" \
  'summary=GameWeld started the selected shortcut through Steam’s already-running runtime service without restarting Steam or modifying shortcuts.vdf.'

printf 'STATUS\tstarted\tRestart-free Steam runtime launch started.\t%s\n' "$LOG"
