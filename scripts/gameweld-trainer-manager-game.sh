#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-plan}"; EXE="${2:-}"; PROVIDER="${3:-}"; RUNNER="${4:-}"; APPID="${5:-}"; GAME_KEY="${6:-}"; TITLE="${7:-}"; INSTALL="${8:-}"; GAME_EXE="${9:-}"; PREFIX="${10:-}"; WINE_TYPE="${11:-}"; WINE_BIN="${12:-}"; COMPATDATA="${13:-}"; LAUNCH_ID="${14:-}"
HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
DATA="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/gameweld"
STATE="${XDG_STATE_HOME:-$HOME_DIR/.local/state}/gameweld"
PROC_ROOT="${GAMEWELD_PROC_ROOT:-/proc}"
mkdir -p "$STATE"

sanitize_id(){ printf '%s' "$1" | tr -c '[:alnum:]_.-' '_'; }
canon(){ readlink -f -- "$1" 2>/dev/null || printf '%s' "$1"; }
read_env(){ [[ -r "$PROC_ROOT/$1/environ" ]] || return 1; tr '\0' '\n' < "$PROC_ROOT/$1/environ" 2>/dev/null; }
read_cmd(){ [[ -r "$PROC_ROOT/$1/cmdline" ]] || return 1; tr '\0' ' ' < "$PROC_ROOT/$1/cmdline" 2>/dev/null; }

manager_identity(){
  local exe="$1" dir low
  [[ -f "$exe" ]] || return 1
  dir="$(cd -- "$(dirname -- "$exe")" && pwd -P)"; low="${exe##*/}"; low="${low,,}"
  case "$low" in
    aurora.exe)
      [[ -f "$dir/WebView2Loader.dll" && -f "$dir/CheatHappensOverlay_x64.dll" && -f "$dir/Bootstrapper64.dll" ]] || return 1
      printf 'cheat-happens-aurora\tCheat Happens Aurora\n';;
    cheatevolution.exe)
      [[ -f "$dir/lua53-64.dll" && -f "$dir/Launcher.exe" && -f "$dir/speedhack-x86_64.dll" ]] || return 1
      printf 'cheat-evolution\tCheat Evolution\n';;
    *) return 1;;
  esac
}

[[ -n "$EXE" ]] || { echo 'Manager executable path is required.' >&2; exit 2; }
EXE="$(canon "$EXE")"; IDENT="$(manager_identity "$EXE" || true)"
[[ -n "$IDENT" ]] || { echo 'The selected executable is not a validated GameWeld manager package.' >&2; exit 3; }
IFS=$'\t' read -r MANAGER_ID MANAGER_LABEL <<<"$IDENT"
EXE_DIR="$(cd -- "$(dirname -- "$EXE")" && pwd -P)"
SAFE_KEY="$(sanitize_id "${GAME_KEY:-${PROVIDER}-${APPID}}")"
LOG="$STATE/manager-game-$(sanitize_id "$MANAGER_ID")-$SAFE_KEY.log"
RESULT="$STATE/manager-game-$(sanitize_id "$MANAGER_ID")-$SAFE_KEY.result"
DEDICATED_ROOT="$DATA/manager-prefixes/$MANAGER_ID"
DEDICATED_PFX="$DEDICATED_ROOT/pfx"

write_result(){ local f="$1"; shift; local t="$f.tmp.$$"; printf '%s\n' "$@" > "$t"; mv -f -- "$t" "$f"; }

proc_has_marker(){
  local needle="$1" p envs
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    envs="$(tr '\0' '\n' < "$p/environ" 2>/dev/null || true)"
    grep -Fqx "$needle" <<<"$envs" && return 0
  done
  return 1
}

manager_process_name(){
  case "$MANAGER_ID" in
    cheat-happens-aurora) printf 'aurora.exe\n' ;;
    cheat-evolution) printf 'cheatevolution.exe\n' ;;
    *) return 1 ;;
  esac
}

proc_is_real_manager(){
  local pid="$1" want cmd comm want15
  want="$(manager_process_name || true)"; [[ -n "$want" ]] || return 1
  cmd="$(read_cmd "$pid" 2>/dev/null || true)"; cmd="${cmd,,}"
  comm="$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null || true)"; comm="${comm,,}"; comm="${comm//$'\n'/}"
  want15="${want:0:15}"
  # Wine/Proton service processes inherit the launch environment.  They are not
  # proof that the manager UI is still alive.  Require the actual Windows EXE
  # to be visible in cmdline/comm before suppressing a new launch.
  [[ "$cmd" == *"$want"* || "$comm" == "$want" || "$comm" == "$want15" ]]
}

proc_in_expected_session(){
  local envs="$1" expected ep
  case "$PROVIDER" in
    steam|steam-shortcut) expected="${COMPATDATA:-}" ;;
    heroic) expected="${PREFIX:-}" ;;
    *) expected="" ;;
  esac
  [[ -n "$expected" ]] || return 0
  expected="$(canon "$expected")"
  local expected_pfx="$(canon "$expected/pfx")"
  while IFS= read -r ep; do
    [[ -n "$ep" ]] || continue
    ep="$(canon "$ep")"
    [[ "$ep" == "$expected" || "$ep" == "$expected_pfx" ]] && return 0
  done < <(sed -n 's/^WINEPREFIX=//p;s/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs")
  return 1
}

