#!/usr/bin/env bash
set -Eeuo pipefail
RUNNER="${1:?runner required}"; APPID="${2:?app id required}"; TITLE="${3:-$APPID}"; INSTALL="${4:-}"; EXE="${5:-}"; PREFIX="${6:-}"; WINE_TYPE="${7:-}"; WINE_BIN="${8:-}"; TRAINER="${9:?trainer required}"; HEROIC_ROOT="${10:-}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=gameweld-heroic-common.sh
source "$script_dir/gameweld-heroic-common.sh"
[[ -n "$HEROIC_ROOT" ]] && export GAMEWELD_HEROIC_ROOT="$HEROIC_ROOT"
LOG="$GAMEWELD_STATE/heroic-local-trainer-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Heroic local trainer launch runner=%s appid=%s title=%s root=%s\n' -1 "$RUNNER" "$APPID" "$TITLE" "${HEROIC_ROOT:-auto}"

HEROIC_SESSION_RUNNER_ACTIVE=0
restore_temporary_heroic_runner() {
  (( HEROIC_SESSION_RUNNER_ACTIVE )) || return 0
  local out
  if ! out="$(python3 "$HEROIC_PROVIDER" session-runner-restore "$APPID" 2>&1)"; then
    echo "Heroic temporary compatibility runner restore FAILED: $out"
    return 1
  fi
  echo "Heroic temporary compatibility runner restore: $out"
  HEROIC_SESSION_RUNNER_ACTIVE=0
}
trap 'restore_temporary_heroic_runner || true; [[ -z "${ELEVATE_HELPER_COPY:-}" ]] || rm -f -- "$ELEVATE_HELPER_COPY" 2>/dev/null || true' EXIT

begin_temporary_heroic_runner() {
  local proton="$1" out
  out="$(python3 "$HEROIC_PROVIDER" session-runner-begin "$APPID" "$proton" 2>&1)" || {
    echo "Could not prepare Heroic temporary compatibility runner: $out"
    return 1
  }
  echo "Heroic temporary compatibility runner: $out"
  HEROIC_SESSION_RUNNER_ACTIVE=1
}
require_no_runtime_repair "$RUNNER" "$APPID" || exit 12

# 0.2.2 Test 2: validate that the selection still belongs to the exact Heroic
# installation that discovered it before touching any game configuration.
PREFLIGHT="$(python3 "$HEROIC_PROVIDER" preflight "$APPID" 2>&1)" || {
  echo "Heroic compatibility preflight FAILED: $PREFLIGHT"
  echo 'Refresh the GameWeld library. No Heroic configuration was changed.'
  exit 18
}
echo "Heroic compatibility preflight: $PREFLIGHT"
python3 - "$PREFLIGHT" "$HEROIC_ROOT" "$PREFIX" <<'PYCHK' || exit 18
import json, os, sys
j=json.loads(sys.argv[1]); expected_root=os.path.realpath(os.path.expanduser(sys.argv[2])) if sys.argv[2] else ''
actual_root=os.path.realpath(os.path.expanduser(str(j.get('heroic_root') or ''))) if j.get('heroic_root') else ''
if expected_root and actual_root and expected_root != actual_root:
    print(f'Heroic root mismatch: selected={expected_root} resolved={actual_root}', file=sys.stderr); raise SystemExit(1)
selected_prefix=os.path.realpath(os.path.expanduser(sys.argv[3])) if sys.argv[3] else ''
resolved_prefix=str(j.get('prefix') or '')
resolved_prefix=os.path.realpath(os.path.expanduser(resolved_prefix)) if resolved_prefix else ''
if selected_prefix and resolved_prefix and selected_prefix != resolved_prefix:
    print(f'Heroic prefix mismatch: selected={selected_prefix} resolved={resolved_prefix}', file=sys.stderr); raise SystemExit(1)
PYCHK

[[ -r "$TRAINER" ]] || { echo "Trainer is not readable: $TRAINER"; exit 3; }
if ! is_windows_pe "$TRAINER"; then echo "Trainer is not a Windows PE executable: $TRAINER"; exit 3; fi
HINTS="$(build_game_exe_hints "$INSTALL" "$EXE" || true)"
BRIDGE_MODE=0
UMU_BUS_ACTIVE=0
case "${WINE_TYPE,,}" in
  proton|proton-ge|ge-proton|umu)
    BRIDGE_MODE=1
    ;;
esac

clean_env=(
  env
  -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
  -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
  -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH
  -u PYTHONHOME -u PYTHONPATH
  -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
  -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
)

