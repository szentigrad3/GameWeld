# DeckCheatz rewrite/v2 integration (draft, batch 2)

GameWeld remains the sole user-facing GUI and launch/session owner. DeckCheatz's AGPL-licensed rewrite and Rust gRPC monitor are separate upstream components. This GameWeld branch supplies only MIT-licensed headless adapters. **Nothing in this draft changes Steam Launch Options or registered compatibility tools.**

Upstream design: https://github.com/DeckCheatz/wemod-launcher/tree/rewrite/v2 and https://github.com/DeckCheatz/wemod-launcher/issues/307.

GameWeld adapter stages:
1. `scripts/gameweld-wand-v2-preflight.py` checks a selected app's existing prefix and user-selected WeMod executable, without starting processes.
2. `scripts/gameweld-wand-v2-session.py` accepts --appid, --compatdata, --client, --game-exe, --monitor-endpoint and --rewrite-root **only when GameWeld has already created an authenticated monitor inside its selected live game Proton environment**. It passes these to the upstream headless entrypoint, never constructs another Proton command and never invokes a shell.
3. Neither script claims a WeMod trainer is attached just because processes are seen.

**Known blockers before enablement:** The standalone upstream monitor Rust source in the separate Batch 2 artifact is not yet compiled or field-tested. Steam's exact launch command/arguments and session startup by GameWeld are still incomplete; the GameWeld GTK Play with WeMod callback is not yet switched to this adapter. The published DeckCheatz Rust monitor is not yet its specified gRPC implementation. This is a development interface only, not a functioning WeMod launch integration.

Do not merge this draft until the upstream gRPC monitor builds, prefix/data safety review is complete, Steam’s original runtime command and game arguments are preserved, and the WeMod GUI, login, trainer attachment and cleanup pass live testing. Preserve AGPL/MIT attribution and distribution boundaries.

## Batch 5 safety checks (2026-10-29)

The development monitor's positive native gRPC smoke has been confirmed by its tester, including trainer cleanup. The new Batch 5 source adds stricter Rust process ownership and event sequencing, plus local gRPC failure tests. These changes are **not an installed GameWeld feature** and Rust Batch 5 compilation has not yet been verified.

The GameWeld bridge rejects out-of-range loopback ports and boolean game exit codes, requires both processes to start and requires explicit trainer cleanup evidence. This does **not** prove the WeMod UI rendered or that a trainer attached.

The GTK Play with WeMod callback must not be switched to this experimental bridge until GameWeld supplies a real monitor in the correct Steam Proton/Wine session, preserves the game's actual launch command, and verifies game identity and cleanup. Do not change Steam Launch Options or compatibility selection.
