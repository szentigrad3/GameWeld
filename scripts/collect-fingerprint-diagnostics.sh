#!/usr/bin/env bash
set -euo pipefail

APPID="${1:-2713000}"
OUT_DIR="${HOME}/Desktop"
[[ -d "$OUT_DIR" ]] || OUT_DIR="$HOME"
LATEST="$(
  find "$OUT_DIR" -maxdepth 1 -type f \
    -name "wand-fingerprint-${APPID}-*.txt" \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr | head -1 | cut -d' ' -f2-
)"
[[ -n "$LATEST" && -f "$LATEST" ]] || {
  echo "No wand-fingerprint-${APPID}-*.txt found in $OUT_DIR" >&2
  exit 1
}

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/wand-fingerprint-summary-${APPID}-${STAMP}.txt"
TELEMETRY_REPORT="$OUT_DIR/wand-tophat-telemetry-${APPID}-${STAMP}.txt"
TELEMETRY_BUNDLE="$OUT_DIR/wand-tophat-telemetry-${APPID}-${STAMP}.zip"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

{
  echo "Wand Native PE section-map fingerprint summary"
  echo "timestamp=$(date --iso-8601=seconds)"
  echo "source=$LATEST"
  echo

  echo "===== process / ptrace context ====="
  grep -E '^(linux_pid|cmdline|interval_seconds|yama_ptrace_scope|initial_threads|initial_state)=' "$LATEST" || true
  echo

  echo "===== PE fingerprints ====="
  grep '^PE ' "$LATEST" || true
  echo

  echo "===== trainer file access order ====="
  grep -E ' TRAINER_EPOCH | FILE ' "$LATEST" || true
  echo

  echo "===== module section matches ====="
  grep -E ' MODULE_SECTION_MATCH ' "$LATEST" || true
  echo

  echo "===== individual section matches ====="
  grep -E ' SECTION_MATCH ' "$LATEST" || true
  echo

  echo "===== candidate image maps ====="
  grep -E ' MODULE_MAP(_BEGIN|_END)? ' "$LATEST" || true
  echo

  echo "===== anonymous executable mappings ====="
  grep -E ' ANON_EXEC_(ADD|CHANGE) ' "$LATEST" || true
  echo

  echo "===== executable permission transitions ====="
  grep ' EXEC_PERM_CHANGE ' "$LATEST" || true
  echo

  echo "===== trainer-init burst ====="
  grep -E ' (BURST_PEAK|BURST_RECOVERED|BURST_METRICS|THREAD_ADD|THREAD_REMOVE|TRAINER_FD_OPEN|TRAINER_FD_CLOSE)' "$LATEST" || true
  echo

  echo "===== burst map deltas ====="
  grep -E ' BURST_MAP_(ADD|REMOVE|CHANGE|SNAPSHOT) ' "$LATEST" || true
  echo

  echo "===== thread / process-state transitions ====="
  grep -E ' (THREADS|STATE|PROCESS_GONE)' "$LATEST" || true
  echo

  echo "===== bounded memory samples ====="
  grep -E ' MEM_SAMPLE(_UNAVAILABLE)? ' "$LATEST" || true
  echo

  echo "===== offline section geometry analysis ====="
  if [[ -x "$SCRIPT_DIR/analyze-fingerprint-sections.py" ]]; then
    "$SCRIPT_DIR/analyze-fingerprint-sections.py" "$LATEST" || true
  else
    echo "offline analyzer unavailable"
  fi
  echo

  echo "===== offline trainer-init burst analysis ====="
  if [[ -x "$SCRIPT_DIR/analyze-trainer-burst.py" ]]; then
    "$SCRIPT_DIR/analyze-trainer-burst.py" "$LATEST" || true
  else
    echo "burst analyzer unavailable"
  fi
  echo

  echo "===== burst summary ====="
  sed -n '/^===== trainer-init burst summary =====$/,/^===== section-match summary =====$/p' "$LATEST" || true
  echo

  echo "===== final ====="
  tail -24 "$LATEST"
} > "$OUT"

if [[ -x "$SCRIPT_DIR/extract-tophat-telemetry.py" ]]; then
  if "$SCRIPT_DIR/extract-tophat-telemetry.py" \
      --trace "$LATEST" \
      --report "$TELEMETRY_REPORT" \
      --bundle "$TELEMETRY_BUNDLE" >/dev/null; then
    {
      echo
      echo "===== tophat telemetry extraction ====="
      cat "$TELEMETRY_REPORT"
    } >> "$OUT"
  fi
fi

echo "$OUT"
[[ -s "$TELEMETRY_REPORT" ]] && echo "$TELEMETRY_REPORT"
[[ -s "$TELEMETRY_BUNDLE" ]] && echo "$TELEMETRY_BUNDLE"
