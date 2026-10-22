#!/usr/bin/env bash
set -Eeuo pipefail
RUNNER="${1:?runner required}"; APPID="${2:?app id required}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=gameweld-heroic-common.sh
source "$script_dir/gameweld-heroic-common.sh"
LOG="$GAMEWELD_STATE/heroic-$(sanitize_id "$RUNNER")-$(sanitize_id "$APPID").log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Heroic normal launch runner=%s appid=%s\n' -1 "$RUNNER" "$APPID"
require_no_runtime_repair "$RUNNER" "$APPID" || exit 12
if heroic_launch_game "$RUNNER" "$APPID"; then
  echo 'Heroic launch request sent.'
  exit 0
fi
echo 'Could not dispatch Heroic launch URI. Is Heroic installed and registered as the heroic:// handler?'
exit 4