prefix_windows_cmd() {
  if (( BRIDGE_MODE )); then
    if (( UMU_BUS_ACTIVE )); then
      heroic_umu_inject "$PREFIX" "$WINE_BIN" "$INSTALL" "$RUNNER" "$APPID" "$@"
    else
      # Host/native Proton builds (notably proton-cachyos-native) may not
      # expose an UMU launcher-service bus. In that case use the exact Heroic
      # Proton build directly, matching the known-working Test 4 runinprefix
      # path rather than forcing UMU_CONTAINER_NSENTER into a nonexistent bus.
      heroic_proton_wine_direct "$PREFIX" "$WINE_BIN" "$@"
    fi
  else
    [[ -x "$WINE_BIN" && -n "$PREFIX" ]] || return 2
    "${clean_env[@]}" "WINEPREFIX=$PREFIX" "$WINE_BIN" "$@"
  fi
}

trainer_is_fling() {
  local low="${TRAINER,,}" line
  [[ "$low" == *fling* ]] && return 0
  if LC_ALL=C grep -aEiqm1 'flingtrainer|fling[[:space:]_-]*trainer' "$TRAINER" 2>/dev/null; then return 0; fi
  if command -v strings >/dev/null 2>&1; then
    while IFS= read -r line; do
      [[ "${line,,}" == *flingtrainer* || "${line,,}" == *"fling trainer"* ]] && return 0
    done < <(strings -a "$TRAINER" 2>/dev/null || true)
    while IFS= read -r line; do
      [[ "${line,,}" == *flingtrainer* || "${line,,}" == *"fling trainer"* ]] && return 0
    done < <(strings -el "$TRAINER" 2>/dev/null || true)
  fi
  return 1
}

trainer_looks_like_fling_family() {
  # Some packed FLiNG releases do not expose the FLiNG strings that older
  # builds did. Their public filenames are commonly "<game> vX Plus N
  # Trainer.exe". Treat that shape as a FLiNG-family hint rather than letting
  # a packed bootstrap silently fall back to the Wine 11 direct-launch path.
  trainer_is_fling && return 0
  local base low
  base="${TRAINER##*/}"
  low="${base,,}"
  [[ "$low" =~ [[:space:]_-]plus[[:space:]_-]*[0-9]+[[:space:]_-]*trainer\.exe$ ]]
}

trainer_uses_managed_runtime() {
  # Native FLiNG bootstrap binaries can safely use process-local builtin IE
  # networking DLLs. Managed/WPF trainers are left untouched.
  LC_ALL=C grep -aEiqm1 'mscoree\.dll|PresentationFramework|WindowsBase\.dll|System\.Xaml' "$TRAINER" 2>/dev/null
}

# Newer Wine/Proton 11 builds can create a FLiNG trainer window whose client
# area does not render.  For FLiNG on Wine/Proton 11+, GameWeld launches the
# game through Heroic with a temporary GE-Proton10-34 + Wine-Wayland override,
# restores Heroic's saved configuration immediately after the real game process
# appears, then launches the trainer in that same compatibility session.
COMPAT_RUNTIME_TAG="GE-Proton10-34"
COMPAT_RUNTIME_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/gameweld/repair-runtimes/$COMPAT_RUNTIME_TAG"
LEGACY_FOCUS_STATE="$GAMEWELD_STATE/heroic-trainer-focus-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").state"
LEGACY_RENDER_STATE="$GAMEWELD_STATE/heroic-trainer-render-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").state"
X11_DRIVER_KEY='HKCU\Software\Wine\X11 Driver'
AVALON_KEY='HKCU\Software\Microsoft\Avalon.Graphics'

restore_legacy_test_state() {
  local proton="${1:-${COMPAT_PROTON:-${WINE_BIN:-}}}" old
  [[ -n "$proton" && -x "$proton" && -n "$PREFIX" ]] || return 0

  # One-time cleanup for interrupted pre-release focus experiments. Stable
  # GameWeld never applies UseTakeFocus itself.
  if [[ -f "$LEGACY_FOCUS_STATE" ]]; then
    old="$(head -n1 "$LEGACY_FOCUS_STATE" 2>/dev/null || true)"
    echo "Restoring legacy pre-release Wine focus state: ${old:-unknown}"
    case "$old" in
      present:*) heroic_proton_wine_direct "$PREFIX" "$proton" reg.exe add "$X11_DRIVER_KEY" /v UseTakeFocus /t REG_SZ /d "${old#present:}" /f >/dev/null 2>&1 || true ;;
      missing|*) heroic_proton_wine_direct "$PREFIX" "$proton" reg.exe delete "$X11_DRIVER_KEY" /v UseTakeFocus /f >/dev/null 2>&1 || true ;;
    esac
    rm -f "$LEGACY_FOCUS_STATE"
  fi

  # One-time cleanup for interrupted pre-release WPF renderer experiments.
  # Stable GameWeld avoids the affected Wine generation instead of changing
  # Avalon.Graphics.
  if [[ -f "$LEGACY_RENDER_STATE" ]]; then
    old="$(head -n1 "$LEGACY_RENDER_STATE" 2>/dev/null || true)"
    echo "Restoring legacy pre-release WPF renderer state: ${old:-unknown}"
    case "$old" in
      present:*) heroic_proton_wine_direct "$PREFIX" "$proton" reg.exe add "$AVALON_KEY" /v DisableHWAcceleration /t REG_DWORD /d "${old#present:}" /f >/dev/null 2>&1 || true ;;
      missing|*) heroic_proton_wine_direct "$PREFIX" "$proton" reg.exe delete "$AVALON_KEY" /v DisableHWAcceleration /f >/dev/null 2>&1 || true ;;
    esac
    rm -f "$LEGACY_RENDER_STATE"
  fi
}

