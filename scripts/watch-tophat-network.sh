#!/usr/bin/env bash
set -euo pipefail

SECONDS_TO_WATCH="${1:-30}"
OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-tophat-network-${STAMP}.txt"

END=$((SECONDS + SECONDS_TO_WATCH))
while (( SECONDS < END )); do
  {
    echo "===== $(date '+%H:%M:%S.%3N') ====="
    echo "-- processes --"
    pgrep -afi 'Wand\\.exe|WandAuxiliaryService|Resonance\\.exe|tophat|ACE: WinMain' || true
    echo "-- tcp --"
    ss -Htanp 2>/dev/null | grep -Ei 'wine|proton|resonance|wand|ESTAB|LISTEN|SYN-' || true
    echo "-- udp --"
    ss -Huanp 2>/dev/null | grep -Ei 'wine|proton|resonance|wand' || true
    echo
  } >> "$OUT"
  sleep 0.1
done

echo "$OUT"