attached_manager_pid(){
  local p pid envs
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    envs="$(tr '\0' '\n' < "$p/environ" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_MANAGER_ID=$MANAGER_ID" <<<"$envs" || continue
    grep -Fqx "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" <<<"$envs" || continue
    proc_is_real_manager "$pid" || continue
    proc_in_expected_session "$envs" || continue
    printf '%s\n' "$pid"
    return 0
  done
  return 1
}
attached_manager_active(){ attached_manager_pid >/dev/null; }
standalone_manager_active(){
  local p pid envs
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    envs="$(tr '\0' '\n' < "$p/environ" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_MANAGER_ID=$MANAGER_ID" <<<"$envs" || continue
    grep -Fqx "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" <<<"$envs" && continue
    proc_is_real_manager "$pid" || continue
    { grep -Fqx "WINEPREFIX=$DEDICATED_PFX" <<<"$envs" || grep -Fqx "STEAM_COMPAT_DATA_PATH=$DEDICATED_ROOT" <<<"$envs"; } && return 0
  done
  return 1
}

proton_from_parent_chain(){
  local q="$1" cmd parent cand
  for _ in {1..16}; do
    [[ -r "$PROC_ROOT/$q/cmdline" ]] || break
    cmd="$(read_cmd "$q" || true)"
    if [[ "$cmd" =~ (^|[[:space:]])([^[:space:]]*/proton)([[:space:]]|$) ]]; then cand="${BASH_REMATCH[2]}"; [[ -x "$cand" ]] && { printf '%s\n' "$cand"; return 0; }; fi
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"; [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break; q="$parent"
  done
  return 1
}

proc_looks_like_real_windows_app(){
  local pid="$1" cmd comm low
  cmd="$(read_cmd "$pid" 2>/dev/null || true)"; low="${cmd,,}"
  comm="$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null || true)"; comm="${comm,,}"; comm="${comm//$'\n'/}"
  # A compatdata prefix can remain alive after the game exits.  Never use the
  # inherited Steam/Heroic environment from Wine infrastructure as proof that
  # the game itself is running.
  case "$low $comm" in
    *wineserver*|*services.exe*|*winedevice.exe*|*plugplay.exe*|*rpcss.exe*|*svchost.exe*|*explorer.exe*|*conhost.exe*|*rundll32.exe*|*aurora.exe*|*cheatevolution.exe*) return 1 ;;
  esac
  [[ "$low" == *.exe* || "$comm" == *.exe ]] || return 1
  return 0
}

find_steam_session(){
  local p pid envs compat tools steamroot proton item cmd expected base
  expected="$(canon "${COMPATDATA:-/nonexistent}")"; base="${GAME_EXE##*/}"; base="${base,,}"
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"; envs="$(read_env "$pid" || true)"; [[ -n "$envs" ]] || continue
    compat="$(sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs" | head -1)"; [[ -n "$compat" ]] || continue
    cmd="$(read_cmd "$pid" || true)"
    if [[ "$PROVIDER" == steam-shortcut ]]; then
      [[ -n "$COMPATDATA" && "$(canon "$compat")" == "$expected" ]] || continue
      # Steam shortcut service processes inherit the shortcut's AppId and
      # compatdata environment.  The exact configured Windows target must be
      # present before a manager is allowed to join the session.
      [[ -n "$base" && "${cmd,,}" == *"$base"* ]] || continue
    else
      grep -Eq "^(SteamAppId|SteamGameId|STEAM_COMPAT_APP_ID)=${APPID}$" <<<"$envs" || continue
      proc_looks_like_real_windows_app "$pid" || continue
    fi
    tools="$(sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' <<<"$envs" | head -1)"; steamroot="$(sed -n 's/^STEAM_COMPAT_CLIENT_INSTALL_PATH=//p' <<<"$envs" | head -1)"; proton=""
    IFS=':' read -r -a parts <<<"$tools"; for item in "${parts[@]}"; do [[ -x "$item/proton" ]] && { proton="$item/proton"; break; }; done
    [[ -n "$proton" ]] || proton="$(proton_from_parent_chain "$pid" || true)"
    if [[ -z "$proton" && -n "${WINE_BIN:-}" && -x "$WINE_BIN" && "${WINE_BIN##*/}" == proton ]]; then proton="$WINE_BIN"; fi
    [[ -n "$proton" && -x "$proton" ]] || continue
    printf '%s\t%s\t%s\t%s\n' "$pid" "$compat" "$proton" "$steamroot"; return 0
  done
  return 1
}

heroic_game_live(){
  local p pid envs cmd ep base wantpfx
  base="${GAME_EXE##*/}"; base="${base,,}"; wantpfx="$(canon "${PREFIX:-/nonexistent}")"
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"; envs="$(read_env "$pid" || true)"; cmd="$(read_cmd "$pid" || true)"
    # If Heroic reported the actual game EXE, require that exact executable.
    # Prefix services may retain HEROIC_APP_NAME after the visible game exits.
    if [[ -n "$base" ]]; then
      [[ "${cmd,,}" == *"$base"* ]] || continue
    else
      proc_looks_like_real_windows_app "$pid" || continue
    fi
    if grep -Fqx "HEROIC_APP_NAME=$APPID" <<<"$envs"; then printf '%s\n' "$pid"; return 0; fi
    ep="$(sed -n 's/^WINEPREFIX=//p;s/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs" | head -1)"
    [[ -n "$ep" && -n "$PREFIX" && "$(canon "$ep")" == "$wantpfx" ]] || continue
    printf '%s\n' "$pid"; return 0
  done
  return 1
}

