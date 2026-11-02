"""Launch the GameWeld GTK4 alpha or run its headless smoke check."""
import argparse
import json
import sys
from . import __version__
from .core import installed_games, load_settings

def main(argv=None):
    parser = argparse.ArgumentParser(prog="gameweld")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--steamapps")
    args = parser.parse_args(argv)
    if args.smoke:
        prefs = load_settings()
        games = installed_games(args.steamapps or prefs["steamapps"])
        print(json.dumps({"operation": "desktop-smoke", "version": __version__,
                          "installed_games": len(games), "steam_modified": False,
                          "trainer_launched": False, "game_memory_accessed": False}))
        return 0
    try:
        from .ui import launch
        return launch()
    except (ImportError, ValueError) as exc:
        print("GTK4/PyGObject required: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
