#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
STEAM_ROOT="${WAND_STEAM_ROOT:-/mnt/games/Steam}"
COMPAT="${WAND_COMPAT_DATA_PATH:-$STEAM_ROOT/steamapps/compatdata/$APPID}"
PREFIX="$COMPAT/pfx"
PROTON="${WAND_PROTON:-$STEAM_ROOT/compatibilitytools.d/Proton-GE Latest/proton}"

OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-clr-preflight-${APPID}-${STAMP}.txt"

WAND_ROOT="$(
  find "$PREFIX/drive_c/users" -type f \
    -path '*/AppData/Local/Wand/app-*/Wand.exe' \
    -printf '%T@ %h\n' 2>/dev/null \
    | sort -nr | head -1 | cut -d' ' -f2-
)"

TRAINERLIB=""
if [[ -n "$WAND_ROOT" ]]; then
  TRAINERLIB="$WAND_ROOT/resources/app.asar.unpacked/static/unpacked/trainerlib"
fi

{
  echo "Wand Native trainer CLR preflight"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "appid=$APPID"
  echo "prefix=$PREFIX"
  echo "proton=$PROTON"
  echo "wand_root=${WAND_ROOT:-not-found}"
  echo

  echo "===== .NET Full registry ====="
  env \
    STEAM_COMPAT_DATA_PATH="$COMPAT" \
    STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
    STEAM_COMPAT_APP_ID="$APPID" \
    WINEPREFIX="$PREFIX" \
    "$PROTON" runinprefix reg.exe query \
    'HKLM\Software\Microsoft\NET Framework Setup\NDP\v4\Full' 2>&1 || true
  echo

  echo "===== Wine DLL overrides ====="
  env \
    STEAM_COMPAT_DATA_PATH="$COMPAT" \
    STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
    STEAM_COMPAT_APP_ID="$APPID" \
    WINEPREFIX="$PREFIX" \
    "$PROTON" runinprefix reg.exe query \
    'HKCU\Software\Wine\DllOverrides' 2>&1 || true
  echo

  echo "===== mscoree files and CLR hosting exports ====="
  for f in \
    "$PREFIX/drive_c/windows/system32/mscoree.dll" \
    "$PREFIX/drive_c/windows/syswow64/mscoree.dll"; do
    if [[ -f "$f" ]]; then
      echo "-- $f"
      file "$f" || true
      sha256sum "$f" || true
      if command -v objdump >/dev/null; then
        objdump -p "$f" 2>/dev/null \
          | grep -Ei \
            'CLRCreateInstance|CorBindToRuntime|CorExitProcess|AddressOfEntryPoint|ImageBase' \
          | head -240 || true
      fi
    else
      echo "missing: $f"
    fi
  done
  echo

  echo "===== TrainerLibPlugin x64 imports ====="
  if [[ -n "$TRAINERLIB" && -f "$TRAINERLIB/TrainerLibPlugin_x64.dll" ]]; then
    file "$TRAINERLIB/TrainerLibPlugin_x64.dll" || true
    objdump -p "$TRAINERLIB/TrainerLibPlugin_x64.dll" 2>/dev/null \
      | sed -n '/The Import Tables/,/The Export Tables/p' \
      | head -280 || true
  else
    echo "TrainerLibPlugin_x64.dll not found"
  fi
  echo

  echo "===== TrainerLib x64 imports ====="
  if [[ -n "$TRAINERLIB" && -f "$TRAINERLIB/TrainerLib_x64.dll" ]]; then
    file "$TRAINERLIB/TrainerLib_x64.dll" || true
    objdump -p "$TRAINERLIB/TrainerLib_x64.dll" 2>/dev/null \
      | sed -n '/The Import Tables/,/The Export Tables/p' \
      | head -240 || true
  else
    echo "TrainerLib_x64.dll not found"
  fi
  echo

  echo "===== winetricks components ====="
  if command -v winetricks >/dev/null; then
    WINEPREFIX="$PREFIX" winetricks list-installed 2>&1 \
      | grep -Ei 'dotnet|mono|vcrun|msxml|corefonts|d3dcompiler' || true
  else
    echo "winetricks not installed"
  fi
} > "$OUT"

echo "$OUT"
