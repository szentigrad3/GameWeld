# GameWeld — Batch 15: live Linux identity gate before DeckCheatz v2 handoff

**30 October 2026 · Development only · No verified WeMod attachment**

## Confirmed live result

Dying Light: The Beast (Steam App ID `3008130`) passed the Batch 14 three-sample liveness check with Linux PID `58638`, process start ticks `3641164`, exact prefix identity, and same-prefix wineserver evidence. No Steam configuration changes, game prefix edits, or signals were issued.

This result does **not** establish a Windows process ID, DeckCheatz monitor authentication, game attachment, or trainer cleanup.

## Batch 15 implementation

The existing `scripts/gameweld-wand-v2-session.py` now performs a live identity check **before invoking the external DeckCheatz v2 monitor**:

1. Verify the selected App ID, existing prefix, existing game executable, local monitor endpoint format, monitor-token format, and upstream source path.
2. Acquire a *fresh* Linux PID/start-time anchor from the Batch 13/14 game identity auditor.
3. Repeat three identity samples at 400 ms intervals. The same Linux PID/start ticks, unique candidate, exact App ID/prefix and same-prefix wineserver must still match.
4. Block the upstream monitor invocation if any read or identity check fails, or if the game exits/restarts while sampling.
5. If the guard succeeds, keep the existing upstream monitor handoff behavior. **The guard never launches Wine or WeMod itself.**
6. Treat a cleanup success reported by an upstream process as `upstream_trainer_cleanup_reported=true` rather than `trainer_cleanup_verified=true`, since GameWeld has not independently checked trainer-owned process termination.

The handoff remains intentionally restricted to the local loopback monitor endpoint with a session token. Endpoint/token format alone is not authentication proof; the upstream implementation must independently authenticate and verify Win32 process ownership.

## CI and regression coverage

- Batch 13 live-context safety suite: **14 tests**
- Batch 14 anchored liveness suite: **24 tests**
- Batch 15 monitor-handoff safety suite: **14 tests**
- Combined: **52 automated tests**, all three suites plus compile checks passed on Ubuntu/Python 3.13 in GitHub Actions run [40983509404](https://github.com/szentigrad3/GameWeld/actions/runs/40983509404).
- No live WeMod game attachment was tested by GitHub Actions.

## Test in a separate CachyOS checkout

```bash
cd /mnt/other/github/GameWeld-PR18-test
git pull --ff-only
python3 scripts/test-gameweld-wand-v2-live-context.py -v
python3 scripts/test-gameweld-wand-v2-live-anchor.py -v
python3 scripts/test-gameweld-wand-v2-session-gate.py -v
```

Run the **read-only** game identity check while Dying Light is open via Steam:

```bash
python3 scripts/gameweld-wand-v2-live-anchor.py \
  --appid 3008130 \
  --compatdata /mnt/games/Steam/steamapps/compatdata/3008130 \
  --game-exe "/full/path/to/DyingLightGame_TheBeast_x64_rwdi.exe" \
  --samples 3 --interval-ms 400
```

No Steam launch options, prefix modifications, trainer process starts, or cleanup signals are required by these tests.

## Next release gates

1. Obtain/access the actual local `deckcheatz-rewrite-v2-gameweld-batch12_3` code needed for Wine/Win32 PID and monitor integration; repository code only contains the current integration contract.
2. Verify a Windows PID and current session runtime identity from an independent Wine-side proof source in the exact prefix, with a revalidation immediately before attachment.
3. Authenticate a GameWeld-owned monitor endpoint and confirm WeMod starts and attaches to that *Windows* process.
4. Track trainer-owned PID identities, verify cleanup after game exit, and prove Steam/the game/other Wine sessions remain untouched.
5. Run live CachyOS/Proton tests. Keep this PR draft until those pass.

The Batch 15 Linux gate is a safety improvement and **does not fix WeMod attachment end to end**.
