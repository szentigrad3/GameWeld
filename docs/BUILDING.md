# Building and testing

## Supported development host

Linux x86_64 with Python 3, GCC, Git and GTK3 runtime libraries. Some optional Cargo workspaces have additional GTK4/libadwaita requirements; the released AppImage UI currently builds from `crates/wand-ui/appimage-gtk3/gameweld-native-040.c`.

On Debian/Ubuntu development hosts:

```bash
sudo apt-get update
sudo apt-get install -y build-essential python3 libgtk-3-dev
```

On CachyOS/Arch, ensure `base-devel`, `python`, `gtk3` and `git` are installed.

## Offline checks

```bash
./scripts/ci-check.sh
```

The checks use local fixtures and do not install trainers.

## AppImage packaging

The **0.8.0 Dev 1 packaging process is incremental**: it extracts a verified 0.7.0 AppImage, compiles GameWeld's GTK UI, replaces 14 GameWeld libexec helpers, and repacks the runtime. The 0.7.0 AppImage must be supplied separately.

```bash
sha256sum GameWeld-0.7.0-x86_64.AppImage
# Must equal the pinned value in docs/BASELINE-SHA256.txt.
chmod +x GameWeld-0.7.0-x86_64.AppImage
./MAKE-APPIMAGE.sh "$(realpath GameWeld-0.7.0-x86_64.AppImage)" "$(pwd)/build/GameWeld-0.8.0-dev1-x86_64.AppImage"
```

The current packager uses the Ubuntu/Debian-style GTK3 shared-library paths (`/lib/x86_64-linux-gnu`). Builds on CachyOS can use an Ubuntu CI runner/container for packaging even when the resulting AppImage is tested on CachyOS.

**Not a clean-room reproducible build yet:** binaries/assets inherited from the stable AppImage are outside this source checkout. The bootstrap runtime is pinned by SHA256, and release candidates should include a matching source tree and a validation report. Never claim bit-for-bit reproducibility without checking it.

## Release gates

- Offline suites and static source checks pass.
- AppImage extracts and launches in an isolated X display.
- Packaged helper checksums match the release source.
- No third-party trainer packages or user-specific state files are included.
- Real Steam/Heroic/Lutris handoff tests are recorded before stable promotion.
