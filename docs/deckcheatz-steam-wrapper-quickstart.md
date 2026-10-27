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

3. The first click now **reads the selected game's existing Steam per-account**
   LaunchOptions from localconfig.vdf without changing Steam. When the
   existing command has a conservative, unambiguous merge (empty setting,
   environment assignments and straightforward game flags), GameWeld shows
   both original and proposed text. Confirm to save the **exact original**
   in a private, exclusive 0600 GameWeld backup *before* the merged command
   goes to your clipboard. An existing backup is never overwritten.
   Other wrappers (Gamescope, MangoHud, GameMode, custom shell scripts),
   multiple Steam accounts, or unsupported syntax block auto-merge; GameWeld
   does not copy a potentially destructive replacement.
4. In Steam, select the matching installed game, open
   Properties > General > Launch Options, and paste the generated line.
   Preserve any other required game options. The generated command
   includes WINEDLLOVERRIDES, WEMOD_LOG, the actual executable path
   of the DeckCheatz launcher, and %command%.
5. Close the game and WeMod before asking GameWeld to launch. Enable
   the private source GUI's Steam launch gate for this invocation:

       bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch

6. Select that same Steam game in GameWeld. Click
   **Play via Steam + DeckCheatz** and explicitly confirm that Steam's
   current per-game Launch Options contain the DeckCheatz wrapper.

GameWeld requests a normal Steam -applaunch for the exact AppID, and Steam
executes the game's own saved Launch Options if configured. GameWeld does
not edit Steam's options, switch Proton, run a separate trainer process,
register a Steam Bridge, or replace a game prefix during this operation.

A read-only preview and user confirmation precede each launch. The
Steam wrapper route blocks if an existing process is already identified
with this AppID, to avoid launching the same game twice.



## Review and restore existing Steam launch options

In GameWeld, select the exact Steam game and use **Restore original Steam launch
option** to retrieve the private backed-up original and copy it to your clipboard.
A blank original setting is valid; paste/clear it in Steam Properties manually.

For read-only inspection from the development checkout:

    python3 scripts/gameweld-steam-launch-options-preserve.py --preview --appid 3008130

Only after inspecting the report, explicitly save the unmodified original:

    python3 scripts/gameweld-steam-launch-options-preserve.py --save-original --appid 3008130

To print the preserved original for manual restore:

    python3 scripts/gameweld-steam-launch-options-preserve.py --restore-original --appid 3008130 --format text

The helper auto-detects one Steam localconfig.vdf. With multiple accounts, pass
--steam-account ACCOUNT_ID explicitly. It does not guess the active account.
Steam launch settings are **never edited by GameWeld**. Steam may rewrite
localconfig.vdf while running, so all changes happen manually via Steam's UI.
The private backup only snapshots the selected per-game Launch Options
**text**, not Steam's entire configuration or every game.

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
