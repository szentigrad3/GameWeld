#!/usr/bin/env bash
set -Eeuo pipefail

CMD="${1:-}"
APPID="${2:-}"
ARG="${3:-}"

CE_LINUX_URL="${WAND_CE_LINUX_URL:-https://cheatengine.org/download/CheatEngineLinux771.zip}"
CE_VERSION="7.7.1"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/gameweld"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/gameweld"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
CE_ROOT="$DATA/cheat-engine-linux/$CE_VERSION"
WINDOWSBIN="$CE_ROOT/windowsbin"
WINDOWS_STATE="$STATE/managed-cheat-engine-windows.txt"
CE_SETUP_COMPAT="$DATA/cheat-engine-windows-setup-prefix"
mkdir -p "$DATA" "$CACHE" "$STATE"
LOG="$STATE/cheat-engine-manager-${APPID:-global}.log"

usage() {
  cat <<'TXT'
GameWeld managed Cheat Engine provider

Usage:
  gameweld-cheat-engine-manager.sh detect APPID
  gameweld-cheat-engine-manager.sh status APPID
  gameweld-cheat-engine-manager.sh windows-detect APPID
  gameweld-cheat-engine-manager.sh install APPID /path/to/CheatEngineLinux771.zip
  gameweld-cheat-engine-manager.sh download-install APPID
  gameweld-cheat-engine-manager.sh install APPID /path/to/CheatEngine-setup.exe

The native Linux Cheat Engine 7.7.1 archive provides GameWeld's Linux CE bridge.
For automatic Proton handoff, install a Windows Cheat Engine package once as
well; GameWeld copies the resulting Windows CE directory into the bridge's windowsbin
folder, matching Cheat Engine's supported Linux Proton-launcher layout.
TXT
}

[[ "$CMD" =~ ^(detect|status|windows-detect|install|download-install)$ ]] || { usage >&2; exit 2; }
[[ "$APPID" =~ ^[0-9]+$ ]] || { usage >&2; exit 2; }

read_proc_env() {
  local pid="$1"
  [[ -r "/proc/$pid/environ" ]] || return 1
  cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n'
}

is_windows_ce_payload() {
  local f="$1" magic base
  [[ -n "$f" && -f "$f" ]] || return 1
  base="${f##*/}"
  case "${base,,}" in *.exe) ;; *) return 1 ;; esac
  magic="$(head -c 2 -- "$f" 2>/dev/null || true)"
  [[ "$magic" == "MZ" ]]
}

