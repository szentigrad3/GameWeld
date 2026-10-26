# GameWeld — prepared WeMod setup for all game libraries

**Scope:** Steam, Heroic, Lutris, and future supported Windows-game providers.
**Status:** Architecture, read-only catalog and archive audit, plus opt-in isolated cache staging are implemented. Per-game application, account migration, rollback, and verified trainer activation **not yet done**.
Cache-only download code and consent-driven GUI wiring exist; the discovery-only GUI deliberately disables downloads.

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

## Download-only cache stage (development GUI; not a game installation)

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
- After **Find prepared WeMod setup**, the GUI shows a bounded list of
  candidate ZIP releases. A matching archive is **not** considered a
  verified Proton/runtime fit or a working game trainer.
- **No release is auto-selected.** Players must choose an archive themselves.
  The normal UI deliberately avoids pages of low-level catalog diagnostics.
- A separate **Download selected prepared setup (cache only)** action is
  implemented for explicitly opted-in private functional builds and shows
  a release-specific approval dialog. The usual **discovery-only GUI keeps
  download and cancel disabled**.
- In a functional test download, the helper sends bounded progress records
  to the GUI for bytes transferred and ZIP checking. **Cancel cache download**
  sends SIGINT to its managed subprocess; Python attempts to remove the
  incomplete .part file. A forced termination cannot be guaranteed to clean
  temporary files on every filesystem.
- On successful verification, GameWeld stores the content-addressed ZIP in
  the separate cache only, never in a game's prefix. It does not extract
  it, configure WeMod, or claim working trainer support.

**Before treating this as general user-ready functionality:** independently
review publisher integrity and release applicability; validate live progress,
cancel, restart and interrupted-download recovery on CachyOS, and complete a
separately approved, reversible per-game install and trainer-attachment flow.

## Isolated staged extraction (private development only)

The opt-in helper `scripts/gameweld-prepared-prefix-stage.py` reads only a
content-addressed ZIP already in `.../gameweld/prepared-wemod/downloads/<sha256>.zip`.
Its `--approve-stage` gate, SHA-256 filename check, archive member inspection and CRC
verification run before staging begins. It refuses symlinked cache locations,
preexisting destination directories and inadequate free space.

If approved, the helper extracts into a newly created 0700 temporary directory
inside the dedicated cache `staging/` subtree, writes a per-file SHA-256
manifest, and renames the directory to its final content-addressed staging
location. A failed or cancelled staging callback removes the incomplete
temporary tree. Extracted files are ordinary private data files; no executable
bit is inherited from the ZIP. Tests use synthetic archives and preserve
fixture Steam, Heroic and Lutris prefixes.

This is **not a prepared WeMod installer**. Staging does **not** inspect or
modify an individual game's working prefix; it does not identify a trusted
publisher, transfer WeMod account data, attach a trainer, or enable Play.
Staging is not exposed as an ordinary ready-to-use GUI installation action.
Third-party archive contents remain untrusted and MUST NOT be executed merely
because they staged successfully.

Manual, private development test against a previously verified cached ZIP:

```bash
python3 scripts/gameweld-prepared-prefix-stage.py \
  --archive "$HOME/.cache/gameweld/prepared-wemod/downloads/<actual-sha256>.zip" \
  --approve-stage
```

No game's prefix should ever be used as `--cache-root`.

## Independent, opt-in game-prefix backup foundation (development)

`scripts/gameweld-prefix-backup.py` provides a default **read-only inventory preview** for one
explicit Steam, Heroic, or Lutris game prefix, with the chosen provider/game ID.
It counts regular files, directory entries, symlinks and estimated space.
No game configuration or content is read by the preview beyond names and metadata.

An explicit `--approve-backup --acknowledge-game-closed` additionally saves a
standalone prefix TAR + SHA-256 file manifest under the user's private
`$XDG_STATE_HOME/gameweld/prefix-backups` directory. The archive preserves
link *entries* without following them outside the prefix, refuses special
files, checks available disk space, verifies changed-file metadata during
copy, and removes partial temporary backups on failure. Archive and manifest
are kept separately from the disposable prepared-prefix cache. A successful
backup never changes or replaces game data.

**Limitations:** a user acknowledgement does not verify that a game or
Wine/Proton process has actually stopped. A file-level copy is not an
atomic snapshot; consistency checks detect common concurrent changes but
cannot guarantee consistent live data. The backup tool does **not** contain
a restore or transactional apply implementation; it must not make the
GUI's **Install** or **Play with WeMod** controls available. Existing account
content is private and not uploaded, but names and metadata may appear in
the local backup manifest.

