# GameWeld Batches 19–20 — private session ownership and trainer residue visibility

Development branch: \`fix/wand-v2-proton-game-identity-batch13-20261030\`. Draft PR #18.
**Not a working WeMod attachment release.**

## Grounded live baseline

The tester's Batch 17 AIO result for Dying Light: The Beast / App ID \`3008130\` confirmed one installed game manifest, one existing Proton prefix, one full executable under the installed Steam game directory and one unique running Wine game process (Linux PID \`185951\`, birth ticks \`12945298\`). Three consecutive inspections confirmed stability and a same-prefix wineserver.

This is **Linux-side identity evidence only**. It does not verify a Windows PID, monitor authentication, WeMod attachment or ownership-scoped trainer cleanup. Previous PIDs are not reused by these scripts.

## Batch 19: single owned handoff per game

Added \`scripts/gameweld-wand-v2-session-lock.py\` with a private nonblocking advisory \`flock\`.

- Locks are keyed by Steam App ID, under the current user's \`XDG_RUNTIME_DIR\`, or a private per-UID temporary fallback if unavailable.
- The directory must be user-owned and inaccessible to other users. Lock files must be regular files owned by the user with mode \`0600\`.
- \`O_NOFOLLOW\`, canonical inode validation and private directory checks reject unsafe symlinks or path substitution.
- Duplicate GameWeld v2 handoffs for **the same App ID** fail immediately with \`duplicate_gameweld_session\`. Different App IDs are independent.
- The bridge holds the lock **through the entire live Linux PID verification and upstream monitor child lifecycle** and releases it in \`finally\` after success or failure.
- The lock file is **not unlinked** on release. A stale file without an active advisory lock does not block startup and is never interpreted as a PID to terminate.
- No Steam settings, launch options, compatibility tool, game prefix, Wine server or game process are modified.

**Important:** This lock only coordinates callers using GameWeld's v2 bridge. It does not prevent external WeMod processes or other unrelated programs from running.

## Batch 20: read-only same-prefix provider residue audit

Added \`scripts/gameweld-wand-v2-residue-audit.py\` and post-session audit integration.

- Inspects up to 20,000 readable \`/proc\` entries from the current user.
- Correlates the selected existing Wine prefix, Wine preloader, mapped Wine libraries, matching \`WeMod.exe\` or \`Wand.exe\` executable argument, matching task \`comm\`, and stable Linux PID/start tick.
- Allows missing Steam AppID marker in trainer processes; if present, a conflicting Steam AppID is rejected.
- Reports \`same_prefix_provider_candidate_count\`, with redacted per-process metadata: Linux PID, process birth ticks, provider executable basename.
- The v2 session bridge includes **advisory** \`provider_residue_audit_state\` and candidate count in its completion report.
- A positive count **does not establish ownership** or confirm a leak. A zero count **does not establish cleanup**. Every report keeps \`provider_process_ownership_verified=false\` and \`trainer_cleanup_verified=false\`.
- Auditing **never sends signals, calls a shell, installs packages, writes Steam configuration, or modifies the game prefix**.

This makes it easier to understand situations where WeMod seems to leave processes behind without arbitrarily killing Steam/Wine processes.

## Tests

The existing CI workflow now executes eight synthetic/unit suites:

| Batch | Cases |
|---|---:|
| 13: Linux game-process identity | 14 |
| 14: PID anchor stability | 24 |
| 15: v2 bridge session guard and post-session status | 26 |
| 16: bounded monitor subprocess | 15 |
| 17: Steam AIO discovery | 16 |
| 18: Windows observer evidence (untrusted claims only) | 21 |
| 19: private per-AppID session lock | 17 |
| 20: read-only process residue audit | 17 |
| **Total** | **150** |

All test fixtures are synthetic; the subprocess suite only spawns harmless Python processes, never Wine, games or WeMod. Before reporting 150/150 passing, verify the new workflow result on the current commit.

## CachyOS commands

Update the **separate test checkout** only:

\`\`\`bash
cd /mnt/other/github/GameWeld-PR18-test
git pull --ff-only
python3 scripts/test-gameweld-wand-v2-session-gate.py -v
python3 scripts/test-gameweld-wand-v2-session-lock.py -v
python3 scripts/test-gameweld-wand-v2-residue-audit.py -v
\`\`\`

The Linux game AIO remains read-only while Dying Light is running normally from Steam:

\`\`\`bash
python3 scripts/gameweld-wand-v2-aio.py --appid 3008130 --steam-root /mnt/games/Steam
\`\`\`

If the game's compatdata is in \`/mnt/games/Steam/steamapps/compatdata/3008130\`, run the standalone residue audit:

\`\`\`bash
python3 scripts/gameweld-wand-v2-residue-audit.py \
  --appid 3008130 \
  --compatdata /mnt/games/Steam/steamapps/compatdata/3008130
\`\`\`

Use the *actual* compatdata path if Steam places it elsewhere. A nonzero residue count is merely a same-prefix candidate list, **not an authorization to kill any of those PIDs**.

## Non-negotiable blockers for WeMod release

1. Integrate the actual newer local \`deckcheatz-rewrite-v2-gameweld-batch12_3\` Windows/Proton source (not available in the connected GameWeld repository).
2. Prove Win32 game identity with a trusted Windows monitor handle inside the **same existing Steam-managed Wine session**. JSON and Linux PID are not sufficient.
3. Authenticate the monitor, prove real WeMod GUI/login/trainer attachment and preserve original Steam launch behavior.
4. Track GameWeld-owned monitor/trainer process identities at launch, protect against PID reuse, and **independently verify cleanup** after normal exit, game crash, and monitor failure.
5. Live acceptance on the tester's CachyOS / Steam / Proton stack. Keep the PR draft and the production GUI feature gate disabled until verified.

**Status:** Private per-game handoff ownership and advisory residue visibility are implementation improvements, not an end-to-end trainer launch.
