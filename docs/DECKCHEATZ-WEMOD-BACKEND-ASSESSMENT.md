# GameWeld PC2 — DeckCheatz WeMod Launcher backend assessment

Reviewed on 2026-10-24. Research/design only; **no runtime integration was installed**, no game or trainer was started, and no Proton files were modified.

## Source verification

- **Upstream:** <https://github.com/DeckCheatz/wemod-launcher>, main branch, 1.x README identifies release **1.544**. The upstream team says 1.x receives bug fixes only. It is an existing Linux/Steam WeMod launcher, not a version of GameWeld.
- **Usage:** documented Steam launch option is `/absolute/path/to/wemod-launcher/wemod %command%`; the tool parses Steam's Proton/UMU invocation, prepares the game's Wine prefix, and creates a combined trainer/game command. It supports downloading or copying preconfigured Wine prefixes and warns that WeMod's automatic game discovery may fail (manually choose the game).
- **v2 branch:** <https://github.com/DeckCheatz/wemod-launcher/tree/rewrite/v2>, pinned reference at review commit `3d12ecf98ca466a204f0a2e2537e46c50aae5527` (2026-10-11). The README explicitly says the rewrite is unfinished. The tree has `src/wand_launcher/entrypoint.py` and *no implementations* for modules it imports (settings, logger, UI, updater, prefix manager, monitor). It is not a usable launcher.
- **v2 architecture document:** <https://github.com/DeckCheatz/wemod-launcher/blob/rewrite/v2/docs/ARCHITECTURE.md>. Design intentions include separate settings/logger/GUI, versioned prefix migrations, shared Wand login data, XDG paths, disposable vs downloaded prefixes, a separate monitor binary, and per-phase troubleshooting. These are proposals, not tested v2 functionality.
- **v2 goals:** <https://github.com/DeckCheatz/wemod-launcher/blob/rewrite/v2/docs/GOALS.md>. Describes GUI, `--no-prompt`, bundled AppImage, prefix metadata, structured logs. No actual 2.x end-to-end runnable implementation is present on the reviewed branch.
- **Project tracking:** <https://github.com/orgs/DeckCheatz/projects/3/>. The board itself could not be retrieved through the available public GitHub repository interface, so **no completeness percentages or project-board status claims are made**. Open issues include upstream `#301` (v2 entrypoint), `#307` (monitor protocol draft), `#289` (deterministic Steam argument parsing), `#292` (prefix consistency), and `#287` (noninteractive mode).
- **License:** DeckCheatz launcher is `AGPL-3.0`; GameWeld currently has a separate MIT license. **Do not paste, copy, vendor, or relicense AGPL source into GameWeld's MIT implementation** without reviewing full redistribution and combined-work obligations. An optional separately obtained executable/backend may be evaluated as a separate program, with proper notices, terms and source availability where required. Legal compatibility should be reviewed before release.

## Recommendation for PC2

Offer an **optional DeckCheatz 1.x launcher provider** alongside the current managed Wand / WeMod Enhancer workflow, rather than making the unfinished v2 rewrite a dependency or replacing existing functionality. Keep GameWeld's GTK GUI and launch-state ownership.

**Proposed phases (none automatically activated by these notes):**

1. **Read-only detection and prerequisites:** find an explicitly selected existing DeckCheatz 1.x checkout, verify `wemod` entrypoint, Python/Tk/venv requirements and upstream identity/version; reject unexpected paths/symlinks; never execute an unknown `wemod` command just for version detection. Do not auto-clone/update or pull arbitrary main-branch code without an opt-in.
2. **Per-game option:** show `GameWeld managed Wand` versus `DeckCheatz 1.x (experimental)` in the GameWeld GUI. Keep *all* saved game identifiers, original Steam launch command, launcher path, Proton selection and prefix data separate. Display the exact intended `wemod %command%` argv before any change.
3. **Safe invocation:** for Steam titles, prefer Steam's real game-launch command/launch-option integration, because DeckCheatz expects a full Proton `%command%` argument vector and a populated `STEAM_COMPAT_DATA_PATH`. Do not naively execute `wemod` with only a Steam AppID or concatenate unescaped shell strings. Record process handoff and game/trainer PIDs. Do not run a second independent Proton instance targeting the game's active prefix.
4. **Prefix safeguards:** snapshot relevant metadata, require explicit per-game consent before any prefix copying/overwriting/downloading or WeMod installation. Never silently replace the user's working Steam prefix. Do not run with `sudo`. Keep retries/resets user-approved, with a rollback path.
5. **Validation:** begin with read-only plan and synthetic argv fixtures. Then run on one opted-in game (e.g. Astrometica AppID 2353250) with actual launcher selected, confirming the game starts, the WeMod/Wand app opens, the trainer attaches to the **correct game process**, and a harmless supported trainer toggle responds. Collect separate loader, process and app logs. Do not imply success from CI fixtures alone.
6. **Release gate:** keep the current PC2 managed Wand hashes and experimental Wine crypt32 candidate checks unchanged. An external launcher provider should **not** bypass these checks for the old managed-provider path; it should have its own independently verified provenance and runtime tests. The optional provider must remain disabled until runtime validation passes.

## Relationship to existing crypt32 work

