#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
command -v cargo >/dev/null || { echo "cargo is required. On Arch/CachyOS: sudo pacman -S --needed rust cargo gtk4 libadwaita pkgconf rsync" >&2; exit 1; }
pkg-config --atleast-version=4.10 gtk4 || { echo "GTK 4.10+ development files are required" >&2; exit 1; }
pkg-config --exists libadwaita-1 || { echo "libadwaita development files are required" >&2; exit 1; }
cargo fmt --all
cargo check --workspace
cargo test --workspace
cargo build --workspace --release
WAND_USE_EXISTING_BUILD=1 ./install.sh
echo
echo "Installed Wand Native 0.1.42."
echo "Normal setup: wandctl setup"
echo "Health check: wandctl trainer-health [APPID]"
