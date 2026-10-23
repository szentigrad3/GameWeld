# GameWeld 0.7.0 — Publication Candidate 1 (PC1)

**Not a public/stable release. Licensing/provenance sign-off remains required.**

This candidate starts from the checksum-pinned, field-tested 0.7.0 stable AppImage. To reduce redistribution risk, it removes the bundled Resonance/game-specific artwork and converted `resonance-native-trainer.exe`, and disables all native converted-table profiles in the GTK UI and the three runtime launch scripts.

Steam, Heroic, Lutris, local trainer assignments, Cheat Engine table support, FLiNG metadata checks, offline signed-catalog validation and rollback were not intentionally modified. These paths still require field regression after the runtime was repacked.

No downloaded third-party trainers are included. Launcher AppImage inheritance means this is **not** an independently rebuilt, fully license-cleared binary; attribution and licensing of branding, inherited runtime and helper binaries still require owner review. The original 0.7.0 stable AppImage is unmodified and can remain a local fallback.

## Building

On an Ubuntu/Debian x86_64 host with GCC, Python 3 and GTK3 development libraries:

```bash
./scripts/build-gameweld-0.7.0-pc1-appimage.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage /absolute/path/GameWeld-0.7.0-pc1-x86_64.AppImage
```

The input must match SHA256 `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`; do not substitute other AppImages.
