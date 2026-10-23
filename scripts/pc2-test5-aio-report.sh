#!/usr/bin/env bash
# PC2 Test 5: distinguish missing versus invalid metadata, without changes.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test5-aio-report.txt"
mkdir -p "$OUT"
command -v go >/dev/null || { echo "Missing go" >&2; exit 1; }
command -v python3 >/dev/null || { echo "Missing python3" >&2; exit 1; }
cd "$ROOT/cmd/gameweld-backend"
printf '%s\n' "Running PC2 source tests, race checks, static analysis and local API check..."
go test -race -count=1 ./...
go vet ./...
go build -trimpath -o "$OUT/wand-native-backend" .
LOG="$OUT/pc2-test5-backend-start.log"
"$OUT/wand-native-backend" >"$LOG" 2>&1 &
BACKEND_PID="$!"
cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 1 100); do
  if grep -q 'Wand Native UI: http://127.0.0.1:' "$LOG"; then break; fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo 'Backend exited before startup' >&2
    cat "$LOG" >&2
    exit 1
  fi
  sleep 0.1
done
PORT="$(sed -nE 's#^Wand Native UI: http://127\.0\.0\.1:([0-9]+)/$#\1#p' "$LOG" | head -n 1)"
if [[ -z "$PORT" ]]; then echo 'Missing backend handshake' >&2; exit 1; fi
python3 - "$PORT" "$REPORT" <<'PY'
import json
import pathlib
import sys
import urllib.error
import urllib.request

port = int(sys.argv[1])
report = pathlib.Path(sys.argv[2])
url = f"http://127.0.0.1:{port}"

def request(path, method="GET"):
    req = urllib.request.Request(url + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)

code, status = request("/api/status")
assert code == 200 and status.get("ok") is True, "Status API failed"
code, compatibility = request("/api/compatibility")
assert code == 200 and compatibility.get("ok") is True, "Compatibility API failed"
info = compatibility["data"]
assert info["mode"] == "read_only", "Inspector not read-only"
assert info["verified"] is False, "Premature verified claim"
assert info["state"] in {"not_found", "incomplete", "detected_unverified"}, "Invalid compatibility state"
for ep in ("/api/install", "/api/set-game"):
    code, result = request(ep, method="POST")
    assert code == 501 and result.get("ok") is False, f"{ep} unexpectedly enabled"

games = status["data"].get("games", [])
lines = [
    "GameWeld PC2 Test 5 — Detailed Metadata Diagnostics AIO Report",
    "Result: PASS",
    "Source-built backend: PASS",
    "Steam game manifests detected: " + str(len(games)),
    "Compatibility inspector mode: " + info["mode"],
    "Compatibility status: " + info["state"],
    "Compatibility candidate count: " + str(len(info["candidates"])),
    "Compatibility verified: false (by design)",
    "Mutation endpoints: HTTP 501 (fail-closed)",
    "Inspection is metadata-only; Proton DLL checksums and actual trainer health are not verified.",
    "No installed game settings, Wine prefixes or trainers were changed.",
]
fields = [
    ("has_proton", "Proton launcher executable"),
    ("has_manifest", "compatibilitytool.vdf registration"),
    ("has_metadata", "WAND-HYBRID.json metadata"),
]
for number, item in enumerate(info["candidates"], 1):
    lines.append(f"Candidate {number} state: {item['state']}")
    detail = item.get("metadata_state")
    allowed = {"missing", "unreadable", "not_regular", "empty", "too_large", "invalid_json", "invalid_schema", "unexpected_tool_id", "missing_base_proton", "valid_metadata_only"}
    assert detail in allowed, "Unknown or absent metadata diagnostic state"
    lines.append(f"Candidate {number} metadata_state: {detail}")
    if detail == "missing":
        lines.append(f"Candidate {number} interpretation: No WAND-HYBRID.json file found; older or independently installed tool may lack GameWeld metadata")
    elif detail != "valid_metadata_only":
        lines.append(f"Candidate {number} interpretation: Metadata present or unreadable but not valid for this schema; do not overwrite it")
    missing = []
    for key, description in fields:
        value = item.get(key)
        assert type(value) is bool, f"Missing or invalid candidate indicator: {key}"
        lines.append(f"Candidate {number} {key}: {str(value).lower()}")
        if not value:
            missing.append(description)
    if missing:
        lines.append(f"Candidate {number} missing/invalid: " + ", ".join(missing))
    else:
        lines.append(f"Candidate {number} metadata: appears complete, but health is NOT verified")
if not info["candidates"]:
    lines.append("No matching candidate directories found; no automatic setup attempted.")
if info["state"] == "incomplete":
    lines.append("Action: inspect missing indicators; do NOT delete/reinstall the working compatibility tool based on this preliminary check.")
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print("Report:", report)
PY