Test21 produced compiled x86_64/i386 crypt32 candidates; they do not match the historical 0.1.41 fingerprints. Test22's built-in Wine controls passed but candidate loading under native-only override failed with `status c0000135` (both architectures). Even EXE-adjacent candidate staging failed to load. These tests do not establish a cryptographic correctness error; they establish **native Wine-built DLL packaging/loader incompatibility** in the current scratch Proton environment. Treat those candidates as **unverified**.

DeckCheatz's preconfigured-prefix/Steam wrapper approach may avoid relying on GameWeld's custom Wine crypt32 payload at all for some supported games. It is **not** guaranteed to fix any particular title or trainer, and no live GameWeld + DeckCheatz integration has been attempted or passed.

## Next implementation slice

Build a **read-only `deckcheatz` provider discovery and launch-plan preview** in GameWeld without importing AGPL code or starting the trainer. Add fixture tests for `%command%` argument preservation, noninteractive fallback, per-game opt-in and rejection of untrusted paths. After review, implement and test a real opt-in GUI handoff.


## PC2 no-Steam-options direct provider prototype (2026-10-24)

Implementation now exists in `scripts/gameweld-deckcheatz-direct.py` (MIT GameWeld code, **NO DeckCheatz source vendored**) with synthetic fixture tests `scripts/test_gameweld_deckcheatz_direct.py`. The optional DeckCheatz 1.x checkout remains a user-chosen external AGPL application.

GameWeld's PC2 GTK Overview and Library each have a **DeckCheatz 1.x — Detect (no Steam options)** button. Detection is read-only; it does not install anything, patch Wine, alter the game's Steam LaunchOptions, or start a game/trainer. It checks for a recognized external 1.x tree. An installed checkout elsewhere may be selected for scanner discovery using `GAMEWELD_DECKCHEATZ_LAUNCHER=/absolute/path/to/wemod`.

The new backend's **read-only launch plan** is explicitly supplied the installed Steam AppID, executable inside the matching `steamapps/common/<game>` install path, Proton launcher, existing `steamapps/compatdata/<appid>` game prefix, and Steam client root. It validates the external upstream 1.x layout, AppID manifest, .exe path/prefix and Proton executable. It builds the same runner vector that DeckCheatz expects internally, without changing Steam preferences or Steam's `localconfig.vdf`: `python3 /path/to/external/wemod /path/to/GE-Proton/proton waitforexitandrun /library/steamapps/common/Game/Game.exe`. The exact argv and Steam compatibility env are rendered as JSON; there are no hand-edited `%command%` fields or shell concatenations.

Read-only discovery:

    cd /mnt/other/github/GameWeld
    python3 scripts/gameweld-deckcheatz-direct.py --discover

Read-only plan for an explicitly confirmed game, after filling in the paths to actual installed software:

    python3 scripts/gameweld-deckcheatz-direct.py --preview --appid 2353250 --launcher /absolute/path/to/wemod-launcher/wemod --proton /absolute/path/to/GE-Proton/proton --game-exe /absolute/path/to/Astrometica.exe --install-dir /absolute/path/to/steamapps/common/Astrometica --compatdata /absolute/path/to/steamapps/compatdata/2353250 --steam-root /absolute/path/to/Steam

An experimental direct-launch option exists, but is **not enabled as a one-click PC2 GTK play button**; the launcher is not yet field-verified with Steam DRM, Proton prefix ownership, game process readiness or actual trainer injection. It requires both the explicit flags `--launch --confirm-prefix-changes --experimental-direct-launch` and all validated paths. A no-op preview cannot launch even if flags are accidentally supplied. External upstream may modify the selected game prefix or download WeMod, and its own behavior is outside GameWeld's control. GameWeld never runs `sudo`, edits Steam LaunchOptions, or disables its separate managed Wand crypt32 hash validation.

IMPORTANT: DeckCheatz upstream documents Steam/Lutris prefix commands and warns that manually running outside a launcher is difficult. A manually reconstructed Proton argv is **experimental** and not equivalent to Steam's actual native launcher or guaranteed SteamAPI initialization. The UI will offer per-game settings, preview, consent and live launch only when this provider has successfully completed end-to-end field validation. For now, the new GUI control is **read-only detection**, not a false 'Play' button.


## PC2 read-only preview and opt-in field test (2026-10-24)

The GTK PC2 Overview and Library now have three separate DeckCheatz controls:

- **Detect (no Steam options)**: source-layout inspection only.
- **Preview selected game (read-only)**: validates selected Steam AppID, EXE, Proton, existing compatdata and the Steam client root, then shows the exact JSON launch plan. Missing EXE or unresolved Proton uses an explicit file picker; Proton auto-resolution reuses Steam compatibility mapping and prefix config evidence.
- **Test game + WeMod (experimental)**: runs the same read-only preview first, then shows a second confirmation identifying the game, AppID, prefix mutation risk, and lack of real-launch verification. Choosing No causes no external launch. Choosing Yes creates a private log and asynchronously starts the separately installed DeckCheatz backend using the Python helper's two required consent flags.

The experimental test is **not** the default Play action, has **not** passed any live game/trainer validation, and cannot claim success merely when its subprocess is queued. It uses no Steam launch option edits or shell string concatenation. The backend rechecks selected paths and refuses same-AppID active Proton sessions. Upstream may alter the selected game prefix or download trainer components. The operator should back up the prefix before opting in; GameWeld does not automatically snapshot or roll back that prefix in this prototype.

