# GameWeld 0.7.0 PC1 — recovered artifact provenance audit

**Audit date:** 23 October 2026  
**Scope:** the **previously produced** PC1 AppImage (not an arbitrary new PC1 repack or a source-complete build).  
**Decision:** **BLOCK PUBLIC REDISTRIBUTION** pending owner/third-party provenance review. This report is an inventory, not a legal opinion or a rights sign-off.

## Inputs verified by SHA256

| Recovered artifact | SHA256 |
| --- | --- |
| `GameWeld-0.7.0-pc1-x86_64.AppImage` | `1a5ea219923bbd94fcb7f4d83edb66cdcdaf97a81c2d73d16c85f10d83c219da` |
| `GameWeld-0.7.0-x86_64.AppImage` (stable build input, **not approved for public binary distribution**) | `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a` |
| `GameWeld-0.7.0-PC1-source.zip` (prior source snapshot) | `f96a51f98dac3213d081f9a291fb3a97d0e7542b6840a783919c5d26689b85cf` |

The recovered PC1 candidate was extracted for file inspection. **94 regular files, 0 symlinks, 5 ELF/PE executable paths** were observed. The current branch includes the PR #11 *build-time* audit for future outputs; checks on the recovered artifact do **not** transfer automatically to a differently hashed repack.

## Compiled component inventory

| AppDir path | File identity | Source/provenance conclusion |
| --- | --- | --- |
| `usr/bin/gameweld`, `usr/bin/gameforge`, `usr/bin/wand-native` | Three byte-identical x86_64 GTK ELF executables; SHA256 `d6633c092458ec0231ea7909ecebf707e6bdf96be5635bab641018a4bec6c10a` | Native GTK C source exists in `crates/wand-ui/appimage-gtk3/gameweld-native-040.c`; local source compilation has passed. No independent byte-for-byte reproduction of these historical binaries asserted |
| `usr/libexec/wand-native-backend` | Linux x86_64 Go 1.23.2 ELF; SHA256 `ecf76f3cad46713a1a43901c0bad67a6e50960f175ae341fd7337cfd4897b70a`; Go build metadata: `path command-line-arguments`, `CGO_ENABLED=1` | **BLOCKER:** matching Go backend source/build recipe is absent from the current PC1 GitHub tree and the inspected original stable and PC1 source ZIPs. The Rust `wandd` in this repository speaks a different Unix-socket protocol and is **not** a proven replacement for the HTTP backend |
| `usr/libexec/gameweld-elevate.exe` | Windows x86_64 PE Go 1.23.2; SHA256 `36d93b5597aec71dc54ea2d15647a0b6b0a84747ce7c3d2d1a373d59652513ef` | Source exists at `cmd/gameweld-elevate/main.go`. The separate historical source-correspondence review (`docs/PC1-ELEVATION-HELPER-REBUILD.md` on `main`) reports near-identical recompilation with differences in build ID/header; not byte-identical or legal clearance |

No `.dll` files were present in this inspected PC1 AppDir. The generic `THIRD-PARTY.md` describes optional/downloaded dependencies and possible payloads, **not necessarily components shipped in this particular artifact**.

## Packaged scripts and artwork

- **41/41** `usr/libexec` shell/Python helper scripts were byte-identical to `scripts/` in the SHA256-verified archived **PC1 source ZIP**. This compares the recovered artifact to that historical snapshot; it is **not** a claim that all helpers are byte-identical to the latest GitHub branch or that the executable backend is source-complete.
- The known excluded converted `resonance-native-trainer.exe`, named game-reference PNG/JPG assets, and bundled DLLs were absent. A historic documentation file `usr/share/doc/wand-native/NATIVE-CT-RESONANCE-0.1.43.md` **remains**; review whether it should be omitted as part of release cleanup. Its presence alone is not evidence of a bundled trainer binary.
- `usr/share/gameweld/assets/gameweld-app-icon.png`: SHA256 `2f6bbc18d777c18049524eb01327edbe219fde2df9eabb5f87f40dc6c9e70a40`.
- `usr/share/gameweld/assets/gameweld-brand-logo.png`: SHA256 `ca7fd3c3ac5283af3cbfdf1c0fd4bf7c2081fe841ec8b3d9b0cfebf8f9ffb1c8`.
- Both branding PNG files are byte-identical to the historical PC1 source snapshot. Their PNG metadata contains no embedded attribution. **Being committed into source does not establish copyright ownership or redistribution permission.** The desktop icon also occurs as `gameweld.png` and `.DirIcon`.

## Field-testing status and scope

- Local/offline checks on the branch: 66/66 source regression tests passed (maintainer-provided test output).
- Post-merge branch CI: successful at commit `ca7cfda49100187e9f07cb0cd2cb15b3e483f46e` ([workflow run](https://github.com/szentigrad3/GameWeld/actions/runs/39881103466)).
- Maintainer reports that the recovered PC1 AppImage **launches** on CachyOS and later reports that the requested Steam, Heroic and Lutris game/trainer tests **work**. No per-launcher logs, game IDs or session traces were supplied; this is *maintainer-reported field validation*, not independent telemetry.
- That field result applies only to the **recovered PC1 checksum above**, not another repacked binary.

## Release blockers and acceptance

- [ ] Owner confirms the creation/ownership/license and redistribution rights for **each** GameWeld logo/icon and any third-party branding or assets.
- [ ] Locate matching `wand-native-backend` Go source, dependency provenance, and a documented build procedure; or replace it with a newly implemented source-available equivalent and retest the full app. Document any inherited binary exception explicitly and assess whether publishing that binary is permissible.
- [ ] Confirm any redistribution obligations for all compiled runtime components, including the elevation helper, corresponding source and notices; do not infer a license from the mere presence of `LICENSE`.
- [ ] Determine whether to remove residual historic converted-table docs and retest the resulting hash if the packaged payload changes.
- [ ] Record version/tag/source-to-binary correspondence for the **specific** artifact selected for release; do not silently apply the original stable `v0.7.0` tag to the PC1 candidate.
- [ ] Update `docs/PUBLICATION-REVIEW.md`, `THIRD-PARTY.md`, release notes and checksums after approval; obtain owner sign-off.
- [ ] Only then publish and checksum-verify a public GitHub Release; see #4, #5, #6.

**No tag, release, binary upload, merger into `main`, or approval is created by this report.**
