# GameWeld — Proton game identity correlation (Batch 13)

Date: 2026-10-30. Development branch; **not a WeMod attachment release**.

## Evidence and diagnosis

Dying Light: The Beast, Steam App ID `3008130`:

- Five launch-chain processes reference a verified full install path for `DyingLightGame_TheBeast_x64_rwdi.exe`.
- The actual Wine game candidate is Linux PID `58638`, comm `DyingLightGame_`, `exe=wine64-preloader`. Its argv has the executable basename but no full path.
- A prefix-associated wineserver appears as PID `58556`.
- The uploaded redacted report did **not** prove exact prefix equality between those processes, a Win32 PID, or WeMod attachment.
- Historical PIDs are diagnostic examples, never stored as a live launch authorization.

## Implemented in scripts/gameweld-wand-v2-live-context.py

1. Requires an existing, canonical `compatdata/<appid>/pfx` and selected game .exe; never creates a prefix.
2. Requires consistent, exact Steam AppID markers and **both** canonical `STEAM_COMPAT_DATA_PATH` and `WINEPREFIX` on the candidate.
3. Separates full-path provenance in Steam wrappers from executable identity of the running game.
4. Requires the Wine preloader executable, exact game executable argv basename, Linux `comm` (including 15-byte truncation) and Wine/Proton maps on the *same* game PID.
5. Captures the Linux `/proc/<pid>/stat` start tick and checks it twice to detect immediate PID replacement. Any actual attach must revalidate it again.
6. Rejects multiple eligible game processes instead of choosing an arbitrary one.
7. Reports matching wineserver PIDs as diagnostic evidence; it does not execute their binaries.
8. Explicitly marks `exact_runtime_verified=false`, `game_process_verified=false`, `trainer_attachment_verified=false`, and `monitor_attached=false`.

Neither Steam launch options nor Steam settings, game prefix files, or system processes are modified.

## Run tests

```bash
python3 scripts/test-gameweld-wand-v2-live-context.py -v
```

## Read-only live check (requires a running Steam game)

```bash
python3 scripts/gameweld-wand-v2-live-context.py \
  --appid 3008130 \
  --compatdata /mnt/games/Steam/steamapps/compatdata/3008130 \
  --game-exe "/absolute/path/to/DyingLightGame_TheBeast_x64_rwdi.exe"
```

If Steam uses a different library for compatdata, use its actual path. **Do not put anything into Steam launch options.**

## Still needed before a working trainer release

- Import the corrected Linux-process candidate identity into the newer local DeckCheatz rewrite process detector (not included in this repository snapshot).
- Confirm a Windows process ID and exact Wine runtime/loader/server identity in the intended prefix; Linux PID is not Win32 PID.
- Bind the verified GameWeld-owned session monitor to the selected Steam session without a launcher override, and confirm that WeMod attaches.
- Track only verified trainer-owned processes for cleanup and verify termination without killing the game, Steam, other trainers, or wineserver.
- Test on the user's actual CachyOS Steam/Proton environment. Offline tests cannot prove live attachment.

The existing `gameweld-wand-v2-session.py` bridge remains unchanged. This batch improves the read-only auditor; it must not be described as fixing the trainer attachment end to end.
