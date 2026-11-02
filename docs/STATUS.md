# GameWeld desktop alpha status

This is a clean **0.1.0-alpha** GTK4 shell, not a third-party trainer manager.

## Included

Read-only installed Steam game discovery, search, favourites, local settings and a graphical game detail panel. The `--smoke` command and core tests do not require GTK.

## Not yet validated

Actual GTK4 window launch on CachyOS; this development environment lacks a graphical session. The Batch77 isolated system-Wine IPC milestone was verified separately, but its executable is deliberately **not bundled** or integrated into this clean GitHub alpha.

No Proton game-session equivalence, game memory attachment or third-party trainer compatibility is verified. No external binaries are embedded.

## History

The old `main` commit before resetting the tree was `5545a3e6464e3044d4699e9ceea98f5aa56e0bd7`. It remains a parent ancestor of the reset commit for recovery. Historical issues and PRs were closed, not deleted. Legacy branch references were removed separately.

## CachyOS first graphical feedback (2026-11-02)

The user verified that the GTK4 window opens and the headless smoke test discovers 127 local Steam games. The initial Gtk.Paned layout was too short to display the game list and GTK emitted minimum-size warnings. Commit `61f40c6` replaces the Paned with an expanding scrolled list, displays visible/discovered counts and preserves selection on favourite toggles. **This layout fix still requires a new graphical verification on CachyOS.** Headless source-contract tests do not prove GTK warnings are gone.
