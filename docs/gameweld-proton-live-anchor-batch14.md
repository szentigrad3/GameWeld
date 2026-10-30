# GameWeld Batch 14 — pinned Proton PID liveness

Development-only read-only check, following Batch 13 live evidence for Dying Light: The Beast (AppID `3008130`).

## Confirmed user-provided live evidence

- One Linux Wine game candidate: PID `58638`, start ticks `3641164`.
- `exact_prefix_identity_crosschecked=true`.
- `game_process_candidate_pids=[58638]`.
- Matching wineserver list included PID `58556`.
- No PID reuse rejections or Steam configuration writes.
- `exact_runtime_verified=false`, `game_process_verified=false`, `monitor_attached=false` and `trainer_attachment_verified=false`.

PIDs are ephemeral. Do not reuse them as launch authorization after a restart.

## Implementation

`scripts/gameweld-wand-v2-live-anchor.py` samples the existing read-only context auditor 1–30 times, at 0–2000 ms intervals, without changing processes or files. Each sample must maintain exact AppID, the single same Wine game candidate, same PID and Linux start time, exact prefix identity, and a same-prefix wineserver. Any disappearance, second candidate, PID replacement, malformed evidence or unexpected claim of Win32/trainer success fails closed.

The result `linux_runtime_anchor_stable` is explicitly **not** proof of a Windows PID, monitor attachment, shared wineserver IPC, or WeMod injection. All trainer and Win32 proof flags remain false.

## Offline tests

```bash
python3 scripts/test-gameweld-wand-v2-live-context.py -v
python3 scripts/test-gameweld-wand-v2-live-anchor.py -v
```

14 original reference tests + 19 Batch 14 liveness tests were run on the standalone local reference copy. The corresponding GitHub test files are committed to the branch; run them in the branch checkout to verify the exact GitHub snapshot.

## Live read-only command

Start the game normally in Steam; use paths and fresh PID/ticks returned by the first script.

```bash
python3 scripts/gameweld-wand-v2-live-context.py \
  --appid 3008130 \
  --compatdata /mnt/games/Steam/steamapps/compatdata/3008130 \
  --game-exe "/absolute/path/to/DyingLightGame_TheBeast_x64_rwdi.exe"

python3 scripts/gameweld-wand-v2-live-anchor.py \
  --appid 3008130 \
  --compatdata /mnt/games/Steam/steamapps/compatdata/3008130 \
  --game-exe "/absolute/path/to/DyingLightGame_TheBeast_x64_rwdi.exe" \
  --pid 58638 --start-ticks 3641164 --samples 3 --interval-ms 400
```

The PID and ticks above are **illustrative** from the uploaded session and may be stale. Never use them if a new game launch occurred.

## Still blocked

1. Confirm Win32 process ID and exact Wine runtime/IPC ownership for the same prefix, rather than assuming a Linux PID is a Win32 PID.
2. Integrate with the newer local DeckCheatz rewrite implementation (not in the accessible GitHub snapshot).
3. Verify actual WeMod launch, trainer attachment, and bounded GameWeld-owned trainer cleanup on live CachyOS.
4. Confirm ordinary Steam game startup is unaffected.

No Steam launch options, Steam configuration, game prefix, or processes are modified by this batch.