SESSION_KIND=''; SESSION_RUNTIME=''; SESSION_PREFIX=''; SESSION_PID=''; SESSION_STEAMROOT=''; STATUS=''; REASON=''
resolve_game_session(){
  local s
  if attached_manager_active; then STATUS=running; REASON='This manager is already active in the selected game compatibility session.'; return 0; fi
  if standalone_manager_active; then STATUS=standalone-running; REASON='The manager is already running in its dedicated standalone prefix. Close that standalone instance before attaching it to a game session.'; return 0; fi
  case "$PROVIDER" in
    steam|steam-shortcut)
      s="$(find_steam_session || true)"
      if [[ -n "$s" ]]; then IFS=$'\t' read -r SESSION_PID SESSION_PREFIX SESSION_RUNTIME SESSION_STEAMROOT <<<"$s"; SESSION_KIND=proton; STATUS=ready; REASON='Live Steam Proton session found. GameWeld will launch the manager with Proton runinprefix in this exact compatdata/wineserver session; no trainer assignment is created.'; else STATUS=game-not-running; REASON='No matching live Steam Proton session is active. Start the selected game first, then launch the manager for that game.'; fi
      ;;
    heroic)
      SESSION_PID="$(heroic_game_live || true)"
      if [[ -z "$SESSION_PID" ]]; then STATUS=game-not-running; REASON='No live Heroic Windows game process was found for the selected title. Start the game first, then launch the manager for that game.'
      elif [[ -z "$PREFIX" || -z "$WINE_BIN" || ! -x "$WINE_BIN" ]]; then STATUS=runtime-unresolved; REASON='The game is running, but its exact Heroic Wine/Proton runner or prefix could not be resolved safely.'
      else SESSION_PREFIX="$PREFIX"; SESSION_RUNTIME="$WINE_BIN"; case "${WINE_TYPE,,}" in proton|proton-ge|ge-proton|umu) SESSION_KIND=proton;; *) SESSION_KIND=wine;; esac; STATUS=ready; REASON='Live Heroic game session found. GameWeld will launch the manager with the selected game’s exact Wine/Proton runner and prefix; no trainer assignment is created.'; fi
      ;;
    *) STATUS=unsupported; REASON='This game provider does not have a validated live-session manager attachment recipe.';;
  esac
}
resolve_game_session

emit_plan(){
  printf 'MANAGER_GAME_PLAN\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$MANAGER_ID" "$MANAGER_LABEL" "$STATUS" "${SESSION_KIND:-—}" "${SESSION_RUNTIME:-—}" "${SESSION_PREFIX:-—}" "${SESSION_PID:-—}" "$LOG" "$GAME_KEY" "$TITLE" "$REASON"
}
stop_attached_manager(){
  local p pid envs cmd comm low killed=0
  local -a targets=()
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    envs="$(read_env "$pid" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_MANAGER_ID=$MANAGER_ID" <<<"$envs" || continue
    grep -Fqx "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" <<<"$envs" || continue
    proc_in_expected_session "$envs" || continue
    cmd="$(read_cmd "$pid" 2>/dev/null || true)"; comm="$(cat "$p/comm" 2>/dev/null || true)"; low="${cmd,,} ${comm,,}"
    case "$low" in
      *wineserver*|*services.exe*|*explorer.exe*|*rpcss.exe*|*plugplay.exe*|*svchost.exe*|*wineboot.exe*) continue ;;
    esac
    targets+=("$pid")
  done
  if ((${#targets[@]}==0)); then
    write_result "$RESULT" 'state=not-running' "manager=$MANAGER_LABEL" "game=$TITLE" "game_key=$GAME_KEY" 'summary=No live manager process was found for the selected game session.'
    return 0
  fi
  printf 'stop_targets=%s
' "${targets[*]}"
  kill -TERM "${targets[@]}" 2>/dev/null || true
  for _ in {1..30}; do
    local any=0
    for pid in "${targets[@]}"; do kill -0 "$pid" 2>/dev/null && any=1; done
    ((any==0)) && break
    sleep 0.1
  done
  local -a remain=()
  for pid in "${targets[@]}"; do kill -0 "$pid" 2>/dev/null && remain+=("$pid"); done
  ((${#remain[@]})) && kill -KILL "${remain[@]}" 2>/dev/null || true
  write_result "$RESULT" 'state=stopped-by-user' "manager=$MANAGER_LABEL" "game=$TITLE" "game_key=$GAME_KEY" "provider=$PROVIDER" "prefix=${SESSION_PREFIX:-${PREFIX:-}}" "log=$LOG" 'summary=GameWeld stopped the trainer manager without terminating the game compatibility session.'
  return 0
}

case "$ACTION" in
  plan|status) emit_plan; exit 0;;
  stop)
    exec >>"$LOG" 2>&1
    printf '
[%(%F %T)T] manager=%s id=%s action=game-stop game=%s game_key=%s
' -1 "$MANAGER_LABEL" "$MANAGER_ID" "$TITLE" "$GAME_KEY"
    stop_attached_manager
    exit 0
    ;;
  launch) ;;
  *) echo "Unknown action: $ACTION" >&2; exit 2;;
esac

if [[ "$STATUS" == running ]]; then exit 0; fi
if [[ "$STATUS" != ready ]]; then emit_plan >&2; exit 4; fi

clean_env=(env -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN -u GIO_LAUNCHED_DESKTOP_FILE -u GIO_LAUNCHED_DESKTOP_FILE_PID)
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] manager=%s id=%s action=game-attach\n' -1 "$MANAGER_LABEL" "$MANAGER_ID"
printf 'game_key=%s\ngame=%s\nprovider=%s\nrunner=%s\nappid=%s\ngame_pid=%s\nmanager_exe=%s\nmanager_working_dir=%s\nsession_kind=%s\nsession_runtime=%s\nsession_prefix=%s\n' "$GAME_KEY" "$TITLE" "$PROVIDER" "$RUNNER" "$APPID" "$SESSION_PID" "$EXE" "$EXE_DIR" "$SESSION_KIND" "$SESSION_RUNTIME" "$SESSION_PREFIX"

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ -n "${APPDIR:-}" && -r "${APPDIR}/usr/libexec/gameweld-heroic-common.sh" ]]; then COMMON="${APPDIR}/usr/libexec/gameweld-heroic-common.sh"; else COMMON="$script_dir/gameweld-heroic-common.sh"; fi

