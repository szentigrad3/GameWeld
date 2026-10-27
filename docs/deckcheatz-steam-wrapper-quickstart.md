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


## New private alpha: one-shot DeckCheatz session

GameWeld now includes an experimental **Set up one-session DeckCheatz** action
in Game Connection. It installs its own private, user-owned Steam shim and
copies a conservative merged one-time Launch Option **after backup and explicit
consent**. You still have to paste the option into Steam **once**.

From the development source GUI:

    bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch

For the selected standard Steam Windows title:

1. Choose **Set up one-session DeckCheatz**, confirm private helper installation.
2. Verify the original/proposed launch options. If the Steam config is empty on
   disk, explicitly check the current Steam Properties field and confirm it is
   also empty. Otherwise do not proceed.
3. GameWeld backs up the exact original string (once, in private state), then
   copies the new one-time session shim option. Paste it into Steam manually.
4. Close the game and any WeMod client; Steam should save the launch option.
5. Click **Play via Steam + DeckCheatz**. When GameWeld can verify the exact shim
   is in the selected game's saved Launch Options, its UI will arm a token
   bound to that AppID (10-minute expiry), then request a normal Steam launch.
6. The Steam shim atomically consumes the token before executing DeckCheatz
   with Steam's full original Proton/game command. All following launches,
   whether through Steam or GameWeld, simply pass Steam's original command
   through with no DeckCheatz; no background monitor is required. A crash,
   SIGKILL or regular exit cannot leave the token armed after consumption.

This is **behaviour restoration, NOT literal Steam Launch Options text
restoration**. The persistent GameWeld shim remains in the launch options
until the user uses **Restore original Steam launch option** and pastes the
original back in Steam. Steam caches launch options while open, so GameWeld
does not overwrite localconfig.vdf on each play session.

For extra private command-line tests, without changing Steam:

    python3 scripts/gameweld-deckcheatz-session.py install --appid 3008130
    python3 scripts/gameweld-deckcheatz-session.py status --appid 3008130
    python3 scripts/gameweld-deckcheatz-session.py verify --appid 3008130

The source GUI's GameWeld shim verification is based on saved Steam config,
which can lag the live Steam client. If it is not verified, the older
**already-configured permanent DeckCheatz** Steam route remains available
and is not automatically switched or described as temporary. No trainer
attachment or gameplay effect is inferred from a Steam association result.

This is still draft development and needs a real one-shot gameplay trial.
Complex wrappers such as MangoHud, GameMode, Gamescope and arbitrary shell
commands are intentionally not merged automatically, because their wrapper
ordering and semantics cannot safely be inferred.

## Experimental Rust native wrapper plan (private development)

The wand-runtime crate now exposes the opt-in Rust API:

- build_native_wrapper_launch_plan(game, steam_root, proton, wrapper, wrapper_log)
- run_native_wrapper_launch_plan(plan, game_install_dir, dry_run)

The builder creates the familiar DeckCheatz -> Proton -> waitforexitandrun ->
game.exe command with existing per-game Steam compatdata, WINEDLLOVERRIDES,
WEMOD_LOG, Steam app IDs and install paths. It is read-only. Unlike the older
heuristic executable search, it refuses multiple plausible EXEs unless
WAND_GAME_EXE is explicitly set to a reviewed path within the game's install.

The Rust runner returns None in dry-run mode, without spawning a process
or writing its own logs. A separately authorized non-dry-run call creates
a unique private log and starts an isolated DeckCheatz process group.
It refuses a detected already-running game. A spawned PID does not prove
Steamworks, overlay, DRM, trainer attachment, or actual gameplay success.

The Rust functions are library APIs, not yet the default GameWeld GUI Play
path. Continue to prefer the user-verified Steam wrapper until a real-game
direct-runtime test has passed. The standalone Python dry-run is currently
available through:

    python3 scripts/gameweld-deckcheatz-autodetect.py --dry-run --appid 3008130

Rust verification in GitHub Actions: cargo test -p wand-runtime --lib.
All checks are based on fake Steam/Proton fixture files; no real game
or Steam Launch Options are edited by these tests.
