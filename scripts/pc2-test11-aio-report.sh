#!/usr/bin/env bash
# GameWeld PC2 Test 11: read-only Steam game session evidence.
# Never launches/kills Steam, games, trainers or Proton.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/build/pc2-source"
REPORT="$OUT/pc2-test11-aio-report.txt"
mkdir -p "$OUT"
(
 cd "$ROOT/cmd/gameweld-backend"
 go test -race -count=1 ./...
 go vet ./...
 go build -trimpath -o "$OUT/wand-native-backend" .
)
LOG="$OUT/pc2-test11-backend-start.log"
"$OUT/wand-native-backend" >"$LOG" 2>&1 &
PID="$!"
cleanup(){ kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 100); do
  grep -q '^Wand Native UI: http://127.0.0.1:' "$LOG" && break
  kill -0 "$PID" 2>/dev/null || { cat "$LOG" >&2; exit 1; }
  sleep 0.1
done
PORT="$(sed -nE 's#^Wand Native UI: http://127\.0\.0\.1:([0-9]+)/$#\1#p' "$LOG" | head -n1)"
[[ -n "$PORT" ]] || { echo 'Missing source backend handshake' >&2; exit 1; }
python3 - "$PORT" "$REPORT" <<'PY'
import json, pathlib, sys, urllib.error, urllib.request
base = "http://127.0.0.1:" + sys.argv[1]
report = pathlib.Path(sys.argv[2])
def req(path,method="GET"):
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,method=method), timeout=6) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        return e.code,json.load(e)
code, status = req("/api/status")
assert code==200 and status.get("ok"), "Backend status failed"
games=status["data"].get("games") or []
target=next((g for g in games if g.get("install_dir") and
    (id:=str(g.get("appid",""))).isdigit() and id==str(int(id)) and
    0<int(id)<2**32),None)
lines=[
    "GameWeld PC2 Test 11 — Steam Session Evidence AIO",
    "Result: PASS",
    "Source-built backend: PASS",
    "Steam manifests detected: "+str(len(games)),
    "Inspector mode: read_only",
    "Game running confirmed: false (observation is not process identity verification)",
    "Trainer handoff enabled: false",
    "Steam/Proton configurations changed: false",
]
if target:
    appid=target["appid"]
    code,payload=req("/api/steam-session?appid="+appid)
    assert code==200 and payload.get("ok"), "Installed Steam game session endpoint failed"
    data=payload["data"]
    assert data.get("mode")=="read_only" and data.get("appid")==appid
    assert data.get("game_running_confirmed") is False
    assert data.get("state") in {"associated_processes_observed","no_process_evidence","unavailable"}
    processes=data.get("processes") or []
    count=data.get("associated_process_count")
    assert isinstance(count,int) and count>=len(processes) and len(processes)<=32
    assert all(isinstance(item.get("pid"),int) and item.get("pid")>0 for item in processes)
    lines.append("Installed Steam game session read-only endpoint: PASS")
    lines.append("Session observation state: "+data["state"])
    lines.append("Observed associated process count: "+str(count))
    lines.append("Process evidence is an environment match only; no process ownership/trainer readiness verified.")
else:
    lines.append("Installed Steam game session check: SKIPPED (no manifest)")
    lines.append("Fixture-backed Go session tests: PASS")
for query in ("", "0", "1%3Bwhoami", "4294967296"):
    code,payload=req("/api/steam-session?appid="+query)
    assert code==404 and payload.get("ok") is False, "Unknown or malformed app ID accepted"
code,payload=req("/api/steam-session?appid=1","POST")
assert code==405 and payload.get("ok") is False, "Mutation accepted"
for ep in ("/api/install","/api/set-game"):
    code,payload=req(ep,"POST")
    assert code==501 and payload.get("ok") is False, "PC2 write endpoint unexpectedly enabled"
lines.extend((
    "Unknown/malformed Steam app ID checks: PASS",
    "Session mutation request: HTTP 405",
    "Install and mapping endpoints: HTTP 501",
    "No game was launched, stopped, configured or modified by this diagnostic.",
))
report.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("\n".join(lines))
print("Report:",report)
PY
