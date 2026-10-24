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
