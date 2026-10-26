# GameWeld — prepared WeMod setup for all game libraries

**Scope:** Steam, Heroic, Lutris, and future supported Windows-game providers.
**Status:** Architecture + read-only catalog and archive audit implemented. Game integration, account migration, and verified trainer activation **not yet done**.
Cache-only download code exists but is not enabled in the GUI.

## User-visible goal

1. Open GameWeld and select a game from any supported library.
2. If the game's WeMod setup is missing or incompatible, choose **Set Up WeMod**.
3. GameWeld finds the verified release-compatible prepared template, downloads it
   once to a managed cache (with progress), stages and checks it, and offers a
   clear confirmation before touching any existing game environment.
4. Preserve the game's existing saves, configuration and account data, back up
   the complete affected content, and provide one-click rollback.
5. Start the title through the **original platform** with the game's existing
   runner and launch context; launch WeMod in the same appropriate Proton/Wine
   runtime namespace so the trainer can identify the running game.
6. Confirm whether WeMod and the trainer actually function, rather than
   assuming that a process starting means the trainer is attached.

Advanced Proton, .NET, cache, and Winetricks diagnostics stay behind an
advanced-expander, not in the ordinary setup flow.

## Important architecture distinction

**Shared cache, game-specific runtime** — *not* one shared game Wine prefix.

The prepared WeMod prefix archive is acquired once per compatible version and
safely cached by GameWeld. Each game has its own Steam Proton/Heroic/Lutris
prefix, sandbox, or runner configuration. A template can be *used to prepare*
the game-specific WeMod components only after compatibility is established.
Never replace the live game prefix wholesale. Never copy all of another game's
registry or DLLs, and never set a game's Proton version as a side effect.

Existing WeMod account data may be offered for reuse **only with the user's
explicit choice**; avoid unprompted symlinks or credential copying. Preserve
existing account data and permissions, and never send it to the release catalog.

A prepared prefix is not proof that every game has a supported WeMod trainer.
Missing trainers and unsupported game processes must be shown as distinct states.

## No mandatory GameWeld Steam Bridge

The default GameWeld WeMod flow must **not** require registering or selecting
the custom GameWeld Steam Bridge. Steam Bridge is an **optional legacy fallback**
for users with a previously tested working configuration (for example,
Astrometica), not a new installation requirement.

The existing DeckCheatz/wemod-launcher 1.x approach uses a Steam launch-options
command prefix (the \`%command%\` wrapper). Its successor DeckCheatz uses a
Steam compatibility-tool slot. Both can start the trainer in the game's own
Proton environment, but neither establishes a universal "no platform
integration needed" capability. GameWeld must detect the actual integration
before enabling **Play with WeMod**.

**Implementation status:** GameWeld's primary PC2 button is now
**Check WeMod setup**, and the provider-native route assessor is read-only
for Steam/Heroic/Lutris. The previous Bridge actions are available under the
collapsed **Legacy Steam Bridge — optional compatibility fallback** section
and live legacy launch is disabled in ordinary discovery-only builds. Native
runtime attachment and transaction-safe prepared-prefix installation still
need to be implemented and verified.


## Provider adapters

| Provider | Preparation context | Launch requirement |
| --- | --- | --- |
| Steam | Validate the exact AppID and compatibility context | Launch through Steam using a verified DeckCheatz-style command prefix, native compat tool or equivalent hook; don't require GameWeld Steam Bridge or overwrite existing settings |
| Heroic | Validate game/runner/prefix against Heroic provider preflight | Launch via Heroic's supported path; preserve its per-game runner and prefix |
| Lutris | Validate selected game and configured Wine prefix/runner | Launch via Lutris's registered game path; preserve existing runner |
| Other supported Windows games | Use an explicit provider adapter | Do not guess executable locations, prefixes or attach semantics |

Global actions such as **Find prepared WeMod setup** and **Check prepared ZIP**
must work without a selected game or AppID. Per-game installation and launch
actions must require an unambiguous game and provider context.

## Download-only cache stage (development code; not yet connected to GUI)

The helper \`scripts/gameweld-prepared-prefix-cache.py\` adds an opt-in
**cache-only** download path for the user-approved release ZIP. It is disabled
unless \`--approve-cache-download\` is supplied. This is deliberately distinct
from the future **Install** and **Play** actions.

- Only an exact GitHub release ZIP URL under the configured
  DeckCheatz/BuiltPrefixes-dev project is accepted; the downloaded response
  must remain on GitHub's HTTPS asset hosts.
- The declared asset size is bounded and checked against actual bytes, with
  a free-space gate. Downloads stream to a temporary file under a separate
  GameWeld cache directory.
- Before committing to the cache, the helper validates ZIP member paths,
  symlinks, decompression ratios and CRC through the shared archive inspector.
  Any failed/aborted download discards its temporary file.
- The resulting cache ZIP is content-addressed by SHA-256, but labeled
  **publisher authenticity unverified**, **game compatibility unverified**
  and **not installed**.
- No archive is extracted, no WeMod account data is read, no Wine/Proton
  runtime is invoked, and no selected game's live prefix is modified.
- The normal GUI currently exposes only **Find prepared WeMod setup**, a
  release-metadata lookup. No cache download/install button is enabled yet.

**Before surfacing a download button:** verify the exact selected release
against authoritative metadata, show source/size/compatibility cautions,
require a click-through user confirmation, handle cancellation/progress, and
ensure the setup cannot be confused with a finished game installation.

## Required transactional installer (not implemented)

- Trusted upstream release origin and integrity verification. Metadata filename
  matches do not establish trust, and a user-entered SHA-256 alone does not
  authenticate a publisher.
- Download to a separate cache with size quotas, progress, checksums and a
  distinct staging directory.
- ZIP preflight before extraction: reject absolute/traversal paths, symlinks and
  special files, duplicate/case-colliding names, encryption, excessive
  decompression ratios, oversized entries, and CRC failures.
- Extract to a disposable, never-to-live-prefix staging directory. Do not
  follow symlinks during extraction. Inspect actual prefix layout, runtime
  files and potential account content before proposing any apply.
- Verify the selected game is closed and no Proton/Wine process owns its prefix.
- Create a complete independent backup of all files that would be changed,
  including saves/account settings where relevant. Verify backup readability
  and record a manifest before allowing Apply.
- Show **exact changes** and require explicit per-game approval.
- Apply with a transaction journal and cancellation/rollback that also works
  on interruption, insufficient space, partial extraction, or failed launch.
- Verify actual CLR startup and in-game trainer interaction separately from
  GameWeld/Steam launch success.
- Never auto-publish or bundle proprietary prepared prefix content without
  reviewing third-party licensing and redistribution terms.

## Current implemented pieces

- Read-only GitHub release catalog lookup, global across providers.
- Release-label comparison with compatibility explicitly **unverified**.
- Offline read-only prepared-prefix archive inspection.
- No game-prefix writes/downloads/runtimes from catalog or audit.
- Regression tests in CI for catalog and unsafe archive fixtures.

## Acceptance criteria for first release

- No developer-only terminal commands for typical player installation.
- Steam, Heroic and Lutris test games each complete safe setup and launch,
  including account preservation and cancellation.
- A mismatch or unsupported trainer clearly declines instead of claiming
  success.
- Rollback restores an independently backed-up game prefix and account data.
- Dying Light (Steam AppID 3008130) and a second known-good Steam game are both
  tested; one successful title must not be used as proof for all titles.
- No release until those specific provider workflows pass live testing.
