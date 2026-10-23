#!/usr/bin/env bash
# Test 9: source-only, preview-only Steam URI path. No game launch or file change.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test9-aio-report.txt"
mkdir -p "$OUT"
command -v go >/dev/null
command -v python3 >/dev/null
(
 cd "$ROOT/cmd/gameweld-backend"
 go test -race -count=1 ./...
 go vet ./...
 go build -trimpath -o "$OUT/wand-native-backend" .
)
LOG="$OUT/pc2-test9-backend-start.log"
"$OUT/wand-native-backend" >"$LOG" 2>&1 &
PID="$!"
cleanup() { kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 100); do
  grep -q '^Wand Native UI: http://127.0.0.1:' "$LOG" && break
  kill -0 "$PID" 2>/dev/null || { cat "$LOG" >&2; exit 1; }
  sleep 0.1
done
PORT="$(sed -nE 's#^Wand Native UI: http://127\.0\.0\.1:([0-9]+)/$#\1#p' "$LOG" | head -n1)"
[[ -n "$PORT" ]] || { cat "$LOG" >&2; exit 1; }
python3 - "$PORT" "$REPORT" <<'PY'
import json, pathlib, sys, urllib.error, urllib.request

base = "http://127.0.0.1:" + sys.argv[1]
report = pathlib.Path(sys.argv[2])
def call(path, method="GET"):
    req = urllib.request.Request(base + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as ex:
        return ex.code, json.load(ex)

code, result = call("/api/status")
assert code == 200 and result.get("ok"), "Source backend status failed"
games = result["data"].get("games") or []
target = next((g for g in games
    if g.get("install_dir") and (id := g.get("appid","")).isdigit()
       and str(int(id)) == id and 0 < int(id) < 2**32), None)
lines = [
    "GameWeld PC2 Test 9 — Steam Launch Preview AIO",
    "Result: PASS",
    "Source-built backend: PASS",
    f"Steam manifests detected: {len(games)}",
    "Mode: preview_only",
    "Game launched: false",
    "Trainer launched: false",
    "Steam configuration changed: false",
]
if target:
    appid = target["appid"]
    code, preview = call("/api/launch-preview?appid=" + appid)
    assert code == 200 and preview.get("ok"), "Installed game not previewable"
    data = preview["data"]
    assert data.get("mode") == "preview_only"
    assert data.get("launch_enabled") is False
    assert data.get("uri") == "steam://rungameid/" + appid
    lines.append("Installed Steam game launch preview: PASS")
    lines.append("Preview URI generated: yes (not executed)")
else:
    lines.append("Installed Steam game launch preview: SKIPPED (no manifests found)")
    lines.append("Fixture-backed Go preview tests: PASS")
for value in ("", "0", "1%3Bwhoami", "4294967296"):
    code, payload = call("/api/launch-preview?appid=" + value)
    assert code == 404 and payload.get("ok") is False, "Invalid Steam ID allowed"
code, payload = call("/api/launch-preview?appid=1", "POST")
assert code == 405 and payload.get("ok") is False
for ep in ("/api/install", "/api/set-game"):
    code, payload = call(ep, "POST")
    assert code == 501 and payload.get("ok") is False
lines.extend((
  "Unknown/malformed Steam ID checks: PASS",
  "Preview mutation attempt: HTTP 405",
  "Install and mapping remain disabled: HTTP 501",
  "No game or trainer launch was requested.",
))
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print("Report:", report)
PY
