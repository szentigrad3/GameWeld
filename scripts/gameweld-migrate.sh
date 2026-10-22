#!/usr/bin/env bash
set -Eeuo pipefail

# GameWeld 0.2.0 RC2 non-destructive compatibility migration.
# Priority: existing GameWeld state > GameForge RC state > Wand Native state.
# Existing directories are never deleted or overwritten.
link_or_merge() {
  local old="$1" new="$2" label="$3"
  [[ -e "$old" || -L "$old" ]] || return 0
  mkdir -p -- "$(dirname -- "$new")"
  if [[ ! -e "$new" && ! -L "$new" ]]; then
    ln -s -- "$old" "$new"
    printf 'GameWeld migration: linked %s -> %s (%s)\n' "$new" "$old" "$label"
    return 0
  fi
  if [[ -d "$new" && ! -L "$new" && -d "$old" ]]; then
    cp -a -n -- "$old"/. "$new"/ 2>/dev/null || true
  fi
}

CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

for spec in \
  "$CONFIG_HOME/gameforge|$CONFIG_HOME/gameweld|GameForge RC" \
  "$CONFIG_HOME/wand-native|$CONFIG_HOME/gameweld|Wand Native" \
  "$DATA_HOME/gameforge|$DATA_HOME/gameweld|GameForge RC" \
  "$DATA_HOME/wand-native|$DATA_HOME/gameweld|Wand Native" \
  "$STATE_HOME/gameforge|$STATE_HOME/gameweld|GameForge RC" \
  "$STATE_HOME/wand-native|$STATE_HOME/gameweld|Wand Native"
do
  IFS='|' read -r old new label <<<"$spec"
  link_or_merge "$old" "$new" "$label"
done

mkdir -p "$CACHE_HOME/gameweld"
exit 0
