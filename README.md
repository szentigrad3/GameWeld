# GameWeld 0.7.0 — Publication Candidate 1 (PC1)

This branch is a **release-review source snapshot**, not the published 0.7.0 stable release. Current 0.8.0 development continues on [main](https://github.com/szentigrad3/GameWeld/tree/main).

PC1 starts from the SHA256-pinned GameWeld 0.7.0 stable AppImage and removes bundled game reference artwork and the converted Resonance native trainer. It also disables the corresponding native-table launch profiles. Regular Steam, Heroic, Lutris and local trainer launch paths are retained.

The maintainer reported that PC1 works on CachyOS. Individual Steam, Heroic and Lutris handoffs have **not** been separately reconfirmed for PC1. The original 0.7.0 stable build had earlier live launch validation.

## Build and offline checks

On Linux x86_64 with GCC, GTK3 development libraries and Python 3:

```bash
./scripts/ci-check.sh
./scripts/build-gameweld-0.7.0-pc1-appimage.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage /absolute/path/GameWeld-0.7.0-pc1-x86_64.AppImage
```

The source input is pinned, and this build **repackages an earlier verified GameWeld AppImage**. It is not independently reproducible or source-complete. The input stable AppImage SHA256 is `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`.

## Publication status

- Source branch: `release/0.7.0-pc1`
- This branch is **not** the `v0.7.0` tag.
- No GitHub binary release has been approved or published from this branch.
- GameWeld branding, remaining inherited runtime binaries and third-party notices still require rights/provenance review.
- Inspect [PC1 release notes](docs/RELEASE-NOTES-0.7.0-pc1.md), [build instructions](docs/BUILDING.md) and [release gates](docs/RELEASING.md).
- Track the publication process in [issue #4](https://github.com/szentigrad3/GameWeld/issues/4) and the licensing review in [issue #5](https://github.com/szentigrad3/GameWeld/issues/5).

GameWeld does not bundle third-party trainer packages for automated execution, and a link on a publisher's page is not proof of an authenticated or safe executable.
