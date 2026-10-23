# Build and test GameWeld 0.7.0 stable source snapshot

This snapshot is kept for source-tag correspondence; current development and CI live on `main`.

The original stable packager requires an independently supplied, tested `GameWeld-0.7.0-rc11-x86_64.AppImage` as its runtime baseline. The build is not independently reproducible. Run it on a compatible Ubuntu/Debian x86_64 host with GCC, Python 3 and GTK3 libraries:

```bash
./MAKE-APPIMAGE.sh /absolute/path/GameWeld-0.7.0-rc11-x86_64.AppImage
```

After building, compare all embedded application helper files against this source checkout and perform GTK startup and live launcher handoff checks. The stable binary was previously tested with 8 live game/trainer launch scenarios, but any redistribution changes require retesting.

Do not publish a binary/tag until artwork, the converted native trainer, and runtime provenance have been reviewed and approved. The tested stable AppImage SHA256 is `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`.
