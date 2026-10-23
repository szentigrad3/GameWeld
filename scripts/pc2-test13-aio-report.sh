#!/usr/bin/env bash
# PC2 Test 13 — classify exact Steam-associated process roles read-only.
# Read-only. Does not start, stop, attach to or modify a game.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test13-aio-report.txt"
TARGET_APPID="346900"
if [[ "$#" -eq 1 ]]; then TARGET_APPID="$1"; fi
if [[ "$#" -gt 1 || ! "$TARGET_APPID" =~ ^[1-9][0-9]{0,9}$ ]]; then
  echo "Usage: bash scripts/pc2-test12-aio-report.sh [decimal Steam app ID, default: 346900]" >&2
  exit 2
fi
mkdir -p "$OUT"
command -v go >/dev/null
command -v python3 >/dev/null
(
  cd "$ROOT/cmd/gameweld-backend"
  go test -race -count=1 ./...
  go vet ./...
  go build -trimpath -o "$OUT/wand-native-backend" .
)
LOG="$OUT/pc2-test13-backend-start.log"
"$OUT/wand-native-backend" >"$LOG" 2>&1 &
PID=$!
cleanup() { kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 100); do
  grep -q '^Wand Native UI: http://127.0.0.1:' "$LOG" && break
  kill -0 "$PID" 2>/dev/null || { cat "$LOG" >&2; exit 1; }
  sleep 0.1
done
PORT="$(sed -nE 's#^Wand Native UI: http://127\.0\.0\.1:([0-9]+)/$#\1#p' "$LOG" | head -n1)"
[[ -n "$PORT" ]] || { echo "Backend did not return its startup port" >&2; exit 1; }

python3 - "$PORT" "$REPORT" "$TARGET_APPID" <<'PY'
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

port, output, appid = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
assert appid.isascii() and appid.isdecimal() and str(int(appid)) == appid and 0 < int(appid) < 2**32
base = "http://127.0.0.1:" + port

def request(path, method="GET"):
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path, method=method), timeout=6) as reply:
            return reply.status, json.load(reply)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)

code, status = request("/api/status")
assert code == 200 and status.get("ok") is True
games = status["data"].get("games") or []
target = next((item for item in games if item.get("appid") == appid and item.get("install_dir")), None)

lines = [
    "GameWeld PC2 Test 13 — Steam Process Roles AIO",
    "Result: PASS",
    "Source-built backend: PASS",
    "Inspector mode: read_only",
    "Target Steam app ID: " + appid,
    "Steam manifests detected: " + str(len(games)),
    "Target installed manifest: " + ("found" if target else "not_found"),
    "Steam process/session ownership verified: false",
    "Game running confirmed: false",
    "Trainer handoff enabled: false",
]
if target:
    counts = []
    states = []
    truncated = False
    for i in range(3):
        code, payload = request("/api/steam-session?appid=" + appid)
        assert code == 200 and payload.get("ok") is True, "Installed-game session API failed"
        data = payload["data"]
        assert data.get("mode") == "read_only"
        assert data.get("appid") == appid
        assert data.get("game_running_confirmed") is False
        assert data.get("state") in {"associated_processes_observed", "no_process_evidence", "unavailable"}
        count = data.get("associated_process_count")
        processes = data.get("processes")
        assert type(count) is int and count >= 0
        assert type(processes) is list and len(processes) <= 32 and count >= len(processes)
        counts.append(count)
        states.append(data["state"])
        truncated = truncated or data.get("scan_truncated") is True
        if i < 2:
            time.sleep(1)
    lines += [
        "Targeted session endpoint: PASS",
        "Observation states: " + ", ".join(states),
        "Associated process counts across samples: " + ", ".join(map(str, counts)),
        "Any exact Steam-app environment association: " + str(any(counts)).lower(),
        "Process scan truncated: " + str(truncated).lower(),
        "Environment association is NOT proof of executable identity or trainer session ownership.",
    ]
    code, role_response = request("/api/steam-process-roles?appid=" + appid)
    assert code == 200 and role_response.get("ok") is True, "Process-role endpoint failed"
    roles = role_response["data"]
    assert roles.get("mode") == "read_only" and roles.get("appid") == appid
    assert roles.get("game_executable_verified") is False
    assert roles.get("prefix_ownership_verified") is False
    assert roles.get("trainer_handoff_enabled") is False
    assert roles.get("state") in {"associated_processes_observed", "no_process_evidence", "unavailable"}
    records = roles.get("roles") or []
    assert type(records) is list and len(records) <= 32
    allowed = {"steam_helper", "wine_runtime", "windows_executable_candidate", "other_associated"}
    role_counts = {name:0 for name in sorted(allowed)}
    lines.append("Process roles endpoint: PASS")
    lines.append("Process role scan state: " + roles["state"])
    lines.append("Role-associated process count: " + str(roles["associated_process_count"]))
    for role in records:
        role_type = role.get("role")
        assert role_type in allowed, "Unexpected process role"
        role_counts[role_type] += 1
        assert type(role.get("has_compatdata_env")) is bool
        assert type(role.get("has_wineprefix_env")) is bool
        for label in ("comm", "executable_name"):
            value = role.get(label)
            assert isinstance(value, str) and 1 <= len(value) <= 64
            assert all(c.isascii() and (c.isalnum() or c in ".-_+") for c in value), "Unsanitized process label"
        lines.append(
            "Observed role " + str(len([line for line in lines if line.startswith("Observed role ")]) + 1) +
            ": " + role_type + " | comm=" + role["comm"] +
            " | executable=" + role["executable_name"] +
            " | compatdata_env=" + str(role["has_compatdata_env"]).lower() +
            " | wineprefix_env=" + str(role["has_wineprefix_env"]).lower()
        )
    for name in sorted(allowed):
        lines.append("Role count " + name + ": " + str(role_counts[name]))
    lines.append("Process role evidence incomplete: " + str(roles.get("scan_truncated") is True).lower())
    lines.append("Game executable verified: false")
    lines.append("Wine/Proton prefix ownership verified: false")
    lines.append("Trainer handoff remains disabled: true")
    lines.append("Role inference uses names and environment hints ONLY; no attach target is certified.")
else:
    code, payload = request("/api/steam-process-roles?appid=" + appid)
    assert code == 404 and payload.get("ok") is False
    code, payload = request("/api/steam-session?appid=" + appid)
    assert code == 404 and payload.get("ok") is False
    lines += [
        "Targeted session endpoint: SKIPPED (no installed manifest for target)",
        "Note: AIO PASS is contract validation, not evidence target was running.",
    ]
for bad in ("", "0", "1%3Bwhoami", "4294967296"):
    code, payload = request("/api/steam-session?appid=" + bad)
    assert code == 404 and payload.get("ok") is False
code, payload = request("/api/steam-session?appid=" + appid, "POST")
assert code == 405 and payload.get("ok") is False
code, payload = request("/api/steam-process-roles?appid=" + appid, "POST")
assert code == 405 and payload.get("ok") is False
for bad in ("", "0", "1%3Bwhoami", "4294967296"):
    code, payload = request("/api/steam-process-roles?appid=" + bad)
    assert code == 404 and payload.get("ok") is False
for endpoint in ("/api/install", "/api/set-game"):
    code, payload = request(endpoint, "POST")
    assert code == 501 and payload.get("ok") is False
lines += [
    "Unknown/malformed app IDs: rejected",
    "POST session and role observation: HTTP 405",
    "Install/mapping operations: HTTP 501",
    "Game or trainer launched by diagnostic: false",
    "Steam/Proton configuration changed by diagnostic: false",
]
output.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print("Report:", output)
PY
