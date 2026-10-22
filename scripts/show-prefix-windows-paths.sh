#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
PREFIX="/mnt/games/Steam/steamapps/compatdata/$APPID/pfx"

echo "Wine/Proton DOS drive mappings for AppID $APPID:"
find "$PREFIX/dosdevices" -maxdepth 1 -type l -printf '%f -> %l\n' | sort

echo
echo 'For Resonance on this installation, Wand should use:'
echo 'S:\steamapps\common\Resonance A Plague Tale Legacy\Resonance.exe'
