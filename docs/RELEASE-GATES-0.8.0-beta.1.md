# GameWeld 0.8.0-beta.1 — Release Gates

**Status: NOT APPROVED FOR PUBLICATION.** This document tracks a limited Linux x86_64 Steam-first beta. It does not certify the application, third-party binaries, or trademarks.

## Scope

- Include: GTK GameWeld frontend, discovery, Steam Bridge workflow, user-authorized WeMod/DeckCheatz setup paths verified on supported games.
- Defer: claims of comprehensive Heroic/Lutris WeMod support, unverified native trainers, 1.0 stability, and unsupported game coverage.
- Do not silently modify game prefixes, download unverified executables, or change Steam Launch Options without explicit user intent.

## Technical gates

- [ ] Run `bash scripts/pc2-rc1-preflight.sh` on the intended release commit; retain the generated report.
- [ ] Verify `python3 -m unittest discover -s scripts -p 'test_gameweld_steam_compat_bridge.py' -q`.
- [ ] Confirm GUI main page no longer exposes development diagnostics; keep useful diagnostics in a separate troubleshooting view.
- [ ] Confirm initial window size is reasonable across 1080p, 1440p and 4K, is not full-screen by default, and survives close/reopen.
- [ ] Test at least two additional games besides Astrometica; record game ID, Proton version, launch result, trainer result and teardown.
- [ ] Test missing dependencies, blocked/offline download, corrupted download and cancelled setup; preserve existing user files.
- [ ] Build a source-traceable standalone AppImage (not just the source runner or an inherited repackage).
- [ ] On a clean Linux account/system, test AppImage start, library discovery, restart, game launching and error reporting.
- [ ] Record release commit, build inputs, binary hash and build logs.

## Mandatory publication approval

- [ ] Resolve branding, ownership and redistribution of inherited executable/runtime content.
- [ ] Inventory bundled third-party binaries with upstream links, versions, hashes, licenses and required attribution/source offers.
- [ ] Review downloadable WeMod/DeckCheatz/Wand components separately: link to upstream is not permission to rebundle.
- [ ] Publish only binaries with reviewed provenance, applicable notices, checksum and installation instructions.
- [ ] Get explicit maintainer approval before tagging, creating a GitHub release or publishing binary artifacts.

Related earlier review: [issue #4](https://github.com/szentigrad3/GameWeld/issues/4), [issue #5](https://github.com/szentigrad3/GameWeld/issues/5). Previous 0.7.0 PC1 documentation is historical, not approval for this beta.

## Release decision

**No-go** until *every* mandatory publication item is cleared and the core technical gates pass. A successful offline preflight alone is insufficient.

Suggested future tag: `v0.8.0-beta.1` (not created). The test matrix and approved release asset must reference the exact tagged commit.
