#!/usr/bin/env bash
# Non-mutating capability regression test for PC2 settings controls.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DISCOVERY="${1:-$ROOT/build/pc2-source/private-AppDir/usr/bin/gameweld}"
FUNCTIONAL="${2:-$ROOT/build/pc2-source/private-functional-AppDir/usr/bin/gameweld}"
[[ -x "$DISCOVERY" && -x "$FUNCTIONAL" ]] || {
  echo "Missing compiled discovery/functional GUIs" >&2; exit 2;
}
status() {
  env -u GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST "$1" --pc2-provider-controls-status
}
[[ "$(status "$DISCOVERY")" == "PC2 provider controls: enabled" ]] || {
  echo "FAIL: discovery mode's PC2 providers regressed" >&2; exit 1;
}
[[ "$(status "$FUNCTIONAL")" == "PC2 provider controls: disabled" ]] || {
  echo "FAIL: functional mode fails closed without runtime opt-in" >&2; exit 1;
}
[[ "$(GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST=INVALID "$FUNCTIONAL" --pc2-provider-controls-status)" == "PC2 provider controls: disabled" ]] || {
  echo "FAIL: invalid functional opt-in activated providers" >&2; exit 1;
}
[[ "$(GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST=I_UNDERSTAND_PRIVATE_TEST_ONLY "$FUNCTIONAL" --pc2-provider-controls-status)" == "PC2 provider controls: enabled" ]] || {
  echo "FAIL: opted-in functional GUI suppresses DeckCheatz and Steam Bridge actions" >&2; exit 1;
}
echo "PASS: DeckCheatz, Steam Bridge and WeMod action gate enabled for opted-in functional GUI."
echo "No Steam, game, setup, network or download action performed."