For the field test, select **Astrometica** on the PC2 GUI; verify the read-only preview, close any running Astrometica session, make a prefix backup if desired, then explicitly choose the experimental button and approve only if willing to accept prefix changes. See a log under `$XDG_STATE_HOME/gameweld/deckcheatz` or `~/.local/state/gameweld/deckcheatz`. Record separately: (1) helper starts, (2) game process/window, (3) WeMod window/login, (4) trainer recognizes Astrometica, (5) a safe single-player trainer toggle operates. A launcher exit status by itself never verifies steps (2)–(5).

Observed user preview has:
- Steam AppID 2353250;
- executable `/mnt/games/Steam/steamapps/common/ASTROMETICA/Astrometica.exe`;
- Proton `/mnt/games/Steam/steamapps/common/Proton - Experimental/proton`;
- existing compatdata `/home/szentigrade/.steam/root/steamapps/compatdata/2353250`.

These are **user-supplied, validated paths**, not proof of live launch. The Proton tool directory and game install library differ from the Steam client root/prefix; this is permissible for preview but needs field validation. GameWeld's managed Wand and custom crypt32 work remain isolated and unmodified.


## Astrometica PC2 end-to-end field validation — PASS (2026-10-24)

This entry supersedes the earlier "live handoff not yet validated" status above **for this single game and test configuration only**. An actual user-run GUI test was performed on CachyOS, not a synthetic CI fixture.

- Selected Steam game: **Astrometica**, AppID **2353250**, Windows executable `/mnt/games/Steam/steamapps/common/ASTROMETICA/Astrometica.exe`.
- External upstream provider: DeckCheatz/wemod-launcher **1.544** (as reported in the runtime log), checkout under the user's local GameWeld data directory.
- Runtime: `/mnt/games/Steam/steamapps/common/Proton - Experimental/proton`.
- Existing game prefix: `~/.steam/root/steamapps/compatdata/2353250`.
- GameWeld GUI provided a valid read-only launch preview and the separately consented experimental launch.
- Runtime log shows the opted-in DeckCheatz provider starting and forwarding `proton waitforexitandrun start Z:\\...\\wemod.bat Astrometica.exe`.
- Screenshot 1 visibly shows **the Astrometica Early Access game window and a running WeMod desktop window**.
- Screenshot 2 visibly shows **Astrometica's WeMod trainer page**, available cheats and a **Playing** status.
- After being asked to test **Unlimited Oxygen** in-game, the user explicitly confirmed **"works ingame"**. Record **end-to-end player-reported trainer operation: PASS**.
- The validated workflow did **not require changes to Steam Launch Options**. The read-only launch plan explicitly reported `steam_launch_options_modified: false`; the test did not independently diff all Steam configuration files.

**Scope:** one game, one host, one Proton choice, one upstream build, one player-reported working cheat. This does **not** establish all-game compatibility, SteamAPI behavior for other titles, reliable automatic game registration, absence of Wine prefix changes, or a stable/default Play path. Leave other games under experimental opt-in safeguards. A real game-and-trainer success for Astrometica is more than simple process spawn or GUI detection, but not a general compatibility guarantee.

**Next engineering steps:** preserve a machine-readable per-game field-validation record without hardcoding home-directory paths, add reproducible result collection for game process/window and WeMod association, ensure the existing no-LaunchOptions and prefix safeguards remain enforced, and simplify the GUI for validated workflows without silently enabling experimental direct launch for every game.


## GameWeld-managed upstream DeckCheatz 1.x installation (2026-10-24)

The PC2 GUI now supports **Install DeckCheatz 1.x (managed)** on Overview and Library. Users no longer need a terminal `git clone` or to hand-configure `GAMEWELD_DECKCHEATZ_LAUNCHER` for a normal per-user install.

On first selection of **Preview selected game** or **Test game + WeMod** with no DeckCheatz checkout detected, GameWeld offers to download and install the official upstream 1.x checkout. This is a user-approved **one-time download**, not a silent process and not a Steam launch action. A worker thread keeps the GTK UI responsive, and after installation the original selected game action resumes automatically if the selection has not changed. Users can also invoke the Install button explicitly.

The independent MIT GameWeld installer is `scripts/gameweld-deckcheatz-install.py`:
- `--status` is read-only and prints availability, existing checkouts, dependencies, and managed path.
- `--install --confirm` uses Git to clone `https://github.com/DeckCheatz/wemod-launcher.git` from **main** (1.x); it never selects unfinished `rewrite/v2`.
- Installs to `${XDG_DATA_HOME:-~/.local/share}/gameweld/deckcheatz` and reuses external existing 1.x checkouts rather than cloning again.
- Verifies its launcher/symlink-to-source layout, README and AGPL-3.0 license with the existing provider checks, records the checked-out Git commit hash, uses a temporary staging directory, exclusive install lock and atomic rename.
- Preserves existing user data: an occupied, invalid target is **not** overwritten or removed. A clone failure cleans the staging directory.
- Does **not** run DeckCheatz during installation, package AGPL upstream source into GameWeld, use `sudo`, modify Steam Launch Options, patch Wine, change a game prefix, or install WeMod into a prefix.
- Separately identifies `git`, Python/Tkinter and `venv` availability. Installing missing distribution packages is **not** automated and may require a normal system package manager; no unapproved privilege elevation.
- No automatic background update of already-installed upstream source is enabled; update/version policy needs separate validation.

