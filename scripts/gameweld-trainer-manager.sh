#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-plan}"
EXE="${2:-}"
HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
DATA="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/gameweld"
STATE="${XDG_STATE_HOME:-$HOME_DIR/.local/state}/gameweld"
mkdir -p "$DATA/manager-prefixes" "$STATE"

sanitize_id(){ printf '%s' "$1" | tr -c '[:alnum:]_.-' '_'; }

manager_identity(){
  local exe="$1" dir base low
  [[ -f "$exe" ]] || return 1
  dir="$(cd -- "$(dirname -- "$exe")" && pwd -P)"
  base="$(basename -- "$exe")"; low="${base,,}"
  case "$low" in
    aurora.exe)
      [[ -f "$dir/WebView2Loader.dll" && -f "$dir/CheatHappensOverlay_x64.dll" && -f "$dir/Bootstrapper64.dll" ]] || return 1
      printf '%s\t%s\n' 'cheat-happens-aurora' 'Cheat Happens Aurora'
      return 0
      ;;
    cheatevolution.exe)
      [[ -f "$dir/lua53-64.dll" && -f "$dir/Launcher.exe" && -f "$dir/speedhack-x86_64.dll" ]] || return 1
      printf '%s\t%s\n' 'cheat-evolution' 'Cheat Evolution'
      return 0
      ;;
  esac
  return 1
}

find_newest_exec(){
  local root="$1" pattern="$2" maxdepth="${3:-4}"
  [[ -d "$root" ]] || return 1
  find "$root" -maxdepth "$maxdepth" -type f -path "$pattern" -perm -u+x 2>/dev/null | sort -Vr | head -n1
}

