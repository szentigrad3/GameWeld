#!/usr/bin/env bash
set -Eeuo pipefail
ACTION="${1:?action required}"; RUNNER="${2:-}"; APPID="${3:-}"; TITLE="${4:-$APPID}"; PREFIX="${5:-}"; WINE_TYPE="${6:-}"; WINE_BIN="${7:-}"; TRAINER="${8:-}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"; mkdir -p "$STATE"
LOG="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] action=%s runner=%s appid=%s title=%s prefix=%s wine_type=%s wine_bin=%s trainer=%s\n' -1 "$ACTION" "$RUNNER" "$APPID" "$TITLE" "$PREFIX" "$WINE_TYPE" "$WINE_BIN" "$TRAINER"
LOCK="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').repairing"
PROGRESS="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').progress"
RESULT="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').result"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/gameweld"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/gameweld"
REPAIR_RUNTIME_TAG="GE-Proton10-34"
REPAIR_RUNTIME_ROOT="$DATA/repair-runtimes/$REPAIR_RUNTIME_TAG"
REPAIR_RUNTIME_URL="https://github.com/GloriousEggroll/proton-ge-custom/releases/download/$REPAIR_RUNTIME_TAG/$REPAIR_RUNTIME_TAG.tar.gz"
REPAIR_RUNTIME_SUM_URL="https://github.com/GloriousEggroll/proton-ge-custom/releases/download/$REPAIR_RUNTIME_TAG/$REPAIR_RUNTIME_TAG.sha512sum"
# Official Microsoft .NET Framework 4.8 offline installer.  The exact build and
# checksum match the installer used by the established Linux WeMod launcher path.
DOTNET48_OFFLINE_URL="${GAMEWELD_DOTNET48_OFFLINE_URL:-https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu.exe}"
DOTNET48_OFFLINE_SHA256="${GAMEWELD_DOTNET48_OFFLINE_SHA256:-95889D6DE3F2070C07790AD6CF2000D33D9A1BDFC6A381725AB82AB1C314FD53}"
lock_pid(){ [[ -r "$LOCK" ]] && head -n1 "$LOCK" 2>/dev/null || true; }
lock_active(){ local p; p="$(lock_pid)"; [[ "$p" =~ ^[0-9]+$ ]] && kill -0 "$p" 2>/dev/null; }
clear_stale_lock(){ if [[ -e "$LOCK" ]] && ! lock_active; then rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true; fi; }
write_progress(){ printf '%s\n' "$*" > "$PROGRESS"; }
write_result(){ local tmp="$RESULT.tmp.$$"; printf '%s\n' "$@" > "$tmp"; mv -f -- "$tmp" "$RESULT"; }
kill_descendants(){ local parent="$1" child; while read -r child; do [[ "$child" =~ ^[0-9]+$ ]] || continue; kill_descendants "$child"; kill -TERM "$child" 2>/dev/null || true; done < <(pgrep -P "$parent" 2>/dev/null || true); }

