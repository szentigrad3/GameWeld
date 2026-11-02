"""GameWeld command line, optional GUI, and fixed-fixture IPC lab."""
import argparse
import json
import sys
from . import __version__
from .core import installed_games, load_settings
from .diagnostics import game_report
from .ipc import preflight, run_probe


def main(argv=None):
    parser = argparse.ArgumentParser(prog='gameweld')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--steamapps', help='Read-only Steam steamapps location')
    parser.add_argument('--diagnose-appid', type=int)
    parser.add_argument('--ipc-preflight', action='store_true')
    parser.add_argument('--ipc-test', action='store_true', help='Run one owned pinned fixture only')
    parser.add_argument('--consent-owned-fixture', action='store_true', help='Required for --ipc-test')
    parser.add_argument('--fixture', help='Must match the pinned original Win64 v2 SHA-256')
    args = parser.parse_args(argv)
    if args.smoke:
        prefs=load_settings()
        games=installed_games(args.steamapps or prefs['steamapps'])
        print(json.dumps({'operation':'desktop-smoke','version':__version__,
             'installed_games':len(games),'steam_modified':False,
             'game_memory_accessed':False,'trainer_launched':False}))
        return 0
    if args.diagnose_appid is not None:
        prefs=load_settings()
        games=installed_games(args.steamapps or prefs['steamapps'])
        found=next((g for g in games if g['appid']==args.diagnose_appid),None)
        if found is None:
            print(json.dumps({'operation':'gameweld-readonly-game-report','state':'game_not_found',
                              'trainer_launched':False,'game_memory_accessed':False}))
            return 1
        print(json.dumps(game_report(found),sort_keys=True))
        return 0
    if args.ipc_preflight:
        print(json.dumps(preflight(args.fixture),sort_keys=True))
        return 0
    if args.ipc_test:
        report=run_probe(consent=args.consent_owned_fixture,fixture=args.fixture,timeout=75)
        print(json.dumps(report,sort_keys=True))
        return 0 if report.get('state')=='owned_win64_v2_protocol_verified' else 1
    try:
        from .ui import launch
        return launch()
    except (ImportError,ValueError) as exc:
        print('GTK4/PyGObject required. On CachyOS: sudo pacman -S python-gobject gtk4',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