proton_wine_from_runtime(){
  local proton="$1" root wine
  [[ -n "$proton" ]] || return 1
  root="$(cd -- "$(dirname -- "$proton")" 2>/dev/null && pwd -P || dirname -- "$proton")"
  for wine in "$root/files/bin/wine" "$root/files/bin/wine64"; do
    [[ -x "$wine" ]] && { printf '%s\n' "$wine"; return 0; }
  done
  return 1
}


same_mount_namespace(){
  local a="$1" b="$2" na nb
  na="$(readlink "$PROC_ROOT/$a/ns/mnt" 2>/dev/null || true)"
  nb="$(readlink "$PROC_ROOT/$b/ns/mnt" 2>/dev/null || true)"
  [[ -n "$na" && "$na" == "$nb" ]]
}

pressure_vessel_bus_from_process(){
  local pid="$1" arg
  [[ -r "$PROC_ROOT/$pid/cmdline" ]] || return 1
  while IFS= read -r -d '' arg; do
    case "$arg" in
      --bus-name=*) printf '%s\n' "${arg#--bus-name=}"; return 0 ;;
    esac
  done < "$PROC_ROOT/$pid/cmdline"
  return 1
}

pressure_vessel_bus_from_environment(){
  local pid="$1" envs value key
  envs="$(read_env "$pid" 2>/dev/null || true)"
  [[ -n "$envs" ]] || return 1
  for key in SRT_LAUNCHER_SERVICE SRT_LAUNCHER_SERVICE_ALONGSIDE_STEAM STEAM_RUNTIME_LAUNCHER_SERVICE; do
    value="$(sed -n "s/^${key}=//p" <<<"$envs" | head -1)"
    case "$value" in
      :[0-9]*|com.steampowered.*) printf '%s\n' "$value"; return 0 ;;
    esac
  done
  return 1
}

runtime_bus_present(){
  local bus="$1" out
  [[ -n "$bus" ]] || return 1
  if command -v busctl >/dev/null 2>&1; then
    timeout 2 busctl --user status "$bus" >/dev/null 2>&1 && return 0
  fi
  if command -v gdbus >/dev/null 2>&1; then
    out="$(timeout 2 gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner "$bus" 2>/dev/null || true)"
    [[ "$out" == *true* ]] && return 0
  fi
  # If neither inspector exists, let steam-runtime-launch-client be the probe.
  ! command -v busctl >/dev/null 2>&1 && ! command -v gdbus >/dev/null 2>&1
}

runtime_appid_candidates(){
  local envs value key
  # Prefer GameWeld's resolved Steam shortcut ID. For non-Steam Proton sessions
  # the Windows process can expose SteamAppId=0 even though Steam assigned the
  # shortcut a real compatibility ID.
  [[ "$APPID" =~ ^[0-9]+$ ]] && printf '%s\n' "$APPID"
  envs="$(read_env "$SESSION_PID" 2>/dev/null || true)"
  for key in STEAM_COMPAT_APP_ID SteamGameId SteamAppId; do
    value="$(sed -n "s/^${key}=//p" <<<"$envs" | head -1)"
    [[ "$value" =~ ^[0-9]+$ ]] && printf '%s\n' "$value"
  done
}

runtime_bus_candidates(){
  local id
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    if command -v busctl >/dev/null 2>&1; then
      busctl --user --list --no-legend 2>/dev/null | awk -v id="$id" '$1 ~ ("^com\\.steampowered\\.App" id "($|\\.)") {print $1}' || true
    fi
    printf 'com.steampowered.App%s\n' "$id"
  done < <(runtime_appid_candidates | awk 'NF && !seen[$0]++')
}

