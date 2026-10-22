# Publication review — maintainer sign-off

This source tree is prepared for GitHub publication, but public redistribution requires a final review by the project owner.

- [ ] Confirm the MIT license is appropriate for every GameWeld-owned source file. The existing Cargo manifest already declares MIT; this repository adds the corresponding `LICENSE`.
- [ ] Check provenance of GameWeld logos and icons. Game-specific reference art and prebuilt trainer `.exe` files were excluded from this source tree.
- [ ] Review `THIRD-PARTY.md` for LGPL Wine compatibility binaries or other redistributed runtime dependencies, and retain legally required notices/source offers in binary releases.
- [ ] Verify the release asset is the tested 0.7.0 AppImage with SHA256 `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`.
- [ ] Inspect the source with `./scripts/publication-audit.py` and review any strings containing machine-specific test paths.
- [ ] Confirm that no login tokens, credentials, personal game libraries, Wine prefixes, local trainer executables or proprietary source assets are committed.
- [ ] Confirm GitHub repository owner and release URL, then perform `main` push and initial release manually.
- [ ] Turn on protected branches, CI status checks and private vulnerability reporting after the repository is created.

The 0.8.0 Dev 1 build requires a pinned 0.7.0 AppImage runtime baseline. Completing a full-source reproducible build remains a roadmap task.
