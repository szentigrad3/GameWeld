#!/usr/bin/env bash
set -Eeuo pipefail

GAMEWELD_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/gameweld"
GAMEWELD_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$GAMEWELD_DATA" "$GAMEWELD_STATE"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${APPDIR:-}" && -x "${APPDIR}/usr/libexec/gameweld-heroic-provider.py" ]]; then
  HEROIC_PROVIDER="${APPDIR}/usr/libexec/gameweld-heroic-provider.py"
elif [[ -x "$script_dir/gameweld-heroic-provider.py" ]]; then
  HEROIC_PROVIDER="$script_dir/gameweld-heroic-provider.py"
else
  HEROIC_PROVIDER="gameweld-heroic-provider.py"
fi
if [[ -n "${APPDIR:-}" && -x "${APPDIR}/usr/libexec/gameweld-cheat-engine-manager.sh" ]]; then
  CE_MANAGER="${APPDIR}/usr/libexec/gameweld-cheat-engine-manager.sh"
elif [[ -x "$script_dir/gameweld-cheat-engine-manager.sh" ]]; then
  CE_MANAGER="$script_dir/gameweld-cheat-engine-manager.sh"
else
  CE_MANAGER="gameweld-cheat-engine-manager.sh"
fi

sanitize_id() { printf '%s' "$1" | tr -c '[:alnum:]_.-' '_'; }

heroic_runtime_repair_lock(){
  local runner="$1" appid="$2"
  printf '%s/heroic-trainer-runtime-%s-%s.repairing\n' "$GAMEWELD_STATE" "$(sanitize_id "$runner")" "$(sanitize_id "$appid")"
}
heroic_runtime_repair_active(){
  local lock pid
  lock="$(heroic_runtime_repair_lock "$1" "$2")"
  [[ -r "$lock" ]] || return 1
  pid="$(head -n1 "$lock" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then return 0; fi
  rm -f -- "$lock" "${lock%.repairing}.progress" 2>/dev/null || true
  return 1
}
require_no_runtime_repair(){
  local runner="$1" appid="$2" lock pid progress
  if heroic_runtime_repair_active "$runner" "$appid"; then
    lock="$(heroic_runtime_repair_lock "$runner" "$appid")"; pid="$(head -n1 "$lock" 2>/dev/null || true)"; progress="${lock%.repairing}.progress"
    echo "FLiNG runtime repair is still active for this Heroic game (PID ${pid:-unknown})."
    [[ -r "$progress" ]] && { printf 'Repair progress: '; cat "$progress"; }
    echo 'Game launch is blocked until repair completes or is cancelled in GameWeld Settings.'
    return 1
  fi
  return 0
}

heroic_uri() {
  local appid="$1" runner="$2" alt="${3:-}"; shift 3 || true
  python3 "$HEROIC_PROVIDER" uri "$appid" "$runner" "$alt" "$@"
}

heroic_dispatch_uri() {
  local uri="$1"
  # Heroic must inherit the user's desktop/session environment, not GameWeld's
  # AppImage loader/runtime paths.  Leaking APPDIR/LD_LIBRARY_PATH/GIO/GTK or
  # Python paths into Heroic can subtly change its UMU/Proton child processes.
  local -a clean_env=(
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
  # Prefer the desktop protocol registration; this works for native Heroic and
  # Flatpak Heroic without GameWeld having to guess which package owns it.
  if command -v xdg-open >/dev/null 2>&1; then
    "${clean_env[@]}" xdg-open "$uri" >/dev/null 2>&1 &
    return 0
  fi
  if command -v heroic >/dev/null 2>&1; then
    if [[ "$uri" == *'gui=true'* ]]; then
      "${clean_env[@]}" heroic "$uri" >/dev/null 2>&1 &
    else
      "${clean_env[@]}" heroic --no-gui "$uri" >/dev/null 2>&1 &
    fi
    return 0
  fi
  if command -v flatpak >/dev/null 2>&1 && flatpak info com.heroicgameslauncher.hgl >/dev/null 2>&1; then
    if [[ "$uri" == *'gui=true'* ]]; then
      "${clean_env[@]}" flatpak run com.heroicgameslauncher.hgl "$uri" >/dev/null 2>&1 &
    else
      "${clean_env[@]}" flatpak run com.heroicgameslauncher.hgl --no-gui "$uri" >/dev/null 2>&1 &
    fi
    return 0
  fi
  return 1
}

heroic_launch_game() {
  local runner="$1" appid="$2" uri
  uri="$(heroic_uri "$appid" "$runner" "")"
  printf 'Heroic launch URI: %s\n' "$uri"
  heroic_dispatch_uri "$uri"
}

heroic_launch_game_visible() {
  local runner="$1" appid="$2" uri
  uri="$(GAMEWELD_HEROIC_PROTOCOL_GUI=true heroic_uri "$appid" "$runner" "")"
  printf 'Heroic visible launch URI: %s\n' "$uri"
  heroic_dispatch_uri "$uri"
}

heroic_process_identity() {
  # Match Heroic itself, never generic Electron markers such as app.asar.
  # Discord, Slack, VS Code and many other Electron apps all expose app.asar in
  # their command lines; Test 13 could therefore mistake them for Heroic.
  local low="${1,,}"
  case "$low" in
    *heroic-games-launcher*|*com.heroicgameslauncher.hgl*|*'/usr/bin/heroic'*|*'/opt/heroic/'*|*'/opt/heroic '*|*'/usr/lib/heroic/'*|*'/app/bin/heroic'*|*'/app/heroic'*) return 0 ;;
    *) return 1 ;;
  esac
}