runtime_bus_owner_pid(){
  local bus="$1" pid=""
  [[ -n "$bus" ]] || return 1
  if command -v busctl >/dev/null 2>&1; then
    pid="$(busctl --user --list --no-legend 2>/dev/null | awk -v b="$bus" '$1==b && $2 ~ /^[0-9]+$/ {print $2; exit}' || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && { printf '%s\n' "$pid"; return 0; }
    pid="$(timeout 2 busctl --user status "$bus" 2>/dev/null | awk '/^[[:space:]]*PID:/ {print $2; exit}' || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && { printf '%s\n' "$pid"; return 0; }
  fi
  if command -v gdbus >/dev/null 2>&1; then
    pid="$(timeout 2 gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.GetConnectionUnixProcessID "$bus" 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && { printf '%s\n' "$pid"; return 0; }
  fi
  return 1
}

runtime_bus_owner_matches_game(){
  local bus="$1" pid envs
  pid="$(runtime_bus_owner_pid "$bus" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  same_mount_namespace "$SESSION_PID" "$pid" && return 0
  envs="$(read_env "$pid" 2>/dev/null || true)"
  if grep -Fqx 'GAMEWELD_MANAGED_STEAM_SHORTCUT=1' <<<"$envs" && grep -Fqx "GAMEWELD_STEAM_SHORTCUT_APPID=$APPID" <<<"$envs"; then
    return 0
  fi
  [[ -n "$SESSION_PREFIX" ]] && grep -Fqx "STEAM_COMPAT_DATA_PATH=$SESSION_PREFIX" <<<"$envs" && return 0
  [[ -n "$SESSION_PREFIX" ]] && grep -Fqx "WINEPREFIX=$SESSION_PREFIX/pfx" <<<"$envs" && return 0
  return 1
}

pressure_vessel_bus_for_game(){
  local q="$SESSION_PID" parent bus p pid cmd envs fallback="" fallback_count=0 owner

  # Test 44: bind to the exact command-launcher service that belongs to the
  # selected live game before considering any well-known App alias. This is
  # critical for non-Steam Proton titles because Steam can expose SteamAppId=0,
  # making com.steampowered.App0 too broad to trust without provenance.
  for _ in {1..24}; do
    bus="$(pressure_vessel_bus_from_process "$q" 2>/dev/null || true)"
    if [[ -n "$bus" && "$bus" != *LaunchAlongsideSteam* ]]; then
      printf 'runtime_bus_selection=parent-chain pid=%s bus=%s\n' "$q" "$bus" >&2
      printf '%s\n' "$bus"; return 0
    fi
    bus="$(pressure_vessel_bus_from_environment "$q" 2>/dev/null || true)"
    if [[ -n "$bus" && "$bus" != *LaunchAlongsideSteam* ]]; then
      printf 'runtime_bus_selection=parent-env pid=%s bus=%s\n' "$q" "$bus" >&2
      printf '%s\n' "$bus"; return 0
    fi
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
    q="$parent"
  done

  # Game-specific launcher services are often siblings of the Windows process.
  # Prefer an exact mount-namespace or compatdata match and log the provenance.
  for p in "$PROC_ROOT"/[0-9]*; do
    pid="${p##*/}"; [[ -r "$p/cmdline" ]] || continue
    cmd="$(read_cmd "$pid" 2>/dev/null || true)"
    [[ "$cmd" == *steam-runtime-launcher-service* ]] || continue
    bus="$(pressure_vessel_bus_from_process "$pid" 2>/dev/null || pressure_vessel_bus_from_environment "$pid" 2>/dev/null || true)"
    [[ -n "$bus" && "$bus" != *LaunchAlongsideSteam* ]] || continue
    if same_mount_namespace "$SESSION_PID" "$pid"; then
      printf 'runtime_bus_selection=sibling-mount pid=%s bus=%s\n' "$pid" "$bus" >&2
      printf '%s\n' "$bus"; return 0
    fi
    envs="$(read_env "$pid" 2>/dev/null || true)"
    if [[ -n "$SESSION_PREFIX" ]] && { grep -Fqx "STEAM_COMPAT_DATA_PATH=$SESSION_PREFIX" <<<"$envs" || grep -Fqx "WINEPREFIX=$SESSION_PREFIX/pfx" <<<"$envs"; }; then
      printf 'runtime_bus_selection=sibling-prefix pid=%s bus=%s\n' "$pid" "$bus" >&2
      printf '%s\n' "$bus"; return 0
    fi
    fallback="$bus"; fallback_count=$((fallback_count+1))
  done

  # Finally consider documented well-known aliases. Non-zero App IDs remain a
  # useful fallback. App0 is accepted only when D-Bus owner provenance proves
  # that the service belongs to this exact game's namespace/prefix.
  while IFS= read -r bus; do
    [[ -n "$bus" && "$bus" == com.steampowered.App* ]] || continue
    runtime_bus_present "$bus" || continue
    if [[ "$bus" == "com.steampowered.App0" ]]; then
      if runtime_bus_owner_matches_game "$bus"; then
        owner="$(runtime_bus_owner_pid "$bus" 2>/dev/null || true)"
        printf 'runtime_bus_selection=validated-app0 owner_pid=%s bus=%s\n' "${owner:-unknown}" "$bus" >&2
        printf '%s\n' "$bus"; return 0
      fi
      printf 'runtime_bus_rejected=unproven-app0 bus=%s\n' "$bus" >&2
      continue
    fi
    printf 'runtime_bus_selection=appid-alias bus=%s\n' "$bus" >&2
    printf '%s\n' "$bus"; return 0
  done < <(runtime_bus_candidates | awk 'NF && !seen[$0]++')

  # Never guess among unrelated launcher services. If no exact provenance is
  # available, fail closed and let GameWeld surface a diagnostic instead of
  # attaching a trainer to another Steam title.
  return 1
}