resolve_fling_compat_proton() {
  local c
  # Pin the compatibility engine to the exact runtime validated by 0.2.1.
  # Do not silently substitute a different GE-Proton10 build.
  for c in \
    "$COMPAT_RUNTIME_ROOT/proton" \
    "$HOME/.steam/root/compatibilitytools.d/$COMPAT_RUNTIME_TAG/proton" \
    "$HOME/.local/share/Steam/compatibilitytools.d/$COMPAT_RUNTIME_TAG/proton" \
    "$HOME/.config/heroic/tools/proton/$COMPAT_RUNTIME_TAG/proton" \
    "/usr/share/steam/compatibilitytools.d/$COMPAT_RUNTIME_TAG/proton"; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

ensure_fling_compat_proton() {
  local c runtime_tool
  c="$(resolve_fling_compat_proton || true)"
  if [[ -n "$c" ]]; then printf '%s\n' "$c"; return 0; fi
  runtime_tool="$script_dir/gameweld-heroic-trainer-runtime.sh"
  [[ -x "$runtime_tool" ]] || { echo 'Managed FLiNG compatibility runtime is missing and the downloader is unavailable.' >&2; return 1; }
  echo "Managed FLiNG compatibility runtime $COMPAT_RUNTIME_TAG is not installed; downloading it now (~500 MB)." >&2
  "$runtime_tool" download-helper "$RUNNER" "$APPID" "$TITLE" "$PREFIX" "$WINE_TYPE" "$WINE_BIN" "$TRAINER" || return 1
  c="$(resolve_fling_compat_proton || true)"
  [[ -n "$c" ]] || { echo 'The managed compatibility runtime download completed but proton could not be resolved.' >&2; return 1; }
  printf '%s\n' "$c"
}

# Decide whether the local-trainer session must avoid the selected Wine 11
# build. Test 2 only did this when static FLiNG detection succeeded. That is too
# narrow for packed trainers: Ghostbusters proved that the game can launch while
# an unclassified trainer never creates a process. On Wine/Proton 11+, Test 3
# therefore defaults ALL local Windows trainers to the same known-good managed
# session. FLiNG detection still controls the optional builtin wininet/iertutil
# isolation below; it is no longer required just to get the compatibility
# runtime.
FLING_COMPAT_SESSION=0
COMPAT_SESSION_REASON=""
SELECTED_WVER=""
SELECTED_WMAJOR=""
case "${WINE_TYPE,,}" in
  proton|proton-ge|ge-proton|umu)
    SELECTED_WVER="$(heroic_proton_wine_version "$WINE_BIN" || true)"
    SELECTED_WMAJOR="$(printf '%s' "$SELECTED_WVER" | sed -nE 's/.*wine[^0-9]*([0-9]+).*/\1/p' | head -n1)"
    COMPAT_MODE="${GAMEWELD_LOCAL_TRAINER_COMPAT_SESSION:-${GAMEWELD_FLING_COMPAT_SESSION:-auto}}"
    case "$COMPAT_MODE" in
      on|force)
        FLING_COMPAT_SESSION=1
        COMPAT_SESSION_REASON="forced"
        ;;
      off)
        FLING_COMPAT_SESSION=0
        ;;
      auto|*)
        if [[ "${SELECTED_WMAJOR:-0}" =~ ^[0-9]+$ ]] && (( SELECTED_WMAJOR >= 11 )); then
          FLING_COMPAT_SESSION=1
          if trainer_looks_like_fling_family; then
            COMPAT_SESSION_REASON="fling-family trainer on Wine/Proton ${SELECTED_WMAJOR}"
          else
            COMPAT_SESSION_REASON="unclassified local trainer on Wine/Proton ${SELECTED_WMAJOR}"
          fi
        fi
        ;;
    esac
    ;;
esac

