#!/usr/bin/env bash
set -Eeuo pipefail
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/wand-native"
BIN="$HOME/.local/bin"

if [[ -x "$DATA_HOME/scripts/wand-proton-manager.sh" ]]; then
  "$DATA_HOME/scripts/wand-proton-manager.sh" remove || true
fi
systemctl --user disable --now wandd.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/wandd.service"
systemctl --user daemon-reload 2>/dev/null || true
rm -f "$BIN/wandctl" "$BIN/wandd" "$BIN/wand-ui" "$BIN/wand-setup"
rm -f "$HOME/.local/share/applications/dev.wand.WandNative.desktop"
rm -f "$HOME/.local/share/applications/dev.wand.WandNative.Setup.desktop"
rm -rf "$DATA_HOME"
echo "Wand Native removed. Restart Steam if the Wand Proton tool was installed."