find_steam_runtime_launch_client(){
  local c root
  local -a candidates=()
  root="${SESSION_STEAMROOT:-}"
  [[ -n "$root" ]] && candidates+=(
    "$root/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt64/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt3/pressure-vessel/bin/steam-runtime-launch-client"
    "$root/steamrt4/pressure-vessel/bin/steam-runtime-launch-client"
  )
  candidates+=(
    "$HOME_DIR/.local/share/Steam/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME_DIR/.local/share/Steam/steamrt3/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME_DIR/.local/share/Steam/steamrt4/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME_DIR/.steam/root/steamrt64/pv-runtime/steam-runtime-steamrt/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME_DIR/.local/share/umu/steamrt3/pressure-vessel/bin/steam-runtime-launch-client"
    "$HOME_DIR/.local/share/umu/steamrt4/pressure-vessel/bin/steam-runtime-launch-client"
  )
  for c in "${candidates[@]}"; do [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }; done

  # Some Steam installs keep pressure-vessel under SteamLinuxRuntime_*.
  if [[ -n "$root" && -d "$root/steamapps/common" ]]; then
    shopt -s nullglob
    for c in "$root"/steamapps/common/SteamLinuxRuntime*/pressure-vessel/bin/steam-runtime-launch-client \
             "$root"/steamapps/common/SteamLinuxRuntime*/_v2-entry-point; do
      [[ -x "$c" && "${c##*/}" == steam-runtime-launch-client ]] && { printf '%s\n' "$c"; shopt -u nullglob; return 0; }
    done
    shopt -u nullglob
  fi
  return 1
}