existing="$(find_live_game_target "$INSTALL" "$HINTS" || true)"
GAME_WAS_ALREADY_RUNNING=0
COMPAT_PROTON=""
HEROIC_OWNED_COMPAT=0
HEROIC_COMPAT_RELOAD=0
HEROIC_WAS_RUNNING=0
if (( FLING_COMPAT_SESSION )); then
  echo "Selected Heroic runtime reports: ${SELECTED_WVER:-unknown}."
  echo "Local-trainer compatibility session required (${COMPAT_SESSION_REASON:-Wine/Proton compatibility}): using the known-good managed Proton for BOTH game and trainer."
  echo "Heroic compatibility profile: runner=$RUNNER root=${HEROIC_ROOT:-auto} runtime=$COMPAT_RUNTIME_TAG Wine-Wayland=on reason=${COMPAT_SESSION_REASON:-compat}."
  echo 'All Heroic backends use Heroic itself as the game-session owner. If Heroic is already open, GameWeld fully stops the idle Electron UI, applies the temporary compatibility profile, then starts a fresh Heroic process with the launch URI.'
  echo "Epic/Legendary secondary trainers re-enter Heroic's exact live UMU/pressure-vessel container through the launcher-service bus; a second standalone UMU/Wine session is not allowed."
  if [[ -n "$existing" ]]; then
    echo 'The game is already running under the selected Heroic runner. Close the game once, then press PLAY WITH LOCAL TRAINER again so GameWeld can start both processes in the same compatibility session.'
    exit 14
  fi
  COMPAT_PROTON="$(ensure_fling_compat_proton)" || { echo 'Could not prepare the managed FLiNG compatibility runtime.'; exit 15; }
  echo "Managed FLiNG compatibility Proton: $COMPAT_PROTON"
  restore_legacy_test_state "$COMPAT_PROTON" || true

  # Test 9: Heroic caches GameConfig instances in memory. Editing GamesConfig
  # while an already-running Heroic GUI owns that cache can leave Epic/Legendary
  # on the old runner. Close the idle Heroic main process FIRST, then apply the
  # temporary profile and launch through a fresh Heroic instance. This preserves
  # Heroic's own PLAYING/STOP ownership while guaranteeing that the launch reads
  # GE-Proton10-34 + Wine-Wayland from disk.
  if heroic_main_running; then
    HEROIC_WAS_RUNNING=1
    other_game="$(heroic_other_game_active "$APPID" || true)"
    if [[ -n "$other_game" ]]; then
      echo "Another Heroic game session appears to be active ($other_game). GameWeld will not restart Heroic underneath another running game."
      exit 19
    fi
    echo 'Heroic is already open. Restarting the idle Heroic main process so the compatibility profile is loaded from disk.'
    heroic_stop_main_for_reload || { echo 'Could not restart Heroic cleanly; refusing to launch with a stale cached runner.'; exit 16; }
  fi

  begin_temporary_heroic_runner "$COMPAT_PROTON" || exit 15
  HEROIC_COMPAT_RELOAD=1
  echo "Launching the compatibility session THROUGH Heroic runner '$RUNNER'. Heroic remains the game-session owner."
  if (( HEROIC_WAS_RUNNING )); then
    heroic_launch_game_fresh_visible "$RUNNER" "$APPID" || {
      echo 'Could not start a fresh Heroic process for the compatibility launch.'
      restore_temporary_heroic_runner || true
      exit 16
    }
  else
    heroic_launch_game "$RUNNER" "$APPID" || {
      echo 'Could not dispatch the temporary compatibility launch through Heroic.'
      restore_temporary_heroic_runner || true
      exit 16
    }
  fi
  existing="$(wait_for_live_game_target "$INSTALL" "$HINTS" 120 || true)"
  if ! restore_temporary_heroic_runner; then
    echo 'Heroic configuration restore verification failed; refusing to launch the trainer until the original config is safely restored.'
    exit 17
  fi
  if [[ -z "$existing" ]]; then
    echo 'Heroic compatibility session did not produce the real game process.'
    exit 16
  fi
  echo 'Heroic configuration restored byte-for-byte on disk after game process detection. The live Heroic-owned session continues on the compatibility runtime.'
  HEROIC_OWNED_COMPAT=1
  # All secondary Windows processes must use this exact Proton build too.
  WINE_BIN="$COMPAT_PROTON"
  WINE_TYPE="proton"
  BRIDGE_MODE=1
  UMU_BUS_ACTIVE=0
else
  if [[ -z "$existing" ]]; then
    echo 'Starting game normally through Heroic with the UMU launcher-service bridge enabled...'
    heroic_enable_umu_nsenter "$APPID" || { echo 'Could not enable the Heroic UMU trainer bridge for this game.'; exit 9; }
    heroic_launch_game "$RUNNER" "$APPID" || { echo 'Could not dispatch Heroic game launch.'; exit 4; }
    existing="$(wait_for_live_game_target "$INSTALL" "$HINTS" 120 || true)"
  else
    GAME_WAS_ALREADY_RUNNING=1
  fi
fi
[[ -n "$existing" ]] || { echo 'Timed out waiting for the real game process. Trainer was not launched early.'; exit 6; }
IFS=$'\t' read -r GAMEPID PRIMARY GAMECMD <<< "$existing"
echo "Actual game process detected: PID=$GAMEPID exe=$PRIMARY"

