#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-basic}"
case "$MODE" in
  basic|tophat|plugin|deep) ;;
  *)
    echo "Usage: $0 [basic|tophat|plugin|deep]" >&2
    exit 2
    ;;
esac

DROPIN="$HOME/.config/systemd/user/wandd.service.d"
mkdir -p "$DROPIN"

cat > "$DROPIN/aux-diagnostics.conf" <<EOF
[Service]
Environment="WAND_AUX_DIAGNOSTICS=$MODE"
EOF

systemctl --user daemon-reload
systemctl --user restart wandd

echo "Wand auxiliary diagnostics enabled: $MODE"
echo "Start Wand Native normally, reproduce the 'trouble running mods' popup once,"
case "$MODE" in
  tophat)
    echo "Keep Wand, Resonance, and the error popup open, then run:"
    echo "  ./scripts/collect-tophat-diagnostics.sh 2713000"
    ;;
  plugin)
    echo "After reproducing the trainer failure once, run:"
    echo "  ./scripts/collect-plugin-loader-diagnostics.sh 2713000"
    ;;
  *)
    echo "then run: ./scripts/collect-aux-diagnostics.sh 2713000"
    ;;
esac
