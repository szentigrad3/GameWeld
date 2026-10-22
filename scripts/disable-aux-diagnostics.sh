#!/usr/bin/env bash
set -euo pipefail

DROPIN="$HOME/.config/systemd/user/wandd.service.d/aux-diagnostics.conf"
rm -f "$DROPIN"

systemctl --user daemon-reload
systemctl --user restart wandd

echo "Wand auxiliary diagnostics disabled."