# Test 9: the compatibility game is Heroic-owned again. The fresh Heroic
# process intentionally retains the temporary runner in memory for this live
# session even after the on-disk config is restored. A small finalizer waits for
# game + trainer exit, then restarts Heroic so subsequent normal launches reload
# the user's original runner from disk.
if (( HEROIC_COMPAT_RELOAD )); then
  SESSION_FINALIZER="$script_dir/gameweld-heroic-session-finalizer.sh"
  if [[ -x "$SESSION_FINALIZER" ]]; then
    nohup "$SESSION_FINALIZER" "$RUNNER" "$APPID" "$TITLE" "$INSTALL" "$EXE" "$PREFIX" "$GAMEPID" "$TRAINER" "$HEROIC_WAS_RUNNING" >/dev/null 2>&1 &
    FINALIZER_PID=$!
    echo "Heroic compatibility-session finalizer started: PID=$FINALIZER_PID original_gui_running=$HEROIC_WAS_RUNNING"
  else
    echo 'WARNING: Heroic session finalizer is unavailable. Restart Heroic after this game session so its in-memory compatibility profile is cleared.'
  fi
fi
sleep 2

# Use normal desktop windows. FLiNG on affected Wine/Proton 11 builds has
# already been moved to the managed compatibility session above; process-local
# builtin wininet/iertutil isolation remains as protection against stale
# Winetricks overrides in the shared prefix.
launch_direct=0
TRAINER_WINDOW_MODE="native"
LAUNCH_PATH=""
PROTON_SECONDARY=0
TRAINER_DLL_MODE="default"
GAMEWELD_SECONDARY_DLL_OVERRIDES=""
GAMEWELD_SECONDARY_WINEDEBUG=""
TRAINER_ELEVATION_MODE="normal"
ELEVATE_HELPER_COPY=""

trainer_process_pids() {
  local p pid comm cmd low needle
  needle="${TRAINER##*/}"
  needle="${needle,,}"
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$comm$cmd" ]] || continue
    case "${comm,,}" in
      bash|sh|dash|zsh|fish|python|python3|proton|umu-run|timeout|bwrap|pv-bwrap|pressure-vessel*) continue ;;
    esac
    low="${cmd,,} ${comm,,}"
    [[ "$low" == *"$needle"* ]] && printf '%s\n' "$pid"
  done
}

BASELINE_TRAINER_PIDS="$(trainer_process_pids | tr '\n' ' ' || true)"
new_trainer_process_pid() {
  local pid
  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    case " $BASELINE_TRAINER_PIDS " in *" $pid "*) continue ;; esac
    printf '%s\n' "$pid"
    return 0
  done < <(trainer_process_pids)
  return 1
}

wait_for_new_trainer_process() {
  local attempts="${1:-24}" pid i
  for ((i=0; i<attempts; i++)); do
    pid="$(new_trainer_process_pid || true)"
    if [[ -n "$pid" ]]; then printf '%s\n' "$pid"; return 0; fi
    sleep 0.5
  done
  return 1
}

start_proton_secondary() {
  local exe="$1"; shift || true
  if (( HEROIC_OWNED_COMPAT )) && [[ "${RUNNER,,}" == "legendary" || "${RUNNER,,}" == "epic" ]]; then
    # Test 12: a second standalone UMU runinprefix invocation can see the game
    # process name while still living in a different pressure-vessel/Wine-server
    # session. FLiNG then reports Access Denied when it opens the game process.
    # Require the launcher-service bus and re-enter Heroic's *existing* live
    # container instead. Never silently fall back to a second container here.
    if ! wait_umu_bus "$PREFIX" 20; then
      echo "Heroic live UMU launcher-service bus did not appear: $(umu_bus_name "$PREFIX")" >&2
      echo 'Refusing to start the trainer in a separate UMU/Wine session.' >&2
      return 23
    fi
    echo "Heroic live UMU bus confirmed: $(umu_bus_name "$PREFIX")" >&2
    heroic_umu_inject "$PREFIX" "$WINE_BIN" "$INSTALL" "$RUNNER" "$APPID" "$exe" "$@"
  elif (( UMU_BUS_ACTIVE )); then
    heroic_umu_inject "$PREFIX" "$WINE_BIN" "$INSTALL" "$RUNNER" "$APPID" "$exe" "$@"
  else
    heroic_proton_wine_direct "$PREFIX" "$WINE_BIN" "$exe" "$@"
  fi
}

stage_trainer_elevation_helper() {
  local src="$script_dir/gameweld-elevate.exe" dst_dir
  [[ -r "$src" ]] || { echo "GameWeld elevation helper is missing: $src"; return 1; }
  if [[ -d "$PREFIX/pfx/drive_c/windows/temp" ]]; then
    dst_dir="$PREFIX/pfx/drive_c/windows/temp"
  elif [[ -d "$PREFIX/drive_c/windows/temp" ]]; then
    dst_dir="$PREFIX/drive_c/windows/temp"
  else
    echo 'Could not locate the prefix Windows temp directory for the elevation helper.'
    return 1
  fi
  ELEVATE_HELPER_COPY="$dst_dir/gameweld-elevate-$(sanitize_id "$APPID")-$$.exe"
  cp -f -- "$src" "$ELEVATE_HELPER_COPY"
  chmod 0644 "$ELEVATE_HELPER_COPY" 2>/dev/null || true
}

