#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
VERSION="0.1.42"
ARCH="x86_64"
OUT="${1:-$ROOT/dist}"
APPDIR="$OUT/Wand-Native.AppDir"
TOOLS="${XDG_CACHE_HOME:-$HOME/.cache}/wand-native/appimage-tools"

say(){ printf '%s\n' "$*"; }
die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }
fetch(){
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 20 -o "$out" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$out" "$url"
  else
    die "curl or wget is required"
  fi
}

for cmd in cargo install cp mkdir sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || die "Required build tool missing: $cmd"
done

for f in \
  "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" \
  "$ROOT/payload/crypt32/i386-windows/crypt32.dll"; do
  [[ -s "$f" ]] || die "Patched crypt32 payload missing: $f"
done

for bin in wand-ui wandd wandctl; do
  [[ -x "$ROOT/target/release/$bin" ]] || die "Missing release binary: target/release/$bin"
done

mkdir -p "$OUT" "$TOOLS"
rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/share/wand-native/scripts" \
  "$APPDIR/usr/share/wand-native/assets" \
  "$APPDIR/usr/share/wand-native/payload/crypt32/x86_64-windows" \
  "$APPDIR/usr/share/wand-native/payload/crypt32/i386-windows" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps"

install -m755 "$ROOT/target/release/wand-ui" "$APPDIR/usr/bin/wand-ui"
install -m755 "$ROOT/target/release/wandd" "$APPDIR/usr/bin/wandd"
install -m755 "$ROOT/target/release/wandctl" "$APPDIR/usr/bin/wandctl"
cp -a "$ROOT/crates/wand-ui/assets/." "$APPDIR/usr/share/wand-native/assets/"

for script in \
  wand-appimage-setup.sh \
  wand-proton-manager.sh \
  wand-trainer-health.sh \
  install-dwritecore.sh; do
  install -m755 "$ROOT/scripts/$script" "$APPDIR/usr/share/wand-native/scripts/$script"
done

install -m644 "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" \
  "$APPDIR/usr/share/wand-native/payload/crypt32/x86_64-windows/crypt32.dll"
install -m644 "$ROOT/payload/crypt32/i386-windows/crypt32.dll" \
  "$APPDIR/usr/share/wand-native/payload/crypt32/i386-windows/crypt32.dll"
[[ -f "$ROOT/payload/crypt32/manifest.json" ]] && \
  install -m644 "$ROOT/payload/crypt32/manifest.json" "$APPDIR/usr/share/wand-native/payload/crypt32/manifest.json"

install -m755 "$ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
install -m644 "$ROOT/packaging/appimage/dev.wand.WandNative.desktop" \
  "$APPDIR/usr/share/applications/dev.wand.WandNative.desktop"
install -m644 "$ROOT/packaging/appimage/dev.wand.WandNative.svg" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps/dev.wand.WandNative.svg"
cp "$ROOT/packaging/appimage/dev.wand.WandNative.desktop" "$APPDIR/dev.wand.WandNative.desktop"
cp "$ROOT/packaging/appimage/dev.wand.WandNative.svg" "$APPDIR/dev.wand.WandNative.svg"
cp "$ROOT/packaging/appimage/dev.wand.WandNative.svg" "$APPDIR/.DirIcon"

# GTK/GLib applications need their schemas even when the shared libraries are bundled.
if [[ -d /usr/share/glib-2.0/schemas ]]; then
  mkdir -p "$APPDIR/usr/share/glib-2.0"
  cp -a /usr/share/glib-2.0/schemas "$APPDIR/usr/share/glib-2.0/"
fi

LINUXDEPLOY="$TOOLS/linuxdeploy-${ARCH}.AppImage"
APPIMAGETOOL="$TOOLS/appimagetool-${ARCH}.AppImage"
if [[ ! -x "$LINUXDEPLOY" ]]; then
  say "Downloading linuxdeploy..."
  fetch "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-${ARCH}.AppImage" "$LINUXDEPLOY.part"
  mv "$LINUXDEPLOY.part" "$LINUXDEPLOY"
  chmod +x "$LINUXDEPLOY"
fi
if [[ ! -x "$APPIMAGETOOL" ]]; then
  say "Downloading appimagetool..."
  fetch "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage" "$APPIMAGETOOL.part"
  mv "$APPIMAGETOOL.part" "$APPIMAGETOOL"
  chmod +x "$APPIMAGETOOL"
fi

say "Deploying ELF dependencies into AppDir..."
"$LINUXDEPLOY" --appimage-extract-and-run \
  --appdir "$APPDIR" \
  --executable "$APPDIR/usr/bin/wand-ui" \
  --executable "$APPDIR/usr/bin/wandd" \
  --executable "$APPDIR/usr/bin/wandctl" \
  --desktop-file "$APPDIR/usr/share/applications/dev.wand.WandNative.desktop" \
  --icon-file "$APPDIR/usr/share/icons/hicolor/scalable/apps/dev.wand.WandNative.svg"

# linuxdeploy may generate a generic AppRun; restore our backend-owning launcher.
install -m755 "$ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"

APPIMAGE="$OUT/Wand-Native-${VERSION}-${ARCH}.AppImage"
rm -f "$APPIMAGE" "$APPIMAGE.sha256"
say "Creating AppImage..."
ARCH="$ARCH" VERSION="$VERSION" \
  "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE"
chmod +x "$APPIMAGE"
sha256sum "$APPIMAGE" > "$APPIMAGE.sha256"

say
say "Created: $APPIMAGE"
ls -lh "$APPIMAGE" "$APPIMAGE.sha256"
