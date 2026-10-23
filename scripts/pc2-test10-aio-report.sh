#!/usr/bin/env bash
# GameWeld PC2 Test 10: prove game-only launch is off by default.
# Does NOT execute Steam, open the GUI, or modify compatibility tools.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test10-aio-report.txt"
mkdir -p "$OUT"

# Reuse the real installed-manifest preview tests, always preview-only.
bash "$ROOT/scripts/pc2-test9-aio-report.sh" > /dev/null
test -s "$OUT/pc2-test9-aio-report.txt"

# The ordinary runner must ignore inherited environment opt-ins.
default="$(bash "$ROOT/scripts/run-pc2-source-frontend.sh" --pc2-launch-gate-status)"
if ! grep -q 'PC2 Steam game-only launch: disabled' <<<"$default"; then
  echo 'FAIL: normal runner enabled game launch' >&2
  exit 1
fi
inherited="$(env GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1 bash "$ROOT/scripts/run-pc2-source-frontend.sh" --pc2-launch-gate-status)"
if ! grep -q 'PC2 Steam game-only launch: disabled' <<<"$inherited"; then
  echo 'FAIL: inherited environment activated game launch' >&2
  exit 1
fi

# Probe the compiled GTK gate ONLY; the executable exits before GTK init.
opted_in="$(env GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1 "$OUT/gameweld" --pc2-launch-gate-status)"
if ! grep -q 'PC2 Steam game-only launch: enabled' <<<"$opted_in"; then
  echo 'FAIL: explicit GUI opt-in probe did not enable gate' >&2
  exit 1
fi
disabled="$(env GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=0 "$OUT/gameweld" --pc2-launch-gate-status)"
if ! grep -q 'PC2 Steam game-only launch: disabled' <<<"$disabled"; then
  echo 'FAIL: non-opt-in value enabled game launch' >&2
  exit 1
fi

cat >"$REPORT" <<'EOF'
GameWeld PC2 Test 10 — Steam Game-Only Launch Gate AIO
Result: PASS
Steam launch-preview regression: PASS (Test 9)
Ordinary PC2 runner launch gate: disabled
Inherited opt-in environment: ignored
Explicit opt-in GTK gate probe: enabled
Non-opt-in GTK gate probe: disabled
Steam game launched: false
Trainer launched: false
Steam configuration changed: false
Install and mapping endpoints: HTTP 501 (Test 9)
Actual user-triggered Steam launch: NOT TESTED
EOF
cat "$REPORT"
printf 'Report: %s\n' "$REPORT"
