#!/usr/bin/env bash
set -Eeuo pipefail

# GameForge 0.2.0 RC1 non-destructive Wand Native compatibility migration.
# If GameForge has no directory yet, alias it to the existing Wand Native
# directory so current CE payloads, tables and settings remain immediately
# usable by both old test builds and GameForge during the RC period.
link_or_merge() {
  local old="$1" new="$2"
  [[ -e "$old" || -L "$old" ]] || return 0
  mkdir -p -- "$(dirname -- "$new")"
  if [[ ! -e "$new" && ! -L "$new" ]]; then
    ln -s -- "$old" "$new"
    printf 'GameForge migration: linked %s -> %s\n' "$new" "$old"
    return 0
  fi
  # If a real GameForge directory already exists, copy only missing legacy
  # files. Never overwrite newer GameForge state.
  if [[ -d "$new" && ! -L "$new" && -d "$old" ]]; then
    cp -a -n -- "$old"/. "$new"/ 2>/dev/null || true
  fi
}

CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

link_or_merge "$CONFIG_HOME/wand-native" "$CONFIG_HOME/gameforge"
link_or_merge "$DATA_HOME/wand-native" "$DATA_HOME/gameforge"
link_or_merge "$STATE_HOME/wand-native" "$STATE_HOME/gameforge"

mkdir -p "$CACHE_HOME/gameforge"
exit 0
