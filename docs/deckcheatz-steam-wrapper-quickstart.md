# DeckCheatz Steam wrapper quickstart (PC2 private test)

Status: draft only. A user reported that DeckCheatz's existing Steam
%command% wrapper works for Dying Light: The Beast (AppID 3008130).
This does not establish universal game compatibility or verify that a
specific WeMod trainer feature attached successfully.

The Steam wrapper is **not** equivalent to launching WeMod.exe directly
through Proton runinprefix. That separate experiment caused repeated
Electron GPU process failures (error_code=43) on the test machine.

## Set up a Steam title once

1. Keep the existing DeckCheatz launcher, or install it through GameWeld's
   managed DeckCheatz 1.x installation option.
2. In Game Connection click **Copy DeckCheatz Steam launch option**,
   or generate it without changes using:

       python3 scripts/gameweld-deckcheatz-steam-options.py

3. In Steam, select the matching installed game, open
   Properties > General > Launch Options, and paste the generated line.
   Preserve any other required game options. The generated command
   includes WINEDLLOVERRIDES, WEMOD_LOG, the actual executable path
   of the DeckCheatz launcher, and %command%.
4. Close the game and WeMod before asking GameWeld to launch. Enable
   the private source GUI's Steam launch gate for this invocation:

       bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch

5. Select that same Steam game in GameWeld. Click
   **Play via Steam + DeckCheatz** and explicitly confirm that Steam's
   current per-game Launch Options contain the DeckCheatz wrapper.

GameWeld requests a normal Steam -applaunch for the exact AppID, and Steam
executes the game's own saved Launch Options if configured. GameWeld does
not edit Steam's options, switch Proton, run a separate trainer process,
register a Steam Bridge, or replace a game prefix during this operation.

A read-only preview and user confirmation precede each launch. The
Steam wrapper route blocks if an existing process is already identified
with this AppID, to avoid launching the same game twice.

## Validation boundaries

The launch worker can report that a Steam AppID-associated process
appeared. This does **not** prove the game's window opened, that the
DeckCheatz wrapper ran, that WeMod started, or that a trainer feature
worked in the game. Verify those outcomes manually in offline or
single-player mode. If Steam's per-game option was never configured,
Steam may simply launch the game without WeMod.

For read-only setup, run the normal source GUI (without the launch
flag); it will offer **Set up DeckCheatz for Steam** instead of a launch.

Avoid the direct live-client WeMod.exe handoff while using this Steam
wrapper route. Do not restore or swap Proton prefixes while the game
or WeMod is running. Keep your original Steam Launch Options setting
until testing is finished, and restore it through Steam Properties if
you later decide to stop using DeckCheatz.

Offline test suites and GTK smoke tests do not qualify this path
for a public release. The PR remains draft until real end-to-end
trainer functionality is verified.
