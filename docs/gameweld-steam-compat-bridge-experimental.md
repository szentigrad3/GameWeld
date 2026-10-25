# GameWeld Steam Compatibility Bridge (experimental)

This is a developer-only prototype for Windows games using Steam/Proton, not an RC release. It does not yet prove WeMod rendering or trainer attachment.

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

The already-patched WeMod installation must exist. This does not patch WeMod, install .NET, or modify the game's Steam launch options or prefix. The window and trainer functionality remain unverified.

Per-session logs: ~/.local/state/gameweld/steam-bridge-<appid>-*.log

## Recovery and limitations

If the game does not start, change its Steam Compatibility selection back to **Proton Experimental**. Do not delete compatdata or run wineserver -k against the game.

The prototype is a CLI helper, **not integrated into the GTK GUI yet**. It requires a one-time compatibility-tool selection in Steam, and it has not completed live Steam Runtime 4 or gameplay validation. Avoid multiplayer and anti-cheat games.
