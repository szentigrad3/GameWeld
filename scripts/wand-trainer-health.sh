#!/usr/bin/env bash
set -Eeuo pipefail
APPID="${1:-}"

roots=()
for r in "${STEAM_DIR:-}" "$HOME/.local/share/Steam" "$HOME/.steam/root" "$HOME/.steam/steam"; do
  [[ -n "$r" && -d "$r" ]] && roots+=("$(readlink -f "$r" 2>/dev/null || echo "$r")")
done
for root in "${roots[@]}"; do
  for vdf in "$root/steamapps/libraryfolders.vdf" "$root/config/libraryfolders.vdf"; do
    [[ -f "$vdf" ]] || continue
    while IFS= read -r p; do [[ -d "$p" ]] && roots+=("$p"); done < <(sed -nE 's/^[[:space:]]*"path"[[:space:]]+"([^"]+)".*/\1/p' "$vdf" | sed 's#\\\\#/#g')
  done
done

find_traces() {
  local root pattern
  for root in "${roots[@]}"; do
    if [[ -n "$APPID" ]]; then
      pattern="$root/steamapps/compatdata/$APPID/pfx/drive_c/users/*/AppData/Local/Wand/logs/tophat"
    else
      pattern="$root/steamapps/compatdata/*/pfx/drive_c/users/*/AppData/Local/Wand/logs/tophat"
    fi
    # shellcheck disable=SC2086
    find $pattern -type f -name '*.traces.otlp' -printf '%T@ %p\n' 2>/dev/null || true
  done
}

TRACE="$(find_traces | sort -nr | head -1 | cut -d' ' -f2-)"
[[ -n "$TRACE" && -f "$TRACE" ]] || { echo "No Tophat trainer telemetry found."; exit 1; }

TEXT="$(mktemp)"; trap 'rm -f "$TEXT"' EXIT
strings -a "$TRACE" > "$TEXT"

has() { grep -Fqi -- "$1" "$TEXT"; }
fail=0
printf 'Trainer health\n'
printf '  Trace: %s\n' "$TRACE"

if has "Plugin 'TrainerLib' registered 7 commands"; then
  echo "  TrainerLib plugin: loaded"
else
  echo "  TrainerLib plugin: NOT CONFIRMED"; fail=1
fi
if has "trainer_run_mod_json"; then
  echo "  Trainer command bridge: active"
else
  echo "  Trainer command bridge: NOT CONFIRMED"; fail=1
fi
if has "Plugin 'input_capture' registered 3 commands"; then
  echo "  Input capture plugin: loaded"
else
  echo "  Input capture plugin: not confirmed"
fi
if has "verification_error" || has "Plugin signature verification failed"; then
  echo "  Signature verification: FAILED"
  fail=1
else
  echo "  Signature verification: passed/no failure observed"
fi

if (( fail == 0 )); then
  echo "Result: healthy"
else
  echo "Result: needs attention"
  exit 2
fi
