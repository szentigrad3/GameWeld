#!/usr/bin/env bash
# PC2 Test 7: fingerprint known-layout Proton runtime files without modifying them.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test7-aio-report.txt"
mkdir -p "$OUT"
command -v go >/dev/null || { echo "Missing go" >&2; exit 1; }
command -v python3 >/dev/null || { echo "Missing python3" >&2; exit 1; }
cd "$ROOT/cmd/gameweld-backend"
printf '%s\n' "Running PC2 source tests, race checks, static analysis and local API check..."
go test -race -count=1 ./...
go vet ./...
go build -trimpath -o "$OUT/wand-native-backend" .
LOG="$OUT/pc2-test7-backend-start.log"
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
code, runtime = request("/api/runtime-integrity")
assert code == 200 and runtime.get("ok") is True, "Runtime integrity API failed"
runtime_info = runtime["data"]
assert runtime_info["mode"] == "read_only", "Runtime inspector not read-only"
assert runtime_info["integrity_verified"] is False, "Unexpected trust escalation"
assert info["mode"] == "read_only", "Inspector not read-only"
assert info["verified"] is False, "Premature verified claim"
assert info["state"] in {"not_found", "incomplete", "detected_unverified", "legacy_metadata_missing"}, "Invalid compatibility state"
for ep in ("/api/install", "/api/set-game"):
    code, result = request(ep, method="POST")
    assert code == 501 and result.get("ok") is False, f"{ep} unexpectedly enabled"

games = status["data"].get("games", [])
lines = [
    "GameWeld PC2 Test 7 — Runtime Fingerprint AIO Report",
    "Result: PASS",
    "Source-built backend: PASS",
    "Steam game manifests detected: " + str(len(games)),
    "Compatibility inspector mode: " + info["mode"],
    "Compatibility status: " + info["state"],
    "Compatibility candidate count: " + str(len(info["candidates"])),
    "Compatibility verified: false (by design)",
    "Mutation endpoints: HTTP 501 (fail-closed)",
    "Runtime files are fingerprinted (SHA256) where present; no trusted comparison or trainer health certification.",
    "No installed game settings, Wine prefixes or trainers were changed.",
]
if info["state"] == "legacy_metadata_missing":
    assert any(item["state"] == "legacy_metadata_missing" for item in info["candidates"]), "Legacy state needs evidence"
    assert status["data"].get("wand_tool"), "Legacy tool path not reported to frontend"
    assert status["data"].get("wand_installed") is False, "Legacy tool was incorrectly marked healthy"
    assert status["data"].get("wand_healthy") is False, "Legacy tool was incorrectly marked healthy"
    lines.append("Legacy tool: registered and executable, but sidecar missing; NO reinstall required by this result")
    lines.append("Legacy backend health flags: false (correct, not yet verified)")
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
lines.append("Runtime candidate count: " + str(len(runtime_info["candidates"])))
accepted = {"missing", "unreadable", "symlink_not_followed", "not_regular", "empty",
            "oversized", "changed_while_reading", "fingerprinted_unverified",
            "not_found_in_known_layouts"}
for number, candidate in enumerate(runtime_info["candidates"], 1):
    assert candidate["integrity_verified"] is False, "Runtime candidate verified prematurely"
    lines.append(f"Runtime candidate {number}: " + str(candidate.get("label", "candidate")))
    for arch in ("x86_64", "i386"):
        evidence = candidate[arch]
        state = evidence.get("state")
        assert state in accepted, f"Unexpected {arch} runtime state: {state}"
        lines.append(f"Runtime candidate {number} {arch} state: {state}")
        if state == "fingerprinted_unverified":
            digest = evidence.get("sha256","")
            assert len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest), "Invalid fingerprint"
            lines.append(f"Runtime candidate {number} {arch} SHA256: {digest}")
        else:
            assert not evidence.get("sha256"), "Unusable file unexpectedly hashed"
lines.append("Integrity verified against trusted reference: false")
lines.append("Interpretation: fingerprints are evidence only; do not reinstall, patch, or enable trainer operations.")
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print("Report:", report)
PY
