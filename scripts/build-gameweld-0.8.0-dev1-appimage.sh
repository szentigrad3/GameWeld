#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BASE_APPIMAGE="${1:?Usage: build-gameweld-0.8.0-dev1-appimage.sh BASE_STABLE.APPIMAGE [OUT]}"
OUT="${2:-$ROOT/GameWeld-0.8.0-dev1-x86_64.AppImage}"
WORK="$(mktemp -d -t gameweld-080-dev1-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
( cd "$WORK"; "$BASE_APPIMAGE" --appimage-extract >/dev/null )
APPDIR="$WORK/squashfs-root"
gcc -O2 -pipe -fno-plt -pthread \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" -o "$APPDIR/usr/bin/gameweld" \
  /lib/x86_64-linux-gnu/libgtk-3.so.0 \
  /lib/x86_64-linux-gnu/libgdk-3.so.0 \
  /lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0 \
  /lib/x86_64-linux-gnu/libgobject-2.0.so.0 \
  /lib/x86_64-linux-gnu/libglib-2.0.so.0
strip "$APPDIR/usr/bin/gameweld"
cp "$APPDIR/usr/bin/gameweld" "$APPDIR/usr/bin/gameforge"
cp "$APPDIR/usr/bin/gameweld" "$APPDIR/usr/bin/wand-native"
# Freeze launcher-owned session helpers. Keep Steam/Heroic/Lutris ownership unchanged.
for helper in \
  gameweld-trainer-manager-game.sh \
  gameweld-steam-shortcut-trainer.sh \
  gameweld-steam-shortcuts.py \
  gameweld-steam-shortcut-live-launch.sh \
  gameweld-lutris-provider.py \
  gameweld-lutris-session.sh \
  gameweld-support-bundle.py \
  gameweld-wand-compat-audit.py \
  gameweld-wand-patcher.py \
  gameweld-wand-discovery.py \
  gameweld-trainer-library.py \
  gameweld-trainer-updates.py \
  gameweld-update-monitor.py \
  gameweld-stability-preflight.py; do
  install -m 0755 "$ROOT/scripts/$helper" "$APPDIR/usr/libexec/$helper"
done
mkdir -p "$APPDIR/usr/share/gameweld" "$APPDIR/usr/share/doc/gameweld" "$APPDIR/usr/share/applications"
# Stable runtime ships current release guidance, not the earlier candidate/test doc archive.
find "$APPDIR/usr/share/doc/gameweld" -maxdepth 1 -type f \
  \( -name 'RELEASE-NOTES-*' -o -name 'SIGNED-CATALOGS-*' \) -delete
cp "$ROOT/docs/RELEASE-NOTES-0.8.0-dev1.md" "$APPDIR/usr/share/doc/gameweld/RELEASE-NOTES-0.8.0-dev1.md"
cp "$ROOT/docs/SIGNED-CATALOGS-0.7.0-rc6.md" "$APPDIR/usr/share/doc/gameweld/SIGNED-CATALOGS-0.8.0-dev1.md"
cat > "$APPDIR/usr/share/gameweld/RELEASE.txt" <<'TXT'
GameWeld 0.8.0 Dev 1 — First-party FLiNG file-link review
Development build on 0.7.0 Stable. No automatic trainer downloads or unverified installs. Launcher helpers preserved.
TXT
sed -i 's/^X-AppImage-Version=.*/X-AppImage-Version=0.8.0-dev1/' "$APPDIR/gameweld.desktop"
cp "$APPDIR/gameweld.desktop" "$APPDIR/usr/share/applications/gameweld.desktop"
python3 "$ROOT/scripts/mksquash-minimal.py" "$APPDIR" "$WORK/root.squashfs"
OFFSET="$("$BASE_APPIMAGE" --appimage-offset)"
python3 - "$BASE_APPIMAGE" "$OFFSET" "$WORK/root.squashfs" "$OUT" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1]);offset=int(sys.argv[2]);sq=Path(sys.argv[3]);out=Path(sys.argv[4]);out.parent.mkdir(parents=True,exist_ok=True)
with base.open('rb') as f:runtime=f.read(offset)
out.write_bytes(runtime+sq.read_bytes());out.chmod(0o755)
PY
printf 'Built %s\n' "$OUT"