start_trainer_normal() {
  if [[ "$TRAINER_WINDOW_MODE" == "virtual-desktop" ]]; then
    local win_trainer
    win_trainer="$(windows_z_path "$TRAINER")"
    start_proton_secondary explorer.exe "/desktop=GameWeldTrainer,1400x900" "$win_trainer"
  else
    start_proton_secondary "$TRAINER"
  fi
}

start_trainer_elevated() {
  # Do not route elevation through WSH/COM. Test 10 proved that a wscript.exe +
  # Shell.Application trampoline can disappear inside a Heroic-owned UMU
  # runinprefix session without ever creating the trainer process.
  #
  # Test 11 uses a tiny native Windows helper that calls ShellExecuteW with the
  # standard "runas" verb directly. The helper is copied inside the prefix so
  # pressure-vessel/UMU can always see it. This is Windows-token elevation only;
  # no Linux sudo/root or file-permission changes are involved.
  stage_trainer_elevation_helper || return 1
  local win_trainer win_dir
  win_trainer="$(windows_z_path "$TRAINER")"
  win_dir="$(windows_z_path "$(dirname -- "$TRAINER")")"
  start_proton_secondary "$ELEVATE_HELPER_COPY" "$win_trainer" "$win_dir"
}

start_selected_trainer() {
  if [[ "$TRAINER_ELEVATION_MODE" == "windows-admin" && "$TRAINER_WINDOW_MODE" == "native" ]]; then
    start_trainer_elevated
  else
    start_trainer_normal
  fi
}
case "${WINE_TYPE,,}" in
  proton|proton-ge|ge-proton|umu)
    [[ -x "$WINE_BIN" && -n "$PREFIX" ]] || { echo "Heroic Proton runner is incomplete (bin=$WINE_BIN prefix=$PREFIX)."; exit 7; }
    WVER="$(heroic_proton_wine_version "$WINE_BIN" || true)"
    WMAJOR="$(printf '%s' "$WVER" | sed -nE 's/.*wine[^0-9]*([0-9]+).*/\1/p' | head -n1)"
    echo "Selected Heroic Wine/Proton runtime reports: ${WVER:-unknown}"
    case "${GAMEWELD_TRAINER_ELEVATION:-auto}" in
      never|off|0) TRAINER_ELEVATION_MODE="normal" ;;
      always|admin|1) TRAINER_ELEVATION_MODE="windows-admin" ;;
      *) trainer_looks_like_fling_family && TRAINER_ELEVATION_MODE="windows-admin" || TRAINER_ELEVATION_MODE="normal" ;;
    esac
    if [[ "$TRAINER_ELEVATION_MODE" == "windows-admin" ]]; then
      echo 'FLiNG-family trainer: requesting Wine Windows-token elevation through the standard runas verb.'
      echo 'This does not use sudo/root; it only gives the trainer the linked Windows administrator token inside the existing prefix.'
    fi
    if trainer_looks_like_fling_family && ! trainer_uses_managed_runtime; then
      # Older compatibility repairs can leave native Win7 wininet/iertutil overrides
      # in the game prefix even when the later .NET install fails. On Wine 11
      # that exact mixed DLL state is known to abort at iertutil.dll ordinal 650.
      # Do not rewrite the prefix while the game is running: isolate only the
      # trainer process and force Wine's matching builtin pair.
      TRAINER_DLL_MODE="builtin-wininet-iertutil"
      GAMEWELD_SECONDARY_DLL_OVERRIDES='wininet=b;iertutil=b'
      export GAMEWELD_SECONDARY_DLL_OVERRIDES
      echo 'FLiNG-family/native trainer detected. Forcing builtin wininet + iertutil for the trainer process only.'
      echo 'This bypasses stale native Winetricks DLL overrides without changing the running game or Heroic prefix.'
    fi
    if [[ "${GAMEWELD_TRAINER_WINDOW_MODE:-auto}" == "virtual-desktop" ]]; then
      TRAINER_WINDOW_MODE="virtual-desktop"
    fi
    echo "Trainer window compatibility mode: $TRAINER_WINDOW_MODE"
    echo "Trainer DLL compatibility mode: $TRAINER_DLL_MODE"
    echo "Trainer Windows privilege mode: $TRAINER_ELEVATION_MODE"
    if (( HEROIC_OWNED_COMPAT )) && [[ "${RUNNER,,}" == "legendary" || "${RUNNER,,}" == "epic" ]]; then
      # Keep Heroic as owner of the game and re-enter the exact already-running
      # pressure-vessel/UMU container for the trainer. This is required for
      # cross-process memory access; same prefix alone is not sufficient.
      UMU_BUS_ACTIVE=1
      LAUNCH_PATH="heroic-owned-umu-live-container"
      echo 'Heroic-owned Epic/Legendary compatibility session: requiring live UMU container re-entry for the trainer.'
      echo 'A second standalone UMU/Wine session and host-Wine fallback are both forbidden.'
    else
      echo "Checking for Heroic/UMU live-container bridge: $(umu_bus_name "$PREFIX")"
      BRIDGE_WAIT=6
      if wait_umu_bus "$PREFIX" "$BRIDGE_WAIT"; then
        UMU_BUS_ACTIVE=1
        echo 'Heroic/UMU live-container bridge detected. Re-entering the exact running game container.'
        LAUNCH_PATH="umu-live-container"
      else
        UMU_BUS_ACTIVE=0
        echo 'No UMU launcher-service bus was exposed. Using the exact Wine binary from Heroic selected Proton tool against the live WINEPREFIX.'
        LAUNCH_PATH="direct-live-wine"
      fi
    fi
    if [[ "$TRAINER_WINDOW_MODE" == "virtual-desktop" ]]; then
      WIN_TRAINER="$(windows_z_path "$TRAINER")"
      echo 'Wine/Proton 11+ trainer window workaround enabled.'
      echo 'The trainer will run inside a private Wine virtual desktop; the game remains in the normal desktop.'
      echo "Trainer Windows path: $WIN_TRAINER"
    fi
    start_selected_trainer >>"$LOG" 2>&1 &
    TPID=$!
    PROTON_SECONDARY=1
    launch_direct=1
    ;;
  wine|wine-ge|wine-lutris|crossover|'')
    if [[ -x "$WINE_BIN" && -n "$PREFIX" ]]; then
      WVER="$("$WINE_BIN" --version 2>/dev/null | head -n1 || true)"
      WMAJOR="$(printf '%s' "$WVER" | sed -nE 's/.*wine[^0-9]*([0-9]+).*/\1/p' | head -n1)"
      if [[ "${GAMEWELD_TRAINER_WINDOW_MODE:-auto}" == "virtual-desktop" ]]; then
        TRAINER_WINDOW_MODE="virtual-desktop"
      fi
      echo "Launching local trainer in active Heroic Wine prefix. Window mode: $TRAINER_WINDOW_MODE"
      echo "Heroic Wine: $WINE_BIN"
      echo "Heroic prefix: $PREFIX"
      if [[ "$TRAINER_WINDOW_MODE" == "virtual-desktop" ]]; then
        WIN_TRAINER="$(windows_z_path "$TRAINER")"
        LAUNCH_PATH="direct-wine"
        nohup "${clean_env[@]}" "WINEPREFIX=$PREFIX" "$WINE_BIN" explorer.exe "/desktop=GameWeldTrainer,1400x900" "$WIN_TRAINER" >>"$LOG" 2>&1 &
      else
        LAUNCH_PATH="direct-wine"
        nohup "${clean_env[@]}" "WINEPREFIX=$PREFIX" "$WINE_BIN" "$TRAINER" >>"$LOG" 2>&1 &
      fi
      TPID=$!
      launch_direct=1
    fi
    ;;