find_proton_from_config_info() {
  local compat="$1" cfg line candidate parent marker
  [[ -n "$compat" ]] || return 1
  cfg="$compat/config_info"
  [[ -r "$cfg" ]] || return 1
  while IFS= read -r line; do
    line="${line%$'\r'}"
    [[ -n "$line" ]] || continue
    if [[ "$line" == */proton && -x "$line" ]]; then printf '%s\n' "$line"; return 0; fi
    [[ "$line" == /* ]] || continue
    candidate="$line"
    [[ -d "$candidate" ]] || candidate="$(dirname -- "$candidate")"
    for _ in {1..12}; do
      [[ -n "$candidate" && "$candidate" != "/" && "$candidate" != "." ]] || break
      if [[ -x "$candidate/proton" ]]; then printf '%s\n' "$candidate/proton"; return 0; fi
      parent="$(dirname -- "$candidate")"
      [[ "$parent" != "$candidate" ]] || break
      candidate="$parent"
    done
  done < <(strings -a "$cfg" 2>/dev/null || tr '\0' '\n' < "$cfg" 2>/dev/null || true)
  while IFS= read -r line; do
    for marker in /files/ /dist/; do
      case "$line" in *"$marker"*) candidate="${line%%$marker*}"; [[ -x "$candidate/proton" ]] && { printf '%s\n' "$candidate/proton"; return 0; };; esac
    done
  done < <(strings -a "$cfg" 2>/dev/null || true)
  return 1
}

find_active_session() {
  local p pid env compat tools proton item steamroot q parent cmdline
  for p in /proc/[0-9]*; do
    pid="${p##*/}"
    env="$(read_proc_env "$pid" || true)"
    [[ "$env" == *"SteamAppId=$APPID"* || "$env" == *"SteamGameId=$APPID"* || "$env" == *"STEAM_COMPAT_APP_ID=$APPID"* ]] || continue
    compat="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' | head -1)"
    [[ -n "$compat" && -d "$compat/pfx" ]] || continue
    tools="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' | head -1)"
    steamroot="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_CLIENT_INSTALL_PATH=//p' | head -1)"
    proton=""
    IFS=':' read -r -a parts <<< "$tools"
    for item in "${parts[@]}"; do
      [[ -x "$item/proton" ]] && { proton="$item/proton"; break; }
    done
    if [[ -z "$proton" ]]; then
      q="$pid"
      for _ in {1..14}; do
        [[ -r "/proc/$q/stat" ]] || break
        cmdline="$(tr '\0' ' ' < "/proc/$q/cmdline" 2>/dev/null || true)"
        if [[ "$cmdline" =~ (^|[[:space:]])([^[:space:]]*/proton)([[:space:]]|$) ]]; then
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

steam_roots() {
  {
    printf '%s\n' \
      "$HOME/.local/share/Steam" \
      "$HOME/.steam/root" \
      "$HOME/.steam/steam" \
      "$HOME/.var/app/com.valvesoftware.Steam/data/Steam" \
      "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" \
      "/mnt/games/Steam"
    find /mnt /media "/run/media/${USER:-}" -maxdepth 4 -type d -name Steam -print 2>/dev/null || true
  } | while IFS= read -r p; do
    [[ -d "$p" ]] || continue
    readlink -f "$p" 2>/dev/null || printf '%s\n' "$p"
  done | awk 'NF && !seen[$0]++'
}

steam_libraries() {
  local root vdf path
  while IFS= read -r root; do
    printf '%s\n' "$root"
    vdf="$root/config/libraryfolders.vdf"
    [[ -r "$vdf" ]] || continue
    while IFS= read -r path; do
      [[ -n "$path" && -d "$path" ]] && printf '%s\n' "$path"
    done < <(sed -n 's/^[[:space:]]*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$vdf" | sed 's/\\\\/\\/g')
  done < <(steam_roots)
}

find_compatdata() {
  local lib p
  while IFS= read -r lib; do
    p="$lib/steamapps/compatdata/$APPID"
    [[ -d "$p/pfx" ]] && { printf '%s\n' "$p"; return 0; }
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
  return 1
}

find_native_ce() {
  local saved f
  saved="$STATE/managed-cheat-engine-linux.txt"
  if [[ -r "$saved" ]]; then
    IFS= read -r f < "$saved" || true
    [[ -n "${f:-}" && -f "$f" ]] && { chmod +x "$f" 2>/dev/null || true; [[ -x "$f" ]] && { printf '%s\n' "$f"; return 0; }; }
  fi
  [[ -d "$CE_ROOT" ]] || return 1
  # Official builds have changed exact filenames over time, so detect instead
  # of hardcoding one package layout. Prefer the 64-bit main GUI and exclude
  # tutorial/server/helper binaries.
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    case "${f,,}" in
      *tutorial*|*ceserver*|*server*|*uninstall*) continue ;;
    esac
    chmod +x "$f" 2>/dev/null || true
    if [[ -x "$f" ]] && head -c 4 "$f" 2>/dev/null | LC_ALL=C grep -q $'^\x7fELF'; then
      printf '%s\n' "$f" > "$saved"
      printf '%s\n' "$f"
      return 0
    fi
  done < <(find "$CE_ROOT" -maxdepth 5 -type f \( -iname 'cheatengine-x86_64*' -o -iname 'cheatengine*' -o -iname '*cheat*engine*' \) -print 2>/dev/null | sort -V)
  return 1
}

find_ce_in_prefix() {
  local compat="$1" pfx f
  pfx="$compat/pfx"
  [[ -d "$pfx" ]] || return 1
  # CE 7.7 can install the AVX2/SSE4 GUI rather than the older plain
  # cheatengine-x86_64.exe name, and some installer builds use AppData.
  # Search broadly for a real PE Cheat Engine GUI while excluding helpers.
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    case "${f,,}" in
      *tutorial*|*ceserver*|*server*|*unins*.exe|*uninstall*.exe) continue ;;
    esac
    if is_windows_ce_payload "$f"; then
      printf '%s\n' "$f"
      return 0
    fi
  done < <(find "$pfx/drive_c" -maxdepth 10 -type f \
      \( -iname 'cheatengine-x86_64*.exe' -o -iname 'cheatengine-i386*.exe' -o -iname 'cheatengine*.exe' -o -iname 'cheat engine*.exe' \) \
      2>/dev/null | sort -V -r)
  return 1
}

find_windows_companion() {
  local f
  if [[ -r "$WINDOWS_STATE" ]]; then
    IFS= read -r f < "$WINDOWS_STATE" || true
    if [[ -n "${f:-}" ]] && is_windows_ce_payload "$f"; then printf '%s\n' "$f"; return 0; fi
  fi
  [[ -d "$WINDOWSBIN" ]] || return 1
  f="$(find "$WINDOWSBIN" -maxdepth 5 -type f \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
  [[ -n "$f" ]] && is_windows_ce_payload "$f" || return 1
  printf '%s\n' "$f" > "$WINDOWS_STATE"
  printf '%s\n' "$f"
}

find_any_installed_windows_ce() {
  local lib compat ce
  # First check Wand's dedicated setup prefix, then every Steam Proton prefix.
  if ce="$(find_ce_in_prefix "$CE_SETUP_COMPAT" 2>/dev/null || true)"; then
    [[ -n "$ce" ]] && { printf '%s\n' "$ce"; return 0; }
  fi
  while IFS= read -r lib; do
    [[ -d "$lib/steamapps/compatdata" ]] || continue
    for compat in "$lib"/steamapps/compatdata/*; do
      [[ -d "$compat/pfx" ]] || continue
      ce="$(find_ce_in_prefix "$compat" 2>/dev/null || true)"
      [[ -n "$ce" ]] && { printf '%s\n' "$ce"; return 0; }
    done
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
  return 1
}

repair_windows_companion() {
  local ce shared
  if ce="$(find_windows_companion 2>/dev/null || true)"; then
    [[ -n "$ce" ]] && { printf '%s\n' "$ce"; return 0; }
  fi
  ce="$(find_any_installed_windows_ce 2>/dev/null || true)"
  [[ -n "$ce" ]] || return 1
  echo "Recovering existing Windows Cheat Engine installation: $ce" >&2
  shared="$(copy_windows_ce_to_windowsbin "$ce" | tail -1)"
  [[ -n "$shared" ]] || return 1
  printf '%s\n' "$shared"
}

find_any_proton() {
  local lib compat p root f
  # Prefer the selected game's recorded Proton build.
  compat="$(find_compatdata 2>/dev/null || true)"
  if [[ -n "$compat" ]] && p="$(find_proton_from_config_info "$compat" 2>/dev/null || true)" && [[ -x "$p" ]]; then
    printf '%s\n' "$p"; return 0
  fi
  # Then reuse any known Proton build from an existing Steam compatdata prefix.
  while IFS= read -r lib; do
    [[ -d "$lib/steamapps/compatdata" ]] || continue
    for compat in "$lib"/steamapps/compatdata/*; do
      [[ -r "$compat/config_info" ]] || continue
      p="$(find_proton_from_config_info "$compat" 2>/dev/null || true)"
      [[ -n "$p" && -x "$p" ]] && { printf '%s\n' "$p"; return 0; }
    done
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
  # Finally scan the normal custom compatibility-tool locations.
  for root in \
    "$HOME/.local/share/Steam/compatibilitytools.d" \
    "$HOME/.steam/root/compatibilitytools.d" \
    "$HOME/.steam/steam/compatibilitytools.d" \
    "$HOME/.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d" \
    "/mnt/games/Steam/compatibilitytools.d"; do
    [[ -d "$root" ]] || continue
    f="$(find "$root" -maxdepth 4 -type f -name proton -perm -u+x 2>/dev/null | sort -V -r | head -1 || true)"
    [[ -n "$f" && -x "$f" ]] && { printf '%s\n' "$f"; return 0; }
  done
  return 1
}

copy_windows_ce_to_windowsbin() {
  local ce="$1" src f
  is_windows_ce_payload "$ce" || return 1
  src="$(cd -- "$(dirname -- "$ce")" && pwd)"
  mkdir -p "$CE_ROOT"
  rm -rf "$WINDOWSBIN"
  mkdir -p "$WINDOWSBIN"
  cp -a "$src"/. "$WINDOWSBIN"/
  f="$(find "$WINDOWSBIN" -maxdepth 3 -type f \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
  [[ -n "$f" ]] && is_windows_ce_payload "$f" || return 1
  printf '%s\n' "$f" > "$WINDOWS_STATE"
  echo "Windows CE companion populated: $f"
  printf '%s\n' "$f"
}

extract_windows_archive() {
  local archive="$1" stage="$CACHE/ce-windows-stage-$$" ce
  rm -rf "$stage"; mkdir -p "$stage"
  if command -v unzip >/dev/null 2>&1; then unzip -q -o "$archive" -d "$stage"; else python3 -m zipfile -e "$archive" "$stage"; fi
  ce="$(find "$stage" -maxdepth 8 -type f \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -n "$ce" ]] && is_windows_ce_payload "$ce"; then
    copy_windows_ce_to_windowsbin "$ce"
    rm -rf "$stage"
    return 0
  fi
  rm -rf "$stage"
  return 1
}

extract_linux_archive() {
  local archive="$1" stage="$CACHE/ce-linux-stage-$$" exe preserve="$CACHE/ce-windowsbin-preserve-$$"
  [[ -f "$archive" ]] || { echo "Cheat Engine Linux archive not found: $archive" >&2; return 3; }
  rm -rf "$stage"
  mkdir -p "$stage"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$archive" -d "$stage"
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m zipfile -e "$archive" "$stage"
  else
    echo "Need unzip or python3 to extract the official Cheat Engine Linux ZIP." >&2
    return 7
  fi
  rm -rf "$preserve"
  if [[ -d "$WINDOWSBIN" ]]; then mkdir -p "$preserve"; cp -a "$WINDOWSBIN"/. "$preserve"/; fi
  rm -rf "$CE_ROOT"
  mkdir -p "$CE_ROOT"
  cp -a "$stage"/. "$CE_ROOT"/
  if [[ -d "$preserve" ]]; then mkdir -p "$WINDOWSBIN"; cp -a "$preserve"/. "$WINDOWSBIN"/; rm -rf "$preserve"; fi
  rm -rf "$stage"
  rm -f "$STATE/managed-cheat-engine-linux.txt"
  exe="$(find_native_ce || true)"
  [[ -n "$exe" ]] || { echo "Archive extracted, but no native Cheat Engine ELF executable was detected." >&2; return 8; }
  echo "Native Cheat Engine installed: $exe"
  if command -v ldd >/dev/null 2>&1; then
    missing="$(ldd "$exe" 2>/dev/null | awk '/not found/{print $1}' | paste -sd, - || true)"
    [[ -z "$missing" ]] || echo "Warning: missing shared libraries: $missing"
  fi
  printf '%s\n' "$exe"
}

download_linux_archive() {
  local out="$CACHE/CheatEngineLinux771.zip.part" final="$CACHE/CheatEngineLinux771.zip"
  rm -f "$out"
  echo "Downloading official Cheat Engine Linux 7.7.1: $CE_LINUX_URL" >&2
  case "$CE_LINUX_URL" in
    file://*) cp -f -- "${CE_LINUX_URL#file://}" "$out" ;;
    *)
      if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --connect-timeout 20 -o "$out" "$CE_LINUX_URL"
      elif command -v wget >/dev/null 2>&1; then
        wget -O "$out" "$CE_LINUX_URL"
      else
        echo "Need curl or wget for one-click Cheat Engine download." >&2
        return 9
      fi
      ;;
  esac
  mv -f "$out" "$final"
  command -v sha256sum >/dev/null 2>&1 && sha256sum "$final" >&2 || true
  printf '%s\n' "$final"
}

compat=""
session="$(find_active_session || true)"
if [[ -n "$session" ]]; then
  IFS=$'\t' read -r GAMEPID compat PROTON STEAMROOT <<< "$session"
else
  compat="$(find_compatdata || true)"
fi

case "$CMD" in
  detect)
    # Detect/Refresh also repairs windowsbin from a CE install left in any
    # Proton prefix by earlier Wand builds.
    repair_windows_companion >/dev/null 2>&1 || true
    if ce="$(find_native_ce 2>/dev/null)"; then printf '%s\n' "$ce"; exit 0; fi
    [[ -n "$compat" ]] || exit 1
    find_ce_in_prefix "$compat"
    ;;
  windows-detect)
    if ce="$(repair_windows_companion 2>/dev/null || true)"; then
      [[ -n "$ce" ]] && { printf '%s\n' "$ce"; exit 0; }
    fi
    exit 1
    ;;
  status)
    if ce="$(find_native_ce 2>/dev/null)"; then
      echo "installed-native-linux:$ce"
      exit 0
    fi
    if [[ -n "$compat" ]] && ce="$(find_ce_in_prefix "$compat" 2>/dev/null)"; then
      echo "installed-windows-proton:$ce"
      exit 0
    fi
    echo "not-installed"
    exit 1
    ;;
  download-install)
    exec >>"$LOG" 2>&1
    printf '\n[%(%F %T)T] managed native Linux CE download/install appid=%s\n' -1 "$APPID"
    archive="$(download_linux_archive)"
    extract_linux_archive "$archive"
    ;;
  install)
    [[ -f "$ARG" ]] || { echo "Cheat Engine package not found: $ARG" >&2; exit 3; }
    exec >>"$LOG" 2>&1
    printf '\n[%(%F %T)T] managed CE install appid=%s package=%s\n' -1 "$APPID" "$ARG"

    case "${ARG,,}" in
      *.zip)
        if extract_windows_archive "$ARG"; then
          echo "Installed Windows CE companion from ZIP into: $WINDOWSBIN"
          exit 0
        fi
        extract_linux_archive "$ARG"
        exit $?
        ;;
    esac

    # Windows CE setup path. The package is a global Wand dependency, not a
    # per-game modification, so install it in a dedicated Wand Proton prefix.
    # The selected game is used only as a hint for locating an installed Proton.
    PROTON="$(find_any_proton 2>/dev/null || true)"
    if [[ -z "$PROTON" && -n "$session" ]]; then
      IFS=$'\t' read -r GAMEPID compat PROTON STEAMROOT <<< "$session"
    fi
    [[ -n "${PROTON:-}" && -x "$PROTON" ]] || { echo "Could not resolve an installed Proton executable for Windows Cheat Engine setup."; exit 5; }

    STEAMROOT="${STEAMROOT:-}"
    if [[ -z "$STEAMROOT" ]]; then STEAMROOT="$(steam_roots | head -1 || true)"; fi
    mkdir -p "$CE_SETUP_COMPAT"
    echo "Windows CE setup prefix: $CE_SETUP_COMPAT"
    echo "Proton: $PROTON"
    env_args=("STEAM_COMPAT_DATA_PATH=$CE_SETUP_COMPAT")
    [[ -n "$STEAMROOT" ]] && env_args+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAMROOT")
    # Use Proton 'run' once so a fresh dedicated prefix is initialized before
    # the installer starts. This keeps CE and any installer extras out of games.
    env -u LD_LIBRARY_PATH -u LD_PRELOAD -u APPDIR -u APPIMAGE -u OWD \
      "${env_args[@]}" SteamAppId=0 SteamGameId=0 STEAM_COMPAT_APP_ID=0 WINEDEBUG=-all \
      "$PROTON" run "$ARG" || echo "Windows CE installer returned a non-zero status; checking for a completed installation anyway."

    # Some CE installer builds exit their bootstrap process before the final
    # installed files settle. Poll the dedicated prefix and all legacy prefixes
    # so Test 8 installations are recovered too.
    ce=""
    for _ in {1..60}; do
      ce="$(find_ce_in_prefix "$CE_SETUP_COMPAT" 2>/dev/null || true)"
      [[ -n "$ce" ]] || ce="$(find_any_installed_windows_ce 2>/dev/null || true)"
      [[ -n "$ce" ]] && break
      sleep 1
    done
    [[ -n "$ce" ]] || { echo "Installer finished, but no Windows Cheat Engine GUI executable was detected. Expected cheatengine*.exe (including AVX2/SSE4 builds)."; exit 6; }
    echo "Windows Cheat Engine detected: $ce"
    shared="$(copy_windows_ce_to_windowsbin "$ce" | tail -1)"
    [[ -n "$shared" ]] || { echo "Windows CE installed, but Wand could not populate the shared windowsbin companion."; exit 7; }
    printf '%s\n' "$shared" > "$STATE/managed-cheat-engine-${APPID}.txt"
    echo "Automatic Proton handoff companion ready: $shared"
    ;;
esac
