# GameWeld PC2 — Steam-managed WeMod acceptance gate

**Status:** PRIVATE INTEGRATION TEST — not approval for a public one-click WeMod claim.

## Intended behaviour

GameWeld must ask the *installed Steam client* to launch the selected Windows game. Steam alone selects Proton and handles Steam Runtime, Steam API, DRM and the game's saved Launch Options. The game launch must not use a second direct Proton game instance, and must not require GameWeld Steam Bridge. Once the selected game has a matching running Steam AppID and exact Proton prefix, GameWeld may **preview** starting its already installed WeMod client in that same prefix. A separate explicit approval is mandatory for that live client start.

Steam executes any Launch Options already configured by the user; GameWeld does not edit or silently bypass them.

## Local private acceptance procedure (CachyOS)

1. Close GameWeld, update the dedicated PR #13 test checkout, and run: `bash scripts/pc2-fast-feedback.sh`.
2. Start the source GUI via `bash scripts/run-pc2-source-frontend.sh --enable-steam-wemod-test`.
3. Select an installed Steam Windows title (e.g. AppID 3008130). Click **Play via Steam + WeMod (private test)**. Accept the Steam launch confirmation.
4. Verify Steam starts the game with the version of Proton chosen by Steam itself; GameWeld must not request a direct game process, edit Steam Launch Options, or install a Bridge.
5. A successful process association must trigger the **read-only WeMod live handoff preview**. Verify the report identifies the matching exact AppID, game prefix and unique runtime; a candidate process is not evidence of attachment.
6. If a prepared WeMod client and game runtime are verified, the GUI may show a **second** confirmation before the experimental WeMod-only handoff. Back up the prefix separately before consenting. The helper can modify the game's live prefix.
7. A successful helper spawn means only that a WeMod client process was requested. **Actual trainer attachment and a reversible in-game effect** require separate human verification.
8. When a game is already active, the Play button must not dispatch a duplicate launch. Instead use **Check / start WeMod in running Steam game**.
9. Test wrong AppID, missing prefix, unreadable process, multiple Proton contexts, already-running WeMod, and nonexistent client: these should be blocked or reported clearly.

## Release blockers

- Automated Fast Feedback, GTK startup smoke, Rust tests, experimental backend and full release CI must pass on the **same** final commit.
- Ubuntu release artifact baseline and native CachyOS frontend must pass.
- A real Steam game launch must be observed by the tester.
- The WeMod client must launch in the exact selected game prefix, and trainer attachment/in-game effect must be manually established before any public claim.
- Prefix backups, rollback paths, launcher source/provenance and security review must be completed before enabling experimental prefix-changing operations by default.

**Do not automatically enable the experimental WeMod handoff for public release until these gates pass.**