esac

if (( ! launch_direct )); then
  echo "Could not resolve a directly runnable Heroic Windows runner (type=$WINE_TYPE bin=$WINE_BIN)."
  exit 7
fi

echo "Trainer launch path: ${LAUNCH_PATH:-unknown}"
TRAINER_PID="$(wait_for_new_trainer_process 24 || true)"

# Never let Windows-token elevation regress a previously working trainer
# launch. If the native runas helper does not create the real trainer quickly,
# fall back to the proven Test 9 normal UMU runinprefix launch. This preserves
# game + trainer functionality while keeping the elevation experiment isolated.
if [[ -z "$TRAINER_PID" && "$PROTON_SECONDARY" == "1" && "$TRAINER_ELEVATION_MODE" == "windows-admin" ]]; then
  echo 'Windows-admin helper did not produce the trainer process within 12 seconds.'
  echo 'Falling back immediately to the proven normal same-session trainer launch.'
  kill "$TPID" 2>/dev/null || true
  wait "$TPID" 2>/dev/null || true
  TRAINER_ELEVATION_MODE="normal"
  LAUNCH_PATH="${LAUNCH_PATH:-trainer}-normal-fallback"
  start_trainer_normal >>"$LOG" 2>&1 &
  TPID=$!
  echo "Trainer fallback launch path: $LAUNCH_PATH"
  TRAINER_PID="$(wait_for_new_trainer_process 30 || true)"
fi

# A live UMU service is preferred when present, but keeping only the umu-run launcher
# alive is not proof that a trainer process was created. If live-container
# injection does not produce the actual trainer,
# retry once with the exact Wine binary already inside Heroic's selected Proton tool and the live prefix.
if [[ -z "$TRAINER_PID" && "$PROTON_SECONDARY" == "1" && "$LAUNCH_PATH" == "umu-live-container" ]]; then
  echo 'UMU live-container launch did not produce a trainer process within 12 seconds.'
  echo "Retrying once through Heroic's exact Proton Wine binary in the live WINEPREFIX."
  kill "$TPID" 2>/dev/null || true
  wait "$TPID" 2>/dev/null || true
  UMU_BUS_ACTIVE=0
  LAUNCH_PATH="direct-live-wine"
  start_selected_trainer >>"$LOG" 2>&1 &
  TPID=$!
  echo "Trainer fallback launch path: $LAUNCH_PATH"
  TRAINER_PID="$(wait_for_new_trainer_process 24 || true)"