The only current safe development test is the synthetic-prefix unit suite:

```bash
python3 -m unittest discover -s scripts -p 'test_gameweld_prefix_backup.py' -v
```

The same helper supports `--verify-backup-dir /absolute/private/backup-directory`
to independently reopen the saved TAR, confirm the archive digest and declared
length, validate member names/types/counts, and read every archived regular
file to compare its SHA-256 with the private manifest. It performs **no
restoration or game-prefix writes**. Archive/manifest integrity proves only
internal consistency, not the absolute trustworthiness of that backup.

Do not use backups of real game profiles to claim rollback support until
restore verification and a provider-specific idle/lock check are complete.

## Isolated restore rehearsal — development test only

`scripts/gameweld-prefix-restore-rehearsal.py` uses the independently verified backup TAR
and SHA-256 file manifest to build a **disposable test copy** inside the
private `gameweld/prefix-backups/restore-rehearsals` directory. It first verifies
the backup, validates all TAR paths and member types, refuses symlinked
staging destinations and non-directory path ancestors, then writes files
itself (never uses tarfile.extractall), preserving archived Wine symlinks
as non-followed link entries. A second stream verification checks the
copied files and unchanged source TAR before committing the test copy.
Failures/cancellation remove incomplete rehearsal directories.

The restore rehearsal has **no destination override**; it cannot restore
into the selected game prefix. It neither activates a trainer nor
guarantees atomicity of a live restore. It never executes extracted content.
The presence of a successful test copy must not enable installation
or the public Play with WeMod action.

Run only the synthetic regression suite in this phase:

```bash
python3 -m unittest discover -s scripts -p 'test_gameweld_prefix_restore_rehearsal.py' -v
```

Blockers before live apply/rollback: provider-aware process idle detection,
verified complete user-data scope, trusted prepared archive source and
runtime compatibility, a journaled transaction with tested rollback,
and in-game trainer attachment validation on Steam, Heroic and Lutris.

## Synthetic transactional apply/rollback (development rehearsal, NOT game install)

`scripts/gameweld-transaction-rehearsal.py` adds a journaled copy/apply/rollback
rehearsal **only** for a specially marked `gameweld/transaction-fixtures` directory.
It refuses Steam, Heroic, Lutris and Proton prefix paths, symlinked input,
shared hard links, oversized samples, insufficient space and missing approval.
It cannot accept a downloaded third-party prefix archive or a real game
path as the destination.

The rehearsal keeps an independent original directory. It copies a synthetic
patch into a separate candidate, checks hashes, journals the proposed
transition, moves the original aside, and atomically renames the candidate
into its synthetic fixture. An explicit rollback restores that retained
original, with fault-injection coverage before and after the rename.
A synthetic failure during an ordinary exception triggers automatic rollback.
Actual power-loss recovery and full filesystem durability are NOT guaranteed;
the journal remains for investigating interrupted test transactions.

This demonstrates parts of transaction orchestration, **not** safe
application to a real game. The regular GameWeld UI must not display
"installed" or enable Play based on this test.

Run the disposable-only automated tests:

```bash
python3 -m unittest discover -s scripts -p 'test_gameweld_transaction_rehearsal.py' -v
```

Before real installation: provider-aware runtime idle checks; durable journal
recovery and full rollback validation; secure file/registry/account migration;
real-world compatible and trusted source metadata; live in-game trainer tests.

## Provider-aware Wine/Proton process preflight (read-only)

`scripts/gameweld-prefix-runtime-preflight.py` examines same-user Linux
procfs process environments in memory for an exact per-game WINEPREFIX
or Steam compat-data/app-ID match. It reports one of:
`ACTIVE` (matched), `UNKNOWN` (inspection incomplete), or
`IDLE_CANDIDATE` (no match found). Output omits environment values,
tokens, account data and raw process command lines. It never kills
processes or alters a provider configuration.

**All states keep `installer_authorized=false`. A negative procfs
check is NOT proof the game is closed: sandbox namespaces, shared-prefix
processes, privilege boundaries and different provider launch semantics
can defeat this simple probe. The production installer still requires a
trusted provider-specific process close/lock check before any game writes.

Synthetic offline fixtures and refusal tests are wired into CI.

