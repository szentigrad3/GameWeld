# GameWeld 0.7.0 — Stable Release Notes

GameWeld 0.7.0 is the stable promotion of the RC11 codebase after the user's field confirmation of eight game/trainer launch scenarios and a clean seven-assignment preflight. Functionality is frozen for this release.

## Included

- Clean three-view Trainer Library: **My Trainers**, **Find Updates**, **Advanced**.
- Steam and Steam-shortcut, Heroic Epic/GOG, Lutris/UMU/GE-Proton session ownership and trainer handoff.
- Existing automatic trainer discovery, publisher-page evidence and game-version compatibility review.
- Signed-catalog verification (Ed25519) for independently verified, locally pinned provider keys, explicit-approved SHA256-pinned staging, integrity inspection and rollback.
- Read-only stability preflight, grouped missing targets and per-assignment real-launch checklist.
- Selection-safe actions that reject stale or cross-game update evidence.

## User field validation (reported by user)

- Steam shortcut: CONTROL Resonant + trainer; Onimusha + trainer.
- Heroic: Vampyr + trainer; Control (GOG) + trainer.
- Assassin's Creed Mirage + trainer; Assassin's Creed Shadows + trainer.
- HexTrainer manager/game context; one Lutris game/trainer live session.
- RC11 preflight: seven configured trainer assignments, zero missing targets, zero integrity warnings.

## Existing limitations

- Publisher pages and filename-version labels are informational, not authenticated download feeds.
- No official signed release catalogs or unattended auto-updates are bundled for FLiNG, HexTrainer, Cheat Evolution, Aurora or Wand.
- A package integrity hash alone does not establish publisher identity or binary safety.
- Field checks were performed by the user on their system; this package's smoke tests do not independently repeat those live game launches.

## Upgrade

Use the stable AppImage without deleting existing `~/.config/gameweld` or `~/.local/state/gameweld` files. Keep a copy of the previous AppImage for rollback. To review configuration, open **Trainer Library → Advanced → Export stability and launcher checklist**. The preflight does not modify assignments.