resolve_wine_runner(){
  local c root
  if [[ -n "${GAMEWELD_MANAGER_WINE:-}" && -x "${GAMEWELD_MANAGER_WINE}" ]]; then printf '%s\n' "$GAMEWELD_MANAGER_WINE"; return 0; fi
  for root in \
    "$HOME_DIR/.config/heroic/tools/wine" \
    "$HOME_DIR/.local/share/heroic/tools/wine" \
    "$HOME_DIR/.local/share/lutris/runners/wine" \
    "$HOME_DIR/.local/share/bottles/runners"; do
    c="$(find_newest_exec "$root" '*/bin/wine' 4 || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  c="$(command -v wine 2>/dev/null || true)"
  [[ -n "$c" && -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  return 1
}

resolve_proton_runner(){
  local c root
  if [[ -n "${GAMEWELD_MANAGER_PROTON:-}" && -x "${GAMEWELD_MANAGER_PROTON}" ]]; then printf '%s\n' "$GAMEWELD_MANAGER_PROTON"; return 0; fi
  for root in \
    "$HOME_DIR/.config/heroic/tools/proton" \
    "$HOME_DIR/.local/share/heroic/tools/proton" \
    "$HOME_DIR/.steam/root/compatibilitytools.d" \
    "$HOME_DIR/.steam/steam/compatibilitytools.d" \
    "$HOME_DIR/.local/share/Steam/compatibilitytools.d"; do
    c="$(find_newest_exec "$root" '*/proton' 3 || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  for root in \
    "$HOME_DIR/.steam/root/steamapps/common" \
    "$HOME_DIR/.steam/steam/steamapps/common" \
    "$HOME_DIR/.local/share/Steam/steamapps/common"; do
    [[ -d "$root" ]] || continue
    c="$(find "$root" -maxdepth 2 -type f -name proton -path '*/Proton*/*' -perm -u+x 2>/dev/null | sort -Vr | head -n1 || true)"
    [[ -n "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

resolve_runtime_for_manager(){
  local manager="$1" forced="${GAMEWELD_MANAGER_RUNTIME:-}" w p
  case "$forced" in
    wine)
      w="$(resolve_wine_runner || true)"; [[ -n "$w" ]] && { printf 'wine\t%s\n' "$w"; return 0; }
      ;;
    proton)
      p="$(resolve_proton_runner || true)"; [[ -n "$p" ]] && { printf 'proton\t%s\n' "$p"; return 0; }
      ;;
    '') ;;
    *) echo "Ignoring unknown GAMEWELD_MANAGER_RUNTIME=$forced" >&2 ;;
  esac

  # Explicit runner overrides are still respected. If both are explicitly set,
  # provider policy below decides which family wins.
  if [[ "$manager" == cheat-happens-aurora ]]; then
    # Aurora's Avalonia/ANGLE path has shown real WineD3D shader-compiler crashes
    # in the field. Prefer a current Proton stack when one is installed; Proton
    # remains user-owned and no game prefix is reused.
    p="$(resolve_proton_runner || true)"
    [[ -n "$p" ]] && { printf 'proton\t%s\n' "$p"; return 0; }
    w="$(resolve_wine_runner || true)"
    [[ -n "$w" ]] && { printf 'wine\t%s\n' "$w"; return 0; }
  else
    # Cheat Evolution already passed the Test 6 field launch under Wine-GE, so
    # preserve Wine-first behavior and use Proton only as a fallback.
    w="$(resolve_wine_runner || true)"
    [[ -n "$w" ]] && { printf 'wine\t%s\n' "$w"; return 0; }
    p="$(resolve_proton_runner || true)"
    [[ -n "$p" ]] && { printf 'proton\t%s\n' "$p"; return 0; }
  fi
  printf 'none\t—\n'
  return 1
}

steam_client_path(){
  local p
  for p in "$HOME_DIR/.steam/root" "$HOME_DIR/.steam/steam" "$HOME_DIR/.local/share/Steam"; do
    [[ -d "$p" ]] && { printf '%s\n' "$p"; return 0; }
  done
  printf '%s\n' "$HOME_DIR/.local/share/Steam"
}

prefix_active(){
  local id="$1" root="$2" pfx="$3" p envs pid_list=''
  # Reading every process environment is surprisingly expensive on systems with
  # large process trees. Limit the probe to plausible Wine/Proton/manager
  # processes; fall back to /proc only when procps is unavailable.
  if command -v pgrep >/dev/null 2>&1; then
    pid_list="$(pgrep -u "$(id -u)" -f 'wine|wineserver|proton|Aurora([.]exe)?|CheatEvolution([.]exe)?|gameweld-trainer-manager|fake-(wine|proton)' 2>/dev/null || true)"
    for p in $pid_list; do
      [[ -r "/proc/$p/environ" ]] || continue
      envs="$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null || true)"
      grep -Fqx "GAMEWELD_MANAGER_ID=$id" <<<"$envs" && return 0
      grep -Fqx "WINEPREFIX=$pfx" <<<"$envs" && return 0
      grep -Fqx "STEAM_COMPAT_DATA_PATH=$root" <<<"$envs" && return 0
    done
    return 1
  fi
  for p in /proc/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    envs="$(tr '\0' '\n' < "$p/environ" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_MANAGER_ID=$id" <<<"$envs" && return 0
    grep -Fqx "WINEPREFIX=$pfx" <<<"$envs" && return 0
    grep -Fqx "STEAM_COMPAT_DATA_PATH=$root" <<<"$envs" && return 0
  done
  return 1
}
write_result(){
  local file="$1"; shift
  local tmp="$file.tmp.$$"
  printf '%s\n' "$@" > "$tmp"
  mv -f -- "$tmp" "$file"
}

[[ -n "$EXE" ]] || { echo 'Manager executable path is required.' >&2; exit 2; }
EXE="$(readlink -f -- "$EXE" 2>/dev/null || printf '%s' "$EXE")"
IDENT="$(manager_identity "$EXE" || true)"
[[ -n "$IDENT" ]] || { echo 'The selected executable is not a validated GameWeld manager package.' >&2; exit 3; }
IFS=$'\t' read -r MANAGER_ID MANAGER_LABEL <<<"$IDENT"
EXE_DIR="$(cd -- "$(dirname -- "$EXE")" && pwd -P)"
PREFIX_ROOT="$DATA/manager-prefixes/$MANAGER_ID"
PFX="$PREFIX_ROOT/pfx"
LOG="$STATE/manager-$(sanitize_id "$MANAGER_ID").log"
RESULT="$STATE/manager-$(sanitize_id "$MANAGER_ID").result"
RUNTIME_LINE="$(resolve_runtime_for_manager "$MANAGER_ID" || true)"
IFS=$'\t' read -r RUNTIME_KIND RUNTIME_BIN <<<"$RUNTIME_LINE"
[[ -n "$RUNTIME_KIND" ]] || RUNTIME_KIND=none
[[ -n "$RUNTIME_BIN" ]] || RUNTIME_BIN='—'
STATUS=ready
prefix_active "$MANAGER_ID" "$PREFIX_ROOT" "$PFX" && STATUS=running
if [[ "$RUNTIME_KIND" == none ]]; then STATUS=no-runtime; fi

stop_standalone_manager(){
  local p pid envs low
  local -a targets=()
  for p in /proc/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"
    envs="$(tr '\0' '\n' < "$p/environ" 2>/dev/null || true)"
    grep -Fqx "GAMEWELD_MANAGER_ID=$MANAGER_ID" <<<"$envs" || continue
    { grep -Fqx "WINEPREFIX=$PFX" <<<"$envs" || grep -Fqx "STEAM_COMPAT_DATA_PATH=$PREFIX_ROOT" <<<"$envs"; } || continue
    low="$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null || true) $(cat "$p/comm" 2>/dev/null || true)"; low="${low,,}"
    targets+=("$pid")
  done
  if ((${#targets[@]})); then
    kill -TERM "${targets[@]}" 2>/dev/null || true
    for _ in {1..30}; do
      local any=0
      for pid in "${targets[@]}"; do kill -0 "$pid" 2>/dev/null && any=1; done
      ((any==0)) && break
      sleep 0.1
    done
    local -a remain=(); for pid in "${targets[@]}"; do kill -0 "$pid" 2>/dev/null && remain+=("$pid"); done
    ((${#remain[@]})) && kill -KILL "${remain[@]}" 2>/dev/null || true
  fi
  write_result "$RESULT" 'state=stopped-by-user' "manager=$MANAGER_LABEL" "prefix=$PFX" "exe=$EXE" "log=$LOG" 'summary=GameWeld stopped the standalone trainer manager and its dedicated-prefix processes.'
}

case "$ACTION" in
  plan|status)
    REASON='Dedicated persistent manager prefix; no per-game trainer assignment is changed.'
    if [[ "$MANAGER_ID" == cheat-happens-aurora && "$STATUS" != no-runtime ]]; then
      REASON='Aurora provider recipe prefers installed Proton over Wine because the Test 6 field log exposed an Avalonia/ANGLE D3D shader crash under Wine-GE; a non-invasive ANGLE-disabled software-render fallback is attempted only after that specific crash signature.'
    elif [[ "$MANAGER_ID" == cheat-evolution && "$STATUS" != no-runtime ]]; then
      REASON='Cheat Evolution keeps the Wine-first provider recipe that reached a live manager prefix in the Test 6 field log.'
    fi
    [[ "$STATUS" == no-runtime ]] && REASON='No compatible Wine/Proton runtime was found. Install Wine, Heroic/Lutris Wine, or Steam Proton, then retry.'
    [[ "$STATUS" == running ]] && REASON='A Windows process is already active in this manager-specific prefix; GameWeld will not start a duplicate manager instance.'
    printf 'MANAGER_PLAN\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$MANAGER_ID" "$MANAGER_LABEL" "$RUNTIME_KIND" "$RUNTIME_BIN" "$PFX" "$LOG" "$STATUS" "$REASON"
    exit 0
    ;;
  stop)
    exec >>"$LOG" 2>&1
    printf '
[%(%F %T)T] manager=%s id=%s action=stop
' -1 "$MANAGER_LABEL" "$MANAGER_ID"
    stop_standalone_manager
    exit 0
    ;;
  launch) ;;
  *) echo "Unknown manager action: $ACTION" >&2; exit 2 ;;
esac

if [[ "$STATUS" == running ]]; then
  write_result "$RESULT" 'state=already-running' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" 'summary=Manager is already active in its dedicated GameWeld prefix; duplicate launch skipped.'
  exit 0
fi
if [[ "$RUNTIME_KIND" == none || ! -x "$RUNTIME_BIN" ]]; then
  write_result "$RESULT" 'state=no-runtime' "manager=$MANAGER_LABEL" "prefix=$PFX" "exe=$EXE" 'summary=No Wine/Proton runtime could be resolved for manager launch.'
  exit 4
fi

mkdir -p "$PREFIX_ROOT" "$STATE"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] manager=%s id=%s action=launch\n' -1 "$MANAGER_LABEL" "$MANAGER_ID"
printf 'exe=%s\nworking_dir=%s\nruntime_kind=%s\nruntime=%s\nprefix=%s\n' "$EXE" "$EXE_DIR" "$RUNTIME_KIND" "$RUNTIME_BIN" "$PFX"

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

cd -- "$EXE_DIR"

launch_attempt(){
  local mode="$1" child rc=0 steam_root
  local angle_override=''
  [[ "$mode" == aurora-software-fallback ]] && angle_override='av_libglesv2='
  printf 'attempt=%s\n' "$mode"
  ATTEMPT_START_LINE=$(wc -l < "$LOG" 2>/dev/null || printf '0')
  if [[ "$RUNTIME_KIND" == wine ]]; then
    if [[ -n "$angle_override" ]]; then
      printf 'render_fallback=disable-packaged-angle WINEDLLOVERRIDES=%s\n' "$angle_override"
      printf 'launch_command=WINEDLLOVERRIDES=%q WINEPREFIX=%q %q %q\n' "$angle_override" "$PFX" "$RUNTIME_BIN" "$EXE"
      "${clean_env[@]}" GAMEWELD_MANAGER_ID="$MANAGER_ID" WINEDLLOVERRIDES="$angle_override" \
        WINEPREFIX="$PFX" WINEARCH=win64 WINEDEBUG="${GAMEWELD_MANAGER_WINEDEBUG:--all}" \
        "$RUNTIME_BIN" "$EXE" &
    else
      printf 'launch_command=WINEPREFIX=%q %q %q\n' "$PFX" "$RUNTIME_BIN" "$EXE"
      "${clean_env[@]}" GAMEWELD_MANAGER_ID="$MANAGER_ID" \
        WINEPREFIX="$PFX" WINEARCH=win64 WINEDEBUG="${GAMEWELD_MANAGER_WINEDEBUG:--all}" \
        "$RUNTIME_BIN" "$EXE" &
    fi
  else
    steam_root="$(steam_client_path)"
    printf 'steam_client=%s\n' "$steam_root"
    if [[ -n "$angle_override" ]]; then
      printf 'render_fallback=disable-packaged-angle WINEDLLOVERRIDES=%s\n' "$angle_override"
      printf 'launch_command=WINEDLLOVERRIDES=%q STEAM_COMPAT_DATA_PATH=%q %q run %q\n' "$angle_override" "$PREFIX_ROOT" "$RUNTIME_BIN" "$EXE"
      "${clean_env[@]}" GAMEWELD_MANAGER_ID="$MANAGER_ID" WINEDLLOVERRIDES="$angle_override" \
        STEAM_COMPAT_DATA_PATH="$PREFIX_ROOT" STEAM_COMPAT_CLIENT_INSTALL_PATH="$steam_root" \
        STEAM_COMPAT_INSTALL_PATH="$EXE_DIR" SteamAppId=0 SteamGameId=0 PROTON_LOG=0 \
        "$RUNTIME_BIN" run "$EXE" &
    else
      printf 'launch_command=STEAM_COMPAT_DATA_PATH=%q %q run %q\n' "$PREFIX_ROOT" "$RUNTIME_BIN" "$EXE"
      "${clean_env[@]}" GAMEWELD_MANAGER_ID="$MANAGER_ID" \
        STEAM_COMPAT_DATA_PATH="$PREFIX_ROOT" STEAM_COMPAT_CLIENT_INSTALL_PATH="$steam_root" \
        STEAM_COMPAT_INSTALL_PATH="$EXE_DIR" SteamAppId=0 SteamGameId=0 PROTON_LOG=0 \
        "$RUNTIME_BIN" run "$EXE" &
    fi
  fi
  child=$!
  printf 'launcher_pid=%s\n' "$child"

  # A short readiness window distinguishes immediate loader/render failures
  # from prefix creation without making normal launches feel stalled.
  for _ in 1 2 3 4; do
    if kill -0 "$child" 2>/dev/null; then
      sleep 0.5
    elif prefix_active "$MANAGER_ID" "$PREFIX_ROOT" "$PFX"; then
      sleep 0.5
    else
      break
    fi
  done
  if kill -0 "$child" 2>/dev/null || prefix_active "$MANAGER_ID" "$PREFIX_ROOT" "$PFX"; then
    printf 'readiness=running attempt=%s\n' "$mode"
  else
    wait "$child" || rc=$?
    if [[ "$rc" -eq 0 ]]; then
      printf 'readiness=clean-exit exit_code=0 attempt=%s\n' "$mode"
      LAST_RC=0
      LAST_STATE=stopped
    else
      printf 'readiness=early-exit exit_code=%s attempt=%s\n' "$rc" "$mode"
      LAST_RC=$rc
      LAST_STATE=early-exit
    fi
    return 0
  fi

  wait "$child" || rc=$?
  sleep 0.5
  if prefix_active "$MANAGER_ID" "$PREFIX_ROOT" "$PFX"; then
    printf 'launcher_exit=%s manager_prefix_still_active=yes attempt=%s\n' "$rc" "$mode"
    LAST_RC=$rc
    LAST_STATE=running-background
    return 0
  fi
  printf 'manager_exit=%s attempt=%s\n' "$rc" "$mode"
  LAST_RC=$rc
  LAST_STATE=stopped
}

new_attempt_has_aurora_shader_crash(){
  local from="${ATTEMPT_START_LINE:-0}"
  tail -n "+$((from+1))" "$LOG" 2>/dev/null | grep -Eq 'D3D shader compilation failed|ProgramExecutableD3D|Context11\.cpp.*Error compiling dynamic vertex executable'
}

LAST_RC=0
LAST_STATE=unknown
ATTEMPT_START_LINE=0
PRIMARY_MODE=default
[[ "$MANAGER_ID" == cheat-happens-aurora ]] && PRIMARY_MODE=aurora-primary
launch_attempt "$PRIMARY_MODE"

if [[ "$LAST_STATE" == running-background ]]; then
  write_result "$RESULT" 'state=running-background' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" "exit_code=$LAST_RC" "log=$LOG" 'summary=Launcher process exited but manager-prefix Windows processes remain active.'
  exit 0
fi

if [[ "$MANAGER_ID" == cheat-happens-aurora && "$LAST_RC" -ne 0 ]] && new_attempt_has_aurora_shader_crash; then
  printf 'aurora_field_signature=avalonia-angle-d3d-shader-crash\n'
  printf 'aurora_retry=software-render-fallback\n'
  # No package file is renamed or deleted. Wine/Proton is simply told not to
  # load Aurora's packaged ANGLE DLL for this retry so Avalonia can use its next
  # configured renderer (normally software when available).
  launch_attempt aurora-software-fallback
  if [[ "$LAST_STATE" == running-background || "$LAST_STATE" == stopped && "$LAST_RC" -eq 0 ]]; then
    write_result "$RESULT" 'state=running-fallback' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" "exit_code=$LAST_RC" "log=$LOG" 'compatibility=aurora-angle-disabled-software-fallback' 'summary=Aurora hit the known ANGLE/D3D shader crash and the non-invasive software-render fallback reached a non-error launch state.'
    exit 0
  fi
fi

if [[ "$LAST_STATE" == early-exit ]]; then
  write_result "$RESULT" 'state=early-exit' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" "exit_code=$LAST_RC" "log=$LOG" 'summary=Manager exited before the readiness window; inspect the manager log.'
  exit "$LAST_RC"
fi
if [[ "$LAST_STATE" == stopped ]]; then
  write_result "$RESULT" 'state=stopped' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" "exit_code=$LAST_RC" "log=$LOG" 'summary=Manager process ended.'
  exit "$LAST_RC"
fi
write_result "$RESULT" 'state=unknown' "manager=$MANAGER_LABEL" "runtime=$RUNTIME_KIND:$RUNTIME_BIN" "prefix=$PFX" "exe=$EXE" "exit_code=$LAST_RC" "log=$LOG" 'summary=Manager launch ended in an unclassified state.'
exit "${LAST_RC:-1}"