## Native game-connection check now includes process activity

The existing **Check game WeMod connection** GUI action invokes
`gameweld-wemod-native-route.py` and now incorporates the read-only
`gameweld-prefix-runtime-preflight.py` result. It displays an
`ACTIVE` warning, `UNKNOWN` uncertainty, or a
`NO MATCH FOUND` advisory while keeping
`Install permission: BLOCKED` and trainer attachment unverified.

For Steam the process check prefers the exact AppID-specific compatdata/pfx
location from the chosen install library, rather than an unrelated prefix hint.
For Heroic and Lutris it checks the selected game's configured prefix. If
the helper is unavailable, process inspection fails, or the prefix is missing,
the check fails closed as `UNKNOWN`.

Development AppDir helper scripts are symlinks back to the checkout; native
route resolves its own source directory before loading the peer inspector.
This works with the existing source runner and does not require Steam Bridge.
Synthetic process/GUI-summary regression tests run in CI.

The normal Settings screen now requests a **six-line concise summary**
(`--format summary`) rather than filling the card with all diagnostic details.
The detailed read-only report (`--format text`) and machine-readable JSON
remain available for development/test evidence. The summary always says
installation is BLOCKED and no changes were made.

This is **read-only status integration**, NOT an installer, lock, trusted
trainer compatibility check, or permission to change a live prefix.


## Faster development without skipping release gates

The draft PR has **two testing speeds**:

- **Fast Feedback** runs on each draft PR update, without installing GTK
  packages or building the private AppDir. It runs the existing ten PC2
  offline safety suites (including Steam/Heroic/Lutris fixtures, prefix
  backups, restore rehearsal, symlink and transaction checks). Superseded
  runs are cancelled. Local one-command equivalent:
  `bash scripts/pc2-fast-feedback.sh`.
- **Full CI** and the **PC2 Ubuntu Baseline** (native GTK/Go build, private
  packaging audit, distribution checks) run when the PR is marked **Ready
  for review** or when explicitly started from GitHub Actions. Superseded
  full runs are also cancelled. They still run for main/release pushes where
  configured.

**Before any candidate release:** run both full workflows on the exact
candidate commit and require passing results, then complete actual
CachyOS, Steam, Heroic and Lutris gameplay tests. A passing Fast Feedback
workflow is never equivalent to a native build, tested game integration
or trainer attachment. Never treat a skipped draft-PR native workflow as
proof of success. Restore the PR to draft if subsequent unreviewed changes
invalidate its candidate status.

This optimizes the *iteration loop*, not the safety requirements.

## Live-process candidate check — no game mutations

The existing **Check game WeMod connection** button now also attempts to
identify a `WeMod.exe` process in the **same selected Wine/Proton prefix**.
The read-only process inspector compares exact WINEPREFIX or Steam compat-data
plus AppID environment evidence before inspecting the process name. It reads
only a bounded Linux procfs command line / process name in memory and publishes
only a candidate count and safe status, never command lines, environment
values, account tokens, or game paths.

The normal seven-line GUI summary reports:

- **Process visible in selected prefix** — candidate found; trainer attachment
  and in-game activation are **NOT VERIFIED**
- **Not seen in selected prefix** — selected-prefix processes were inspected
  but no WeMod candidate found; this is not proof of absence
- **Not verified** — no matching process or insufficient procfs access;
  do not assume a runner has stopped or a trainer is missing

Practical next live test: first launch one game **normally from Steam,
Heroic, or Lutris**. If WeMod is already running in that game's existing
environment, select the game in GameWeld and click **Check game WeMod
connection**. Compare the result with the visible game and WeMod windows.
No GameWeld Steam Bridge, prefix replacement or new launch hook is involved.

This process-name heuristic is **not trustworthy attachment verification**.
A candidate process can be unrelated, misnamed or running without an active
trainer. Real in-game feature activation and a secure, provider-native handoff
remain release blockers. The public Install/Play setup is still blocked.

## Running game detected, but WeMod is unverified

When the selected game reports **ACTIVE** and WeMod is **UNVERIFIED**,
GameWeld has confirmed at least one matching Wine/Proton process, but
cannot yet establish whether a WeMod.exe process is in the same prefix.
This is not an install failure and should not be reported as one.

The process-name inspection now independently checks Linux cmdline and
comm: a missing or unreadable cmdline no longer masks an accessible
WeMod.exe comm name. Inspected and unreadable name counts provide a
more specific, private explanation, such as "1/1 process names unreadable".
No raw command line, account information or prefix path is printed.

