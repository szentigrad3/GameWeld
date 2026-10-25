#!/usr/bin/env bash
# Single-command private functional RC validation on a Linux tester machine.
# Does not alter Steam, install tools, start games, or publish artifacts.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LAUNCH=0
case "${1:-}" in
  "") ;;
  --launch) LAUNCH=1 ;;
  *) echo "Usage: $0 [--launch]" >&2; exit 2 ;;
esac
OUT="${GAMEWELD_RC_TEST_DIR:-$ROOT/build/pc2-source/functional-rc-validation}"
[[ ! -e "$OUT" ]] || { echo "Refusing overwrite: $OUT" >&2; exit 2; }
mkdir -p "$OUT"
export GAMEWELD_PC2_BUILD_MODE=functional
export GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST=I_UNDERSTAND_PRIVATE_TEST_ONLY
export GAMEWELD_PC2_STAGE="$OUT/AppDir"
echo "1/4 Build source functional AppDir"
bash scripts/pc2-stage-private-appdir.sh >"$OUT/build.log" 2>&1 || { tail -60 "$OUT/build.log"; exit 1; }
echo "2/4 Structural audit"
GAMEWELD_PC2_AUDIT_REPORT="$OUT/appdir-audit.txt" bash scripts/pc2-audit-private-appdir.sh >"$OUT/audit.log" 2>&1 || { tail -60 "$OUT/audit.log"; exit 1; }
echo "3/4 GUI launch check"
GAMEWELD_GUI_SMOKE_SECONDS=30 bash scripts/pc2-headless-gui-smoke.sh >"$OUT/gui-smoke.log" 2>&1 || { tail -60 "$OUT/gui-smoke.log"; exit 1; }
echo "4/4 Result manifest"
python3 - "$OUT" <<'PY'
import hashlib, json, pathlib, platform, sys
root=pathlib.Path(sys.argv[1])
app=root/"AppDir"
p={
 "test_type":"private-functional-source-build-only",
 "platform":platform.platform(),
 "functional_gui_sha256":hashlib.sha256((app/"usr/bin/gameweld").read_bytes()).hexdigest(),
 "functional_backend_sha256":hashlib.sha256((app/"usr/bin/wand-native-backend").read_bytes()).hexdigest(),
 "appdir_audit":"passed",
 "headless_gui_smoke":"passed",
 "portable":False,"steam_game_launch_tested":False,"wemod_tested":False,
 "redistribution_approved":False
}
(root/"summary.json").write_text(json.dumps(p,indent=2)+"\n")
PY
echo "PASS: private functional source build, local audit, GUI smoke"
echo "Report: $OUT/summary.json"
if (( LAUNCH )); then
  echo "Opening GameWeld functional GUI for manual testing."
  echo "IMPORTANT: Steam/WeMod setup and game actions are user-controlled; no automatic launch."
  "$GAMEWELD_PC2_STAGE/AppRun"
else
  echo "NEXT: run this script with --launch to open functional GameWeld after validation."
fi
