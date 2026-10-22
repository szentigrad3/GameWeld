#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-status}"
APPID="${2:-}"
TITLE="${3:-$APPID}"
LAUNCH_URI="${4:-}"
PREFIX="${5:-}"
WINE_TYPE="${6:-}"
RUNTIME_BIN="${7:-}"
COMPAT_ROOT="${8:-}"
GAME_EXE="${9:-}"
INSTALL="${10:-}"
TRAINER="${11:-}"
RUNTIME_NAME="${12:-}"

HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME_DIR/.local/state}/gameweld"
PROC_ROOT="${GAMEWELD_PROC_ROOT:-/proc}"
mkdir -p "$STATE_ROOT"

sanitize_id(){ printf '%s' "$1" | tr -c '[:alnum:]_.-' '_'; }
canon(){ readlink -f -- "$1" 2>/dev/null || printf '%s' "$1"; }
SAFE_ID="$(sanitize_id "lutris-${APPID:-unknown}")"
STATE_FILE="$STATE_ROOT/${SAFE_ID}.state"
LOG="$STATE_ROOT/${SAFE_ID}.log"
RESULT="$STATE_ROOT/${SAFE_ID}.result"

write_result(){
  local tmp="$RESULT.tmp.$$"
  printf '%s\n' "$@" >"$tmp"
  mv -f -- "$tmp" "$RESULT"
}

log(){ printf '[%(%F %T)T] %s\n' -1 "$*" >>"$LOG"; }
read_env(){ [[ -r "$PROC_ROOT/$1/environ" ]] || return 1; tr '\0' '\n' <"$PROC_ROOT/$1/environ" 2>/dev/null; }
read_cmd(){ [[ -r "$PROC_ROOT/$1/cmdline" ]] || return 1; tr '\0' ' ' <"$PROC_ROOT/$1/cmdline" 2>/dev/null; }

clean_env=(
  env
  -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
  -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
  -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH
  -u PYTHONHOME -u PYTHONPATH
  -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
  -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
  -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN
  -u GIO_LAUNCHED_DESKTOP_FILE -u GIO_LAUNCHED_DESKTOP_FILE_PID
)

prefix_path_matches(){
  local got="${1:-}" want wpfx
  [[ -n "$got" && -n "$PREFIX" ]] || return 1
  got="$(canon "$got")"; want="$(canon "$PREFIX")"; wpfx="$(canon "$PREFIX/pfx")"
  [[ "$got" == "$want" || "$got" == "$wpfx" ]]
}

proc_in_prefix(){
  local pid="$1" envs ep
  envs="$(read_env "$pid" 2>/dev/null || true)"
  [[ -n "$envs" ]] || return 1
  while IFS= read -r ep; do
    [[ -n "$ep" ]] || continue
    prefix_path_matches "$ep" && return 0
  done < <(sed -n 's/^WINEPREFIX=//p;s/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs")
  return 1
}

proc_real_windows_app(){
  local pid="$1" cmd comm low
  cmd="$(read_cmd "$pid" 2>/dev/null || true)"; comm="$(cat "$PROC_ROOT/$pid/comm" 2>/dev/null || true)"
  low="${cmd,,} ${comm,,}"
  case "$low" in
    *wineserver*|*wineboot.exe*|*services.exe*|*winedevice.exe*|*plugplay.exe*|*rpcss.exe*|*svchost.exe*|*explorer.exe*|*conhost.exe*|*rundll32.exe*|*steam-runtime-launcher-service*|*umu-shim*) return 1 ;;
  esac
  [[ "$low" == *.exe* || "${comm,,}" == *.exe ]]
}

