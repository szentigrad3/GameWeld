#!/usr/bin/env bash
# Opt-in redistribution-risk-reduction test build; NOT a cleared public release.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BASE="${1:?Usage: build-gameweld-0.7.0-pc1-appimage.sh VERIFIED_0.7.0_APPIMAGE [OUTPUT]}"
OUT="${2:-$ROOT/GameWeld-0.7.0-pc1-x86_64.AppImage}"
EXPECTED=8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a
GOT="$(sha256sum "$BASE" | cut -d ' ' -f1)"
[[ "$GOT" == "$EXPECTED" ]] || { echo 'Baseline AppImage checksum differs from pinned 0.7.0; refusing to build.' >&2; exit 2; }
TMP="$(mktemp -d -t gameweld-public-candidate-XXXXXX)"
trap 'rm -rf -- "$TMP"' EXIT
(cd "$TMP" && "$BASE" --appimage-extract >/dev/null)
APP="$TMP/squashfs-root"
# Do not ship reference game art or converted native trainer while rights are unresolved.
rm -f -- "$APP/usr/libexec/resonance-native-trainer.exe"
find "$APP/usr/share" -type f \( -name 'resonance-hero-reference.png' -o -name 'resonance-cover-reference.png' -o -name 'wand-logo-reference.png' \) -delete
find "$APP/usr/share" -type f \( -path '*/assets/games/2713000/hero.png' -o -path '*/assets/games/2713000/cover.png' \) -delete
# Do not leave old native-profile scripts able to find and execute external copies.
for name in gameweld gameforge wand; do
  install -m 0755 "$ROOT/scripts/$name-native-profile.sh" "$APP/usr/libexec/$name-native-profile.sh"
done
# Recompile GTK UI with native profile registration disabled.
gcc -O2 -pipe -fno-plt -pthread \
  "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" -o "$APP/usr/bin/gameweld" \
  /lib/x86_64-linux-gnu/libgtk-3.so.0 /lib/x86_64-linux-gnu/libgdk-3.so.0 \
  /lib/x86_64-linux-gnu/libgdk_pixbuf-2.0.so.0 /lib/x86_64-linux-gnu/libgobject-2.0.so.0 \
  /lib/x86_64-linux-gnu/libglib-2.0.so.0
strip "$APP/usr/bin/gameweld"
for name in gameforge wand-native; do cp "$APP/usr/bin/gameweld" "$APP/usr/bin/$name"; done
cat > "$APP/usr/share/gameweld/RELEASE.txt" <<'TXT'
GameWeld 0.7.0 Publication Candidate 1 (PC1)
Risk-reduction TEST BUILD, not a published release and not yet license-cleared.
Third-party converted native trainer and game-reference artwork have been removed.
The ordinary Steam, Heroic, Lutris and local-trainer launch paths are retained for regression testing.
Native converted-table profiles are disabled. Existing trainer assignments are not modified.
TXT
sed -i 's/^X-AppImage-Version=.*/X-AppImage-Version=0.7.0-pc1/' "$APP/gameweld.desktop"
cp "$APP/gameweld.desktop" "$APP/usr/share/applications/gameweld.desktop"
mkdir -p "$APP/usr/share/doc/gameweld"
cp "$ROOT/docs/RELEASE-NOTES-0.7.0-pc1.md" "$APP/usr/share/doc/gameweld/RELEASE-NOTES-0.7.0-pc1.md"
# A passing report enforces package contents; it does not grant redistribution rights.
python3 "$ROOT/scripts/audit-appimage-files.py" "$APP"
python3 "$ROOT/scripts/mksquash-minimal.py" "$APP" "$TMP/root.squashfs"
OFFSET="$("$BASE" --appimage-offset)"
python3 - "$BASE" "$OFFSET" "$TMP/root.squashfs" "$OUT" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1]);off=int(sys.argv[2]);sq=Path(sys.argv[3]);out=Path(sys.argv[4]);out.parent.mkdir(parents=True,exist_ok=True)
with base.open('rb') as f: prefix=f.read(off)
out.write_bytes(prefix+sq.read_bytes())
out.chmod(0o755)
PY
printf 'Built %s (unapproved redistribution candidate)\n' "$OUT"
