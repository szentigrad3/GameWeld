# DeckCheatz rewrite/v2 integration (draft)

GameWeld is the only end-user GUI and game/session owner. DeckCheatz's AGPL-licensed rewrite remains a separate component. This MIT-licensed adapter invokes its headless preflight using an argument array, not a shell.

Upstream references:
- https://github.com/DeckCheatz/wemod-launcher/tree/rewrite/v2
- https://github.com/orgs/DeckCheatz/projects/3/
- https://github.com/DeckCheatz/wemod-launcher/issues/301
- https://github.com/DeckCheatz/wemod-launcher/issues/307
- https://github.com/DeckCheatz/trainer-monitor

This PR does NOT complete the rewrite or activate game launches. The published v2 rewrite still lacks a functioning gRPC launcher and monitor. The separate monitor repository is not yet the specified gRPC implementation.

## Internal contract

GameWeld can invoke the script with --appid APPID --compatdata COMPATDATA --client /path/to/WeMod.exe --rewrite-root /path/to/rewrite/v2, and optionally --client-sha256 EXPECTED_HASH.

A single JSON object returns state gameweld_wand_v2_preflight_passed or blocked. A nonzero exit code means fail closed. The adapter never starts or stops the trainer/game, modifies Steam launch options or registers a compatibility tool.

## Required before GUI enablement

1. Implement the upstream monitor gRPC service and matching launcher client.
2. Complete verified app acquisition, prefix migration/backups and shared login-data synchronization.
3. Wire GameWeld's EXISTING Play with WeMod action to a functioning session controller using the game's Steam-supplied Proton/runtime, not a new GUI.
4. Test trainer attachment, login, process lifetime, cleanup and normal game startup across Steam, Heroic and Lutris.
5. Review AGPL/MIT license boundaries before distribution.

Keep this PR draft until the upstream monitor and GameWeld session integration are operational.
