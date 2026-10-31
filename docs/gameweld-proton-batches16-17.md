# GameWeld Batches 16–17 — bounded monitor handoff and automatic Steam discovery

Development branch `fix/wand-v2-proton-game-identity-batch13-20261030`.
Draft PR #18. This is **not** a working WeMod attachment release.

## Starting point: real-world evidence (App ID 3008130)

The user reported `linux_runtime_anchor_stable`, `samples_completed=3`, same Linux game PID and start ticks across all three checks, and a same-prefix wineserver. Their report explicitly retained `win32_pid_verified=false`, `monitor_attached=false`, `trainer_attachment_verified=false`, `trainer_cleanup_verified=false`, and no Steam setting changes.

### Batch 16: long-session and protocol hardening

- The GameWeld-to-DeckCheatz v2 bridge no longer calls `subprocess.run(..., capture_output=True, timeout=86400)`, which could accumulate unbounded text output in memory during a 24-hour game session.
- New `scripts/gameweld-wand-v2-bounded-monitor.py` drains the direct child process's stdout to a **bounded 256 KiB buffer** in a reader thread. Stderr goes to null to avoid unintentionally collecting credentials and excessive logs.
- On timeout, only the direct Python subprocess started by the bridge is terminated, then killed if necessary. **No process group, game, Steam process, Wine server, or arbitrary trainer PID is signalled.** Orphan/descendant trainer cleanup remains a separate gate.
- Reject malformed UTF-8 output, excessive output, child spawn failures, inherited stdout pipes, and timeouts.
- Reject an upstream App ID that contradicts the selected game and any upstream claim to have launched the Steam game directly rather than observed the existing Steam-managed process.
- Retain the earlier live PID/prefix safety gate. A returned upstream cleanup boolean is still a **claim**, not GameWeld-independent proof.
- New offline regression suites exercise actual harmless Python child processes. They do **not** start games, Wine, WeMod or Steam.

### Batch 17: one read-only auto-discovery command

`scripts/gameweld-wand-v2-aio.py` combines installed game detection and repeated live process checks:

1. Use the existing Steam VDF parser to enumerate canonical library folders.
2. Require the specific App ID's existing `appmanifest_<appid>.acf` and installation directory; reject traversing or malformed `installdir`.
3. Find existing `compatdata/<appid>/pfx` only; never create or alter it.
4. Inspect the user's live /proc process environments for consistent App ID and prefix identity.
5. Accept full executable paths only when they are **verified existing files under the known installed game directory**.
6. Run the earlier exact Wine process correlation, requiring a unique matching game process rather than using a wrapper process.
7. Pin the current Linux PID/start ticks and sample it three times. Fail closed on missing, ambiguous, replaced or inconsistent evidence.
8. Return a compact JSON report without exposing full executable or prefix paths, Steam credentials, child environment variables, or session tokens.

There is no cached PID authorization. Every run discovers the current game and prefix anew. The AIO is **read only**, with Windows PID and WeMod attachment flags always false.

## Commands on CachyOS

Check out/update the PR in a separate directory; do not switch your main working branch:

```bash
cd /mnt/other/github/GameWeld-PR18-test
git pull --ff-only
python3 scripts/test-gameweld-wand-v2-live-context.py -v
python3 scripts/test-gameweld-wand-v2-live-anchor.py -v
python3 scripts/test-gameweld-wand-v2-session-gate.py -v
python3 scripts/test-gameweld-wand-v2-bounded-monitor.py -v
python3 scripts/test-gameweld-wand-v2-aio.py -v
```

With Dying Light: The Beast already running normally in Steam:

```bash
cd /mnt/other/github/GameWeld-PR18-test
python3 scripts/gameweld-wand-v2-aio.py --appid 3008130 --steam-root /mnt/games/Steam
```

Expected on a compatible live session: `state=linux_runtime_anchor_stable`, `samples_completed=3`, `linux_process_identity_stable=true`, `unique_linux_game_candidate=true`. No need to manually find the .exe or supply the old PID.

The correct Steam root must be the root containing `steamapps/libraryfolders.vdf` or the installed game manifest. If the game is not running or the Steam library is different, failure is expected and safe.

## Verification and release gates

- Batch 13: 14 game-process tests
- Batch 14: 24 pinned-liveness tests
- Batch 15: 19 session-handoff tests (expanded from 14)
- Batch 16: 15 bounded-child tests
- Batch 17: 16 Steam AIO tests
- Total: **88 tests**, requiring the latest GitHub workflow run to pass before calling them CI verified.

Still required before any release:

- Win32 PID and exact Proton/Wine server/monitor runtime identity proved by the **actual Windows monitor**.
- A trusted, authenticated monitor lifecycle in the same running game session.
- WeMod window/login and real trainer attachment confirmed.
- Independently verified cleanup of GameWeld-owned trainer processes without touching Steam or the game's Wine server.
- Live end-to-end CachyOS test.
- The current local `deckcheatz-rewrite-v2-gameweld-batch12_3` source is not in the connected repository; the new code must be adapted to that exact current implementation before enabling production GUI integration.

No Steam launch options, compatibility settings or user profiles are modified by these repository-side changes.
