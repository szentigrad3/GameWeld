# GameWeld 0.7.0 PC1 — Compiled runtime inventory

**Observed source:** extracted local `GameWeld-0.7.0-pc1-x86_64.AppImage`, SHA256 `1a5ea219923bbd94fcb7f4d83edb66cdcdaf97a81c2d73d16c85f10d83c219da`.

**Result:** `PACKAGING_PASS_ONLY` (96 files, 0 symlinks, 5 executable *paths*, 3 distinct executable SHA256 hashes). This is a packaging check, **not** a redistribution or security approval. The earlier PC1 report counted 94 regular files; the new full filesystem inventory counts 96, including two inherited Python `__pycache__` files.

| Packaged executable paths | Format | SHA256 | Source status |
| --- | --- | --- | --- |
| `usr/bin/gameweld`, `usr/bin/gameforge`, `usr/bin/wand-native` | ELF (identical bytes) | `d6633c092458ec0231ea7909ecebf707e6bdf96be5635bab641018a4bec6c10a` | GTK C source in `crates/wand-ui/appimage-gtk3/gameweld-native-040.c`; candidate compilation validated, inherited runtime provenance still to review |
| `usr/libexec/wand-native-backend` | ELF, Go 1.23.2, Linux x86_64 | `ecf76f3cad46713a1a43901c0bad67a6e50960f175ae341fd7337cfd4897b70a` | Repository includes Go and Rust backend components, but a source-to-binary rebuild and complete dependency provenance are **not** independently verified |
| `usr/libexec/gameweld-elevate.exe` | Windows PE32+ x86_64 | `36d93b5597aec71dc54ea2d15647a0b6b0a84747ce7c3d2d1a373d59652513ef` | `cmd/gameweld-elevate/main.go` is present; build provenance and third-party dependencies need review |

The GTK executable dynamically requests `libgtk-3.so.0`, `libgdk-3.so.0`, `libgdk_pixbuf-2.0.so.0`, `libgobject-2.0.so.0`, `libglib-2.0.so.0` and `libc.so.6`. These libraries are **not** embedded as `.so` files in this exact candidate, so they are required from the target system/runtime environment. The AppImage does not contain any `.dll` files. The Windows elevation helper is still a distributed `.exe` and must be independently covered by release review.

GameWeld branding remains embedded:

- `usr/share/gameweld/assets/gameweld-brand-logo.png` — SHA256 `ca7fd3c3ac5283af3cbfdf1c0fd4bf7c2081fe841ec8b3d9b0cfebf8f9ffb1c8`
- `usr/share/gameweld/assets/gameweld-app-icon.png` — SHA256 `2f6bbc18d777c18049524eb01327edbe219fde2df9eabb5f87f40dc6c9e70a40`

The artwork's ownership and distribution rights need explicit maintainer approval.

## Automated narrow packaging policy

The read-only `scripts/audit-appimage-files.py` tool checks an **already extracted** AppDir for the expected compiled helpers, any unexpected Windows executables, bundled DLLs and excluded third-party reference images. It emits SHA256 hashes for executable files and exits nonzero on known violations. Six fixture tests cover passing builds and expected failures:

```bash
./GameWeld-0.7.0-pc1-x86_64.AppImage --appimage-extract
python3 scripts/audit-appimage-files.py squashfs-root
python3 scripts/audit-appimage-files.py squashfs-root --json
```

**Important:** `--appimage-extract` runs the AppImage's extraction mechanism; run it only on a verified artifact. This scanner itself does not execute binaries or contact remote services. A packaging pass **does not** imply third-party permission, binary-source correspondence, security, trusted downloads or successful live game launches.

## Before GitHub Release

- [ ] Confirm copyright/licensing/provenance of branding and remaining backend, PE and ELF binaries.
- [ ] Verify the current source can reconstruct the runtime components and document exceptions.
- [ ] Confirm live Steam, Heroic and Lutris launch paths on the PC1 candidate individually.
- [ ] Commit reviewed stable source to a proper dedicated GitHub ref; do **not** tag current 0.8.0 `main` as `v0.7.0`.
- [ ] Publish release assets only after sign-off.

Related: #4, #5, #6, and draft PR #10.
