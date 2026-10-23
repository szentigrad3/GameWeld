# GameWeld 0.7.0 — Stable source snapshot

This directory is a curated snapshot of GameWeld 0.7.0 stable source files, reconstructed from the tested stable source archive and the GitHub source tree. It is **not yet a published tag**, and it has not been approved for public binary redistribution.

For current development, see https://github.com/szentigrad3/GameWeld (`main` tracks 0.8.0 development). The verified stable AppImage SHA256 is `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`.

## Build

The historical stable packager requires the tested 0.7.0 RC11 AppImage as its runtime input. It is **not a source-complete, independently reproducible build**.

```bash
./MAKE-APPIMAGE.sh /absolute/path/GameWeld-0.7.0-rc11-x86_64.AppImage
```

The snapshot deliberately excludes game-specific reference images and redistributable prebuilt trainer executables. The existing binary does still contain reference artwork and a game-specific native trainer. Resolve the license/provenance review in the live repository before tagging/releasing the binary. See `docs/RELEASE-AUDIT-0.7.0.md` after the release audit PR is merged.

## Source and rights

GameWeld-owned source carries the MIT license, but this does not automatically license any derived third-party material or runtime binaries. Check `THIRD-PARTY.md` and `docs/PUBLICATION-REVIEW.md` before distribution.
