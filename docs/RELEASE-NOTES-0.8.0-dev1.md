# GameWeld 0.8.0 Dev 1 — Official Publisher File Review

This is an early 0.8 development build on the 0.7.0 stable codebase. It is **not** a stable release.

## Added

- In **Trainer Library → Find Updates**, the **Review official files…** button inspects FLiNG's exact game-specific publisher page and shows its published trainer filenames, dates and unchanged download links.
- Strict host, page-title, filename, row-anchor and URL-pattern checks reject cross-game and arbitrary external links.
- Results are copyable but remain **untrusted informational evidence**. No executable download, staging, assignment or automatic install is permitted by this new action.
- An asynchronous checker discards late results after the selected game's update-context epoch changes.
- Matching CLI command: `python3 scripts/gameweld-trainer-updates.py publisher-files --game 'CONTROL Resonant' --page 'https://flingtrainer.com/trainer/control-resonant-trainer/' --plain`

## Not yet implemented

- Publisher-authenticated, cross-provider official release feeds or verified direct-download signatures.
- Automated FLiNG downloads/updates from browser-only links. SHA256 must come from a separately trusted release catalog, not a hash computed from unverified bytes.
- Additional managed-provider download APIs for Aurora, Cheat Evolution, HexTrainer and Wand.

## Existing functionality retained

Steam/Steam shortcuts, Heroic, Lutris, Wand, assigned trainer launch and UI, 0.7.0 discovery, signed catalog, checksum staging/rollback and read-only upgrade preflight remain intact. Use Dev 1 only for testing; preserve the 0.7.0 stable AppImage as fallback.

## Test

1. Select a game that already has an exact cached FLiNG publisher page, such as Assassin's Creed Mirage, and select FLiNG as publisher.
2. Choose **Review official files…**. The dialog should show published file/date/download-link evidence, without downloading anything.
3. Switch to a different game during a check; the old dialog must not open for the new selected game.
4. Confirm **Stage approved trainer** stays disabled unless an independently approved matching catalog entry exists.
5. Check Steam/Heroic/Lutris launch paths as in stable, and keep your stable AppImage available.