The next screen for an opted-in **experimental game+trainer test** remains the existing preview and **game-prefix mutation consent**. These are distinct from download permission. The successful Astrometica field test applies to the recorded installed upstream environment; new cloned versions and other games still need verification.

Offline synthetic tests live at `scripts/test_gameweld_deckcheatz_install.py`, including first install, repeated install (no overwrite), invalid pre-existing directory, clone failure and rollback, outside existing checkout reuse, no-install-without-consent, and Steam/compatdata non-mutation. The PC2 GitHub Actions job also builds the GTK source and executes these tests. A successful CI result would validate build and fixtures, **not** downloading over a real end-user network or third-party trainer effectiveness.


## Managed DeckCheatz 1.x updates and simplified game entry (PC2)

This slice retains the previously validated Astrometica + Proton Experimental + WeMod trainer path while improving product flow for new users. The GameWeld UI now labels the game action **Play with WeMod — DeckCheatz (experimental)** in Overview and Library. On an initial install it still offers the download prompt, reuses the selected game and gives a read-only preview followed by a distinct Wine-prefix launch consent. Nothing silently turns on trainer execution for other games.

**Settings → DeckCheatz 1.x — Managed Updates** provides:

- **Check DeckCheatz updates:** performs a read-only `git ls-remote` of the official `main` branch for checkouts GameWeld installed or adopted. No download or local change. Manually installed external checkouts are reported as unmanaged, not overwritten.
- **Update DeckCheatz (opt-in):** after an explicit confirmation, refuses to proceed if DeckCheatz appears to be running, checkout metadata or Git origin differs, or user-local changes/untracked files exist. Stages and validates a fresh `main` checkout first; moves the previous checkout to a uniquely named rollback directory and verifies the replacement. A failure while activating the replacement attempts to restore the prior checkout.
- **Manage existing DeckCheatz checkout:** explicitly enrols a clean manually cloned upstream 1.x checkout already located in GameWeld's expected data folder, after verifying origin URL, branch name, revision and absence of local edits. It writes only `.gameweld-managed.json` metadata and does not download, replace or update any source at adoption time.

The user-managed installation metadata stores only schema, official source URL, `main` and full 40-character commit revision; it does not contain secrets or Steam settings. Updated checkouts retain their own matching metadata. The updater never automatically updates DeckCheatz on application startup and never changes Steam Launch Options or Wine prefixes. The old checkout stays available as a backup; automatic one-click rollback is not yet built. **Upstream behavior can change after an approved update; the first live test following any update should remain experimental.** Tests cannot prove external third-party integrity solely from Git layout checks.

The offline reproducible test command is:

    bash scripts/pc2-deckcheatz-aio.sh

It creates `build/pc2-source/deckcheatz-aio-report.txt` and runs Python compile checks, locally created Git fixture tests for fresh install/update/adoption, Proton chooser and backend safeguards, GTK C syntax verification and read-only checkout status. No real game, Wine prefix, external download or trainer is started by this AIO command. The CI workflow also calls it. Results from actual user's CachyOS system and GitHub Actions must be inspected before declaring a generally ready release.

**Release gate:** Astrometica has a player-reported successful cheat toggle, but the simplified UI and update-manager feature are new code. Do not mark all other games field-tested or promote an across-the-board unattended installer/updater based on the one working game.


## CachyOS DeckCheatz AIO validation — 2026-10-24

User supplied `deckcheatz-aio-report.txt` from `bash scripts/pc2-deckcheatz-aio.sh`. Result: **PASS (OFFLINE FIXTURES + GUI SYNTAX ONLY)**. The observed sections were:

- Installer/updates/adoption: **20/20** synthetic tests passed, including adoption from a clean main checkout, refusal to overwrite dirty/wrong-origin checkouts, update backup, update failure rollback, and preservation of the existing Steam/prefix fixtures.
- Proton discovery: **5/5** synthetic tests passed, including ambiguity failing closed and matching the chosen game's Proton tool.
- DeckCheatz launch plan and consent guards: **8/8** synthetic tests passed, including duplicate-process rejection and no preview-time Steam configuration changes.
- GTK PC2 frontend C source **gcc syntax-only check passed** (empty error output; final report PASS).
- Read-only local checkout status: `installed: true`, `available_count: 1`, `managed_install: false`. Checkout was under the usual `~/.local/share/gameweld/deckcheatz` folder but did not yet have GameWeld-managed metadata. Dependencies detected: `git`, `python3`, `tkinter`, `venv` all true.
- No external download, game or WeMod launch, real Steam LaunchOptions change, or Wine prefix change was performed by this AIO run.

**Interpretation:** The *offline AIO + frontend syntax* gate has passed on this user's CachyOS host. This result alone does **not** verify that GUI adoption and managed updater controls work at runtime, validate upstream network updates, or establish cross-game compatibility. Earlier in this project, Astrometica 2353250 independently passed one end-to-end game+WeMod single-player trainer field test. Those are two distinct validation scopes.