For an existing working game+WeMod session, start the game and WeMod
using their already configured working methods, select the same game
and click **Check game WeMod connection** again. The status can then
report a WeMod **process candidate**, not trainer attachment.
If WeMod is not already running, the check cannot start it.
It does not yet provide a no-Bridge launcher/attacher.

Do not interpret a process candidate as an injected, connected or
functional trainer. No game prefixes, launch options, Steam settings or
WeMod installations are modified by this check.

## Next live milestone after process-candidate detection

When a game-prefix process and WeMod.exe candidate are both detected,
GameWeld's concise status tells the user to select that game inside WeMod,
start its trainer, and observe one harmless feature working **in-game**.
This is a manual validation prompt, not automated trainer attachment.

**Important:** prefix activity proves only that one or more processes
reference the selected Proton/Wine prefix. It does **not** independently
identify the game's Windows executable. A WeMod.exe candidate can be present
without the game itself running or without successful trainer injection.
The UI therefore says "a process uses this prefix" and continues to show
"Trainer: NOT VERIFIED" and "Install: BLOCKED".

A read-only status must never turn into a real setup install, launch-option
change, or game execution based solely on a process name. A real observed
trainer effect and separately proven native launch/attachment remain required
for the first public WeMod integration milestone.

## DeckCheatz tested .NET prefix import — first integration

The original DeckCheatz 1.x launcher reuses a GE-Proton-compatible, tested
prefix in place of rebuilding `dotnet48` with winetricks. Its exported ZIP
intentionally excludes the `version` file; the Proton version is supplied by
the release asset filename, e.g. `GE-Proton10.1.zip` (PfxVer10.1).
GameWeld now retains the GitHub asset/tag metadata through cache → stage,
matches GE-Proton major/minor to the selected game and rejects mismatches.
The .wemod_installer marker and staged hashes are checked. The
selected release is carried through **download → isolated stage → per-game
read-only review**. Asset filenames and source metadata do not prove that
DeckCheatz is a trusted publisher or that the resulting trainer will attach.

**Normal source GUI workflow (development):**

1. In Settings → WeMod & DeckCheatz choose **Find prepared WeMod setup**.
2. Manually select an appropriate release; press **Download selected prepared
   setup (cache only)** and approve the download. Nothing is installed.
3. Select **Step 2 — Stage downloaded .NET prefix (isolated)** and
   confirm. It stages **the exact release selected in the dropdown** using
   cached SHA-256/asset metadata. Other cached Proton releases are ignored,
   not chosen by accident. If the selected release was not downloaded,
   GameWeld tells the user to finish Step 1 first. Games are unchanged.
4. With a selected Steam game, select the same prepared release and choose
   **Step 3 — Review prepared .NET prefix (read-only)**. GameWeld matches
   the exact selected staged archive and compares the game's current
   compatdata/version to the release GE-Proton major/minor. It refuses a
   missing, inconsistent or ambiguous stage rather than guessing.

The developer-only CLI can then create a merged copy, independently of the
game, using `gameweld-prepared-prefix-import.py --single-staged --appid <APPID> --install-dir <GAME_INSTALL_DIRECTORY> --prepare-isolated-copy --approve-isolated-copy`.
It preserves the selected game's original registry/saves and fingerprints the
game files before/after copying. In the **candidate only**, template registry
files and .NET files may override collisions. It cannot be run as a normal
public install command.

`gameweld-prepared-prefix-activate.py` is a separate, **PRIVATE and
DISABLED-BY-DEFAULT** experimental transaction prototype. It requires an
explicit environment opt-in and three command-line approvals, first makes
a same-filesystem copy, keeps the entire original compatdata directory as
a backup, and can restore the backup. It also provides recovery for an
interrupted directory swap. These mechanics currently have only synthetic
regression tests. **Do not run it on personal game prefixes until the actual
prepared archive, Proton version, backup, crash recovery and game launch have
been verified together.** No Install/Play button invokes this prototype.

A prepared prefix solves preconfigured dependencies; it does NOT guarantee
that WeMod can connect to every game without the DeckCheatz launch wrapper.
The Astrometica success was with `%command%` and
`WINEDLLOVERRIDES=version=n,b`, which does not prove an
option-free attachment. This is a separate remaining end-to-end test.

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
