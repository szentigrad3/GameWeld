# GameWeld 0.7.0 — Release artifact audit

**Status: release sign-off pending.** This is a factual inventory of the locally tested AppImage, not a statement that every component is cleared for redistribution. Do not publish a tagged binary release until the outstanding questions are resolved.

## Artifact checked

- File: `GameWeld-0.7.0-x86_64.AppImage`
- SHA256: `8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a`
- Embedded filesystem: 109 regular files, representing 80 unique content hashes.
- Compiled executables: three equal GTK launcher ELF copies (`gameweld`, `gameforge`, `wand-native`), one Go backend ELF, and two Windows PE executables.
- The verified binary launches locally, and the field-tested RC11 functionality passed reported Steam, Heroic and Lutris handoffs. This does not establish redistribution rights or source completeness.

## Release blockers requiring review

### Bundled reference artwork

The runtime includes `resonance-hero-reference.png`, `resonance-cover-reference.png`, artwork for game ID `2713000`, and `wand-logo-reference.png`. Identical image bytes occur across `usr/share/gameweld`, `usr/share/gameforge`, and `usr/share/wand-native`.

The extracted `assets/games/README.md` describes user/Steam-local artwork fallbacks, but does not state redistribution rights for the bundled reference images. The public source repository intentionally omits this reference artwork. Obtain explicit permission/license evidence or build and retest a package that omits it.

Also confirm ownership/licensing of GameWeld's separate icon and brand logo.

### Embedded native trainer executable

The AppImage embeds `usr/libexec/resonance-native-trainer.exe` (SHA256 `2a9b1e72ba668598809112157a9d5fd64c20c5c2091d85720f03de34591bd252`).

The matching repository file `tools/resonance-native-trainer.c` explicitly describes a **direct conversion of the core behavior in Paul44's Resonance v1.1 Cheat Engine table**. That attribution does not by itself establish permission to redistribute derivative implementation code or binaries. Confirm applicable permission/license and any required credit, or remove the affected component and validate the resulting release. The project README should not be interpreted as claiming that *no trainer executable at all* is bundled.

### Compiled helper and backend provenance

The runtime includes `usr/libexec/gameweld-elevate.exe` (SHA256 `36d93b5597aec71dc54ea2d15647a0b6b0a84747ce7c3d2d1a373d59652513ef`) and `usr/libexec/wand-native-backend`, plus the GTK executable. Source files for parts of this functionality are in the repository, but the current build repacks a pinned 0.7.0 AppImage; independent reconstruction and complete dependency notices have **not** been demonstrated.

No `crypt32.dll` was found inside this exact 0.7.0 AppImage. `THIRD-PARTY.md` discusses optional/other builds that may supply modified Wine crypt32 binaries; do not confuse those descriptions with the inventory of this artifact.

## Source and tag correctness

The current `main` tree already contains **0.8.0 Dev 1**. Do **not** create a `v0.7.0` tag at the current `main` commit and describe it as the 0.7.0 source: that would produce incorrect automatically generated GitHub source archives.

Prepare a dedicated, reviewed **0.7.0 stable source snapshot/commit**, using the tested `gameweld-0.7.0-source.zip` as the technical reference while excluding historical test/build outputs and reviewing retained assets. Verify that the stable GTK source and embedded helper versions correspond to the stable AppImage. Tag that stable source commit `v0.7.0` only after this correspondence and licensing sign-off.

The `Build development AppImage` GitHub Actions job intentionally depends on `v0.7.0` and will show `release not found` until the approved release asset exists. Do not change the workflow to download unpinned files from arbitrary locations to bypass that gate.

## Release sign-off

- [ ] Reference artwork: rights established or excluded and retested
- [ ] Native trainer conversion: permission/license established or excluded and retested
- [ ] Branding, helper/backend binaries, and dependency provenance checked
- [ ] Corresponding stable source snapshot committed and validated
- [ ] `v0.7.0` tag created from the correct stable source commit
- [ ] Release binary hash checked against `docs/BASELINE-SHA256.txt`
- [ ] AppImage plus SHA256 and notes published separately from Git source history
- [ ] Downloaded GitHub asset hash and startup verified

Related: #4, #5, #6.