**Next gate:** verify the GameWeld Settings UI can safely enrol the existing clean checkout after explicit consent, then run a read-only upstream update check. Do not run the updating action or alter the validated installed files automatically. Continue with complete frontend compilation and future multi-game compatibility testing before promoting an unqualified stable release.


## PC2 game-first navigation and provider settings cleanup (2026-10-24)

Following the successful player-reported Astrometica live trainer test, managed-checkout adoption/update check and 33/33 previous offline suite, the PC2 GTK interface now prioritises the **Play with WeMod** action.

- **Overview:** The prominent action appears under the selected game. Earlier PC1 play-profile controls are still initialized for existing code but hidden only under PC2 discovery mode. Read-only preview, DeckCheatz discovery/install and Steam/Wand engineering controls remain available inside the collapsed **Advanced Steam / WeMod diagnostics** expander.
- **Library:** The selected-game inspector contains the prominent Play with WeMod action and a per-game readiness sentence. Diagnostic controls are behind **Advanced trainer / launch diagnostics**. The existing PC1 library buttons remain active only outside PC2.
- **Selection gates:** The play action is sensitive only for ordinary installed Steam entries, not Heroic/Lutris or Steam non-Steam shortcuts. Astrometica AppID 2353250 is explicitly labelled as a user-validated host configuration. Every other Steam title retains experimental wording. This is UI feedback, not an assumption of multi-game compatibility.
- **Settings:** PC2 shows three tabs: **Quick Start**, **DeckCheatz / WeMod**, and **Advanced Providers**. The managed install/update/adoption controls live in the DeckCheatz tab; Wand, Cheat Engine and other trainer-specific maintenance tools remain in Advanced Providers. Outside PC2, the existing settings layout remains intact.
- **Safety unchanged:** The actual DeckCheatz backend remains separately opted in. The game-specific preview still occurs before a YES/NO dialog explicitly identifying Wine-prefix mutation risk. Duplicate same-AppID processes and invalid Steam/Proton/prefix paths are refused by the independent Python helper. Steam Launch Options remain unchanged.
- **Regression testing:** `scripts/test_gameweld_deckcheatz_gui_layout.py` checks UI labels, Steam-only availability, the separate preview/consent path, hidden legacy PC2 controls and settings tabs. `scripts/pc2-deckcheatz-aio.sh` runs it along with the installer, Proton and provider tests, GTK C syntax compilation, and read-only status.

This is a development-branch UI change, not a release announcement. Do not assume this newly arranged GUI has passed a live GTK render test until the updated AIO and PC2 source runner have been exercised on the user's CachyOS desktop. Full integrated game+trainer verification remains limited to Astrometica.


## PC2 live GUI screenshot review and responsive layout changes (2026-10-24)

Eight user-provided CachyOS desktop screenshots show the development GUI rendering and navigating successfully across **Overview, Library, Trainer Library, Compatibility, Support, About, and Settings/Quick Start**. The screenshots confirm the selected-game **Play with WeMod** button is displayed in both Overview and Library, the primary Settings entry is simplified, and the player-visible selection includes Steam game `7 Days to Die` as the current selected game. These images **do not** establish a live WeMod handoff for `7 Days to Die`; only Astrometica is field-validated.

**Visual regression found:** On a relatively narrow restored window, the Library game list was squeezed to a thin column of cover thumbnails by the inspector's fixed width. A second presentation issue was the legacy About page's dense long text; Compatibility also still surfaced a status specific to the optional isolated Wand tool without distinguishing it from the successful DeckCheatz/Proton pathway.

**Fixes implemented:**
- PC2 Library has a width-responsive allocation handler. At widths below approximately 990 GTK pixels, the game list and selected-game inspector stack vertically and the page becomes vertically scrollable; at wider widths they return to a side-by-side layout. A hysteresis threshold avoids repeated flips near the breakpoint. The Steam/DeckCheatz launch callback, game selection and saved data are unchanged.
- The PC2 About page is shorter, scrollable and uses individually wrapped cards, while the original PC1 About page remains untouched.
- Compatibility now labels the missing isolated Wand compatibility tool as optional and explicitly states it is not a prerequisite for the independent DeckCheatz/Proton/WeMod workflow.
- The Astrometica readiness message now accurately describes success on **one tested CachyOS system**, not guaranteed success on every user's computer.

The test suite `scripts/test_gameweld_deckcheatz_gui_layout.py` includes static regression assertions for responsive Library orientation, page scrolling, the revised About page and the compatibility-scope description. These tests run from the existing `scripts/pc2-deckcheatz-aio.sh`.

**Gate still required:** Updated GTK syntax compilation, resize testing on the user's real desktop (wide and narrow window), and fresh AIO output. This source change has not yet been proven visually by screenshots. Do not change the already-validated Steam/DeckCheatz launch path merely because a GUI viewport was adjusted.


## PC2 RC1 offline compile preflight and private runtime AppDir staging (2026-10-24)

After the screenshot-driven Library responsiveness/UX fixes, PC2 gains a more complete compile and packaging-boundary gate. Two new source scripts are available:

- `bash scripts/pc2-rc1-preflight.sh`: runs the DeckCheatz offline AIO, verifies AppDir helper links in the source runner, executes Go backend tests, builds a Go backend executable and fully **links** the GTK3 frontend (previous AIO covered only C source syntax). It records SHA-256 hashes of the resulting frontend/backend and writes `build/pc2-source/rc1-preflight/rc1-preflight-report.txt`.
- `bash scripts/pc2-stage-standalone-appdir.sh`: first runs the RC1 preflight, then assembles a private source-built `build/pc2-source/pc2-test-AppDir` with the **compiled binaries and copied runtime helpers** (rather than the symlinked scripts from the source runner). The `AppRun` entrypoint sets `APPDIR` and `WAND_NATIVE_BACKEND`. Existing staging destinations are **never overwritten** without an explicit manual removal/move.

The private AppDir deliberately does not contain DeckCheatz AGPL source, a WeMod binary, game art, trainers or DLL payloads. It uses host GTK3 libraries rather than deploying bundled GTK, is **NOT a distributable AppImage or license-cleared release**, and has not been launched or reverified on a fresh target system. PC1 packaging scripts and existing user installations remain unchanged. CI now stages the internal AppDir and checks launcher/helper presence and absence of symlinks/external DeckCheatz source.

**Gate interpretation:** Successful preflight and staging establishes compiled source and file placement, **not** runtime GUI behavior, real-world trainer compatibility, publication rights or first-use internet install success. Next validation on the user's CachyOS machine is to run the preflight once, inspect its report, and verify narrow/wide Library behavior in the PC2 source runner. Do not publish or rename the private AppDir to an AppImage before distribution/runtime/license review.


## User-verified PC2 RC1 offline preflight — 2026-10-24

The user ran `bash scripts/pc2-rc1-preflight.sh` on CachyOS and uploaded `rc1-preflight-report.txt` for exact checkout commit `39de025385088fafe88dd9444dfea3743826900a`. **Result: PASS (OFFLINE SOURCE BUILD + FIXTURES ONLY)**. The workspace had one previously known uncommitted modification to `scripts/run-pc2-source-frontend.sh`; the preflight did not overwrite or discard it.

Observed test results:
- 20/20 managed DeckCheatz installer, updater and adoption fixtures passed.
- 5/5 Proton discovery fixtures passed.
- 8/8 direct launch consent, duplicate detection and Steam configuration preservation fixtures passed.
- 8/8 static PC2 GUI layout and safeguard assertions passed.
- GTK frontend source syntax passed.
- Source helper AppDir link layout passed.
- Go backend tests passed; a complete backend binary built.
- Complete GTK frontend compiled and **linked** into an executable; SHA256 hashes for both binaries were recorded.
- Existing DeckCheatz 1.x installation reports `installed: true`, `managed_install: true`, revision `f9094b31ee79afe8af8d78c7767b957307ec33ee`. Git, Python3, Tkinter and venv detected. No updater or game launched by the preflight.
- Backend binary SHA256: `455f78c6adb7256406f973c2ceb8ae063131916ad597d271a1acd51a62ba013c`.
- GTK binary SHA256: `553f49a2cadef04fe31b0b6461e0895dba75b31d118185134e4970f8012255f5`.

**Important distinction:** This establishes the precise offline **preflight** gate, not successful staging of the standalone AppDir. The report has no AppDir-staging success line and no real GTK runtime resize evidence. The next gate is a successful `scripts/pc2-stage-standalone-appdir.sh` run followed by actual UI opening/narrow and wide Library checks. Existing Astrometica field validation is independent of this offline build result. Do not yet promote to RC1 or publish any AppImage.


## PC2 4K/HiDPI screen-aware startup correction (2026-10-24)

The user's latest real desktop screenshot still showed a tiny, narrow restored GameWeld window on a 4K monitor. The user specifically asked for automatic window sizing based on the current screen instead of opening narrow. The previous UI implementation used a capped 2200x1400 recommended size and 2 delayed KWin resize callbacks, leading to a confusing start/restore experience.

**Fix committed to PC2 GTK only:**
- On PC2 startup, request **maximized** state from the window manager, automatically using the current monitor work area. Issue this request both before map and once in GTK idle, without subsequent forced resize timers. This is intentionally not fullscreen; taskbars and panels remain visible.
- Compute PC2 restored default size as approximately **90% × 88% of the GTK monitor work area**, with conservative margins and no hard upper 2200x1400 pixel cap. GTK work areas are in logical screen units on HiDPI/KWin, not unconditionally physical 3840x2160 pixels.
- Replace the old click-count based maximization toggle with a query of the actual GTK maximized state, correctly handling manual desktop-titlebar maximization and the new initial state.
- Preserve original PC1 window geometry and its one-shot/delayed legacy sizing. Preserve manually resized PC2 windows after startup.
- The responsive Library's stacked mode remains a narrow-window fallback; it is no longer a substitute for proper monitor-aware startup. The existing WeMod/DeckCheatz game launch and installer flow are unmodified.
- Add 2 static GUI regression tests, increasing the UI subset from 8 to 10. All actual build/runtime results must be obtained using the user's new AIO/preflight and desktop AppDir.