load_session_environment(){
  local pid="$1"
  SESSION_ENV=()
  [[ "$pid" =~ ^[0-9]+$ && -r "$PROC_ROOT/$pid/environ" ]] || return 1
  # Preserve the exact Steam/Proton runtime environment that the real game
  # process is already using.  This is intentionally read as NUL-separated
  # entries so spaces in paths (for example Proton - Experimental) are safe.
  mapfile -d '' -t SESSION_ENV < "$PROC_ROOT/$pid/environ" 2>/dev/null || return 1
  ((${#SESSION_ENV[@]})) || return 1
}

session_env_value(){
  local key="$1" item
  for item in "${SESSION_ENV[@]:-}"; do
    [[ "$item" == "$key="* ]] && { printf '%s\n' "${item#*=}"; return 0; }
  done
  return 1
}

launch_once(){
  local mode="$1" child rc=0 launch_exe="$EXE" readiness_loops=16
  local -a launch_args=()
  local -a SESSION_ENV=()
  if [[ "$MANAGER_ID" == cheat-evolution ]]; then
    readiness_loops="${GAMEWELD_CHEAT_EVOLUTION_READY_LOOPS:-60}"
    case "$mode" in
      cheat-evolution-launcher-runtime-client|cheat-evolution-launcher-live-env|cheat-evolution-launcher-wine-direct|cheat-evolution-launcher-proton)
        if [[ -f "$EXE_DIR/Launcher.exe" ]]; then launch_exe="$EXE_DIR/Launcher.exe"; else launch_exe="$EXE"; fi
        ;;
      cheat-evolution-main-runtime-client|cheat-evolution-main-live-env|cheat-evolution-main-wine-direct|cheat-evolution-main-proton)
        launch_exe="$EXE"
        ;;
    esac
  fi
  printf 'attempt=%s\n' "$mode"; ATTEMPT_LINE="$(wc -l < "$LOG" 2>/dev/null || echo 0)"; cd -- "$EXE_DIR"
  printf 'launch_target=%s\n' "$launch_exe"
  ((${#launch_args[@]})) && printf 'launch_args=%q\n' "${launch_args[*]}"
  if [[ "$PROVIDER" == steam || "$PROVIDER" == steam-shortcut ]]; then
    local -a envv=("GAMEWELD_MANAGER_ID=$MANAGER_ID" "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" "STEAM_COMPAT_DATA_PATH=$SESSION_PREFIX")
    [[ -n "$SESSION_STEAMROOT" ]] && envv+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$SESSION_STEAMROOT")
    [[ "$mode" == aurora-render-fallback ]] && envv+=("WINEDLLOVERRIDES=av_libglesv2=")
    if [[ "$MANAGER_ID" == cheat-evolution && "$mode" == *-runtime-client ]]; then
      local direct_wine direct_pfx runtime_client runtime_bus container_wine
      direct_wine="$(proton_wine_from_runtime "$SESSION_RUNTIME" || true)"; direct_pfx="$SESSION_PREFIX/pfx"
      runtime_client="$(find_steam_runtime_launch_client || true)"
      runtime_bus="$(pressure_vessel_bus_for_game || true)"
      if [[ -z "$runtime_client" || -z "$runtime_bus" ]]; then
        printf 'cheat_evolution_runtime_client=unavailable wine=%s client=%s bus=%s\n' "${direct_wine:-missing}" "${runtime_client:-missing}" "${runtime_bus:-missing}"
        LAST_RC=126; return
      fi
      container_wine=wine
      printf 'launch_recipe=cheat-evolution-game-pressure-vessel-runtime-client\n'
      printf 'runtime_bus_scope=game-container\n'
      printf 'runtime_client=%s\nruntime_bus=%s\nlive_env_wineprefix=%s\n' "$runtime_client" "$runtime_bus" "$direct_pfx"
      printf 'container_wine=%s\n' "$container_wine"
      printf 'launch_command=%q --bus-name=%q --directory %q -- env ... %q %q' "$runtime_client" "$runtime_bus" "$EXE_DIR" "$container_wine" "$launch_exe"
      ((${#launch_args[@]})) && printf ' %q' "${launch_args[@]}"
      printf '\n'
      env -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
          -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
          -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH \
          -u GIO_EXTRA_MODULES -u PYTHONHOME -u PYTHONPATH \
          "$runtime_client" --bus-name="$runtime_bus" --directory "$EXE_DIR" -- \
        env "GAMEWELD_MANAGER_ID=$MANAGER_ID" "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" \
            "STEAM_COMPAT_DATA_PATH=$SESSION_PREFIX" "WINEPREFIX=$direct_pfx" \
            "$container_wine" "$launch_exe" "${launch_args[@]}" & child=$!
    elif [[ "$MANAGER_ID" == cheat-evolution && "$mode" == *-live-env ]]; then
      local direct_wine direct_pfx env_wineprefix env_wineserver env_wineloader
      direct_wine="$(proton_wine_from_runtime "$SESSION_RUNTIME" || true)"; direct_pfx="$SESSION_PREFIX/pfx"
      if [[ -z "$direct_wine" ]]; then printf 'cheat_evolution_live_env_wine=unavailable\n'; LAST_RC=126; return; fi
      if ! load_session_environment "$SESSION_PID"; then printf 'cheat_evolution_live_env=session-environment-unavailable pid=%s\n' "$SESSION_PID"; LAST_RC=126; return; fi
      env_wineprefix="$(session_env_value WINEPREFIX || true)"; [[ -n "$env_wineprefix" ]] || env_wineprefix="$direct_pfx"
      env_wineserver="$(session_env_value WINESERVER || true)"; env_wineloader="$(session_env_value WINELOADER || true)"
      printf 'launch_recipe=cheat-evolution-active-wineserver-live-env\n'
      printf 'live_env_source_pid=%s\n' "$SESSION_PID"
      printf 'live_env_wineprefix=%s\n' "$env_wineprefix"
      [[ -n "$env_wineserver" ]] && printf 'live_env_wineserver=%s\n' "$env_wineserver"
      [[ -n "$env_wineloader" ]] && printf 'live_env_wineloader=%s\n' "$env_wineloader"
      printf 'launch_command=env-from-game-pid:%s %q %q' "$SESSION_PID" "$direct_wine" "$launch_exe"
      ((${#launch_args[@]})) && printf ' %q' "${launch_args[@]}"
      printf '\n'
      env -i "${SESSION_ENV[@]}" \
        "GAMEWELD_MANAGER_ID=$MANAGER_ID" \
        "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" \
        "STEAM_COMPAT_DATA_PATH=$SESSION_PREFIX" \
        "WINEPREFIX=$env_wineprefix" \
        "$direct_wine" "$launch_exe" "${launch_args[@]}" & child=$!
    elif [[ "$MANAGER_ID" == cheat-evolution && "$mode" == *-wine-direct ]]; then
      local direct_wine direct_pfx
      direct_wine="$(proton_wine_from_runtime "$SESSION_RUNTIME" || true)"; direct_pfx="$SESSION_PREFIX/pfx"
      if [[ -z "$direct_wine" ]]; then printf 'cheat_evolution_direct_wine=unavailable\n'; LAST_RC=126; return; fi
      envv+=("WINEPREFIX=$direct_pfx")
      printf 'launch_recipe=cheat-evolution-live-prefix-wine-direct\n'
      printf 'launch_command=WINEPREFIX=%q STEAM_COMPAT_DATA_PATH=%q %q %q' "$direct_pfx" "$SESSION_PREFIX" "$direct_wine" "$launch_exe"
      ((${#launch_args[@]})) && printf ' %q' "${launch_args[@]}"
      printf '\n'
      "${clean_env[@]}" "${envv[@]}" "$direct_wine" "$launch_exe" "${launch_args[@]}" & child=$!
    else
      printf 'launch_command=STEAM_COMPAT_DATA_PATH=%q %q runinprefix %q' "$SESSION_PREFIX" "$SESSION_RUNTIME" "$launch_exe"
      ((${#launch_args[@]})) && printf ' %q' "${launch_args[@]}"
      printf '\n'
      "${clean_env[@]}" "${envv[@]}" "$SESSION_RUNTIME" runinprefix "$launch_exe" "${launch_args[@]}" & child=$!
    fi
  else
    # Reuse the already-proven Heroic secondary-process functions, but only
    # after a live game process has been confirmed above.
    # shellcheck disable=SC1090
    source "$COMMON"
    export GAMEWELD_MANAGER_ID="$MANAGER_ID" GAMEWELD_MANAGER_GAME_KEY="$GAME_KEY"
    if [[ "$mode" == aurora-render-fallback ]]; then export GAMEWELD_SECONDARY_DLL_OVERRIDES='av_libglesv2='; else unset GAMEWELD_SECONDARY_DLL_OVERRIDES || true; fi
    if [[ "$SESSION_KIND" == proton ]]; then
      heroic_proton_wine_direct "$SESSION_PREFIX" "$SESSION_RUNTIME" "$launch_exe" "${launch_args[@]}" & child=$!
    else
      "${clean_env[@]}" "GAMEWELD_MANAGER_ID=$MANAGER_ID" "GAMEWELD_MANAGER_GAME_KEY=$GAME_KEY" "WINEPREFIX=$SESSION_PREFIX" "$SESSION_RUNTIME" "$launch_exe" "${launch_args[@]}" & child=$!
    fi
  fi
  printf 'launcher_pid=%s\n' "$child"
  local ready=0 i manager_pid="" stable=0 stable_need=1
  [[ "$MANAGER_ID" == cheat-evolution ]] && stable_need="${GAMEWELD_CHEAT_EVOLUTION_STABLE_LOOPS:-8}"
  for ((i=0;i<readiness_loops;i++)); do
    manager_pid="$(attached_manager_pid 2>/dev/null || true)"
    if [[ -n "$manager_pid" ]]; then
      stable=$((stable+1))
      if ((stable >= stable_need)); then ready=1; break; fi
    else
      stable=0
    fi
    if ! kill -0 "$child" 2>/dev/null && [[ "$MANAGER_ID" != cheat-evolution ]]; then break; fi
    sleep 0.5
  done
  if ((ready)); then
    printf 'readiness=real-manager-process-stable attempt=%s manager_pid=%s stable_loops=%s\n' "$mode" "$manager_pid" "$stable"
    wait "$child" || rc=$?
  else
    wait "$child" || rc=$?
    if [[ "$rc" -eq 0 ]]; then rc=125; fi
    printf 'readiness=manager-ui-not-stable exit_code=%s attempt=%s stable_loops=%s\n' "$rc" "$mode" "$stable"
  fi
  LAST_RC="$rc"
}

new_shader_crash(){ tail -n "+$((ATTEMPT_LINE+1))" "$LOG" 2>/dev/null | grep -Eq 'D3D shader compilation failed|ProgramExecutableD3D|Context11\.cpp.*Error compiling dynamic vertex executable'; }
LAST_RC=0; ATTEMPT_LINE=0
if [[ "$MANAGER_ID" == cheat-evolution && ( "$PROVIDER" == steam || "$PROVIDER" == steam-shortcut ) ]]; then
  printf 'cheat_evolution_attach_recipe=game-pressure-vessel-app-bus-first\n'
  printf 'cheat_evolution_stabilization_contract=exact-session-field-validated\n'
  printf 'cheat_evolution_entrypoint=CheatEvolution.exe\n'
  printf 'cheat_evolution_launcher_policy=fallback-only-while-game-live\n'
  printf 'cheat_evolution_proton_runinprefix=disabled-while-game-live-prefix-lock\n'
  launch_once cheat-evolution-main-runtime-client
  if [[ "$LAST_RC" -ne 0 ]]; then
    printf 'cheat_evolution_retry=Launcher.exe-runtime-client\n'
    launch_once cheat-evolution-launcher-runtime-client
  fi
  if [[ "$LAST_RC" -ne 0 ]]; then
    printf 'cheat_evolution_retry=CheatEvolution.exe-live-env\n'
    launch_once cheat-evolution-main-live-env
  fi
  if [[ "$LAST_RC" -ne 0 ]]; then
    printf 'cheat_evolution_retry=Launcher.exe-live-env\n'
    launch_once cheat-evolution-launcher-live-env
  fi
else
  launch_once game-session-primary
fi
if [[ "$MANAGER_ID" == cheat-happens-aurora && "$LAST_RC" -ne 0 ]] && new_shader_crash; then
  printf 'aurora_field_signature=avalonia-angle-d3d-shader-crash\naurora_retry=game-session-render-fallback\n'
  launch_once aurora-render-fallback
fi
if [[ "$LAST_RC" -eq 0 ]]; then
  write_result "$RESULT" 'state=stopped-cleanly' "manager=$MANAGER_LABEL" "game=$TITLE" "game_key=$GAME_KEY" "provider=$PROVIDER" "runtime=$SESSION_KIND:$SESSION_RUNTIME" "prefix=$SESSION_PREFIX" "log=$LOG" 'summary=Manager joined the selected game compatibility session and exited without launcher error.'
else
  write_result "$RESULT" 'state=manager-exit-error' "manager=$MANAGER_LABEL" "game=$TITLE" "game_key=$GAME_KEY" "provider=$PROVIDER" "runtime=$SESSION_KIND:$SESSION_RUNTIME" "prefix=$SESSION_PREFIX" "exit_code=$LAST_RC" "log=$LOG" 'summary=Manager attachment did not produce a continuously stable real manager process; inspect the scoped log for the Proton/Launcher and Wine fallback results.'
fi
exit "$LAST_RC"
