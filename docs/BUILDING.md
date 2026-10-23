# Building GameWeld 0.7.0 PC1

This branch is the **PC1 distribution candidate**, not the original stable 0.7.0 source tag. It is maintained separately from the 0.8.0 development branch.

The PC1 AppImage build starts with the exact approved local copy of `GameWeld-0.7.0-x86_64.AppImage` as its baseline. Expected SHA256:

```
8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a
```

Ubuntu/Debian x86_64 build dependencies include GCC, Python 3 and GTK3 development libraries. From this checkout:

```bash
./scripts/ci-check.sh
./scripts/build-gameweld-0.7.0-pc1-appimage.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage /absolute/path/GameWeld-0.7.0-pc1-x86_64.AppImage
```

The release packager inherits runtime components from the pinned input. It is **not** independently reproducible from source alone. Check the resulting AppImage's helper checksums, inspect its extracted filesystem and perform GTK startup and actual Steam/Heroic/Lutris handoff tests.

PC1 removed the disputed game reference artwork and converted native Resonance trainer, but remaining GameWeld branding, inherited binaries and license notices must still be approved. The maintainer reported PC1 working locally without specifying per-launcher test results.

Do not create a public tag or release from this branch until the provenance and field release gates are signed off.