**User validation:** Pull the new PC2 commit, build and stage under a **new** unique AppDir name so an existing old 4K-unaware binary is not reused, and launch its `AppRun`. Verify the app opens maximized on 4K, manual restore gives a comfortable centered 90%-ish window, the maximize button toggles properly, and the Library game names remain readable when restored. Do not interpret old-window screenshots or an already-staged binary as verification of the new build.


## Resolution-adaptive startup policy: UHD fills screen, smaller panels proportional (2026-10-24)

The user clarified the desired window behavior: **automatically size GameWeld for every screen resolution, with physical 4K/UHD filling the screen**. This supersedes the previous PC2 implementation that maximized unconditionally regardless of the monitor resolution.

The sizing policy is now explicitly separated into `crates/wand-ui/appimage-gtk3/gameweld-pc2-window-policy.h` (GTK-independent and reproducibly testable) and the GTK monitor/workarea lookup in `gameweld-native-040.c`. At startup, GameWeld obtains the primary monitor's logical workarea for GTK sizing, and the monitor's physical geometry using `gdk_screen_get_monitor_geometry` multiplied by `gdk_screen_get_monitor_scale_factor`. A physical UHD monitor (at least **3840 × 2160**) gets GTK **maximized**, filling its usable desktop area while leaving taskbars/panels available. It is *not* exclusive fullscreen or an attempt to draw beyond the desktop workarea.

For non-4K displays, GameWeld uses a proportion of the monitor workarea instead of forcing a maximized state: compact monitors (1600×900 or below, including 720p) target **95% width × 93% height**, ordinary 1080p-class displays target **90% × 88%**, and 1440p/ultrawide-class screens target **92% × 90%**. Restored window sizes are bounded to the visible workarea. Physical 4K displays at 200% scaling are recognized from their 1920×1080-ish logical geometry times the GTK monitor scale, preventing accidental misclassification as a 1080p display. On actual fractional-scale platforms, the detection follows the integer factor exposed by GTK3 and needs real desktop verification.

The existing titlebar Maximize/Restore button reads actual GTK window state. No periodic resize callback overrides manual resizing. PC1 geometry and the existing Steam/DeckCheatz launch engine are unchanged.

Native C policy tests are in `scripts/test-pc2-window-policy.c` and now run from `scripts/pc2-deckcheatz-aio.sh`. Cases: 720p compact, 1080p, 1440p, ultrawide 3440×1440, UHD 1×, UHD 2× HiDPI, 5K 2× HiDPI, and 1440p with high scaling, plus exact expected restored dimensions. The static GUI tests now assert the GTK/GDK callsites and the shared policy.

**Next validation:** New source checkout should pass PC2 AIO/RC1 preflight and a brand-new staged AppDir should open maximized on the user's UHD screen. If the user changes KWin scaling or runs the build on a 1080p/1440p monitor, it should open proportionally but *not* maximized. Full GTK runtime behavior and KWin fractional-scale handling remain unverified on this new code.


## PC2 launch geometry revised: comfortable window on all resolutions (2026-10-24)

Following live screenshots, the user clarified that the prior small window was a comfortable size and **maximizing or covering the 4K desktop by default is NOT desired**. This supersedes the previous 4K and 5K auto-maximize policy. Normal users should start in a useful centered window with sufficient room for other applications, independent of how high-resolution their monitor is.

Updated PC2 policy:
- **Never automatically maximize or fullscreen at startup** on 720p, 1080p, 1440p, ultrawide, 4K, 5K or scaled screens.
- Determine the primary monitor's usable GTK workarea and physical resolution/scale for proportional sizing, then apply a reasonable upper cap. Example 4K 1x workarea 3840×2100 opens approximately **1800×1120 logical GTK pixels**, rather than filling 3840×2100. Example 4K 2x workarea 1920×1040 opens **1440×832 logical pixels**, with no auto-maximize.
- Smaller 1080p example 1920×1040 opens **1574×852**; ultrawide/1440p examples cap around **1750×1050**.
- Apply the preferred size only once, shortly after first mapping, to clear prior tiny KWin development-window restores; never enforce on every timer tick. Users remain able to resize or click the existing manual maximize/restore control at any time.
- Preserve the established PC1 window sizing and all working GameWeld/DeckCheatz/Proton/WeMod launch code. No Wine prefix or Steam Launch Options changes.

The native offline `scripts/test-pc2-window-policy.c` and static `scripts/test_gameweld_deckcheatz_gui_layout.py` have been updated to **reject automatic maximize** and check sensible, bounded restored window dimensions across eight monitor configurations. The arithmetic was cross-checked but a fresh local **C compilation and GTK runtime screenshot are still needed** on the user's CachyOS build.

The next AppDir should use a new stage directory so a previously built, auto-maximizing executable is not accidentally reused. For release evaluation, confirm that launch stays in a normal resizable window, without covering the full 4K screen.


## PC2 user-sized window defaults and preference persistence (2026-10-24)

The screenshot review established that both prior extremes were unsuitable for typical users: a very small initial window made the UI hard to browse, while the earlier maximized 4K layout consumed too much desktop. The user validated a **non-fullscreen** PC2 development window, and continuation work now makes the out-of-box size moderately larger with the **explicitly user-controlled** option to resize.

