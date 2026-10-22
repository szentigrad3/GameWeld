#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/wand-native"
BIN="$HOME/.local/bin"
SKIP_PROTON=0
[[ "${1:-}" == "--skip-proton" ]] && SKIP_PROTON=1

say(){ printf '%s\n' "$*"; }
die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }

say "Wand Native 0.1.42 setup"
say

mkdir -p "$BIN" "$PREFIX/scripts" "$PREFIX/payload" "$PREFIX/assets" "$HOME/.config/systemd/user" "$HOME/.local/share/applications"

if [[ -x "$ROOT/bin/wandctl" && -x "$ROOT/bin/wandd" && -x "$ROOT/bin/wand-ui" ]]; then
  say "Installing prebuilt Wand Native binaries..."
  install -m755 "$ROOT/bin/wandctl" "$BIN/wandctl"
  install -m755 "$ROOT/bin/wandd" "$BIN/wandd"
  install -m755 "$ROOT/bin/wand-ui" "$BIN/wand-ui"
elif [[ "${WAND_USE_EXISTING_BUILD:-0}" == "1" && -x "$ROOT/target/release/wandctl" && -x "$ROOT/target/release/wandd" && -x "$ROOT/target/release/wand-ui" ]]; then
  say "Installing the existing local release build..."
  install -m755 "$ROOT/target/release/wandctl" "$BIN/wandctl"
  install -m755 "$ROOT/target/release/wandd" "$BIN/wandd"
  install -m755 "$ROOT/target/release/wand-ui" "$BIN/wand-ui"
else
  command -v cargo >/dev/null || die "This is a source bundle and cargo is not installed. Use the prebuilt release archive, or install Rust/Cargo."
  command -v pkg-config >/dev/null || die "pkg-config is required for a source build"
  pkg-config --atleast-version=4.10 gtk4 || die "GTK 4.10+ development files are required for a source build"
  pkg-config --exists libadwaita-1 || die "libadwaita development files are required for a source build"
  say "No prebuilt binaries found; building from source..."
  (cd "$ROOT" && cargo build --workspace --release)
  install -m755 "$ROOT/target/release/wandctl" "$BIN/wandctl"
  install -m755 "$ROOT/target/release/wandd" "$BIN/wandd"
  install -m755 "$ROOT/target/release/wand-ui" "$BIN/wand-ui"
fi

cp -a "$ROOT/scripts/." "$PREFIX/scripts/"
rm -rf "$PREFIX/assets"
mkdir -p "$PREFIX/assets"
if [[ -d "$ROOT/assets" ]]; then
  cp -a "$ROOT/assets/." "$PREFIX/assets/"
elif [[ -d "$ROOT/crates/wand-ui/assets" ]]; then
  cp -a "$ROOT/crates/wand-ui/assets/." "$PREFIX/assets/"
fi
install -m755 "$ROOT/scripts/wand-setup" "$BIN/wand-setup"
rm -rf "$PREFIX/payload/crypt32"
mkdir -p "$PREFIX/payload"
cp -a "$ROOT/payload/crypt32" "$PREFIX/payload/crypt32"

install -m644 "$ROOT/packaging/systemd/wandd.service" "$HOME/.config/systemd/user/wandd.service"
install -m644 "$ROOT/packaging/desktop/dev.wand.WandNative.desktop" "$HOME/.local/share/applications/dev.wand.WandNative.desktop"
install -m644 "$ROOT/packaging/desktop/dev.wand.WandNative.Setup.desktop" "$HOME/.local/share/applications/dev.wand.WandNative.Setup.desktop"

systemctl --user daemon-reload
systemctl --user enable --now wandd.service

# DWriteCore is useful for Wand/WeMod UI compatibility but a temporary network
# failure should not make the whole installer fail.
if [[ -x "$PREFIX/scripts/install-dwritecore.sh" ]]; then
  "$PREFIX/scripts/install-dwritecore.sh" || say "Note: DWriteCore download failed; rerun it later from $PREFIX/scripts/install-dwritecore.sh"
fi

if (( SKIP_PROTON == 0 )); then
  if [[ -s "$PREFIX/payload/crypt32/x86_64-windows/crypt32.dll" && -s "$PREFIX/payload/crypt32/i386-windows/crypt32.dll" ]]; then
    "$PREFIX/scripts/wand-proton-manager.sh" install
  else
    say
    say "The patched Proton payload is not bundled in this developer/source archive."
    say "Wand Native itself is installed, but the Wand-compatible Proton tool was not created."
  fi
fi

say
say "Wand Native installation complete."
say "Open 'Wand Native' from your application menu."
say "For Wand-compatible game setup, open 'Wand Native Setup' or run: wandctl setup"
say
say "After creating/updating the Wand Proton tool, restart Steam before selecting it for a game."
