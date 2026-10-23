# GameWeld 0.7.0 — Publication Candidate 1

PC1 is a redistribution-risk-reduction test build based on the tested 0.7.0 Stable AppImage. It is not the approved public release.

Changes: excludes the converted Resonance native trainer and game-specific reference artwork; disables native converted-table profiles in the UI and runtime helpers. Normal Steam, Heroic and Lutris trainer launch paths remain included. The 0.7.0 Stable build is unchanged.

Build on Linux x86_64 with Python 3, GCC and GTK3 libraries:

```bash
./scripts/build-gameweld-0.7.0-pc1-appimage.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage
```

The input is SHA256 pinned. Run `./scripts/ci-check.sh` to validate offline behaviour. Live game launches and legal approval remain separate release gates. Branding and inherited runtime component rights are not yet cleared.
