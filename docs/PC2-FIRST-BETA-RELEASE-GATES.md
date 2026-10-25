# GameWeld PC2 — first GitHub beta release gates

Development checklist. **This document does not authorize publication.**

**Proposed version:** `0.8.0-beta.1` (subject to maintainer approval and
version alignment with the existing 0.7.0 PC1 release-review work).

## Implemented and locally field-tested

- [x] Steam, Heroic and Lutris installed-game discovery in the PC2 GTK frontend
- [x] Working Steam Bridge compatibility-tool launch of Astrometica under
  Proton Experimental / Steam Linux Runtime 4
- [x] Wand/WeMod window rendering and functioning trainer for Astrometica,
  confirmed by the maintainer
- [x] Main Overview/Library Play with WeMod action routed through Steam Bridge
- [x] Per-game Bridge status, manual setup, enable/disable, read-only
  compatibility selection and launcher update/rollback preparation
- [x] Recent Games tile list and compact Overview; offline tests and CI builds

## Open gates before *any* public binary

- [ ] **License/provenance sign-off:** complete GitHub
  [issue #5](https://github.com/szentigrad3/GameWeld/issues/5) and
  `docs/PUBLICATION-REVIEW.md`. Existing PC1's inherited AppImage runtime
  binaries and branding do **not** have blanket redistribution clearance.
- [ ] **Release artifact:** create a Linux x86_64 AppImage from a documented,
  appropriately redistributable build process. The PC2 GitHub workflow
  currently compiles a GTK binary and stages a development AppDir; that
  is not yet an approved, published AppImage.
- [ ] **Dependency notices:** audit included executables, GTK/Wine/Proton
  runtime provenance, their licenses, source offers and third-party attribution.
  Do not package proprietary trainer binaries.
- [ ] **End-to-end package tests:** verify extraction, launch, Steam Bridge
  registration, helper availability, config preservation, rollback, clean user
  profile and reproducible checksum on the *actual* release candidate.
- [ ] **Representative field tests:** another single-player Steam/Proton title
  besides Astrometica; a fresh Bridge configuration on a separate
  Steam-library location; verify a missing WeMod package fails safely.
- [ ] **Release process:** choose version/tag, create release notes and SHA256,
  publish a draft candidate, check the downloadable artifact and
  its checksum on Linux x86_64, then approve public publication.

## Beta scope constraints

- Steam Bridge / WeMod functionality is **only proven with Astrometica**
  on one Linux/CachyOS test system. Do not claim universal game support.
- No silent changes to Steam Compatibility settings, Launch Options or game
  Wine prefixes. Preserve the game-only first-run test and explicit consent.
- No bypassing multiplayer anti-cheat or packaging unauthorized game trainers.
- First-time Steam Compatibility tool selection remains a manual Steam UI step.
- Provider-authenticated auto-download workflows and full Linux/Windows
  parity are **future** development milestones, not first-beta promises.

## Source-of-truth tracking

- [Publish stable asset issue #4](https://github.com/szentigrad3/GameWeld/issues/4)
- [License and redistribution issue #5](https://github.com/szentigrad3/GameWeld/issues/5)
- `README-PUBLICATION-CANDIDATE.md` and `docs/RELEASING.md`
- `.github/workflows/pc2-backend-ci.yml`

The current successful PC2 source CI does not by itself satisfy the
publication, binary provenance or live gameplay acceptance gates.
