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