Changes:
- The GTK-independent sizing policy keeps `maximize=0` for **every** display. The example 1080p logical workarea 1920×1040 defaults to **1632×884**; 1440p 2560×1380 to **1850×1100**; and 4K 1× 3840×2100 to **2200×1280**. The caps are designed to leave substantial desktop space, not set minimum monitor requirements. Tiny screens remain clamped within the actual visible workarea; GTK monitor scale still determines physical-vs-logical geometry.
- PC2 stores only the **last normal-window width/height** in `${XDG_CONFIG_HOME:-~/.config}/gameweld/pc2-window-size.txt` (depending on the user's HOME and XDG config settings). Saving occurs when its GUI window is destroyed, but **not** while the window is maximized. Loading refuses malformed or implausibly large values and clamps the saved dimensions to the currently usable monitor. The preference is separate from Steam launch settings, Wine, games, and the external DeckCheatz checkout.
- Settings → Quick Start adds a **Reset window size** action, which removes the PC2 dimension preference and returns the current window to the computed non-maximized default. The existing Maximize/Restore control continues to work at user request; PC2 does not persist or force maximized state on subsequent launches.
- Static PC2 GUI regressions now cover persistence, clamping, reset action, and unchanged external game launch consent. Native C sizing tests have been updated for the larger defaults at eight synthetic resolutions.

These source changes are committed but **the revised linked GTK binary and runtime preference round trip are not yet verified** on the user's desktop. The next gate is staging a new development AppDir with a unique destination, opening GameWeld, resizing it, closing/relaunching the same AppDir, and confirming the saved dimensions return. It should still never automatically maximize. Verify the offline AIO/preflight tests before declaring the preference feature complete.


## PC2 Reset window size disabled-button fix (2026-10-24)

The user reported that Settings → Quick Start → **Reset window size** did nothing on the live CachyOS GUI. Inspection of the GTK source found the exact cause: the global PC2 `button()` factory automatically calls `pc2_guard_button(w)` on any action label not explicitly allow-listed, permanently disabling it in `GAMEWELD_PC2_DISCOVERY_ONLY` mode. The new window reset button had been wired to `on_pc2_window_size_reset` but was **missing from the safe-action allow-list**. Therefore the handler was never invoked.

Fix: add only the string `"Reset window size"` to that safe-action allow-list, which does not affect trainer execution/launch, download/update permissions or Steam Launch Options. The existing reset callback removes only `pc2-window-size.txt`, recomputes screen-proportional default dimensions, exits maximized mode if needed, and resizes/recenters the window. A new static GUI regression assertion inspects the actual `button()` guard to prevent this UI regression. This is a code fix; compile and click testing remain required on a newly built AppDir.

Expected validation: pull the updated PC2 branch and stage a new AppDir in a fresh path (never silently overwrite a prior stage). Launch, resize to a custom normal-window size, close/reopen to check persistence, then click **Reset window size** and confirm a visible size change plus the Activity message `PC2 window reset: ... normal window`. No separate game/WeMod test is required because the launch path was not changed.


## PC2 window-size persistence live bug — save during resize, not destruction (2026-10-24)

The user reported that **Reset window size** now worked but, after manually resizing GameWeld and closing/reopening it, the window reverted to its old dimensions. The previous preference code read `gtk_window_get_size()` **only inside the GTK `destroy` signal**. By that point the GTK3/KWin window may already have been unmapped or may report its original geometry, rather than the size last chosen while visible. Pure static tests had not exercised persistence.

**Corrective implementation:**
- In PC2, connect the main GTK window's `configure-event` signal to `pc2_window_configure`. While the window is visible and not maximized, record every valid last normal width and height into `pc2_window_last_w`/`pc2_window_last_h`, ignoring duplicate sizes and initial pre-startup sizes.
- Queue a coalesced 750-ms timer to write the current cached size to the user's PC2-only state file while GameWeld is still open. The close/destroy handler saves this **cached live size** and never asks an already-disappearing GTK window for its dimensions. Maximizing does not overwrite the last normal dimensions.
- The startup callback sets a sensible initial cached size and enables observation after the initial programmatic fit. The Reset action updates the cache and writes the new default immediately.
- Extract actual on-disk read/write/clamp logic into `gameweld-pc2-window-state.h`, shared between the production GTK window handler and a new compiled C regression test. Writes use a per-process temporary file and rename, rather than potentially leaving partially written settings; reads reject malformed, dangerous symlinks, and implausible dimensions.
- `scripts/test-pc2-window-state.c` tests first-run absence, save/reload, resizing overwriting previous dimensions, clamping on smaller monitor, rejection of invalid state, reset/close/reopen, and symlink refusal. `scripts/pc2-deckcheatz-aio.sh` now compiles and executes this native roundtrip test. Static GUI tests assert a *connected* live configure callback and the shared on-disk codepath. GameWeld logs `PC2 saved live window size: WIDTHxHEIGHT normal window.` upon successful commits.

**Validation limits:** A local reproduction of the standalone C persistence helper was compiled with gcc `-std=gnu11 -Wall -Wextra -Werror` and all simulated file roundtrip cases passed. The new full GTK frontend/AppDir and live interactive KWin resize + relaunch have **not yet** been tested with this correction on the user's machine; do not mark the user-observed bug fixed until that final test succeeds. No Steam, Wine, DeckCheatz or trainer launch actions were changed.
