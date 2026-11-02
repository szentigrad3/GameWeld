"""GameWeld command line, optional GUI, and fixed-fixture IPC lab."""
import argparse
import json
import sys
from . import __version__
from .core import installed_games, load_settings
from .diagnostics import game_report
from .ipc import preflight, run_probe, run_benchmark
from .history import (read_report, record_summary, sanitise_benchmark,
                      history_report, compare_summaries, annotate_summary, annotate_latest, STARTUP_CONTEXTS)
from .startup import compare_startup, startup_trend
from .trainer import inspect_trainer, prepare_trainer, run_trainer, discover_proton, trainer_doctor


def main(argv=None):
    parser = argparse.ArgumentParser(prog='gameweld')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--history', action='store_true', help='Read saved, redacted benchmark summaries')
    parser.add_argument('--review-benchmark', metavar='JSON', help='Read and sanitise one benchmark without saving it')
    parser.add_argument('--record-benchmark', metavar='JSON', help='Explicitly import a benchmark into local history')
    parser.add_argument('--compare-benchmarks', nargs=2, metavar=('OLD','NEW'), help='Read-only startup comparison')
    parser.add_argument('--startup-compare', nargs=2, metavar=('OLD','NEW'),
                        help='Compare verified startup samples without launching Wine')
    parser.add_argument('--startup-trend', action='store_true',
                        help='Read-only session-weighted saved benchmark trend')
    parser.add_argument('--annotate-latest', action='store_true',
                        help='Explicitly label the latest saved benchmark context')
    parser.add_argument('--annotate-benchmark', metavar='JSON',
                        help='Mark an already saved benchmark with its user-observed startup context')
    parser.add_argument('--startup-context', choices=STARTUP_CONTEXTS, default='unclassified',
                        help='User-observed startup context; never an automatic diagnosis')
    parser.add_argument('--save-history', action='store_true', help='Persist sanitised summary after consented benchmark')
    parser.add_argument('--steamapps', help='Read-only Steam steamapps location')
    parser.add_argument('--diagnose-appid', type=int)
    parser.add_argument('--ipc-preflight', action='store_true')
    parser.add_argument('--ipc-test', action='store_true', help='Run one owned pinned fixture only')
    parser.add_argument('--ipc-benchmark', action='store_true', help='Run 1-3 sequential owned fixture sessions')
    parser.add_argument('--runs', type=int, default=2, help='IPC benchmark sessions: 1 to 3')
    parser.add_argument('--timeout', type=int, default=75, help='Per-fixture session timeout: 10 to 120 sec')
    parser.add_argument('--consent-owned-fixture', action='store_true', help='Required for --ipc-test')
    parser.add_argument('--fixture', help='Must match the pinned original Win64 v2 SHA-256')
    parser.add_argument('--trainer-list-proton', action='store_true', help='Read-only installed Proton discovery')
    parser.add_argument('--trainer-doctor', action='store_true', help='Read-only Wine/Proton and game-prefix availability diagnostic')
    parser.add_argument('--trainer-inspect', metavar='EXE', help='Read-only Windows PE and SHA-256 inspection')
    parser.add_argument('--trainer-preview', metavar='EXE', help='Review selected game and trainer before launching')
    parser.add_argument('--trainer-launch', metavar='EXE', help='Launch a personally trusted local trainer with explicit consent')
    parser.add_argument('--trainer-appid', type=int, help='Must be an installed Steam App ID')
    parser.add_argument('--trainer-mode', choices=('isolated', 'proton'), default='isolated')
    parser.add_argument('--trainer-proton', metavar='PATH', help='Exact installed Proton executable for selected game')
    parser.add_argument('--trainer-sha256', metavar='SHA256', help='Expected SHA-256 copied from prior inspection')
    parser.add_argument('--consent-trainer-launch', action='store_true')
    parser.add_argument('--consent-game-prefix', action='store_true', help='I accept that Proton mode can modify existing game prefix')
    parser.add_argument('--trainer-timeout', type=int, default=180, help='Maximum trainer window lifetime, 10..1800 seconds')
    args = parser.parse_args(argv)
    if args.trainer_doctor:
        print(json.dumps(trainer_doctor(appid=args.trainer_appid, mode=args.trainer_mode,
              proton=args.trainer_proton, steamapps=args.steamapps), sort_keys=True))
        return 0
    if args.trainer_list_proton:
        print(json.dumps({'operation': 'trainer-proton-discovery',
                          'candidates': discover_proton(args.steamapps),
                          'game_runtime_match_verified': False}, sort_keys=True))
        return 0
    if args.trainer_inspect or args.trainer_preview or args.trainer_launch:
        if args.trainer_appid is None and not args.trainer_inspect:
            parser.error('--trainer-appid is required for trainer preview or launch')
        try:
            if args.trainer_inspect:
                result = inspect_trainer(args.trainer_inspect)
            elif args.trainer_preview:
                result = prepare_trainer(args.trainer_preview, appid=args.trainer_appid,
                                         mode=args.trainer_mode, proton=args.trainer_proton,
                                         steamapps=args.steamapps)
            else:
                result = run_trainer(args.trainer_launch, appid=args.trainer_appid,
                                     expected_sha256=args.trainer_sha256,
                                     consent=args.consent_trainer_launch,
                                     mode=args.trainer_mode, proton=args.trainer_proton,
                                     consent_game_prefix=args.consent_game_prefix,
                                     steamapps=args.steamapps, timeout=args.trainer_timeout)
        except (OSError, ValueError):
            result = {'operation': 'trainer-launch-or-inspection', 'state': 'trainer_preflight_failed',
                      'trainer_process_started': False, 'raw_paths_disclosed': False}
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get('state') in ('windows_pe_inspected', 'ready_for_explicit_consent',
                                          'trainer_process_exited') and (result.get('exit_code') in (None, 0)) else 1
    if (args.ipc_test or args.ipc_benchmark) and not 10 <= args.timeout <= 120:
        parser.error('--timeout must be between 10 and 120 seconds')
    if args.startup_context != 'unclassified' and not (args.record_benchmark or args.annotate_benchmark or args.annotate_latest or args.save_history):
        parser.error('--startup-context requires import, annotation or --save-history')
    if args.save_history and not args.ipc_benchmark:
        parser.error('--save-history is only valid with --ipc-benchmark')
    if (args.history or args.review_benchmark or args.record_benchmark or
            args.annotate_benchmark or args.annotate_latest or
            args.compare_benchmarks or args.startup_compare or args.startup_trend):
        try:
            if args.history:
                result = history_report()
            elif args.startup_trend:
                result = startup_trend()
            elif args.startup_compare:
                result = compare_startup(read_report(args.startup_compare[0]),
                                         read_report(args.startup_compare[1]))
            elif args.review_benchmark:
                result = read_report(args.review_benchmark)
            elif args.record_benchmark:
                result = record_summary(read_report(args.record_benchmark),
                                        startup_context=args.startup_context)
            elif args.annotate_latest:
                result = annotate_latest(args.startup_context)
            elif args.annotate_benchmark:
                result = annotate_summary(read_report(args.annotate_benchmark), args.startup_context)
            else:
                result = compare_summaries(read_report(args.compare_benchmarks[0]),
                                           read_report(args.compare_benchmarks[1]))
        except (OSError, ValueError):
            print(json.dumps({'operation': 'gameweld-benchmark-history',
                              'state': 'invalid_or_unreadable_report',
                              'trainer_launched': False, 'raw_paths_disclosed': False}))
            return 1
        print(json.dumps(result, sort_keys=True))
        return 0
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
        report=run_probe(consent=args.consent_owned_fixture,fixture=args.fixture,timeout=args.timeout)
        print(json.dumps(report,sort_keys=True))
        return 0 if report.get('state')=='owned_win64_v2_protocol_verified' else 1
    if args.ipc_benchmark:
        try:
            report=run_benchmark(consent=args.consent_owned_fixture,fixture=args.fixture,
                                 timeout=args.timeout,runs=args.runs)
        except ValueError:
            parser.error('--runs must be 1..3 and timeout 10..120')
        if args.save_history and report.get('state')=='isolated_ipc_benchmark_verified':
            try:
                recorded = record_summary(sanitise_benchmark(report), startup_context=args.startup_context)
                report['history_summary_saved'] = recorded['state'] in ('summary_recorded','already_recorded')
            except (OSError, ValueError):
                report['history_summary_saved'] = False
        print(json.dumps(report,sort_keys=True))
        return 0 if report.get('state')=='isolated_ipc_benchmark_verified' else 1
    try:
        from .ui import launch
        return launch()
    except (ImportError,ValueError) as exc:
        print('GTK4/PyGObject required. On CachyOS: sudo pacman -S python-gobject gtk4',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
