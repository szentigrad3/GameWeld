#!/usr/bin/env bash
set -Eeuo pipefail
RUNNER="${1:?runner required}"
APPID="${2:?app id required}"
TITLE="${3:-$APPID}"
INSTALL="${4:-}"
EXE="${5:-}"
PREFIX="${6:-}"
WINE_TYPE="${7:-}"
WINE_BIN="${8:-}"
CE_SUPPLIED="${9:-}"
TABLE="${10:?table required}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=gameweld-heroic-common.sh
source "$script_dir/gameweld-heroic-common.sh"
LOG="$GAMEWELD_STATE/heroic-cheat-table-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Heroic Cheat Table launch runner=%s appid=%s title=%s\n' -1 "$RUNNER" "$APPID" "$TITLE"
require_no_runtime_repair "$RUNNER" "$APPID" || exit 12
printf 'Install: %s\nExecutable: %s\nPrefix: %s\nRunner type: %s\nRunner binary: %s\nTable: %s\n' "$INSTALL" "$EXE" "$PREFIX" "$WINE_TYPE" "$WINE_BIN" "$TABLE"
[[ -r "$TABLE" ]] || { echo "Cheat table is not readable: $TABLE"; exit 3; }
WINDOWS_CE="$(resolve_windows_ce "$CE_SUPPLIED" || true)"
[[ -n "$WINDOWS_CE" ]] || { echo 'No valid Windows Cheat Engine companion is installed. Install the Windows CE companion in GameWeld Settings first.'; exit 5; }
echo "Windows CE: $WINDOWS_CE"
HINTS="$(build_game_exe_hints "$INSTALL" "$EXE" || true)"
echo "Heroic game executable hints: ${HINTS:-<none>}"

existing="$(find_live_game_target "$INSTALL" "$HINTS" || true)"
if [[ -z "$existing" ]]; then
  echo 'Starting game normally through Heroic...'
  heroic_launch_game "$RUNNER" "$APPID" || { echo 'Could not dispatch Heroic game launch.'; exit 4; }
  echo "Heroic launch request sent. Waiting for the actual Windows game executable; launcher status alone is not treated as ready."
  existing="$(wait_for_live_game_target "$INSTALL" "$HINTS" 120 || true)"
fi
[[ -n "$existing" ]] || { echo 'Timed out waiting 120 seconds for the real Heroic game executable. Windows CE was not launched early.'; exit 6; }
IFS=$'\t' read -r GAMEPID PRIMARY GAMECMD <<< "$existing"
echo "Actual Heroic game process detected: PID=$GAMEPID exe=$PRIMARY"
echo "Game command line: $GAMECMD"
sleep 2

CE_DIR="$(cd -- "$(dirname -- "$WINDOWS_CE")" && pwd)"
CE_NAME="$(basename -- "$WINDOWS_CE")"
helper="$(install_heroic_ce_autoattach_helper "$CE_DIR")"
request="$(write_heroic_attach_request "$CE_DIR" "$APPID" "$TITLE" "$HINTS" "$PRIMARY")"
echo "CE auto-attach helper ready: $helper"
echo "CE one-shot attach request: $request"
WIN_TABLE="$(prepare_ct_path "$TABLE" "$PREFIX")"
echo "Wine-side table argument: $WIN_TABLE"

# Heroic's altExe protocol is an alternate GAME executable path.  It is useful
# for replacing the game launch target, but it is not a dependable way to add
# a second process to an already-running Wine/Proton session.  Local trainers
# already use the direct live-prefix path; Windows CE must do the same so the
# game, CE and table all share the exact prefix/wineserver that Heroic started.
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

launch_direct=0
case "${WINE_TYPE,,}" in
  proton|proton-ge|ge-proton|umu)
    if [[ -x "$WINE_BIN" && -n "$PREFIX" ]]; then
      echo 'Launching Windows Cheat Engine directly into the active Heroic Proton prefix via runinprefix.'
      echo "Heroic Proton: $WINE_BIN"
      echo "Heroic compatdata/prefix: $PREFIX"
      pushd "$CE_DIR" >/dev/null
      nohup "${clean_env[@]}" \
        "STEAM_COMPAT_DATA_PATH=$PREFIX" \
        "WINEPREFIX=$PREFIX" \
        "$WINE_BIN" runinprefix "./$CE_NAME" "$WIN_TABLE" >>"$LOG" 2>&1 &
      CE_LAUNCH_PID=$!
      popd >/dev/null
      printf '%s\n' "$CE_LAUNCH_PID" >"$GAMEWELD_STATE/heroic-ce-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").pid"
      launch_direct=1
    fi
    ;;
  wine|wine-ge|wine-lutris|crossover|'')
    if [[ -x "$WINE_BIN" && -n "$PREFIX" ]]; then
      echo 'Launching Windows Cheat Engine directly into the active Heroic Wine prefix.'
      echo "Heroic Wine: $WINE_BIN"
      echo "Heroic prefix: $PREFIX"
      pushd "$CE_DIR" >/dev/null
      nohup "${clean_env[@]}" "WINEPREFIX=$PREFIX" "$WINE_BIN" "./$CE_NAME" "$WIN_TABLE" >>"$LOG" 2>&1 &
      CE_LAUNCH_PID=$!
      popd >/dev/null
      printf '%s\n' "$CE_LAUNCH_PID" >"$GAMEWELD_STATE/heroic-ce-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").pid"
      launch_direct=1
    fi
    ;;
esac

if (( ! launch_direct )); then
  rm -f -- "$request" 2>/dev/null || true
  echo "Could not resolve a directly runnable Heroic Windows runner (type=$WINE_TYPE bin=$WINE_BIN)."
  echo 'Refusing the old Heroic altExe fallback because it can silently fail for secondary Cheat Engine processes.'
  exit 7
fi

# Proton/Wine normally remains as the parent while the Windows program is alive.
# If that launcher exits quickly, do a filtered process scan for the CE payload
# without mistaking this bridge's own command line for the target.
sleep 2
if [[ -n "${CE_LAUNCH_PID:-}" ]] && kill -0 "$CE_LAUNCH_PID" 2>/dev/null; then
  echo "Windows CE handoff is alive in the verified Heroic live prefix (launcher PID $CE_LAUNCH_PID). The one-shot helper will attach to the ranked gameplay process while the table loads."
  exit 0
fi
ce_seen=0
for _ in {1..12}; do
  for p in /proc/[0-9]*; do
    [[ -r "$p/cmdline" ]] || continue
    pid="${p##*/}"; [[ "$pid" != "$$" && "$pid" != "$PPID" ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    case "${comm,,}" in bash|sh|dash|zsh|fish|env|nohup|gameweld) continue ;; esac
    cmd="$(tr '\0' ' ' <"$p/cmdline" 2>/dev/null || true)"
    [[ -n "$cmd" ]] || continue
    low="${cmd,,}"
    case "$low" in *gameweld-heroic-cheat-table*) continue ;; esac
    if [[ "$low" == *"${CE_NAME,,}"* ]]; then ce_seen=1; break 2; fi
  done
  sleep 0.25
done
if (( ce_seen )); then
  echo 'Windows CE process is visible in the verified Heroic live prefix. The one-shot helper will attach to the ranked gameplay process while the table loads.'
  exit 0
fi

echo 'Windows CE launch command exited before the handoff could be verified. Leaving the one-shot request in place for diagnostics.'
exit 8
