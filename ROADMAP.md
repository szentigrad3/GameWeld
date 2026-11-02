# GameWeld roadmap — desktop application reboot

**Status: development transition, 2026-11-02.** This supersedes the historical 0.7.0/0.8.0 feature roadmap **for new development**. The previous roadmap's implementation and history remain in Git history; this document does not declare old GitHub releases complete.

## Milestone D1 — Batch78 GTK4 app shell (in progress, not yet merged)

- Source-built GTK4 launcher for CachyOS/Linux.
- Steam installed-game browser with search and local favourites.
- Read-only per-game diagnostics and session state.
- Separate IPC Lab for the pinned GameWeld Windows fixture. Launch only with explicit consent.
- XDG local settings/state, clear errors, no placeholder controls or fake status.
- Headless UI-core tests and an actual graphical smoke test before declaring GUI verified.

**Exit gate:** downloadable source-complete app launches on CachyOS and the game library/diagnostics work. It need not attach to a game.

## Milestone D2 — Reliable standalone sidecar manager

- Versioned IPC protocol and session ownership.
- Bounded stderr/stdout, startup/idle/shutdown timeouts and cancellation.
- Deterministic cleanup of owned child processes; accurately report unseen detached helpers.
- Explicit capability policy: only approved, integrity-pinned executables; no arbitrary trainer upload/execute.
- Isolation tests and lifecycle evidence on CachyOS.

## Milestone D3 — Packaging, architecture, quality

- Replace inherited AppImage-runtime approach with source-complete packaging.
- Build and smoke-test a Linux native artifact; optional AppImage after dependency audit.
- CI for Python, GTK4 UI-core, historical regression boundaries and packaging.
- Security review, private-log redaction, licensing inventory, accessibility and migration tests.

## Milestone D4 — Opt-in compatibility research (not currently enabled)

- Verify the exact game/runtime context independently of command-line hints.
- Test harmless sidecar integration through supported game launch paths.
- Keep third-party trainer, live game-memory and anti-cheat-dependent workflows behind separate, explicit compatibility and safety gates.
- Never equate the Batch77 fixture handshake with working game integration.

## Historical backlog status

Existing issues and pull requests are **preserved for review**, not automatically carried into the new architecture. See [legacy transition register](docs/LEGACY-TRANSITION.md). Decide individually whether to port, supersede, or close only after confirming relevant code and permissions.

## Rules

Keep `main` and old release history intact until migration is reviewed. No mass deletion of branches or issues, no history rewrite, and no claim of completed GUI/Proton compatibility without host evidence.
