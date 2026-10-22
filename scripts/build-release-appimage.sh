#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BASE_APPIMAGE="${1:?usage: build-release-appimage.sh BASE_APPIMAGE [OUT]}"
OUT="${2:-$ROOT/Wand-Native-0.1.42-x86_64.AppImage}"
WORK="${TMPDIR:-/tmp}/wand-native-release-$$"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK"
chmod +x "$BASE_APPIMAGE"
(
  cd "$WORK"
  "$BASE_APPIMAGE" --appimage-extract >/dev/null
)
APPDIR="$WORK/squashfs-root"

# Stable 0.1.42 is the validated UI Test 9 executable/runtime baseline.
gcc -O2 -pipe -fno-plt -pthread \
  "$ROOT/crates/wand-ui/appimage-gtk3/wand-native-042.c" -o "$APPDIR/usr/bin/wand-native" \
  /lib/x86_64-linux-gnu/libgtk-3.so.0 \
  /lib/x86_64-linux-gnu/libgdk-3.so.0 \
  /lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0 \
  /lib/x86_64-linux-gnu/libgobject-2.0.so.0 \
  /lib/x86_64-linux-gnu/libglib-2.0.so.0
strip "$APPDIR/usr/bin/wand-native"

rm -rf "$APPDIR/usr/share/wand-native/assets"
mkdir -p "$APPDIR/usr/share/wand-native/assets" "$APPDIR/usr/share/doc/wand-native"
cp -a "$ROOT/crates/wand-ui/assets/." "$APPDIR/usr/share/wand-native/assets/"
cp "$ROOT/crates/wand-ui/assets/wand-logo-reference.png" "$APPDIR/.DirIcon"
rm -f "$APPDIR/usr/share/wand-native"/RC*.txt
cat > "$APPDIR/usr/share/wand-native/RELEASE.txt" <<'TXT'
Wand Native 0.1.42 stable
Promoted from the validated UI Test 9 baseline.
TXT
cat > "$APPDIR/usr/share/wand-native/README.txt" <<'TXT'
Wand Native 0.1.42

Stable native Linux launcher UI with per-game Steam artwork, PLAY WITH WAND,
Play Normally, compatibility setup/repair, trainer health and quick actions.
The proven 0.1.41 runtime/session architecture remains the compatibility baseline.
TXT
cp "$ROOT/docs/RELEASE-NOTES-0.1.42.md" "$APPDIR/usr/share/doc/wand-native/RELEASE-NOTES-0.1.42.md"
cat > "$APPDIR/usr/share/doc/wand-native/UI-0.1.42.txt" <<'TXT'
Wand Native 0.1.42 stable UI

Validated UI Test 9 baseline: per-game artwork, GTK client-side titlebar,
mockup-aligned Home layout and existing 0.1.41 runtime behavior.
TXT
sed -i 's/^X-AppImage-Version=.*/X-AppImage-Version=0.1.42/' "$APPDIR/wand-native.desktop" "$APPDIR/usr/share/applications/wand-native.desktop"

python "$ROOT/scripts/mksquash-minimal.py" "$APPDIR" "$WORK/root.squashfs"
OFFSET="$($BASE_APPIMAGE --appimage-offset)"
python - "$BASE_APPIMAGE" "$OFFSET" "$WORK/root.squashfs" "$OUT" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1]); off=int(sys.argv[2]); sq=Path(sys.argv[3]); out=Path(sys.argv[4])
with base.open('rb') as f: runtime=f.read(off)
out.write_bytes(runtime+sq.read_bytes()); out.chmod(0o755)
PY
printf 'Built %s\n' "$OUT"
