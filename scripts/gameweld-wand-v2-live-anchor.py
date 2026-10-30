#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only bounded liveness proof for an already correlated Steam/Proton PID.

A stable Linux Wine process is not a Win32 PID or authorization to attach a
trainer. No Steam launch options, processes, prefixes, or files are modified.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
from typing import Callable


def _load_context_module():
    script = Path(__file__).with_name('gameweld-wand-v2-live-context.py')
    spec = importlib.util.spec_from_file_location('gameweld_wand_live_context', script)
    if spec is None or spec.loader is None:
        raise RuntimeError('live_context_module_unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_report(appid: int, pid: int, ticks: int) -> dict:
    return {
        'appid': appid,
        'state': 'not_verified',
        'reason': 'no_observations',
        'anchored_linux_pid': pid,
        'anchored_process_start_ticks': ticks,
        'samples_requested': 0,
        'samples_completed': 0,
        'linux_process_identity_stable': False,
        'same_prefix_wineserver_observed': False,
        'win32_pid_verified': False,
        'exact_runtime_verified': False,
        'game_process_verified': False,
        'monitor_attached': False,
        'trainer_launched': False,
        'trainer_attachment_verified': False,
        'trainer_cleanup_verified': False,
        'steam_configuration_written': False,
        'steam_launch_options_changed': False,
        'game_prefix_modified': False,
        'processes_signalled': 0,
    }


def acquire_fresh_anchor(appid: int, compatdata: Path, game_exe: Path,
                         inspector: Callable | None = None) -> dict:
    """Acquire a new pinned Linux candidate; never trust historic PID values."""
    result = _public_report(appid, 0, 0)
    if inspector is None:
        inspector = _load_context_module().inspect_context
    try:
        obs = inspector(appid, compatdata, game_exe)
    except (OSError, ValueError, RuntimeError):
        result['reason'] = 'initial_inspection_failed'
        return result
    if not isinstance(obs, dict) or obs.get('appid') != appid:
        result['reason'] = 'initial_inspection_invalid'
        return result
    if obs.get('state') != 'linux_game_process_candidate_correlated':
        result['reason'] = 'initial_linux_candidate_not_unique'
        return result
    pid = obs.get('candidate_linux_pid')
    ticks = obs.get('candidate_start_time_ticks')
    if (type(pid) is not int or pid < 1 or type(ticks) is not int or ticks < 1
            or obs.get('game_process_candidate_pids') != [pid]
            or obs.get('exact_prefix_identity_crosschecked') is not True
            or not isinstance(obs.get('wine_server_pids'), list)
            or not obs.get('wine_server_pids')
            or not all(type(x) is int and x > 0 for x in obs['wine_server_pids'])):
        result['reason'] = 'initial_linux_candidate_identity_incomplete'
        return result
    if any(obs.get(k) is True for k in ('exact_runtime_verified', 'game_process_verified',
                                        'monitor_attached', 'trainer_attachment_verified')):
        result['reason'] = 'initial_inspection_crossed_trust_boundary'
        return result
    result['state'] = 'linux_anchor_acquired'
    result['reason'] = 'read_only_anchor_requires_revalidation'
    result['anchored_linux_pid'] = pid
    result['anchored_process_start_ticks'] = ticks
    return result

def verify_anchor(
    appid: int, compatdata: Path, game_exe: Path,
    *, pid: int, start_ticks: int,
    samples: int = 3, interval_ms: int = 400,
    inspector: Callable | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """Read-only bounded inspections; stop immediately when identity changes.

    A PID from a previous session must never be silently replaced with a new
    process with the same executable name. No launch/attach is performed.
    """
    report = _public_report(appid, pid, start_ticks)
    if (any(type(value) is not int for value in (appid, pid, start_ticks, samples, interval_ms))
            or appid < 1 or pid < 1 or start_ticks < 1 or not 1 <= samples <= 30
            or not 0 <= interval_ms <= 2000):
        report['reason'] = 'invalid_anchor_or_sampling_parameters'
        return report
    report['samples_requested'] = samples
    if inspector is None:
        inspector = _load_context_module().inspect_context
    for sample in range(samples):
        try:
            observation = inspector(appid, compatdata, game_exe)
        except (OSError, ValueError, RuntimeError):
            report['reason'] = 'read_only_process_inspection_failed'
            return report
        if not isinstance(observation, dict):
            report['reason'] = 'invalid_inspection_response'
            return report
        if observation.get('appid') != appid:
            report['reason'] = 'inspection_appid_mismatch'
            return report
        if observation.get('state') != 'linux_game_process_candidate_correlated':
            report['reason'] = 'unique_linux_game_candidate_not_present'
            return report
        if observation.get('game_process_candidate_pids') != [pid]:
            report['reason'] = 'candidate_set_not_exactly_anchor'
            return report
        if observation.get('candidate_linux_pid') != pid:
            report['reason'] = 'anchored_linux_pid_changed'
            return report
        if observation.get('candidate_start_time_ticks') != start_ticks:
            report['reason'] = 'anchored_linux_process_replaced_or_restarted'
            return report
        if observation.get('exact_prefix_identity_crosschecked') is not True:
            report['reason'] = 'exact_prefix_identity_not_crosschecked'
            return report
        # This read-only component never accepts Win32/attachment claims.
        if any(observation.get(key) is True for key in (
            'exact_runtime_verified', 'game_process_verified',
            'monitor_attached', 'trainer_attachment_verified',
        )):
            report['reason'] = 'inspection_crossed_unverified_trust_boundary'
            return report
        wine_servers = observation.get('wine_server_pids')
        if (not isinstance(wine_servers, list) or not wine_servers
                or not all(type(x) is int and x > 0 for x in wine_servers)):
            report['reason'] = 'same_prefix_wineserver_not_observed'
            return report
        # These server candidates passed exact AppID and prefix checks within
        # the auditor; they do not prove a Win32 PID or trainer attachment.
        report['samples_completed'] += 1
        report['same_prefix_wineserver_observed'] = True
        if sample + 1 < samples:
            sleeper(interval_ms / 1000)
    report['state'] = 'linux_runtime_anchor_stable'
    report['reason'] = 'windows_process_id_and_trainer_attach_unverified'
    report['linux_process_identity_stable'] = True
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Bounded, read-only GameWeld Proton game PID liveness check')
    p.add_argument('--appid', type=int, required=True)
    p.add_argument('--compatdata', type=Path, required=True)
    p.add_argument('--game-exe', type=Path, required=True)
    p.add_argument('--pid', type=int)
    p.add_argument('--start-ticks', type=int)
    p.add_argument('--samples', type=int, default=3)
    p.add_argument('--interval-ms', type=int, default=400)
    args = p.parse_args(argv)
    if (args.pid is None) != (args.start_ticks is None):
        p.error('--pid and --start-ticks must be supplied together or both omitted')
    if args.pid is None:
        fresh = acquire_fresh_anchor(args.appid, args.compatdata, args.game_exe)
        if fresh['state'] != 'linux_anchor_acquired':
            print(json.dumps(fresh, sort_keys=True))
            return 2
        pid = fresh['anchored_linux_pid']
        ticks = fresh['anchored_process_start_ticks']
    else:
        pid, ticks = args.pid, args.start_ticks
    result = verify_anchor(args.appid, args.compatdata, args.game_exe,
                           pid=pid, start_ticks=ticks,
                           samples=args.samples, interval_ms=args.interval_ms)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['state'] == 'linux_runtime_anchor_stable' else 2


if __name__ == '__main__':
    raise SystemExit(main())