heroic_main_pids() {
  local p pid comm cmd low
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    [[ "$pid" != "$$" ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$comm$cmd" ]] || continue
    low="${comm,,} ${cmd,,}"
    heroic_process_identity "$low" || continue
    case "$low" in
      *' --type='*|*'--utility-sub-type='*|*legendary*|*gogdl*|*nile*|*umu-run*|*gameweld-heroic*) continue ;;
    esac
    printf '%s\n' "$pid"
  done | sort -n -u
}

heroic_main_running() {
  local p
  p="$(heroic_main_pids | head -n1 || true)"
  [[ -n "$p" ]]
}

# Return Heroic GUI/Electron processes, including renderer/helper children, but
# never the store backends or game-session processes that Heroic may have
# spawned. Test 8 only waited for the main Electron PID to exit; on some native
# Heroic builds a helper can briefly outlive it and keep Electron's single-
# instance handoff alive, so the immediate protocol relaunch disappears.
heroic_ui_process_pids() {
  local p pid comm cmd low
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    [[ "$pid" != "$$" ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$comm$cmd" ]] || continue
    low="${comm,,} ${cmd,,}"
    heroic_process_identity "$low" || continue
    case "$low" in
      *legendary*|*gogdl*|*nile*|*umu-run*|*proton*|*pressure-vessel*|*gameweld-heroic*) continue ;;
    esac
    printf '%s\n' "$pid"
  done | sort -n -u
}

pid_descendants() {
  # Print descendants of the supplied PID based strictly on PPid ownership.
  # This is used for Heroic cleanup so unrelated Electron applications can
  # never be selected merely because their command lines look similar.
  local root="$1" p pid ppid changed=1
  local -A owned=(["$root"]=1)
  while (( changed )); do
    changed=0
    for p in /proc/[0-9]*; do
      [[ -r "$p/status" ]] || continue
      pid="${p##*/}"
      [[ -n "${owned[$pid]:-}" ]] && continue
      ppid="$(awk '/^PPid:/{print $2;exit}' "$p/status" 2>/dev/null || true)"
      [[ -n "$ppid" && -n "${owned[$ppid]:-}" ]] || continue
      owned["$pid"]=1
      changed=1
    done
  done
  for pid in "${!owned[@]}"; do [[ "$pid" != "$root" ]] && printf '%s\n' "$pid"; done | sort -n
}

heroic_other_game_active() {
  local selected="${1:-}" p pid envs app
  for p in /proc/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    pid="${p##*/}"
    envs="$(cat "$p/environ" 2>/dev/null | tr '\0' '\n' || true)"
    app="$(awk -F= '$1=="HEROIC_APP_NAME"{sub(/^[^=]*=/,"");print;exit}' <<<"$envs")"
    [[ -n "$app" ]] || continue
    [[ -n "$selected" && "$app" == "$selected" ]] && continue
    printf '%s\t%s\n' "$pid" "$app"
    return 0
  done
  return 1
}

heroic_stop_main_for_reload() {
  local p i root
  local -a pids=() alive=() owned_helpers=()
  while IFS= read -r p; do [[ -n "$p" ]] && pids+=("$p"); done < <(heroic_main_pids)
  ((${#pids[@]})) || { echo 'Heroic main process is not running.' >&2; return 0; }

  # Snapshot only descendants that actually belong to the confirmed Heroic main
  # process before terminating anything. Never do a global Electron/app.asar
  # sweep; that was capable of selecting Discord in Test 13.
  for root in "${pids[@]}"; do
    while IFS= read -r p; do [[ -n "$p" ]] && owned_helpers+=("$p"); done < <(pid_descendants "$root")
  done
  if ((${#owned_helpers[@]})); then
    mapfile -t owned_helpers < <(printf '%s\n' "${owned_helpers[@]}" | sort -n -u)
  fi

  echo "Stopping Heroic main process for a clean configuration reload. Main PID(s): ${pids[*]}" >&2
  kill -TERM "${pids[@]}" 2>/dev/null || true
  for ((i=0;i<100;i++)); do
    alive=()
    for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive+=("$p") || true; done
    ((${#alive[@]}==0)) && break
    sleep 0.1
  done
  if ((${#alive[@]})); then
    echo "Heroic main process did not exit after TERM; forcing PID(s): ${alive[*]}" >&2
    kill -KILL "${alive[@]}" 2>/dev/null || true
  fi

  # Give genuine Heroic descendants a moment to exit naturally, then terminate
  # only the captured descendants that are still alive.
  for ((i=0;i<30;i++)); do
    alive=()
    for p in "${owned_helpers[@]}"; do kill -0 "$p" 2>/dev/null && alive+=("$p") || true; done
    ((${#alive[@]}==0)) && break
    sleep 0.1
  done
  if ((${#alive[@]})); then
    echo "Stopping captured Heroic child PID(s): ${alive[*]}" >&2
    kill -TERM "${alive[@]}" 2>/dev/null || true
    sleep 0.5
    local -a stubborn=()
    for p in "${alive[@]}"; do kill -0 "$p" 2>/dev/null && stubborn+=("$p") || true; done
    if ((${#stubborn[@]})); then
      echo "Forcing captured Heroic child PID(s): ${stubborn[*]}" >&2
      kill -KILL "${stubborn[@]}" 2>/dev/null || true
    fi
  fi

  sleep 0.3
  if heroic_main_running; then
    echo 'Heroic main process is still present after forced reload stop.' >&2
    return 1
  fi
  return 0
}

heroic_desktop_id() {
  local desktop=''
  if command -v xdg-mime >/dev/null 2>&1; then
    desktop="$(xdg-mime query default x-scheme-handler/heroic 2>/dev/null || true)"
  fi
  [[ -n "$desktop" ]] || desktop='com.heroicgameslauncher.hgl.desktop'
  printf '%s\n' "${desktop%.desktop}"
}

heroic_dispatch_uri_fresh() {
  local uri="$1" desktop_id root="${GAMEWELD_HEROIC_ROOT:-}"
  local -a clean_env=(
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

  # Use an explicit fresh process launcher after Test 8 intentionally stops the
  # old Heroic process. xdg-open is excellent for handing a URI to an existing
  # Heroic instance, but on some desktop setups it can return successfully while
  # the just-terminated Electron single-instance endpoint is still disappearing.
  if [[ "$root" == *'/.var/app/com.heroicgameslauncher.hgl/'* ]] && command -v flatpak >/dev/null 2>&1; then
    echo 'Starting a fresh Flatpak Heroic process with the launch URI.' >&2
    "${clean_env[@]}" flatpak run com.heroicgameslauncher.hgl "$uri" >/dev/null 2>&1 &
    return 0
  fi

  desktop_id="$(heroic_desktop_id)"
  if command -v gtk-launch >/dev/null 2>&1; then
    echo "Starting a fresh Heroic process through desktop entry: $desktop_id" >&2
    "${clean_env[@]}" gtk-launch "$desktop_id" "$uri" >/dev/null 2>&1 &
    return 0
  fi
  if command -v heroic >/dev/null 2>&1; then
    echo 'Starting a fresh native Heroic process directly.' >&2
    "${clean_env[@]}" heroic "$uri" >/dev/null 2>&1 &
    return 0
  fi
  if command -v flatpak >/dev/null 2>&1 && flatpak info com.heroicgameslauncher.hgl >/dev/null 2>&1; then
    echo 'Starting a fresh Flatpak Heroic process.' >&2
    "${clean_env[@]}" flatpak run com.heroicgameslauncher.hgl "$uri" >/dev/null 2>&1 &
    return 0
  fi
  # Last-resort protocol dispatch. Unlike Test 8, this is no longer the primary
  # restart mechanism.
  heroic_dispatch_uri "$uri"
}

heroic_wait_main_start() {
  local i max_ticks="${1:-150}"
  for ((i=0;i<max_ticks;i++)); do
    heroic_main_running && return 0
    sleep 0.1
  done
  return 1
}

heroic_launch_game_fresh_visible() {
  local runner="$1" appid="$2" uri
  uri="$(GAMEWELD_HEROIC_PROTOCOL_GUI=true heroic_uri "$appid" "$runner" "")"
  printf 'Fresh Heroic launch URI: %s\n' "$uri"
  heroic_dispatch_uri_fresh "$uri" || return 1
  if heroic_wait_main_start 150; then
    echo 'Fresh Heroic process detected; waiting for Heroic to own the game launch.' >&2
    return 0
  fi

  # If desktop activation itself was stale, make one final protocol dispatch
  # after the single-instance endpoint has definitely had time to disappear.
  echo 'Fresh desktop activation did not produce a Heroic main process; retrying the protocol handler once.' >&2
  heroic_dispatch_uri "$uri" || return 1
  heroic_wait_main_start 100
}

heroic_open_gui() {
  # Start a genuinely fresh Heroic process after the compatibility session has
  # been finalized. No URI is needed when the desktop entry supports startup,
  # but heroic://ping is harmless and works for all currently supported builds.
  heroic_dispatch_uri_fresh 'heroic://ping'
}

# Proton/UMU games can expose a live launcher service.  GameWeld enables the
# service in the selected Heroic game's own environment options, but never
# changes its Wine/Proton version or prefix.  UMU can then re-enter the exact
# live container and run a secondary Windows process there.
heroic_enable_umu_nsenter() {
  local appid="$1" out
  out="$(python3 "$HEROIC_PROVIDER" ensure-nsenter "$appid" 2>&1)" || { printf '%s\n' "$out" >&2; return 1; }
  printf 'Heroic UMU trainer bridge config: %s\n' "$out" >&2
}

umu_bus_name() {
  local prefix="$1" hash
  hash="$(printf '%s' "$prefix" | md5sum | awk '{print $1}')"
  printf 'com.steampowered.App%s\n' "$hash"
}

umu_bus_active() {
  local prefix="$1" bus client root
  bus="$(umu_bus_name "$prefix")"
  if command -v busctl >/dev/null 2>&1 && busctl --user list --no-legend 2>/dev/null | awk '{print $1}' | grep -Fqx "$bus"; then
    return 0
  fi
  # Some runtime versions expose the launcher service only through
  # steam-runtime-launch-client --list.  Probe a few standard UMU locations.
  for root in "${XDG_DATA_HOME:-$HOME/.local/share}/umu" "$HOME/.local/share/umu" /usr/lib /usr/lib64; do
    [[ -d "$root" ]] || continue
    while IFS= read -r client; do
      [[ -x "$client" ]] || continue
      if timeout 3 "$client" --list 2>/dev/null | grep -Fqx -- "--bus-name=$bus"; then return 0; fi
    done < <(find "$root" -maxdepth 7 -type f -name steam-runtime-launch-client 2>/dev/null | head -n 16)
  done
  return 1
}

wait_umu_bus() {
  local prefix="$1" max_wait="${2:-30}" i
  for ((i=0;i<max_wait;i++)); do
    umu_bus_active "$prefix" && return 0
    sleep 1
  done
  return 1
}


heroic_store_id() {
  case "${1,,}" in
    legendary|epic) printf '%s\n' egs ;;
    gog|gogdl) printf '%s\n' gog ;;
    nile|amazon) printf '%s\n' amazon ;;
    *) printf '%s\n' "${1,,}" ;;
  esac
}

heroic_find_native_legendary() {
  local c
  for c in \
    /usr/lib/heroic-games-launcher/app.asar.unpacked/build/bin/x64/linux/legendary \
    /opt/Heroic/resources/app.asar.unpacked/build/bin/x64/linux/legendary \
    /opt/heroic/resources/app.asar.unpacked/build/bin/x64/linux/legendary; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  done
  c="$(command -v legendary 2>/dev/null || true)"
  [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
  return 1
}

# Launch Epic/Legendary through Heroic's own authenticated Legendary backend,
# but supply the exact compatibility Proton/UMU environment ourselves.  This
# avoids relying on Heroic's already-running GUI process to notice a temporary
# GamesConfig edit before it dispatches the game.
heroic_launch_legendary_compat() {
  local appid="$1" install="$2" prefix="$3" proton="$4" heroic_root="$5"
  local legendary umu proton_root lcfg steamroot store
  legendary="$(heroic_find_native_legendary || true)"
  umu="$(command -v umu-run 2>/dev/null || true)"
  [[ -x "$legendary" && -x "$umu" && -x "$proton" && -n "$prefix" ]] || return 2
  proton_root="$(dirname -- "$proton")"
  lcfg="${heroic_root%/}/legendaryConfig/legendary"
  [[ -d "$lcfg" ]] || return 3
  steamroot="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-$HOME/.steam/steam}"
  store=egs
  echo "Launching Epic game through Heroic's authenticated Legendary backend with an explicit compatibility environment." >&2
  echo "Legendary backend: $legendary" >&2
  echo "Legendary config: $lcfg" >&2
  echo "Compatibility Proton: $proton_root" >&2
  echo "Compatibility prefix: $prefix" >&2
  env \
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
    HEROIC_APP_NAME="$appid" HEROIC_APP_RUNNER=legendary HEROIC_APP_SOURCE=epic \
    GAMEID=umu-0 STORE="$store" \
    WINEPREFIX="$prefix" STEAM_COMPAT_DATA_PATH="$prefix" \
    STEAM_COMPAT_INSTALL_PATH="$install" STEAM_COMPAT_CLIENT_INSTALL_PATH="$steamroot" \
    PROTONPATH="$proton_root" PROTON_ENABLE_WAYLAND=1 WINE_FULLSCREEN_FSR=0 \
    PROTON_EAC_RUNTIME="${heroic_root%/}/tools/runtimes/eac_runtime" \
    PROTON_BATTLEYE_RUNTIME="${heroic_root%/}/tools/runtimes/battleye_runtime" \
    STEAM_COMPAT_APP_ID=0 SteamAppId=0 SteamGameId="heroic-$appid" \
    LEGENDARY_CONFIG_PATH="$lcfg" \
    "$legendary" launch "$appid" --no-wine --wrapper "$umu" --language en >/dev/null 2>&1 &
  echo $!
}

# Official UMU multi-process path: launch the secondary program with the same
# prefix, Proton, GAMEID and store as the already-running game, changing only
# PROTON_VERB to runinprefix.  This works on UMU versions that predate the
# launcher-service/nsenter bridge and avoids host-Wine queueing.
heroic_umu_secondary() {
  local prefix="$1" proton="$2" install="$3" runner="$4" appid="$5" exe="$6"
  shift 6 || true
  local proton_root umu store steamroot
  umu="$(command -v umu-run 2>/dev/null || true)"
  [[ -x "$umu" && -x "$proton" && -n "$prefix" ]] || return 2
  proton_root="$(dirname -- "$proton")"
  store="$(heroic_store_id "$runner")"
  steamroot="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-$HOME/.steam/steam}"
  echo "Launching secondary Windows process through matching UMU runinprefix session: $exe $*" >&2
  echo "UMU prefix: $prefix" >&2
  echo "UMU Proton: $proton_root" >&2
  echo "UMU store: $store" >&2
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    "WINEPREFIX=$prefix" "STEAM_COMPAT_DATA_PATH=$prefix"
    "STEAM_COMPAT_INSTALL_PATH=$install" "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steamroot"
    "PROTONPATH=$proton_root" "GAMEID=umu-0" "STORE=$store"
    "PROTON_VERB=runinprefix" "PROTON_ENABLE_WAYLAND=1" "WINE_FULLSCREEN_FSR=0"
  )
  [[ -n "${GAMEWELD_SECONDARY_DLL_OVERRIDES:-}" ]] && cmd+=("WINEDLLOVERRIDES=$GAMEWELD_SECONDARY_DLL_OVERRIDES")
  [[ -n "${GAMEWELD_SECONDARY_WINEDEBUG:-}" ]] && cmd+=("WINEDEBUG=$GAMEWELD_SECONDARY_WINEDEBUG")
  cmd+=("$umu" "$exe" "$@")
  "${cmd[@]}"
}

heroic_proton_runinprefix() {
  local prefix="$1" proton="$2" install="$3" exe="$4" proton_root steamroot
  shift 4 || true
  [[ -x "$proton" && -n "$prefix" ]] || return 2
  proton_root="$(dirname -- "$proton")"
  steamroot="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-}"
  if [[ -z "$steamroot" ]]; then
    for candidate in "$HOME/.steam/steam" "$HOME/.local/share/Steam"; do
      if [[ -d "$candidate" ]]; then steamroot="$candidate"; break; fi
    done
  fi
  echo "Launching secondary Windows process through exact Heroic Proton runinprefix: $exe $*" >&2
  echo "Direct Proton prefix: $prefix" >&2
  echo "Direct Proton: $proton" >&2
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
    "WINEPREFIX=$prefix"
    "STEAM_COMPAT_DATA_PATH=$prefix"
    "STEAM_COMPAT_INSTALL_PATH=$install"
  )
  [[ -n "$steamroot" ]] && cmd+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$steamroot")
  cmd+=("$proton" runinprefix "$exe" "$@")
  "${cmd[@]}"
}

heroic_proton_wine_direct() {
  local prefix="$1" proton="$2" exe="$3" root wine wineserver rp
  shift 3 || true
  [[ -x "$proton" && -n "$prefix" ]] || return 2
  root="$(dirname -- "$proton")"
  wine=""
  for candidate in "$root/files/bin/wine" "$root/files/bin-wow64/wine" "$root/files/bin/wine64"; do
    if [[ -x "$candidate" ]]; then wine="$candidate"; break; fi
  done
  [[ -n "$wine" ]] || { echo "Could not resolve Wine inside Heroic Proton: $proton" >&2; return 2; }
  wineserver="$(dirname -- "$wine")/wineserver"
  [[ -x "$wineserver" ]] || wineserver=""
  if [[ -d "$prefix/pfx/drive_c" && ! -d "$prefix/drive_c" ]]; then rp="$prefix/pfx"; else rp="$prefix"; fi
  echo "Launching secondary Windows process with the exact Wine binary from Heroic's running Proton tool: $exe $*" >&2
  echo "Direct live WINEPREFIX: $rp" >&2
  echo "Direct Heroic Wine: $wine" >&2
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
    "WINEPREFIX=$rp"
  )
  [[ -n "$wineserver" ]] && cmd+=("WINESERVER=$wineserver")
  [[ -n "${GAMEWELD_SECONDARY_DLL_OVERRIDES:-}" ]] && cmd+=("WINEDLLOVERRIDES=$GAMEWELD_SECONDARY_DLL_OVERRIDES")
  [[ -n "${GAMEWELD_SECONDARY_WINEDEBUG:-}" ]] && cmd+=("WINEDEBUG=$GAMEWELD_SECONDARY_WINEDEBUG")
  cmd+=("$wine" "$exe" "$@")
  "${cmd[@]}"
}

heroic_umu_inject() {
  local prefix="$1" proton="$2" install="$3" runner="$4" appid="$5" exe="$6" proton_root umu store
  shift 6 || true
  umu="$(command -v umu-run 2>/dev/null || true)"
  [[ -x "$umu" ]] || { echo 'umu-run is not available; cannot use live Heroic trainer injection.' >&2; return 2; }
  [[ -x "$proton" && -n "$prefix" ]] || return 2
  proton_root="$(dirname -- "$proton")"
  store="$(heroic_store_id "$runner")"
  echo "Launching secondary Windows process through Heroic/UMU runner environment: $exe $*" >&2
  echo "UMU prefix: $prefix" >&2
  echo "UMU Proton: $proton_root" >&2
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    "WINEPREFIX=$prefix"
    "STEAM_COMPAT_DATA_PATH=$prefix"
    "STEAM_COMPAT_INSTALL_PATH=$install"
    "PROTONPATH=$proton_root"
    "GAMEID=umu-0" "STORE=$store"
    "PROTON_VERB=runinprefix" "UMU_CONTAINER_NSENTER=1" "UMU_LOG=1"
  )
  [[ -n "${GAMEWELD_SECONDARY_DLL_OVERRIDES:-}" ]] && cmd+=("WINEDLLOVERRIDES=$GAMEWELD_SECONDARY_DLL_OVERRIDES")
  [[ -n "${GAMEWELD_SECONDARY_WINEDEBUG:-}" ]] && cmd+=("WINEDEBUG=$GAMEWELD_SECONDARY_WINEDEBUG")
  cmd+=("$umu" "$exe" "$@")
  "${cmd[@]}"
}

windows_z_path() {
  local p="$1"
  p="${p//\\/\\\\}"
  p="${p//\//\\}"
  printf 'Z:%s\n' "$p"
}

heroic_proton_wine_version() {
  local proton="$1" root wine
  root="$(dirname -- "$proton")"
  for wine in "$root/files/bin/wine" "$root/files/bin-wow64/wine" "$root/files/bin/wine64"; do
    [[ -x "$wine" ]] || continue
    "$wine" --version 2>/dev/null | head -n1
    return 0
  done
  return 1
}

safe_cmdline() {
  local pid="$1"
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true
}

build_game_exe_hints() {
  local install="$1" primary="${2:-}" base stem lowstem raw
  base="$(basename -- "$primary" 2>/dev/null || true)"
  stem="${base%.*}"
  lowstem="${stem,,}"
  raw="$({
    if [[ -d "$install" ]]; then
      find "$install" -maxdepth 8 -type f -iname '*.exe' -printf '%s\t%f\n' 2>/dev/null \
        | sort -t$'\t' -k1,1nr \
        | awk -F'\t' '
            BEGIN{IGNORECASE=1}
            {
              name=$2; low=tolower(name)
              if (low ~ /^(unins|uninstall)/) next
              if (low ~ /(vcredist|dxsetup|ue4prereq|vc_redist|crashreportclient|crashpad_handler|easyanticheat|eac_launcher|beservice|battleye)/) next
              print name
              if (++n>=64) exit
            }'
    fi
  } | awk 'BEGIN{IGNORECASE=1} NF && !seen[tolower($0)]++')"

  # Some launchers use a small/root EXE that immediately starts the real game
  # (for example a launcher EXE -> a renderer-specific gameplay EXE). Prefer same-family
  # variants before the configured launcher EXE, then retain all other hints.
  {
    if [[ -n "$lowstem" ]]; then
      while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        lname="${name,,}"
        if [[ "$lname" == "${lowstem}_"*.exe || "$lname" == "${lowstem}-"*.exe || "$lname" == "${lowstem} "*.exe ]]; then
          printf '%s\n' "$name"
        fi
      done <<< "$raw"
    fi
    [[ -n "$base" ]] && printf '%s\n' "$base"
    printf '%s\n' "$raw"
  } | awk 'BEGIN{IGNORECASE=1} NF && !seen[tolower($0)]++' | head -n 64 | paste -sd'|' -
}
find_live_game_target() {
  local install="$1" hint_text="$2" hint hlow p pid cmd comm low ilow
  local -a hints=()
  IFS='|' read -r -a hints <<< "$hint_text"
  for hint in "${hints[@]}"; do
    [[ -n "$hint" ]] || continue
    hlow="${hint,,}"
    for p in /proc/[0-9]*; do
      [[ -d "$p" ]] || continue
      pid="${p##*/}"
      cmd="$(safe_cmdline "$pid")"
      [[ -n "$cmd" ]] || continue
      comm="$(cat "$p/comm" 2>/dev/null || true)"
      low="${cmd,,} ${comm,,}"
      # The GameWeld Heroic bridge itself receives the target EXE as an
      # argument, as do xdg-open/Heroic launcher processes.  Never treat those
      # wrapper command lines as proof that the Windows game process exists.
      case "${comm,,}" in bash|sh|dash|zsh|fish|python|python3|xdg-open|gio|flatpak|bwrap|timeout) continue ;; esac
      case "$low" in *gameweld-heroic*|*heroic://launch*) continue ;; esac
      if [[ "$low" == *"$hlow"* ]]; then
        printf '%s\t%s\t%s\n' "$pid" "$hint" "$cmd"
        return 0
      fi
    done
  done
  [[ -n "$install" ]] || return 1
  ilow="${install,,}"
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$cmd" ]] || continue
    low="${cmd,,}"
    [[ "$low" == *'.exe'* ]] || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"
    case "${comm,,}" in bash|sh|dash|zsh|fish|python|python3|xdg-open|gio|flatpak|bwrap|timeout) continue ;; esac
    case "$low" in
      *gameweld-heroic*|*heroic://launch*|*cheatengine*|*wineboot*|*wineserver*|*steamwebhelper*|*crashpad*|*crashreport*|*easyanticheat*|*battleye*) continue ;;
    esac
    if [[ "$low" == *"$ilow"* ]]; then
      printf '%s\t%s\t%s\n' "$pid" "$(basename -- "${cmd%% *}")" "$cmd"
      return 0
    fi
  done
  return 1
}

wait_for_live_game_target() {
  local install="$1" hints="$2" max_wait="${3:-120}" second target settled
  for ((second=0; second<max_wait; second++)); do
    target="$(find_live_game_target "$install" "$hints" || true)"
    if [[ -n "$target" ]]; then
      # A configured/root EXE may only be a bootstrap launcher.  Give the
      # process tree a short settle window, then rescan using the ranked hints
      # so a later gameplay child (e.g. *_DX12.exe) wins before trainer/CE.
      sleep 3
      settled="$(find_live_game_target "$install" "$hints" || true)"
      [[ -n "$settled" ]] && target="$settled"
      printf '%s\n' "$target"
      return 0
    fi
    if (( second > 0 && second % 10 == 0 )); then
      printf 'Heroic has been asked to launch the game, but the real Windows executable is not visible yet (%ss/%ss)...\n' "$second" "$max_wait" >&2
    fi
    sleep 1
  done
  return 1
}

is_windows_pe() {
  local f="$1" magic
  [[ -n "$f" && -f "$f" ]] || return 1
  case "${f,,}" in *.exe) ;; *) return 1 ;; esac
  magic="$(head -c 2 -- "$f" 2>/dev/null || true)"
  [[ "$magic" == 'MZ' ]]
}

resolve_windows_ce() {
  local supplied="${1:-}" ce
  if is_windows_pe "$supplied"; then printf '%s\n' "$supplied"; return 0; fi
  if [[ -x "$CE_MANAGER" ]]; then
    ce="$("$CE_MANAGER" windows-detect 0 2>/dev/null | tail -n1 || true)"
    if is_windows_pe "$ce"; then printf '%s\n' "$ce"; return 0; fi
  fi
  local root="${XDG_DATA_HOME:-$HOME/.local/share}/gameweld/cheat-engine-linux/7.7.1/windowsbin"
  if [[ -d "$root" ]]; then
    while IFS= read -r -d '' ce; do
      if is_windows_pe "$ce"; then printf '%s\n' "$ce"; return 0; fi
    done < <(find "$root" -maxdepth 3 -type f -iname 'cheatengine*.exe' -print0 2>/dev/null)
  fi
  return 1
}

wine_path_for_host() {
  local host="$1"
  printf 'Z:%s\n' "${host//\//\\}"
}

prepare_ct_path() {
  local table="$1" prefix="${2:-}" base dest drive
  base="$(basename -- "$table")"
  for drive in "$prefix/drive_c" "$prefix/pfx/drive_c"; do
    if [[ -d "$drive" ]]; then
      dest="$drive/users/Public/Documents/GameWeldTables"
      mkdir -p "$dest"
      cp -f -- "$table" "$dest/$base"
      printf 'C:\\users\\Public\\Documents\\GameWeldTables\\%s\n' "$base"
      return 0
    fi
  done
  wine_path_for_host "$table"
}

install_heroic_ce_autoattach_helper() {
  local ce_dir="$1" autorun helper
  [[ -d "$ce_dir" ]] || return 1
  autorun="$ce_dir/autorun"; mkdir -p "$autorun"
  helper="$autorun/gameweld-heroic-autoattach.lua"
  cat > "$helper" <<'LUA'
-- GameWeld Heroic auto-attach bridge.
-- The request file is one-shot: ordinary/manual Cheat Engine launches are inert.
local requestPath = getCheatEngineDir()..[[autorun\gameweld-heroic-request.txt]]
local f = io.open(requestPath, 'r')
if not f then return end
local req = {}
for line in f:lines() do
  local k,v = string.match(line, '^([^=]+)=(.*)$')
  if k then req[k] = v or '' end
end
f:close()
pcall(function() os.remove(requestPath) end)

local appid = req.appid or ''
local title = req.title or ''
local hintText = req.hints or ''
local primaryHint = req.primary or ''
local hints = {}
if primaryHint ~= '' then table.insert(hints, primaryHint) end
for h in string.gmatch(hintText, '([^|]+)') do
  local duplicate=false
  for _,e in ipairs(hints) do if string.lower(e)==string.lower(h) then duplicate=true break end end
  if not duplicate then table.insert(hints,h) end
end
local function lower(s) return string.lower(tostring(s or '')) end
local function basename(s) s=tostring(s or ''); return s:match('([^\\/]+)$') or s end
local function norm(s) return lower(s):gsub('[^%w]','') end
local function opened() return (getOpenedProcessID and getOpenedProcessID() or 0) ~= 0 end
local blocked={
 ['cheatengine.exe']=true,['cheatengine-x86_64.exe']=true,['cheatengine-x86_64-sse4-avx2.exe']=true,['cheat engine.exe']=true,
 ['explorer.exe']=true,['services.exe']=true,['svchost.exe']=true,['steam.exe']=true,['steamwebhelper.exe']=true,
 ['winedevice.exe']=true,['rpcss.exe']=true,['plugplay.exe']=true,['conhost.exe']=true,['start.exe']=true,['cmd.exe']=true,
 ['reg.exe']=true,['wineboot.exe']=true,
}
local function snapshot()
  local ok,p=pcall(getProcesslist)
  if not ok or type(p)~='table' then return {} end
  return p
end
local function attach(pid,name,why)
  if opened() then return true end
  local n=tonumber(pid); if not n then return false end
  local ok,err=pcall(function() openProcess(n) end)
  if ok and opened() then
    print(string.format('[GameWeld] Heroic auto-attached %s to %s (PID %s) via %s',appid,tostring(name),tostring(pid),why))
    return true
  end
  if not ok then print('[GameWeld] Heroic auto-attach openProcess failed: '..tostring(err)) end
  return false
end
local function tryExact(p)
  for _,hint in ipairs(hints) do
    local want=lower(basename(hint))
    for pid,name in pairs(p) do
      if lower(basename(name))==want and attach(pid,name,'Heroic executable hint') then return true end
    end
  end
  return false
end
local function tryWindow()
  if title=='' or not getWindowlist then return false end
  local want=norm(title); if #want<4 then return false end
  local ok,wins=pcall(getWindowlist); if not ok or type(wins)~='table' then return false end
  for pid,entry in pairs(wins) do
    local caption=''
    if type(entry)=='table' then caption=tostring(entry[2] or entry.caption or entry.Caption or '') else caption=tostring(entry or '') end
    local c=norm(caption)
    if c~='' and (c:find(want,1,true) or want:find(c,1,true)) and attach(pid,caption,'window title') then return true end
  end
  return false
end
local function tryTitle(p)
  if title=='' then return false end
  local tokens={}
  for token in string.gmatch(lower(title),'[%w]+') do if #token>=4 and token~='game' then table.insert(tokens,token) end end
  local bp,bn,bs=nil,nil,0
  for pid,name in pairs(p) do
    local b=lower(basename(name))
    if not blocked[b] then
      local n=norm(b); local score=0
      for _,token in ipairs(tokens) do if n:find(norm(token),1,true) then score=score+1 end end
      if score>bs then bp,bn,bs=pid,name,score end
    end
  end
  if bp and bs>=2 then return attach(bp,bn,'game-title process match') end
  return false
end
local function tryAttach()
  if opened() then return true end
  local p=snapshot()
  return tryExact(p) or tryWindow() or tryTitle(p)
end
if tryAttach() then return end
local attempts=0
local timer=createTimer(nil,false); timer.Interval=500
timer.OnTimer=function(t)
  attempts=attempts+1
  if tryAttach() or attempts>=240 then
    t.Enabled=false
    if not opened() then
      print(string.format('[GameWeld] Heroic auto-attach timed out for %s',appid))
      local visible={}
      for pid,name in pairs(snapshot()) do if #visible<96 then table.insert(visible,string.format('%s=%s',tostring(pid),tostring(name))) end end
      table.sort(visible); print('[GameWeld] CE-visible processes at timeout: '..table.concat(visible,' | '))
    end
    pcall(function() t.destroy() end)
  end
end
timer.Enabled=true
LUA
  printf '%s\n' "$helper"
}

write_heroic_attach_request() {
  local ce_dir="$1" appid="$2" title="$3" hints="$4" primary="$5" req
  req="$ce_dir/autorun/gameweld-heroic-request.txt"
  mkdir -p "$(dirname -- "$req")"
  title="${title//$'\n'/ }"; title="${title//$'\r'/ }"
  hints="${hints//$'\n'/}"; primary="${primary//$'\n'/}"
  cat > "$req" <<EOF_REQ
appid=$appid
title=$title
hints=$hints
primary=$primary
EOF_REQ
  printf '%s\n' "$req"
}
