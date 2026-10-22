# GameWeld

**Linux game and trainer management for Steam, Heroic and Lutris.**

GameWeld keeps local trainer assignments together, helps discover publisher-listed trainers, and launches supported games and trainers through their existing Wine, Proton and launcher sessions.

**Latest stable:** 0.7.0  
**Current development build:** 0.8.0 Dev 1 (publisher-file review; no unattended downloads)

GameWeld is maintained by [@szentigrad3](https://github.com/szentigrad3).

## Features

- Trainer Library with **My Trainers**, **Find Updates**, and **Advanced** views.
- Steam and Steam-shortcut, Heroic (Epic/GOG), and Lutris game discovery and session-aware trainer launching.
- FLiNG publisher page and release-listing discovery with game-version compatibility hints.
- Local trainer filename comparisons and read-only metadata reporting.
- Signed-catalog verification (Ed25519 with locally pinned keys), approved checksum-pinned staging, inspection and rollback.
- Read-only upgrade preflight, automatic-check limits, and support diagnostics.
- Experimental Wand/WeMod prefix detection and manager awareness.

**Important:** a publisher page is not a verified trainer update. GameWeld does not bundle third-party trainers, does not guarantee that a found executable is trustworthy, and does not install arbitrary publisher files automatically. The signed catalog format is implemented, but no official signing keys or authenticated feeds for FLiNG, HexTrainer, Aurora, Cheat Evolution or Wand are bundled.

## Install

**GitHub release assets are not published yet.** Track the first stable release in [issue #4](https://github.com/szentigrad3/GameWeld/issues/4). Once published, download the Linux x86_64 **AppImage** from [Releases](https://github.com/szentigrad3/GameWeld/releases), then:

```bash
chmod +x GameWeld-0.7.0-x86_64.AppImage
./GameWeld-0.7.0-x86_64.AppImage
```

Use 0.7.0 for daily play. Test 0.8.0 development releases separately and retain the stable AppImage as a fallback. Existing user configuration lives under XDG configuration/state directories and is not embedded in release packages.

## Build the development AppImage

Current packaging **requires the exact 0.7.0 stable AppImage as its runtime baseline**. This is not yet an entirely from-scratch build. A clean build is a tracked roadmap item. For a build from the checked-out source, see [Building](docs/BUILDING.md).

```bash
./MAKE-APPIMAGE.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage
```

The build regenerates the GTK application and embeds the current GameWeld helpers into the baseline runtime. Do not use an unverified AppImage as the baseline.

## Development & support

- [Build and test](docs/BUILDING.md)
- [Project roadmap](ROADMAP.md)
- [Release process](docs/RELEASING.md)
- [Third-party components](THIRD-PARTY.md)
- [Contributing](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)

Bug reports should include the GameWeld version, launcher (Steam/Heroic/Lutris), Linux distribution, relevant symptoms and a **redacted** log. Don't upload credentials, proprietary trainer executables, Wine prefixes or personal files.

## Licensing and independence

GameWeld's own source is distributed under the [MIT license](LICENSE). Third-party tools, libraries, runtime components and artwork retain their own terms; see [THIRD-PARTY.md](THIRD-PARTY.md). GameWeld is not affiliated with Valve, Epic, GOG, FLiNG, Cheat Happens, HexTrainer, Cheat Evolution or WeMod.
