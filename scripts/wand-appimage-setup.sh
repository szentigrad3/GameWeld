#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
ACTION="${1:-status}"

case "$ACTION" in
  install|setup)
    echo "Wand Native first-run setup"
    echo
    if [[ -x "$ROOT/install-dwritecore.sh" ]]; then
      echo "Preparing Wand UI compatibility..."
      "$ROOT/install-dwritecore.sh" || echo "Note: DWriteCore setup did not complete; Proton setup will continue."
      echo
    fi
    exec "$ROOT/wand-proton-manager.sh" install
    ;;
  verify)
    exec "$ROOT/wand-proton-manager.sh" verify
    ;;
  status)
    exec "$ROOT/wand-proton-manager.sh" status
    ;;
  remove)
    exec "$ROOT/wand-proton-manager.sh" remove
    ;;
  *)
    echo "Usage: wand-appimage-setup.sh {install|status|verify|remove}" >&2
    exit 2
    ;;
esac