fi

# Some self-extracting/native trainer launchers behave differently when Wine
# receives the EXE directly. If the direct live-Wine attempt exits before the
# real trainer process appears, retry through Wine's own start.exe /unix while
# keeping the same live prefix and DLL isolation. This is still a normal desktop
# window and does not create a private Wine desktop.
if [[ -z "$TRAINER_PID" && "$PROTON_SECONDARY" == "1" && "$LAUNCH_PATH" == "direct-live-wine" && "$TRAINER_ELEVATION_MODE" != "windows-admin" ]]; then
  echo 'Direct live-Wine launch did not produce the trainer process within 12 seconds.'
  echo 'Retrying once through Wine start.exe /unix in the same live prefix.'
  kill "$TPID" 2>/dev/null || true
  wait "$TPID" 2>/dev/null || true
  GAMEWELD_SECONDARY_WINEDEBUG='err+all'
  export GAMEWELD_SECONDARY_WINEDEBUG
  LAUNCH_PATH="direct-live-wine-start"
  start_proton_secondary start.exe /unix "$TRAINER" >>"$LOG" 2>&1 &
  TPID=$!
  echo "Trainer fallback launch path: $LAUNCH_PATH"
  TRAINER_PID="$(wait_for_new_trainer_process 30 || true)"
fi

# Last normal-window fallback: let Proton rebuild its own secondary-process
# environment while retaining process-local builtin DLL isolation. This covers
# host-runtime differences
# without changing Heroic's configured runner or prefix.
if [[ -z "$TRAINER_PID" && "$PROTON_SECONDARY" == "1" && "$LAUNCH_PATH" == "direct-live-wine-start" && "$TRAINER_ELEVATION_MODE" != "windows-admin" ]]; then
  echo 'Wine start.exe retry still did not produce the trainer process.'
  echo 'Final retry: exact Heroic Proton runinprefix with the same builtin DLL isolation.'
  kill "$TPID" 2>/dev/null || true
  wait "$TPID" 2>/dev/null || true
  GAMEWELD_SECONDARY_WINEDEBUG='err+all'
  export GAMEWELD_SECONDARY_WINEDEBUG
  LAUNCH_PATH="exact-proton-runinprefix-builtin"
  heroic_proton_runinprefix "$PREFIX" "$WINE_BIN" "$INSTALL" "$TRAINER" >>"$LOG" 2>&1 &
  TPID=$!
  echo "Trainer fallback launch path: $LAUNCH_PATH"
  TRAINER_PID="$(wait_for_new_trainer_process 30 || true)"
fi

if [[ -n "$TRAINER_PID" ]]; then
  echo "Heroic local trainer process confirmed in the live prefix (PID $TRAINER_PID; launcher PID $TPID)."
  if (( FLING_COMPAT_SESSION )); then
    echo 'Managed local-trainer compatibility session is using Wine-Wayland; no KWin window-rule helper is required.'
  fi
  if [[ "$TRAINER_WINDOW_MODE" == "native" ]]; then
    # Best-effort: bring the trainer's normal top-level X11/XWayland window to
    # the front without forcing a separate Wine desktop. Failure is harmless.
    (
      sleep 1
      if command -v xdotool >/dev/null 2>&1; then
        wid="$(xdotool search --onlyvisible --name 'FLiNG Trainer|Trainer' 2>/dev/null | tail -n1 || true)"
        [[ -n "$wid" ]] && xdotool windowactivate --sync "$wid" >/dev/null 2>&1 || true
      elif command -v wmctrl >/dev/null 2>&1; then
        wmctrl -a 'FLiNG Trainer' >/dev/null 2>&1 || wmctrl -a 'Trainer' >/dev/null 2>&1 || true
      fi
    ) &
  fi
else
  rc="unknown"
  if ! kill -0 "$TPID" 2>/dev/null; then wait "$TPID" || rc=$?; fi
  echo "No trainer process appeared after launch (launcher status $rc)."
  if tail -n 240 "$LOG" 2>/dev/null | grep -Eiq 'unimplemented function iertutil\.dll\.(650|653)|wininet.*iertutil|iertutil.*wininet'; then
    echo 'Detected a native wininet/iertutil mismatch in the launch trace.'
    echo 'Process-local builtin-DLL isolation was applied; export this log if the trainer still exits.'
  elif tail -n 240 "$LOG" 2>/dev/null | grep -Eiq 'mscoree|PresentationFramework|CLR|\.NET'; then
    echo 'The trainer trace contains managed-runtime markers; this trainer may require a clean managed runtime path.'
  fi
  echo 'GameWeld will not report this as a successful trainer launch.'
  exit 8
fi
