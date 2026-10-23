#!/usr/bin/env bash
# Optional, user-supplied Wand-Enhancer launcher for Linux/Wine (experimental).
# Does not download, patch, modify accounts, or start a web service by itself.
set -Eeuo pipefail

upstream='https://github.com/k1tbyte/Wand-Enhancer'
usage() {
  cat <<'HELP'
Usage: bash scripts/gameweld-wand-enhancer.sh --status|--launch|--open-upstream

User-supplied configuration for --launch:
  WAND_ENHANCER_EXE    Absolute path to your self-built WandEnhancer.exe
  WAND_ENHANCER_WINE   Wine executable to use (default: wine)
  WAND_ENHANCER_PREFIX Existing compatible Wine prefix (required)

This Windows WPF/.NET Framework 4.8 tool is not verified under Wine.
The launcher performs no patches itself and never auto-enables the LAN panel.
HELP
}
action="${1:---status}"
case "$action" in
  --help|-h) usage ;;
  --open-upstream)
    command -v xdg-open >/dev/null || { echo 'xdg-open unavailable' >&2; exit 3; }
    exec xdg-open "$upstream"
    ;;
  --status|--launch)
    app="${WAND_ENHANCER_EXE:-}"
    wine="${WAND_ENHANCER_WINE:-wine}"
    prefix="${WAND_ENHANCER_PREFIX:-}"
    echo "Upstream: $upstream"
    echo 'Upstream license: Apache-2.0; no official prebuilt EXE is distributed.'
    if [[ -z "$app" || ! -f "$app" ]]; then
      echo 'Wand-Enhancer: no self-built WandEnhancer.exe configured.' >&2
      [[ "$action" == --status ]] && exit 0
      exit 2
    fi
    if [[ "${app##*/}" != "WandEnhancer.exe" ]]; then
      echo 'Refusing unexpected executable basename; select WandEnhancer.exe explicitly.' >&2
      exit 2
    fi
    echo 'Wand-Enhancer: user-supplied executable found.'
    if [[ "$action" == --status ]]; then
      if [[ -n "$prefix" && -d "$prefix" ]]; then
        echo 'Wine prefix: configured and present.'
      else
        echo 'Wine prefix: not configured or missing.'
      fi
      if command -v "$wine" >/dev/null 2>&1 || [[ -x "$wine" ]]; then
        echo 'Wine runner: available.'
      else
        echo 'Wine runner: unavailable.'
      fi
      exit 0
    fi
    if [[ -z "$prefix" || ! -d "$prefix" ]]; then
      echo 'Set WAND_ENHANCER_PREFIX to an existing Wine prefix.' >&2
      exit 2
    fi
    if ! command -v "$wine" >/dev/null 2>&1 && [[ ! -x "$wine" ]]; then
      echo 'Wine executable not found.' >&2
      exit 2
    fi
    echo 'Launching user-supplied WPF utility; its own patch controls remain user-operated.'
    exec env WINEPREFIX="$prefix" "$wine" "$app"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
