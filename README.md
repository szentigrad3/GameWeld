# GameWeld

GameWeld is being rebuilt as a **Linux-native GTK4 desktop application**. This is **0.1.0-alpha**, not a released trainer.

The former GTK3/AppImage/WeMod/DeckCheatz source has been removed from the **current main tree**. The previous main commit `5545a3e6464e3044d4699e9ceea98f5aa56e0bd7` remains reachable through Git history, without preserving any legacy feature branches.

## Run on CachyOS

```bash
sudo pacman -S --needed python python-gobject gtk4 git
git clone https://github.com/szentigrad3/GameWeld.git
cd GameWeld
bash run.sh --smoke
bash run.sh
```

For core tests: `python -m unittest discover -s tests -v`.

## Current capabilities

- Read-only Steam installed-game discovery, including secondary libraries.
- GTK4 desktop shell, game search, favourites and read-only game details.
- XDG local preference storage.
- Disabled IPC Lab tab: the tested Batch77 Windows fixture is **not yet integrated** into this clean alpha.

**Not available:** game-memory access, arbitrary trainer execution, live game attachment, Steam launch-option changes, or game Proton-prefix reuse.

This repository is independent of Valve, WeMod, game publishers and third-party trainer providers. MIT license.

See [current status](docs/STATUS.md).