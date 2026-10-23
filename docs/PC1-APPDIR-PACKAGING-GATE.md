# PC1 compiled-artifact gate

This check is for **GameWeld 0.7.0 PC1**, not the original 0.7.0 Stable binary or the 0.8.0 development branch.

The PC1 package script runs `scripts/audit-appimage-files.py` against the extracted/rebuilt AppDir **before repacking it**. It fails closed when a known excluded reference image, an unexpected ELF/PE executable, a bundled DLL, a missing expected executable, or mismatched GTK launcher copies are found. Digest calculation reads input in chunks rather than loading whole files into memory.

Expected compiled artifacts:

- `usr/bin/gameweld`, `usr/bin/gameforge`, `usr/bin/wand-native` — byte-identical GTK ELF launchers
- `usr/libexec/wand-native-backend` — ELF
- `usr/libexec/gameweld-elevate.exe` — Windows PE

## Validation

From the PC1 source branch, run:

```bash
./scripts/ci-check.sh
./scripts/build-gameweld-0.7.0-pc1-appimage.sh /absolute/path/GameWeld-0.7.0-x86_64.AppImage /absolute/path/PC1-output.AppImage
```

The source's offline CI now includes **9** package-policy tests. A local candidate repack completed with `PACKAGING_PASS_ONLY`: 94 files, 0 symlinks, five expected ELF/PE paths. The original PC1 binary also passed the same scanner with that count.

The locally rebuilt AppImage's overall SHA256 differs from the previously field-tested PC1 release candidate; it must be regarded as **a new build** for field verification if used. No binary was uploaded through this change.

**A passing gate is not proof of copyright permission, full source-to-binary reproducibility, or safe trainer updates.** Review of GameWeld branding and inherited runtime provenance remains open in issues #4, #5 and #6. No `v0.7.0` tag or GitHub release is authorized by these tests.