repair_runtime_proton(){
  local c
  for c in     "$REPAIR_RUNTIME_ROOT/proton"     "$HOME/.steam/root/compatibilitytools.d/$REPAIR_RUNTIME_TAG/proton"     "$HOME/.local/share/Steam/compatibilitytools.d/$REPAIR_RUNTIME_TAG/proton"     "$HOME/.config/heroic/tools/proton/$REPAIR_RUNTIME_TAG/proton"     "/usr/share/steam/compatibilitytools.d/$REPAIR_RUNTIME_TAG/proton"; do
    [[ -x "$c" ]] && { printf '%s
' "$c"; return 0; }
  done
  # Accept an installed GE-Proton 10.x as a repair-only helper.  The user's
  # actual game runner remains untouched; this helper is used only by
  # Winetricks while the game is closed.
  for root in     "$HOME/.steam/root/compatibilitytools.d"     "$HOME/.local/share/Steam/compatibilitytools.d"     "$HOME/.config/heroic/tools/proton"     "/usr/share/steam/compatibilitytools.d"; do
    [[ -d "$root" ]] || continue
    while IFS= read -r c; do [[ -x "$c" ]] && { printf '%s
' "$c"; return 0; }; done < <(find "$root" -maxdepth 2 -type f -path '*/GE-Proton10-*/proton' 2>/dev/null | sort -Vr)
  done
  return 1
}
repair_runtime_wine(){
  local proton="$1" root c
  [[ -x "$proton" ]] || return 1
  root="$(dirname -- "$proton")"
  for c in "$root/files/bin/wine" "$root/files/bin/wine64" "$root/dist/bin/wine"; do
    [[ -x "$c" ]] && { printf '%s
' "$c"; return 0; }
  done
  return 1
}
repair_runtime_wineserver(){
  local wine="$1" c d; d="$(dirname -- "$wine")"
  for c in "$d/wineserver" "$(dirname -- "$d")/bin/wineserver"; do [[ -x "$c" ]] && { printf '%s
' "$c"; return 0; }; done
  return 1
}
download_repair_runtime(){
  local curlbin tarball sumfile tmp extracted
  curlbin="$(command -v curl 2>/dev/null || true)"
  [[ -n "$curlbin" ]] || { write_result 'state=error' 'summary=curl is required to download the managed repair runtime.'; echo 'curl is required.'; return 9; }
  mkdir -p "$CACHE/repair-runtimes" "$DATA/repair-runtimes"
  tarball="$CACHE/repair-runtimes/$REPAIR_RUNTIME_TAG.tar.gz"
  sumfile="$CACHE/repair-runtimes/$REPAIR_RUNTIME_TAG.sha512sum"
  write_progress "downloading $REPAIR_RUNTIME_TAG repair runtime (~500 MB)"
  echo "Downloading repair-only runtime $REPAIR_RUNTIME_TAG from the official GE-Proton GitHub release."
  "$curlbin" -fL --retry 3 --retry-delay 2 -o "$tarball.part" "$REPAIR_RUNTIME_URL"
  mv -f "$tarball.part" "$tarball"
  "$curlbin" -fL --retry 3 --retry-delay 2 -o "$sumfile" "$REPAIR_RUNTIME_SUM_URL"
  write_progress 'verifying repair runtime checksum'
  ( cd "$(dirname -- "$tarball")"; sha512sum -c "$(basename -- "$sumfile")" )
  tmp="$DATA/repair-runtimes/.extract-$REPAIR_RUNTIME_TAG-$$"; rm -rf "$tmp"; mkdir -p "$tmp"
  write_progress 'extracting managed repair runtime'
  tar -xzf "$tarball" -C "$tmp"
  extracted="$(find "$tmp" -maxdepth 2 -type f -name proton -printf '%h
' 2>/dev/null | head -n1 || true)"
  [[ -n "$extracted" && -x "$extracted/proton" ]] || { rm -rf "$tmp"; write_result 'state=error' 'summary=Downloaded repair runtime did not contain a usable proton executable.'; return 10; }
  rm -rf "$REPAIR_RUNTIME_ROOT"
  mv "$extracted" "$REPAIR_RUNTIME_ROOT"
  rm -rf "$tmp"
  write_progress 'repair runtime ready'
  write_result 'state=helper-ready' "summary=Managed repair runtime $REPAIR_RUNTIME_TAG is ready. The Heroic game runner was not changed." "helper=$REPAIR_RUNTIME_ROOT/proton"
  echo "Managed repair runtime ready: $REPAIR_RUNTIME_ROOT/proton"
}

real_prefix(){
  if [[ -n "$PREFIX" && -d "$PREFIX/pfx/drive_c" && ! -d "$PREFIX/drive_c" ]]; then printf '%s\n' "$PREFIX/pfx"; else printf '%s\n' "$PREFIX"; fi
}
resolve_wine(){
  local root c
  case "${WINE_TYPE,,}" in
    proton|proton-ge|ge-proton|umu)
      if [[ -n "$WINE_BIN" ]]; then
        root="$(dirname -- "$WINE_BIN")"
        for c in "$root/files/bin/wine" "$root/files/bin/wine64" "$root/dist/bin/wine" "$root/bin/wine"; do
          [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
        done
      fi
      ;;
    *) [[ -x "$WINE_BIN" ]] && { printf '%s\n' "$WINE_BIN"; return 0; } ;;
  esac
  command -v wine 2>/dev/null || true
}
resolve_wineserver(){
  local w="$1" c d
  [[ -n "$w" ]] || return 0
  d="$(dirname -- "$w")"
  for c in "$d/wineserver" "$(dirname -- "$d")/bin/wineserver"; do [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }; done
  command -v wineserver 2>/dev/null || true
}
active_prefix_processes(){
  local rp="$1" p pid envs comm
  [[ -n "$rp" ]] || return 0
  for p in /proc/[0-9]*; do
    [[ -r "$p/environ" ]] || continue; pid="${p##*/}"; [[ "$pid" != "$$" ]] || continue
    envs="$(cat "$p/environ" 2>/dev/null | tr '\0' '\n' || true)"
    if grep -Fqx "WINEPREFIX=$rp" <<<"$envs" || { [[ -n "$PREFIX" ]] && grep -Fqx "STEAM_COMPAT_DATA_PATH=$PREFIX" <<<"$envs"; }; then
      comm="$(cat "$p/comm" 2>/dev/null || true)"
      case "${comm,,}" in bash|sh|dash|zsh|fish|gameweld) continue;; esac
      printf '%s %s\n' "$pid" "$comm"
    fi
  done | sort -u
}

RP="$(real_prefix)"
WINE_EXE="$(resolve_wine)"
WINESERVER_EXE="$(resolve_wineserver "$WINE_EXE")"
WINETRICKS_BIN="$(command -v winetricks 2>/dev/null || true)"

echo "Effective prefix: $RP"
echo "Resolved Wine: ${WINE_EXE:-<not found>}"
echo "Resolved wineserver: ${WINESERVER_EXE:-<not found>}"
echo "Winetricks: ${WINETRICKS_BIN:-<not found>}"

[[ -n "$RP" && -d "$RP" ]] || { write_result 'state=error' 'summary=Heroic prefix does not exist yet. Launch the game once first.'; echo 'Heroic prefix does not exist yet. Launch the game once first.'; exit 3; }
[[ -n "$WINE_EXE" && -x "$WINE_EXE" ]] || { write_result 'state=error' "summary=Could not resolve the Wine binary inside Heroic's configured runner."; echo "Could not resolve the Wine binary inside Heroic's configured runner."; exit 4; }
[[ -n "$WINETRICKS_BIN" && -x "$WINETRICKS_BIN" ]] || { write_result 'state=error' 'summary=winetricks is not installed. Install the winetricks package, or use Heroic Game Settings -> Wine -> Winetricks.'; echo 'winetricks is not installed. Install the winetricks package, or use Heroic -> Game Settings -> Wine -> Winetricks.'; exit 5; }

wt_with(){
  local wine="$1" wineserver="$2"; shift 2
  env \
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH \
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH \
    -u PYTHONHOME -u PYTHONPATH \
    WINEPREFIX="$RP" WINE="$wine" WINESERVER="${wineserver:-wineserver}" \
    "$WINETRICKS_BIN" "$@"
}
wt(){ wt_with "$WINE_EXE" "${WINESERVER_EXE:-wineserver}" "$@"; }

# Native Microsoft .NET Framework installation is unusually sensitive to
# Proton-created prefixes.  Proton/GE commonly seed synthetic .NET registry
# keys and use read-only symlinks into their template.  Both can make
# Winetricks dotnet40/dotnet48 fail with status 67 / MSI 1603 / FDICopy.
#
# Test 30 fixes a field-proven Test 29 false positive: a failed installer can
# leave the .NET 4.8 Release registry value behind even though the native CLR
# payload is incomplete.  We therefore require the Release value, the real
# Framework + Framework64 CLR payload, and a live RegAsm CLR probe before
# GameWeld is allowed to write the ready marker or start Wand.
dotnet_release_value(){
  local wine="$1" key out val
  for key in \
    'HKLM\Software\Microsoft\NET Framework Setup\NDP\v4\Full' \
    'HKLM\Software\Wow6432Node\Microsoft\NET Framework Setup\NDP\v4\Full'; do
    out="$(WINEPREFIX="$RP" "$wine" reg query "$key" /v Release 2>/dev/null || true)"
    val="$(sed -nE 's/.*Release[[:space:]]+REG_DWORD[[:space:]]+(0x[0-9A-Fa-f]+|[0-9]+).*/\1/p' <<<"$out" | tail -n1)"
    [[ -n "$val" ]] || continue
    if [[ "$val" == 0x* || "$val" == 0X* ]]; then printf '%d\n' "$((val))"; else printf '%s\n' "$val"; fi
    return 0
  done
  return 1
}

dotnet48_payload_present(){
  local base="$RP/drive_c/windows/Microsoft.NET" arch file
  for arch in Framework Framework64; do
    for file in clr.dll mscorlib.dll; do
      [[ -s "$base/$arch/v4.0.30319/$file" ]] || return 1
    done
  done
  return 0
}

dotnet48_payload_report(){
  local base="$RP/drive_c/windows/Microsoft.NET" arch file missing=0
  for arch in Framework Framework64; do
    for file in clr.dll mscorlib.dll; do
      if [[ ! -s "$base/$arch/v4.0.30319/$file" ]]; then
        echo "Missing native .NET payload: C:\\windows\\Microsoft.NET\\$arch\\v4.0.30319\\$file"
        missing=1
      fi
    done
  done
  return "$missing"
}

native_dotnet48_present(){
  local wine="$1" rel
  rel="$(dotnet_release_value "$wine" 2>/dev/null || true)"
  [[ "$rel" =~ ^[0-9]+$ ]] || return 1
  (( rel >= 528040 )) || return 1
  dotnet48_payload_present
}

configure_native_dotnet_overrides(){
  local wine="$1"
  # Wine's builtin mscoree is for Wine Mono.  Native .NET Framework requires
  # the native loader once the Microsoft runtime is installed.
  WINEPREFIX="$RP" "$wine" reg add 'HKCU\Software\Wine\DllOverrides' /v mscoree /t REG_SZ /d native /f >/dev/null 2>&1 || true
}

probe_native_dotnet48(){
  local wine="$1" regasm
  native_dotnet48_present "$wine" || return 1
  configure_native_dotnet_overrides "$wine"
  for regasm in \
    "$RP/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/RegAsm.exe" \
    "$RP/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/RegAsm.exe"; do
    [[ -s "$regasm" ]] || continue
    if WINEPREFIX="$RP" WINEDLLOVERRIDES='mscoree=n' "$wine" "$regasm" /? >/dev/null 2>&1; then
      return 0
    fi
  done
  echo 'Native .NET 4.8 registry and CLR files exist, but the CLR probe did not start successfully.'
  return 1
}

backup_dotnet_registry(){
  local stamp dir f
  stamp="$(date +%Y%m%d-%H%M%S)"
  dir="$STATE/dotnet-registry-backups/${RUNNER:-unknown}-${APPID:-unknown}-$stamp"
  mkdir -p "$dir"
  for f in system.reg user.reg userdef.reg; do
    [[ -f "$RP/$f" ]] && cp -a -- "$RP/$f" "$dir/$f" || true
  done
  printf '%s\n' "$dir"
}

clear_proton_synthetic_dotnet_v4_keys(){
  local wine="$1" key
  for key in \
    'HKLM\Software\Wow6432Node\Microsoft\NET Framework Setup\NDP\v4' \
    'HKLM\Software\Microsoft\NET Framework Setup\NDP\v4'; do
    if WINEPREFIX="$RP" "$wine" reg query "$key" >/dev/null 2>&1; then
      echo "Removing Proton/Wine synthetic or partial .NET v4 registry key before native install: $key"
      WINEPREFIX="$RP" "$wine" reg delete "$key" /f >/dev/null 2>&1 || true
    fi
  done
}

dereference_proton_windows_symlinks(){
  local root="$RP/drive_c/windows" link target tmp count=0 skipped=0
  [[ -d "$root" ]] || { echo 'No drive_c/windows tree exists to normalize.'; return 0; }
  while IFS= read -r -d '' link; do
    # dosdevices intentionally remains symbolic; this function only walks C:\windows.
    target="$(readlink -f -- "$link" 2>/dev/null || true)"
    if [[ -z "$target" || ! -f "$target" ]]; then ((skipped+=1)); continue; fi
    tmp="$link.gameweld-deref-$$"
    rm -f -- "$tmp" 2>/dev/null || true
    if cp -aL -- "$link" "$tmp" 2>/dev/null; then
      rm -f -- "$link"
      mv -f -- "$tmp" "$link"
      ((count+=1))
    else
      rm -f -- "$tmp" 2>/dev/null || true
      ((skipped+=1))
    fi
  done < <(find "$root" -type l -print0 2>/dev/null)
  echo "Native .NET prefix normalization: dereferenced $count Windows file symlink(s); skipped $skipped non-file/broken symlink(s)."
}

prepare_native_dotnet_prefix(){
  local wine="$1" ws="$2" backup marker
  [[ -x "$ws" ]] && WINEPREFIX="$RP" "$ws" -k >/dev/null 2>&1 || true
  sleep 1
  backup="$(backup_dotnet_registry)"
  echo "Native .NET registry backup: $backup"
  marker="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').wemod-dotnet48-ready"
  rm -f -- "$marker" 2>/dev/null || true
  dereference_proton_windows_symlinks
  WINEPREFIX="$RP" "$wine" wineboot -u >/dev/null 2>&1 || true
  clear_proton_synthetic_dotnet_v4_keys "$wine"
}

download_dotnet48_offline(){
  local override="${GAMEWELD_DOTNET48_OFFLINE_INSTALLER:-}" installer expected actual curlbin
  expected="${DOTNET48_OFFLINE_SHA256^^}"
  mkdir -p "$CACHE/dotnet48"
  installer="$CACHE/dotnet48/ndp48-x86-x64-allos-enu.exe"

  if [[ -n "$override" ]]; then
    [[ -f "$override" ]] || { echo "Configured .NET 4.8 offline installer does not exist: $override" >&2; return 15; }
    cp -f -- "$override" "$installer"
  elif [[ ! -s "$installer" ]]; then
    curlbin="$(command -v curl 2>/dev/null || true)"
    [[ -n "$curlbin" ]] || { echo 'curl is required for the Microsoft .NET Framework 4.8 offline fallback.' >&2; return 9; }
    write_progress 'downloading Microsoft .NET Framework 4.8 offline installer'
    echo 'Downloading the official Microsoft .NET Framework 4.8 offline installer for verified fallback repair.' >&2
    "$curlbin" -fL --retry 3 --retry-delay 2 -o "$installer.part" "$DOTNET48_OFFLINE_URL" || { rm -f "$installer.part"; return 15; }
    mv -f "$installer.part" "$installer"
  fi

  actual="$(sha256sum "$installer" | awk '{print toupper($1)}')"
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    echo "Microsoft .NET 4.8 offline installer checksum mismatch: expected $expected, got $actual" >&2
    rm -f -- "$installer"
    return 16
  fi
  printf '%s\n' "$installer"
}

run_offline_dotnet48_installer(){
  local wine="$1" ws="$2" installer rc
  installer="$(download_dotnet48_offline)" || return $?
  echo "Running verified Microsoft .NET Framework 4.8 offline installer with: $wine"
  [[ -x "$ws" ]] && WINEPREFIX="$RP" "$ws" -k >/dev/null 2>&1 || true
  WINEPREFIX="$RP" "$wine" winecfg -v win7 >/dev/null 2>&1 || true
  set +e
  WINEPREFIX="$RP" WINEDLLOVERRIDES='fusion=b' "$wine" "$installer" /sfxlang:1027 /q /norestart
  rc=$?
  set -e
  WINEPREFIX="$RP" "$wine" winecfg -v win10 >/dev/null 2>&1 || true
  [[ -x "$ws" ]] && WINEPREFIX="$RP" "$ws" -k >/dev/null 2>&1 || true
  # Windows reboot-required 3010 is observed by a POSIX shell as 194.
  if (( rc != 0 && rc != 194 )); then
    echo "Microsoft .NET Framework 4.8 offline installer returned status $rc."
    return "$rc"
  fi
  configure_native_dotnet_overrides "$wine"
  return 0
}

install_wemod_dotnet48(){
  local primary_wine="$1" primary_ws="$2" rc host_wine host_ws install_wine install_ws
  prepare_native_dotnet_prefix "$primary_wine" "$primary_ws"
  echo '===== installing dotnet48 for Wand/WeMod after Proton-prefix normalization ====='
  set +e
  wt_with "$primary_wine" "$primary_ws" -q --force dotnet48
  rc=$?
  set -e
  if (( rc == 0 )); then
    configure_native_dotnet_overrides "$primary_wine"
    if probe_native_dotnet48 "$primary_wine"; then
      echo 'Primary Winetricks dotnet48 attempt passed registry, payload and CLR probe verification.'
      return 0
    fi
    echo 'Primary Winetricks returned success, but the native .NET runtime is incomplete. Continuing recovery instead of trusting the Winetricks record.'
    rc=13
  else
    echo "Primary repair runtime dotnet48 attempt failed with status $rc."
  fi

  [[ -x "$primary_ws" ]] && WINEPREFIX="$RP" "$primary_ws" -k >/dev/null 2>&1 || true
  sleep 1

  # GE-Proton 10 has a known native-.NET failure mode.  A non-Proton host Wine
  # can complete the installer in the same normalized prefix without changing
  # Heroic's configured runner.  Use it only as a fallback and only while the
  # prefix is closed.
  host_wine="$(command -v wine 2>/dev/null || true)"
  host_ws="$(command -v wineserver 2>/dev/null || true)"
  if [[ -n "$host_wine" && -x "$host_wine" && "$(readlink -f -- "$host_wine" 2>/dev/null || printf '%s' "$host_wine")" != "$(readlink -f -- "$primary_wine" 2>/dev/null || printf '%s' "$primary_wine")" ]]; then
    echo "Retrying native .NET Framework 4.8 with host Wine fallback: $host_wine"
    WINEPREFIX="$RP" "${host_ws:-wineserver}" -k >/dev/null 2>&1 || true
    clear_proton_synthetic_dotnet_v4_keys "$host_wine"
    WINEPREFIX="$RP" "$host_wine" wineboot -u >/dev/null 2>&1 || true
    set +e
    wt_with "$host_wine" "${host_ws:-wineserver}" -q --force dotnet48
    rc=$?
    set -e
    [[ -n "$host_ws" && -x "$host_ws" ]] && WINEPREFIX="$RP" "$host_ws" -k >/dev/null 2>&1 || true
    if (( rc == 0 )); then
      configure_native_dotnet_overrides "$host_wine"
      if probe_native_dotnet48 "$host_wine"; then
        echo 'Host Wine Winetricks fallback passed registry, payload and CLR probe verification.'
        return 0
      fi
      echo 'Host Wine Winetricks returned success, but the native .NET runtime is still incomplete.'
      rc=13
    else
      echo "Host Wine fallback dotnet48 attempt failed with status $rc."
    fi
  fi

  # Winetricks reaches dotnet40 before the 4.8 bundle and can fail there on a
  # damaged Proton prefix.  As a final repair path, execute Microsoft's signed
  # offline .NET 4.8 bundle directly and verify the resulting CLR rather than
  # trusting its exit code or a registry value alone.
  install_wine="$primary_wine"; install_ws="$primary_ws"
  if [[ -n "$host_wine" && -x "$host_wine" ]]; then install_wine="$host_wine"; install_ws="${host_ws:-wineserver}"; fi
  echo 'Winetricks did not produce a verified CLR. Trying the checksum-verified Microsoft .NET Framework 4.8 offline installer.'
  [[ -x "$install_ws" ]] && WINEPREFIX="$RP" "$install_ws" -k >/dev/null 2>&1 || true
  clear_proton_synthetic_dotnet_v4_keys "$install_wine"
  WINEPREFIX="$RP" "$install_wine" wineboot -u >/dev/null 2>&1 || true
  set +e
  run_offline_dotnet48_installer "$install_wine" "$install_ws"
  rc=$?
  set -e
  if (( rc == 0 )) && probe_native_dotnet48 "$install_wine"; then
    echo 'Microsoft offline .NET Framework 4.8 repair passed registry, payload and CLR probe verification.'
    return 0
  fi
  dotnet48_payload_report || true
  echo "Verified native .NET Framework 4.8 recovery failed (status $rc)."
  return "${rc:-13}"
}

status(){
  clear_stale_lock
  if lock_active; then echo "GameWeld runtime repair: ACTIVE pid=$(lock_pid)"; [[ -r "$PROGRESS" ]] && { printf 'Progress: '; cat "$PROGRESS"; }; else echo 'GameWeld runtime repair: inactive'; fi
  helper_proton="$(repair_runtime_proton 2>/dev/null || true)"
  if [[ -n "$helper_proton" ]]; then echo "GameWeld repair-only runtime: $helper_proton"; else echo "GameWeld repair-only runtime: not installed/detected"; fi
  echo 'Installed Winetricks components:'
  installed="$(wt list-installed 2>&1 || true)"
  printf '%s\n' "$installed"
  missing=0
  wininet_state=missing; dotnet48_state=missing; dotnet8_state=missing
  for verb in wininet dotnet48 dotnet8; do
    if grep -Eiq "(^|[[:space:]])${verb}([[:space:]]|$)" <<<"$installed"; then
      echo "GameWeld runtime check: $verb = installed"
      eval "${verb}_state=installed"
    else
      echo "GameWeld runtime check: $verb = missing/not recorded"
      missing=1
    fi
  done
  if (( missing == 0 )); then
    write_result \
      'state=ready' \
      'summary=FLiNG runtime prerequisites are installed.' \
      "wininet=$wininet_state" "dotnet48=$dotnet48_state" "dotnet8=$dotnet8_state"
  else
    write_result \
      'state=missing' \
      'summary=One or more FLiNG runtime prerequisites are missing.' \
      "wininet=$wininet_state" "dotnet48=$dotnet48_state" "dotnet8=$dotnet8_state"
  fi
  return "$missing"
}

repair(){
  clear_stale_lock
  if lock_active; then write_result 'state=repairing' "summary=A trainer runtime repair is already active (PID $(lock_pid))."; echo "A trainer runtime repair is already active for this game (PID $(lock_pid))."; exit 7; fi
  ( set -o noclobber; printf '%s\n' "$$" > "$LOCK" ) 2>/dev/null || { write_result 'state=error' 'summary=Could not acquire the runtime-repair lock.'; echo 'Could not acquire the runtime-repair lock.'; exit 7; }
  write_result 'state=repairing' 'summary=Adaptive trainer runtime repair started. Heroic game runner will not be changed.'
  cleanup(){ rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true; }
  trap cleanup EXIT INT TERM
  write_progress 'checking prefix activity'
  live="$(active_prefix_processes "$RP" || true)"
  if [[ -n "$live" ]]; then
    echo 'Refusing to modify the prefix while Windows processes are active:'
    printf '%s\n' "$live"
    write_result 'state=error' 'summary=The Heroic prefix still has active Windows processes. Close/reset the prefix before repairing.'
    exit 6
  fi

  helper_proton="$(repair_runtime_proton 2>/dev/null || true)"
  if [[ -z "$helper_proton" ]]; then
    write_result 'state=needs-helper' "summary=GameWeld needs a repair-only compatibility runtime to install legacy .NET without changing Heroic's selected game runner. Use Download Repair Runtime, then retry." 'helper=missing'
    echo 'No compatible repair-only runtime detected. The configured Heroic game runner is intentionally left untouched.'
    exit 11
  fi
  helper_wine="$(repair_runtime_wine "$helper_proton" || true)"
  helper_ws="$(repair_runtime_wineserver "$helper_wine" || true)"
  [[ -x "$helper_wine" ]] || { write_result 'state=error' 'summary=Repair runtime is present but its Wine executable could not be resolved.'; exit 12; }
  echo "Heroic game runner remains: ${WINE_BIN:-$WINE_EXE}"
  echo "Repair-only runtime: $helper_proton"
  echo "Repair-only Wine: $helper_wine"
  echo 'The helper is used only for dependency installation while the game is closed; GameWeld does not change Heroic game settings.'

  # Read the prefix record using the normal game runner, but perform legacy
  # framework installation with the isolated repair runtime. This avoids the
  # known Wine 11/new-WoW64 dotnet48 installer failure while keeping the game
  # on whatever runner the user selected.
  installed="$(wt list-installed 2>&1 || true)"
  for verb in dotnet48 dotnet8 wininet; do
    if grep -Eiq "(^|[[:space:]])${verb}([[:space:]]|$)" <<<"$installed"; then
      echo "Already installed: $verb"
      continue
    fi
    write_progress "installing $verb with repair-only runtime (game runner unchanged)"
    echo "===== installing $verb with repair-only runtime ====="
    if wt_with "$helper_wine" "$helper_ws" -q "$verb"; then
      echo "Installed $verb"
    else
      rc=$?
      echo "Repair runtime failed while installing $verb (status $rc)."
      write_result 'state=error' "summary=Repair runtime failed while installing $verb (status $rc). Heroic game runner was not changed." "helper=$helper_proton"
      exit "$rc"
    fi
    installed="$(wt_with "$helper_wine" "$helper_ws" list-installed 2>&1 || true)"
  done

  write_progress 're-synchronizing prefix with selected Heroic runner'
  # Stop the helper wineserver completely before the user's configured runner
  # touches the prefix again.  Do not launch or alter the game configuration.
  [[ -x "$helper_ws" ]] && WINEPREFIX="$RP" "$helper_ws" -k >/dev/null 2>&1 || true
  sleep 1
  write_progress 'post-install verification'
  echo '===== post-install check with selected game runner ====='
  status || true
  marker="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').ready"
  printf 'title=%s\nprefix=%s\ngame_runner=%s\nrepair_runner=%s\nrepaired_at=%(%FT%T%z)T\n' "$TITLE" "$RP" "${WINE_BIN:-$WINE_EXE}" "$helper_proton" -1 > "$marker"
  write_progress 'complete'
  write_result 'state=ready' 'summary=Adaptive trainer runtime repair complete. Heroic game runner was not changed.' 'wininet=installed' 'dotnet48=installed' 'dotnet8=installed' "helper=$helper_proton"
  echo "Adaptive trainer runtime repair complete. Marker: $marker"
}

ensure_wemod(){
  clear_stale_lock
  if lock_active; then
    write_result 'state=repairing' "summary=A trainer runtime repair is already active (PID $(lock_pid))."
    echo "A trainer runtime repair is already active for this game (PID $(lock_pid))."
    exit 7
  fi

  live="$(active_prefix_processes "$RP" || true)"
  if [[ -n "$live" ]]; then
    echo 'Refusing to modify the prefix while Windows processes are active:'
    printf '%s\n' "$live"
    write_result 'state=error' 'summary=The Heroic prefix still has active Windows processes. Close/reset the prefix before preparing WeMod.'
    exit 6
  fi

  installed="$(wt list-installed 2>&1 || true)"
  if grep -Eiq '(^|[[:space:]])dotnet48([[:space:]]|$)' <<<"$installed"; then
    echo '.NET Framework 4.8 is recorded by Winetricks; Test 30 will verify the native CLR before trusting that record.'
  fi
  rel="$(dotnet_release_value "$WINE_EXE" 2>/dev/null || true)"
  if [[ "$rel" =~ ^[0-9]+$ ]] && (( rel >= 528040 )) && ! dotnet48_payload_present; then
    echo ".NET Framework Release=$rel exists, but the native CLR payload is incomplete. Treating the Release value as stale/partial and forcing repair."
    dotnet48_payload_report || true
  fi
  if native_dotnet48_present "$WINE_EXE"; then
    configure_native_dotnet_overrides "$WINE_EXE"
    if probe_native_dotnet48 "$WINE_EXE"; then
      marker="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').wemod-dotnet48-ready"
      printf 'title=%s\nprefix=%s\ngame_runner=%s\nrepair_runner=not-needed\nverified_payload=yes\nverified_probe=yes\nprepared_at=%(%FT%T%z)T\n' "$TITLE" "$RP" "${WINE_BIN:-$WINE_EXE}" -1 > "$marker"
      echo '.NET Framework 4.8 passed Release, native payload and CLR probe verification in this prefix.'
      write_result 'state=ready' 'summary=.NET Framework 4.8 passed native CLR verification for Wand/WeMod.' 'dotnet48=installed' 'verified_payload=yes' 'verified_probe=yes' "marker=$marker"
      return 0
    fi
  fi

  if [[ -e "$LOCK" ]]; then rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true; fi
  ( set -o noclobber; printf '%s\n' "$$" > "$LOCK" ) 2>/dev/null || {
    write_result 'state=error' 'summary=Could not acquire the runtime-repair lock for WeMod preparation.'
    exit 7
  }
  cleanup(){ rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true; }
  trap cleanup EXIT INT TERM

  helper_proton="$(repair_runtime_proton 2>/dev/null || true)"
  if [[ -z "$helper_proton" ]]; then
    echo 'No compatible GE-Proton 10 repair runtime is installed. Downloading the managed repair-only runtime once for .NET Framework 4.8 preparation.'
    write_progress "downloading $REPAIR_RUNTIME_TAG repair runtime for WeMod .NET Framework 4.8"
    download_repair_runtime || exit $?
    helper_proton="$(repair_runtime_proton 2>/dev/null || true)"
  fi
  [[ -n "$helper_proton" && -x "$helper_proton" ]] || {
    write_result 'state=error' 'summary=Could not resolve the managed repair-only Proton runtime required for .NET Framework 4.8.'
    exit 12
  }

  helper_wine="$(repair_runtime_wine "$helper_proton" || true)"
  helper_ws="$(repair_runtime_wineserver "$helper_wine" || true)"
  [[ -x "$helper_wine" ]] || {
    write_result 'state=error' 'summary=Repair runtime is present but its Wine executable could not be resolved.'
    exit 12
  }

  write_progress 'repairing and verifying native dotnet48 for Wand/WeMod'
  write_result 'state=repairing' 'summary=Test 30 is repairing native .NET Framework 4.8 and will verify the real CLR payload before Wand can start. Heroic game settings are not changed.' "helper=$helper_proton"
  echo "Heroic game runner remains: ${WINE_BIN:-$WINE_EXE}"
  echo "WeMod repair-only runtime: $helper_proton"

  set +e
  install_wemod_dotnet48 "$helper_wine" "$helper_ws"
  rc=$?
  set -e
  if (( rc != 0 )); then
    echo "Verified native .NET Framework 4.8 installation failed after all recovery paths (status $rc)."
    write_result 'state=error' "summary=The .NET 4.8 registry marker was not accepted by itself. GameWeld could not produce a verified native CLR after Winetricks, host-Wine and Microsoft-offline repair paths (status $rc). Wand was not started." "helper=$helper_proton" 'prefix_normalized=yes' 'verified_payload=no' 'verified_probe=no'
    exit "$rc"
  fi

  [[ -x "$helper_ws" ]] && WINEPREFIX="$RP" "$helper_ws" -k >/dev/null 2>&1 || true
  sleep 1
  verify_wine="$helper_wine"
  host_verify="$(command -v wine 2>/dev/null || true)"
  if [[ -n "$host_verify" && -x "$host_verify" ]] && probe_native_dotnet48 "$host_verify"; then verify_wine="$host_verify"; fi
  if ! probe_native_dotnet48 "$verify_wine"; then
    dotnet48_payload_report || true
    write_result 'state=error' 'summary=.NET Framework 4.8 installation returned success, but the final native CLR verification failed. Wand was not started.' 'prefix_normalized=yes' 'verified_payload=no' 'verified_probe=no'
    exit 13
  fi

  marker="$STATE/heroic-trainer-runtime-$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')-$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_').wemod-dotnet48-ready"
  printf 'title=%s\nprefix=%s\ngame_runner=%s\nrepair_runner=%s\nverified_payload=yes\nverified_probe=yes\nprepared_at=%(%FT%T%z)T\n' "$TITLE" "$RP" "${WINE_BIN:-$WINE_EXE}" "$helper_proton" -1 > "$marker"
  write_progress 'complete'
  write_result 'state=ready' 'summary=.NET Framework 4.8 passed Release-key, native CLR payload and live CLR-probe verification for Wand/WeMod. Heroic game settings were not changed.' 'dotnet48=installed' 'prefix_normalized=yes' 'verified_payload=yes' 'verified_probe=yes' "helper=$helper_proton" "marker=$marker"
  echo ".NET Framework 4.8 verified preparation complete. Marker: $marker"
}

download_helper(){
  clear_stale_lock
  if lock_active; then write_result 'state=error' 'summary=Wait for the active trainer runtime repair to finish or cancel it before downloading a helper runtime.'; exit 7; fi
  write_result 'state=downloading' "summary=Downloading managed repair runtime $REPAIR_RUNTIME_TAG. This does not change Heroic game settings."
  download_repair_runtime
}

cancel(){
  clear_stale_lock
  if ! lock_active; then write_result 'state=idle' 'summary=No active FLiNG runtime repair is recorded for this game.'; echo 'No active FLiNG runtime repair is recorded for this game.'; rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true; return 0; fi
  pid="$(lock_pid)"
  echo "Cancelling FLiNG runtime repair PID $pid and its Winetricks children..."
  kill_descendants "$pid"
  kill -TERM "$pid" 2>/dev/null || true
  for _ in {1..20}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi
  rm -f -- "$LOCK" "$PROGRESS" 2>/dev/null || true
  write_result 'state=cancelled' 'summary=FLiNG runtime repair cancelled. Reset the Heroic prefix before launching if Winetricks was interrupted.'
  echo 'Runtime repair cancelled. Use Reset Heroic Prefix before launching if Wine/Winetricks was interrupted mid-install.'
}

case "$ACTION" in
  status) status ;;
  repair) repair ;;
  ensure-wemod) ensure_wemod ;;
  download-helper) download_helper ;;
  cancel) cancel ;;
  *) echo "Unknown action: $ACTION"; exit 2 ;;
esac