find_live_session(){
  local target="${GAME_EXE##*/}" p pid cmd
  target="${target,,}"
  # Exact configured target first.
  if [[ -n "$target" ]]; then
    for p in "$PROC_ROOT"/[0-9]*; do
      [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
      proc_in_prefix "$pid" || continue
      cmd="$(read_cmd "$pid" 2>/dev/null || true)"
      [[ "${cmd,,}" == *"$target"* ]] || continue
      proc_real_windows_app "$pid" || continue
      printf '%s\n' "$pid"; return 0
    done
  fi
  # Launchers such as Battle.net can replace their bootstrap EXE. Once the
  # exact prefix is proven, any non-infrastructure Windows process in it is a
  # valid live-session owner.
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    proc_in_prefix "$pid" || continue
    proc_real_windows_app "$pid" || continue
    printf '%s\n' "$pid"; return 0
  done
  return 1
}

is_windows_pe(){
  [[ -r "$1" ]] || return 1
  [[ "$(dd if="$1" bs=1 count=2 status=none 2>/dev/null || true)" == MZ ]]
}

lutris_bin(){
  local c
  [[ -n "${GAMEWELD_LUTRIS_BIN:-}" && -x "${GAMEWELD_LUTRIS_BIN}" ]] && { printf '%s\n' "$GAMEWELD_LUTRIS_BIN"; return 0; }
  c="$(command -v lutris 2>/dev/null || true)"; [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  return 1
}

dispatch_lutris(){
  local lbin pid
  [[ -n "$LAUNCH_URI" ]] || { log 'dispatch blocked: launch URI missing'; return 2; }
  lbin="$(lutris_bin || true)"
  if [[ -n "$lbin" ]]; then
    log "dispatching Lutris URI through $lbin: $LAUNCH_URI"
    # Current UMU versions expose a command-launcher service. Request nsenter
    # support for this launch when the CLI invocation owns the child; if an
    # already-running Lutris instance services the URI, Test 4 still discovers
    # and validates its actual per-game launcher service from /proc before any
    # trainer handoff.
    nohup "${clean_env[@]}" UMU_CONTAINER_NSENTER=1 GAMEWELD_LUTRIS_SESSION_OWNER=1 \
      "$lbin" "$LAUNCH_URI" >>"$LOG" 2>&1 &
    pid=$!
    log "Lutris dispatch pid=$pid"
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    log "lutris binary unavailable; dispatching URI with xdg-open: $LAUNCH_URI"
    nohup "${clean_env[@]}" UMU_CONTAINER_NSENTER=1 GAMEWELD_LUTRIS_SESSION_OWNER=1 \
      xdg-open "$LAUNCH_URI" >>"$LOG" 2>&1 &
    return 0
  fi
  log 'dispatch failed: neither lutris nor xdg-open is available'
  return 2
}

wait_live_session(){
  local max_wait="${1:-45}" i pid
  for ((i=0;i<max_wait;i++)); do
    pid="$(find_live_session || true)"
    [[ -n "$pid" ]] && { printf '%s\n' "$pid"; return 0; }
    sleep 1
  done
  return 1
}

proton_arg_from_pid(){
  local pid="$1" arg
  [[ -r "$PROC_ROOT/$pid/cmdline" ]] || return 1
  while IFS= read -r -d '' arg; do
    [[ "${arg##*/}" == proton && -x "$arg" ]] && { printf '%s\n' "$arg"; return 0; }
  done <"$PROC_ROOT/$pid/cmdline"
  return 1
}

proton_from_session(){
  local pid="$1" envs val item q parent p
  envs="$(read_env "$pid" 2>/dev/null || true)"
  val="$(sed -n 's/^PROTONPATH=//p' <<<"$envs" | head -1)"
  if [[ -n "$val" ]]; then
    [[ -x "$val" && "${val##*/}" == proton ]] && { printf '%s\n' "$val"; return 0; }
    [[ -x "$val/proton" ]] && { printf '%s\n' "$val/proton"; return 0; }
  fi
  val="$(sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' <<<"$envs" | head -1)"
  IFS=':' read -r -a _gw_tools <<<"$val"
  for item in "${_gw_tools[@]}"; do [[ -x "$item/proton" ]] && { printf '%s\n' "$item/proton"; return 0; }; done
  q="$pid"
  for _ in {1..24}; do
    p="$(proton_arg_from_pid "$q" 2>/dev/null || true)"; [[ -n "$p" ]] && { printf '%s\n' "$p"; return 0; }
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
    q="$parent"
  done
  # The Proton launcher can be a sibling/ancestor not visible from the Windows
  # process after startup. Restrict this fallback to processes proven to share
  # the selected Lutris prefix.
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    proc_in_prefix "${p##*/}" || continue
    val="$(proton_arg_from_pid "${p##*/}" 2>/dev/null || true)"
    [[ -n "$val" ]] && { printf '%s\n' "$val"; return 0; }
  done
  [[ -n "$COMPAT_ROOT" && -x "$COMPAT_ROOT/proton" ]] && { printf '%s\n' "$COMPAT_ROOT/proton"; return 0; }
  return 1
}

wine_from_proton(){
  local proton="$1" root c
  [[ -x "$proton" ]] || return 1
  root="$(cd -- "$(dirname -- "$proton")" && pwd -P)"
  for c in "$root/files/bin/wine" "$root/files/bin-wow64/wine" "$root/files/bin/wine64"; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

same_mount_namespace(){
  local a="$1" b="$2" na nb
  na="$(readlink "$PROC_ROOT/$a/ns/mnt" 2>/dev/null || true)"
  nb="$(readlink "$PROC_ROOT/$b/ns/mnt" 2>/dev/null || true)"
  [[ -n "$na" && "$na" == "$nb" ]]
}

bus_from_process(){
  local pid="$1" arg
  [[ -r "$PROC_ROOT/$pid/cmdline" ]] || return 1
  while IFS= read -r -d '' arg; do
    case "$arg" in --bus-name=*) printf '%s\n' "${arg#--bus-name=}"; return 0;; esac
  done <"$PROC_ROOT/$pid/cmdline"
  return 1
}

bus_from_env(){
  local pid="$1" envs key val
  envs="$(read_env "$pid" 2>/dev/null || true)"
  for key in SRT_LAUNCHER_SERVICE STEAM_RUNTIME_LAUNCHER_SERVICE; do
    val="$(sed -n "s/^${key}=//p" <<<"$envs" | head -1)"
    case "$val" in :[0-9]*|com.steampowered.*) printf '%s\n' "$val"; return 0;; esac
  done
  return 1
}

find_runtime_service(){
  local session_pid="$1" q parent p pid cmd bus envs ep
  q="$session_pid"
  for _ in {1..24}; do
    cmd="$(read_cmd "$q" 2>/dev/null || true)"
    if [[ "$cmd" == *steam-runtime-launcher-service* ]]; then
      bus="$(bus_from_process "$q" 2>/dev/null || bus_from_env "$q" 2>/dev/null || true)"
      [[ -n "$bus" ]] && { printf '%s\t%s\n' "$q" "$bus"; return 0; }
    fi
    [[ -r "$PROC_ROOT/$q/stat" ]] || break
    parent="$(awk '{print $4}' "$PROC_ROOT/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
    q="$parent"
  done
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/cmdline" ]] || continue; pid="${p##*/}"
    cmd="$(read_cmd "$pid" 2>/dev/null || true)"
    [[ "$cmd" == *steam-runtime-launcher-service* ]] || continue
    bus="$(bus_from_process "$pid" 2>/dev/null || bus_from_env "$pid" 2>/dev/null || true)"
    [[ -n "$bus" ]] || continue
    if same_mount_namespace "$session_pid" "$pid"; then
      printf '%s\t%s\n' "$pid" "$bus"; return 0
    fi
    envs="$(read_env "$pid" 2>/dev/null || true)"
    while IFS= read -r ep; do
      [[ -n "$ep" ]] || continue
      if prefix_path_matches "$ep"; then printf '%s\t%s\n' "$pid" "$bus"; return 0; fi
    done < <(sed -n 's/^WINEPREFIX=//p;s/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs")
  done
  return 1
}

runtime_client_from_service(){
  local service_pid="$1" exe dir envs runtime c root
  exe="$(readlink -f "$PROC_ROOT/$service_pid/exe" 2>/dev/null || true)"
  if [[ -n "$exe" ]]; then
    dir="$(dirname -- "$exe")"; c="$dir/steam-runtime-launch-client"
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  fi
  envs="$(read_env "$service_pid" 2>/dev/null || true)"
  runtime="$(sed -n 's/^RUNTIMEPATH=//p' <<<"$envs" | head -1)"
  if [[ -n "$runtime" && -d "$runtime" ]]; then
    c="$(find "$runtime" -maxdepth 8 -type f -name steam-runtime-launch-client -perm -u+x -print -quit 2>/dev/null || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  fi
  for root in "${XDG_DATA_HOME:-$HOME_DIR/.local/share}/umu" "$HOME_DIR/.local/share/umu" /usr/lib /usr/lib64; do
    [[ -d "$root" ]] || continue
    c="$(find "$root" -maxdepth 9 -type f -name steam-runtime-launch-client -perm -u+x -print -quit 2>/dev/null || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

write_state(){
  local state="$1" game_pid="$2" trainer_pid="$3" proton="$4" wine="$5" service_pid="$6" bus="$7" client="$8" launch_path="$9"
  local tmp="$STATE_FILE.tmp.$$"
  {
    printf 'state=%s\n' "$state"
    printf 'appid=%s\n' "$APPID"
    printf 'title=%s\n' "$TITLE"
    printf 'game_pid=%s\n' "$game_pid"
    printf 'trainer_pid=%s\n' "$trainer_pid"
    printf 'prefix=%s\n' "$PREFIX"
    printf 'runtime_type=%s\n' "$WINE_TYPE"
    printf 'runtime_name=%s\n' "$RUNTIME_NAME"
    printf 'runtime_entry=%s\n' "$RUNTIME_BIN"
    printf 'proton=%s\n' "$proton"
    printf 'wine=%s\n' "$wine"
    printf 'launcher_service_pid=%s\n' "$service_pid"
    printf 'runtime_bus=%s\n' "$bus"
    printf 'runtime_client=%s\n' "$client"
    printf 'launch_path=%s\n' "$launch_path"
    printf 'game_exe=%s\n' "$GAME_EXE"
    printf 'trainer=%s\n' "$TRAINER"
    printf 'log=%s\n' "$LOG"
  } >"$tmp"
  mv -f -- "$tmp" "$STATE_FILE"
}

trainer_base="$(basename -- "${TRAINER:-trainer}")"
trainer_marker="gameweld-lutris-${APPID}-$(printf '%s' "$trainer_base" | tr -c '[:alnum:]_.-' '_')"
find_trainer_pid(){
  local p pid envs cmd base
  base="${TRAINER##*/}"; base="${base,,}"
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    envs="$(read_env "$pid" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_LUTRIS_TRAINER_MARKER=$trainer_marker" <<<"$envs" || continue
    proc_in_prefix "$pid" || continue
    cmd="$(read_cmd "$pid" 2>/dev/null || true)"
    if [[ -z "$base" || "${cmd,,}" == *"$base"* || "$(cat "$p/comm" 2>/dev/null | tr '[:upper:]' '[:lower:]')" == *"${base:0:15}"* ]]; then
      printf '%s\n' "$pid"; return 0
    fi
  done
  return 1
}

wait_trainer(){
  local max_wait="${1:-30}" i pid
  for ((i=0;i<max_wait;i++)); do
    pid="$(find_trainer_pid || true)"
    [[ -n "$pid" ]] && { printf '%s\n' "$pid"; return 0; }
    sleep 1
  done
  return 1
}

validate_base(){
  [[ -n "$APPID" && -n "$PREFIX" && -d "$PREFIX" ]] || return 1
  [[ -n "$GAME_EXE" && -f "$GAME_EXE" ]] || return 1
  [[ -n "$RUNTIME_BIN" && -x "$RUNTIME_BIN" ]] || return 1
  [[ -n "$LAUNCH_URI" ]] || return 1
}

session_pid="$(find_live_session || true)"

case "$ACTION" in
  status)
    if [[ -n "$session_pid" ]]; then
      printf 'STATUS\trunning\t%s\t%s\n' "$session_pid" "$STATE_FILE"
      exit 0
    fi
    printf 'STATUS\tnot-running\t0\t%s\n' "$STATE_FILE"
    exit 1
    ;;
  launch|trainer) ;;
  *) echo "usage: $0 [status|launch|trainer] APPID TITLE LAUNCH_URI PREFIX WINE_TYPE RUNTIME_BIN COMPAT_ROOT GAME_EXE INSTALL [TRAINER] [RUNTIME_NAME]" >&2; exit 2;;
esac

if ! validate_base; then
  write_result 'state=error' 'reason=unresolved-selection' "appid=$APPID" "prefix=$PREFIX" "runtime=$RUNTIME_BIN" "target=$GAME_EXE" "log=$LOG"
  log "blocked: selection is not fully resolved (prefix=$PREFIX runtime=$RUNTIME_BIN target=$GAME_EXE uri=$LAUNCH_URI)"
  exit 3
fi

if [[ -z "$session_pid" ]]; then
  dispatch_lutris || {
    write_result 'state=error' 'reason=lutris-dispatch-failed' "appid=$APPID" "log=$LOG"
    exit 4
  }
  session_pid="$(wait_live_session 60 || true)"
fi

if [[ -z "$session_pid" ]]; then
  write_result 'state=error' 'reason=live-session-not-found' "appid=$APPID" "prefix=$PREFIX" "log=$LOG"
  log 'no matching live Windows process appeared in the selected Lutris prefix'
  exit 5
fi

if [[ "$ACTION" == launch ]]; then
  write_state running "$session_pid" 0 '' '' 0 '' '' 'lutris-owned-game'
  write_result 'state=running' "game_pid=$session_pid" "appid=$APPID" "prefix=$PREFIX" 'launch_path=lutris-owned-game' "log=$LOG" 'summary=Lutris owns the running game session; GameWeld validated the exact prefix and process.'
  log "live Lutris game session confirmed pid=$session_pid prefix=$PREFIX"
  exit 0
fi

[[ -n "$TRAINER" && -r "$TRAINER" ]] || { write_result 'state=error' 'reason=trainer-missing' "trainer=$TRAINER" "log=$LOG"; log "trainer unreadable: $TRAINER"; exit 6; }
is_windows_pe "$TRAINER" || { write_result 'state=error' 'reason=trainer-not-pe' "trainer=$TRAINER" "log=$LOG"; log "trainer is not a Windows PE executable: $TRAINER"; exit 6; }

proton=''; wine=''; service_pid='0'; bus=''; client=''; launch_path=''; launcher_pid='0'
low_type="${WINE_TYPE,,}"
if [[ "$low_type" == *umu* || "$low_type" == *proton* || "${RUNTIME_BIN##*/}" == umu-run || "${RUNTIME_BIN##*/}" == umu_run.py ]]; then
  proton="$(proton_from_session "$session_pid" || true)"
  [[ -n "$proton" && -x "$proton" ]] || {
    write_result 'state=error' 'reason=live-proton-unresolved' "game_pid=$session_pid" "prefix=$PREFIX" "log=$LOG"
    log 'trainer handoff blocked: the live Lutris UMU session did not expose its concrete Proton executable'
    exit 7
  }
  wine="$(wine_from_proton "$proton" || true)"
  [[ -n "$wine" && -x "$wine" ]] || {
    write_result 'state=error' 'reason=live-proton-wine-unresolved' "proton=$proton" "log=$LOG"
    log "trainer handoff blocked: could not resolve Wine inside live Proton tool $proton"
    exit 7
  }
  service="$(find_runtime_service "$session_pid" || true)"
  [[ -n "$service" ]] || {
    write_result 'state=error' 'reason=live-runtime-service-unproven' "game_pid=$session_pid" "proton=$proton" "prefix=$PREFIX" "log=$LOG"
    log 'trainer handoff blocked: no launcher-service could be proven to belong to the selected Lutris game session; isolated UMU fallback is intentionally forbidden'
    exit 8
  }
  IFS=$'\t' read -r service_pid bus <<<"$service"
  client="$(runtime_client_from_service "$service_pid" || true)"
  [[ -n "$client" && -x "$client" && -n "$bus" ]] || {
    write_result 'state=error' 'reason=runtime-client-unresolved' "service_pid=$service_pid" "bus=$bus" "log=$LOG"
    log "trainer handoff blocked: live runtime service found but launch client is unresolved (service=$service_pid bus=$bus)"
    exit 8
  }
  workdir="$INSTALL"; [[ -d "$workdir" ]] || workdir="$(dirname -- "$GAME_EXE")"
  log "same-session UMU handoff: game_pid=$session_pid service_pid=$service_pid bus=$bus client=$client proton=$proton wine=$wine trainer=$TRAINER"
  nohup "${clean_env[@]}" "$client" --bus-name="$bus" --directory "$workdir" -- \
    env "WINEPREFIX=$PREFIX" "GAMEWELD_LUTRIS_TRAINER_MARKER=$trainer_marker" \
    "$wine" "$TRAINER" >>"$LOG" 2>&1 &
  launcher_pid=$!
  launch_path='lutris-umu-live-container'
else
  wine="$RUNTIME_BIN"
  [[ -x "$wine" ]] || { write_result 'state=error' 'reason=wine-runtime-unresolved' "runtime=$wine" "log=$LOG"; exit 7; }
  log "same-session Wine handoff: game_pid=$session_pid wine=$wine prefix=$PREFIX trainer=$TRAINER"
  nohup "${clean_env[@]}" "WINEPREFIX=$PREFIX" "GAMEWELD_LUTRIS_TRAINER_MARKER=$trainer_marker" \
    "$wine" "$TRAINER" >>"$LOG" 2>&1 &
  launcher_pid=$!
  launch_path='lutris-live-wine'
fi

trainer_pid="$(wait_trainer 35 || true)"
if [[ -z "$trainer_pid" ]]; then
  write_state running "$session_pid" 0 "$proton" "$wine" "$service_pid" "$bus" "$client" "$launch_path"
  write_result 'state=error' 'reason=trainer-process-not-confirmed' "game_pid=$session_pid" "launcher_pid=$launcher_pid" "launch_path=$launch_path" "log=$LOG"
  log "trainer launcher started pid=$launcher_pid but the real trainer process was not confirmed; game left running"
  exit 9
fi

write_state running "$session_pid" "$trainer_pid" "$proton" "$wine" "$service_pid" "$bus" "$client" "$launch_path"
write_result 'state=running' "game_pid=$session_pid" "trainer_pid=$trainer_pid" "launcher_pid=$launcher_pid" "prefix=$PREFIX" "proton=$proton" "wine=$wine" "runtime_bus=$bus" "launch_path=$launch_path" "log=$LOG" 'summary=Trainer joined the selected live Lutris compatibility session; no isolated Wine/UMU fallback was used.'
log "trainer process confirmed pid=$trainer_pid launch_path=$launch_path; game pid=$session_pid remains owned by Lutris"
exit 0
