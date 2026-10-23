# GameWeld 0.7.0 — PC1 distribution candidate

**Status: local test candidate only; do not publish, tag, or call it stable.**

A separately identified 0.7.0 PC1 build was produced from the pinned original 0.7.0 Stable AppImage. This reduces two specific redistribution risks without altering the existing tested stable binary.

## Changes

- Removed the embedded converted native trainer `resonance-native-trainer.exe` and the associated conversion source/build helper from PC1 source.
- Removed bundled Resonance reference art, game ID `2713000` hero/cover files, and legacy Wand reference logo images from the PC1 AppImage.
- Disabled native converted-table profile registration in the GUI and replaced three profile shell launchers with fail-closed messages.
- Retained normal Steam, Heroic, Lutris and local trainer launcher functionality and their existing helpers; **14/14** copied stable release helpers match source.
- The About page and desktop metadata identify **0.7.0-pc1**, not the original 0.7.0 Stable.

## Local verification

- **57/57** offline tests pass, including four candidate-specific distribution checks.
- GCC syntax check, GTK binary compile, and AppImage extraction pass.
- **94** regular AppImage files; prohibited game art and converted executable absent.
- Native converted-profile launchers explicitly reject calls with exit **4**, avoiding an unexpected attempt to run an absent helper.
- Headless GTK smoke test ran for 11 seconds until controlled timeout, with zero stderr output.

### Artifact checksums

| Artifact | SHA256 |
|---|---|
| Input original `GameWeld-0.7.0-x86_64.AppImage` | `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a` |
| Local `GameWeld-0.7.0-pc1-x86_64.AppImage` | `1a5ea219923bbd94fcb7f4d83edb66cdcdaf97a81c2d73d16c85f10d83c219da` |
| Local PC1 source ZIP | `f96a51f98dac3213d081f9a291fb3a97d0e7542b6840a783919c5d26689b85cf` |

**This PR records validation evidence only.** The candidate executable/source bundle are not uploaded to the GitHub repository or GitHub Releases, and this documentation commit does not itself include the PC1 source changes. The existing `main` branch continues to be 0.8.0 Dev 1.

## Release blockers remain

- [ ] Document provenance and permitted distribution of retained GameWeld logos/icons.
- [ ] Review inherited compiled runtime, helper sources, transitive dependencies, and required third-party license notices. Repacking a pinned 0.7.0 AppImage is *not* a source-complete build.
- [ ] Repeat live Steam, Heroic and Lutris launch/trainer tests on PC1; prior test evidence applies only to the original 0.7.0 Stable/RC11.
- [ ] Put an approved matching 0.7.0 source snapshot on a separate GitHub branch and point `v0.7.0` to its actual commit, not 0.8.0 `main`.
- [ ] Only after the above sign-offs, prepare a release binary, checksum manifest, provenance notices, and a verified downloadable asset.

Linked tracking: #4 (release), #5 (redistribution audit), #6 (source-complete build). Reference audit: `docs/RELEASE-AUDIT-0.7.0.md`.
