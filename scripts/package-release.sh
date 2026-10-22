#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION=0.1.42

for cmd in cargo zip sha256sum install cp; do
  command -v "$cmd" >/dev/null || { echo "Required release tool missing: $cmd" >&2; exit 1; }
done

for f in \
  "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" \
  "$ROOT/payload/crypt32/i386-windows/crypt32.dll"; do
  [[ -s "$f" ]] || {
    echo "Release payload missing: $f" >&2
    echo "Run scripts/extract-wand-proton-payload.sh first." >&2
    exit 1
  }
done

(cd "$ROOT" && cargo build --workspace --release)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/wand-native-$VERSION"
mkdir -p \
  "$PKG/bin" \
  "$PKG/scripts" \
  "$PKG/assets" \
  "$PKG/payload/crypt32/x86_64-windows" \
  "$PKG/payload/crypt32/i386-windows" \
  "$PKG/packaging/systemd" \
  "$PKG/packaging/desktop"

# Normal-user root: keep only install/uninstall/readme/license material.
install -m755 "$ROOT/install.sh" "$PKG/install.sh"
install -m755 "$ROOT/uninstall.sh" "$PKG/uninstall.sh"
install -m644 "$ROOT/README-PUBLIC.md" "$PKG/README.md"
install -m644 "$ROOT/THIRD-PARTY.md" "$PKG/THIRD-PARTY.md"
if [[ -f "$ROOT/docs/RELEASE-NOTES-0.1.42.md" ]]; then
  install -m644 "$ROOT/docs/RELEASE-NOTES-0.1.42.md" "$PKG/RELEASE-NOTES.md"
elif [[ -f "$ROOT/docs/RELEASE-NOTES-0.1.41.md" ]]; then
  install -m644 "$ROOT/docs/RELEASE-NOTES-0.1.41.md" "$PKG/RELEASE-NOTES.md"
fi

# Prebuilt application binaries.
install -m755 "$ROOT/target/release/wandctl" "$PKG/bin/wandctl"
install -m755 "$ROOT/target/release/wandd" "$PKG/bin/wandd"
install -m755 "$ROOT/target/release/wand-ui" "$PKG/bin/wand-ui"
cp -a "$ROOT/crates/wand-ui/assets/." "$PKG/assets/"

# Only scripts needed by the installed end-user runtime.
for script in \
  wand-proton-manager.sh \
  wand-trainer-health.sh \
  wand-setup \
  install-dwritecore.sh; do
  install -m755 "$ROOT/scripts/$script" "$PKG/scripts/$script"
done

# Tested crypt32 compatibility payload.
install -m644 "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" \
  "$PKG/payload/crypt32/x86_64-windows/crypt32.dll"
install -m644 "$ROOT/payload/crypt32/i386-windows/crypt32.dll" \
  "$PKG/payload/crypt32/i386-windows/crypt32.dll"
if [[ -f "$ROOT/payload/crypt32/manifest.json" ]]; then
  install -m644 "$ROOT/payload/crypt32/manifest.json" "$PKG/payload/crypt32/manifest.json"
fi

# User service and desktop launchers.
install -m644 "$ROOT/packaging/systemd/wandd.service" "$PKG/packaging/systemd/wandd.service"
install -m644 "$ROOT/packaging/desktop/dev.wand.WandNative.desktop" \
  "$PKG/packaging/desktop/dev.wand.WandNative.desktop"
install -m644 "$ROOT/packaging/desktop/dev.wand.WandNative.Setup.desktop" \
  "$PKG/packaging/desktop/dev.wand.WandNative.Setup.desktop"

# Guard against accidentally shipping the development tree to normal users.
for forbidden in \
  Cargo.toml Cargo.lock MAKE-PUBLIC-RELEASE.sh BUILD-NOTES.json crates patches tools target dist; do
  [[ ! -e "$PKG/$forbidden" ]] || {
    echo "ERROR: developer-only path leaked into public package: $forbidden" >&2
    exit 1
  }
done
for forbidden_script in extract-wand-proton-payload.sh package-release.sh release-check.sh; do
  [[ ! -e "$PKG/scripts/$forbidden_script" ]] || {
    echo "ERROR: maintainer script leaked into public package: $forbidden_script" >&2
    exit 1
  }
done

mkdir -p "$OUT"
ZIP="$OUT/wand-native-$VERSION-linux-x86_64.zip"
rm -f "$ZIP" "$ZIP.sha256"
(cd "$STAGE" && zip -qr "$ZIP" "wand-native-$VERSION")
sha256sum "$ZIP" > "$ZIP.sha256"

# Verify the final archive, not only the staging directory.
unzip -tq "$ZIP" >/dev/null
if unzip -Z1 "$ZIP" | grep -Eq \
  '/(Cargo\.toml|Cargo\.lock|MAKE-PUBLIC-RELEASE\.sh|BUILD-NOTES\.json)$|/(crates|patches|tools|target|dist)/'; then
  echo "ERROR: developer-only content found in final public ZIP" >&2
  exit 1
fi

echo "Created $ZIP"
echo "Public package root contains only normal-user files plus runtime subdirectories."
