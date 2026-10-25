#!/usr/bin/env bash
# Private host-dependent AppImage packaging; no downloads or publishing.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${GAMEWELD_PC2_STAGE:-$ROOT/build/pc2-source/private-AppDir}"
OUT="${GAMEWELD_PC2_IMAGE_OUT:-$ROOT/build/pc2-source/GameWeld-0.8.0-rc1-private-x86_64.AppImage}"
TOOL="${GAMEWELD_APPIMAGETOOL:-}"
[[ -d "$SRC" && -f "$SRC/NOT-FOR-DISTRIBUTION.txt" && -x "$SRC/AppRun" ]] || { echo "Stage private AppDir first" >&2; exit 2; }
MODE="$(sed -n 's/^Build mode: //p' "$SRC/NOT-FOR-DISTRIBUTION.txt")"
case "$MODE" in
  discovery) ;;
  functional)
    [[ "${GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST:-}" == "I_UNDERSTAND_PRIVATE_TEST_ONLY" ]] || {
      echo "Refusing to package functional build without explicit private-test opt-in" >&2
      exit 2
    }
    ;;
  *) echo "Missing or invalid private build mode marker" >&2; exit 2 ;;
esac
[[ "${GAMEWELD_PC2_IMAGE_OUT:-}" || "$MODE" == "discovery" ]] || {
  echo "Functional build requires explicit GAMEWELD_PC2_IMAGE_OUT filename" >&2
  exit 2
}
[[ -n "$TOOL" && -f "$TOOL" && -x "$TOOL" ]] || { echo "Set GAMEWELD_APPIMAGETOOL to an executable, manually verified appimagetool path" >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo "Refusing to overwrite existing output: $OUT" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
APP="$TMP/GameWeld.AppDir"
cp -a -- "$SRC" "$APP"
cat > "$APP/gameweld.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GameWeld (Private RC1 Test)
Exec=AppRun
Icon=gameweld
Categories=Game;Utility;
Terminal=false
EOF
mkdir -p "$APP/usr/share/icons/hicolor/scalable/apps"
cat > "$APP/usr/share/icons/hicolor/scalable/apps/gameweld.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect x="8" y="8" width="112" height="112" rx="24" fill="#26384b"/><path d="M31 62h66M64 30v68" stroke="#e9f2f8" stroke-width="12" stroke-linecap="round"/></svg>
EOF
ln -s usr/share/icons/hicolor/scalable/apps/gameweld.svg "$APP/gameweld.svg"
ln -s gameweld.svg "$APP/.DirIcon"
printf "%s\n" "PRIVATE TEST ONLY: system libraries not bundled; redistribution not cleared" > "$APP/NOT-FOR-DISTRIBUTION.txt"
ARCH=x86_64 "$TOOL" "$APP" "$OUT"
[[ -s "$OUT" ]] || { echo "No AppImage generated" >&2; exit 3; }
chmod 755 "$OUT"
sha256sum "$OUT" | tee "$OUT.sha256"
echo "Private host-dependent AppImage ($MODE mode): $OUT"
echo "NOT APPROVED FOR PUBLICATION or cross-distro portability claims."
