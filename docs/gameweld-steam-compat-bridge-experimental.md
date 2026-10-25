# GameWeld Steam Compatibility Bridge (experimental)

This remains a development feature, not an RC release. Astrometica + Proton Experimental + WeMod has passed a real in-game test on one CachyOS system; other games and configurations remain unverified.

## Why

The original live launcher starts Proton's Wine binary from the host, but the game runs under Steam Linux Runtime 4. The game's per-AppID D-Bus launch service is not active, so the existing-container method cannot work in the current session. This alternative allows Steam itself to start the game and trainer inside the same chosen Proton runtime from the beginning.

## Game-only test (safe first step)

With Steam closed, from the GameWeld source checkout:

~~~bash
python3 -m unittest discover -s scripts -p 'test_gameweld_steam_compat_bridge.py' -v

python3 scripts/gameweld-steam-compat-bridge.py register \
  --confirm --steam-root /mnt/games/Steam

python3 scripts/gameweld-steam-compat-bridge.py configure \
  --confirm --appid 2353250 \
  --proton "/mnt/games/Steam/steamapps/common/Proton - Experimental/proton" \
  --client "$HOME/.local/share/gameweld/deckcheatz/wemod_data/wemod_bin"
~~~

Without --enable-trainer, the default is game-only. This first experiment checks that Astrometica still launches, not whether WeMod works.

Restart Steam, then under Astrometica → Properties → Compatibility, explicitly choose **GameWeld Bridge (Experimental)**. Start Astrometica normally. No custom Steam launch options are needed.

The installer does not change any game's existing compatibility selection or Steam config. Unconfigured AppIDs fail closed rather than starting the wrong Proton or trainer.

## Optional trainer-enabled experiment (after game-only succeeds)

~~~bash
python3 scripts/gameweld-steam-compat-bridge.py configure \
  --confirm --appid 2353250 \
  --proton "/mnt/games/Steam/steamapps/common/Proton - Experimental/proton" \
  --client "$HOME/.local/share/gameweld/deckcheatz/wemod_data/wemod_bin" \
  --enable-trainer
~~~

The already-patched WeMod installation must exist. This does not patch WeMod, install .NET, or modify the game's Steam launch options or prefix. Astrometica's window and trainer function were confirmed on one system, but trainer functionality in other games remains unverified.

Per-session logs: ~/.local/state/gameweld/steam-bridge-<appid>-*.log

## GameWeld PC2 GUI controls

In the PC2 development GUI, select an installed Steam title and open
**Settings → Advanced Providers**. The primary **Steam Bridge — Game + WeMod**
panel now offers:

- **Check selected game** (read-only; displays saved Proton/client paths)
- **Set up selected game** (confirmed: registers the Bridge and creates a NEW
  game-only configuration, requiring an exact Proton mapping or prefix hint)
- **Enable WeMod next launch** (confirmed, per-game)
- **Disable WeMod next launch** (confirmed, per-game)

First-time setup refuses to overwrite an already-configured title and refuses
to guess between Proton versions. It uses the managed DeckCheatz WeMod
installation and never downloads clients automatically. If exact Proton
evidence is unavailable, use the manual configuration commands above.

After new setup, **restart Steam and select GameWeld Bridge (Experimental)**
under that game's Properties → Compatibility. No Steam Launch Options change.
The UI cannot yet automatically select this compatibility tool for you.

The old direct-host-Wine, white-window GPU-off, and alternate managed launch
experiments are no longer presented as GUI buttons. Advanced patch/restore
and legacy launch-hook cleanup remain under separate collapsed sections.
The low-level diagnostic scripts are retained in the source tree.

Launch the current source GUI with:

~~~bash
bash scripts/run-pc2-source-frontend.sh
~~~

## Main Play with WeMod buttons

Overview → **Play with WeMod** and Library → **Play with WeMod** now use
the same configured Steam Bridge route, rather than attempting DeckCheatz's
older direct Steamless Proton launch. The confirmation explains that Steam's
current per-game Compatibility selection is used.

Before requesting Steam Play, GameWeld requires an explicit per-game Bridge
configuration, `trainer_enabled=true`, a registered Bridge tool and no
already-running same-AppID process. It will not change Steam settings, re-patch
WeMod or spawn a second Proton process. Steam's handoff response proves at most
a same-AppID process association; it does not by itself prove a visible window
or successful trainer attachment.

With Astrometica closed, this is the corresponding explicit CLI smoke test:

~~~bash
python3 scripts/gameweld-steam-compat-bridge.py play --confirm --appid 2353250
~~~

If Steam selects Proton Experimental instead of GameWeld Bridge, the game may
start without WeMod. Confirm the Bridge selection under Steam Properties →
Compatibility. GameWeld does not force or silently rewrite that choice.

## Recovery and limitations

If the game does not start, change its Steam Compatibility selection back to **Proton Experimental**. Do not delete compatdata or run wineserver -k against the game.

The prototype has an opt-in first-time setup flow and per-game trainer controls in the GTK GUI, but it cannot yet choose a Steam Compatibility tool automatically. Astrometica has passed live Steam Runtime 4 and gameplay validation on one host; other games still require testing. Avoid multiplayer and anti-cheat games.
