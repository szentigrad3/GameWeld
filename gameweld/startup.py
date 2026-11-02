"""Read-only startup performance analysis over allowlisted benchmark summaries.

Variations are observations only. Neither the Wine cause nor the machine's load
can be established by benchmark timing alone. No process or filesystem scan.
"""
from __future__ import annotations

import math
import statistics
from .history import load_history, _validated_summary


def _sessions(summary):
    # Every imported object must have a valid canonical hash and allowlisted body.
    validated = _validated_summary(summary)
    return [float(x['startup_ms']) for x in validated['attempts']
            if x['state'] == 'owned_win64_v2_protocol_verified'
            and type(x['startup_ms']) in (int, float) and math.isfinite(x['startup_ms'])]


def _mean(data):
    return round(statistics.mean(data), 3) if data else None


def _median(data):
    return round(statistics.median(data), 3) if data else None


def compare_startup(old, new):
    """Compare two validated reports; never confuse a spike with causal proof."""
    a, b = _sessions(old), _sessions(new)
    am, bm = _mean(a), _mean(b)
    ratio = round(bm / am, 3) if am and bm is not None else None
    delta = round(bm - am, 3) if am is not None and bm is not None else None
    percent = round(100 * (bm - am) / am, 2) if am and bm is not None else None
    if not a or not b:
        state = 'insufficient_measured_sessions'
    elif len(b) < 2:
        state = 'single_new_session_inconclusive'
    elif ratio is not None and (ratio >= 2 or ratio <= .5):
        state = 'large_startup_variation_observed'
    else:
        state = 'startup_samples_compared'
    return {
        'operation': 'gameweld-startup-comparison', 'schema_version': 1,
        'state': state, 'previous_session_count': len(a), 'current_session_count': len(b),
        'previous_mean_ms': am, 'current_mean_ms': bm,
        'previous_median_ms': _median(a), 'current_median_ms': _median(b),
        'previous_min_ms': round(min(a), 3) if a else None,
        'current_max_ms': round(max(b), 3) if b else None,
        'change_ms': delta, 'change_percent': percent, 'ratio': ratio,
        'large_difference_observed': ratio is not None and (ratio >= 2 or ratio <= .5),
        'single_new_session': len(b) == 1,
        'cause_verified': False, 'comparison_is_not_causal': True,
        'game_memory_accessed': False, 'trainer_launched': False,
        'raw_paths_disclosed': False, 'raw_stderr_disclosed': False,
        'detached_helpers_fully_verified': False,
    }


def startup_trend(*, path=None):
    """Session-weighted trends; explicitly tagged installers excluded from baseline.

    Unclassified is a historical/unknown state, not evidence of routine Wine.
    User-supplied context is never treated as a mechanically verified cause.
    """
    history = load_history(path)
    tagged = [(entry['startup_context'], _sessions(entry['summary'])) for entry in history]
    setup_names = {'mono_setup', 'gecko_setup', 'other_setup'}
    all_values = [n for _, sessions in tagged for n in sessions]
    comparable = [n for tag, sessions in tagged if tag not in setup_names for n in sessions]
    tagged_setup = [n for tag, sessions in tagged if tag in setup_names for n in sessions]
    classified_routine = [n for tag, sessions in tagged if tag == 'routine' for n in sessions]
    unclassified = [n for tag, sessions in tagged if tag == 'unclassified' for n in sessions]
    last_tag, last = tagged[-1] if tagged else ('unclassified', [])
    prior = [n for tag, sessions in tagged[:-1] if tag not in setup_names for n in sessions]
    # Do not compare a known setup run to routine-or-unknown sessions.
    compare_latest = last if last_tag not in setup_names else []
    ratio = round(_mean(compare_latest) / _mean(prior), 3) if compare_latest and prior and _mean(prior) else None
    state = ('no_successful_sessions' if not all_values else
             'setup_only_session_history' if not comparable else
             'limited_session_sample' if len(comparable) < 3 else
             'startup_trend_available')
    return {
        'operation': 'gameweld-startup-trend', 'schema_version': 1,
        'state': state, 'saved_reports': len(history),
        'successful_session_count': len(all_values),
        'session_weighted_mean_ms': _mean(all_values),
        'session_median_ms': _median(all_values),
        'session_min_ms': round(min(all_values), 3) if all_values else None,
        'session_max_ms': round(max(all_values), 3) if all_values else None,
        'comparable_session_count': len(comparable),
        'comparable_mean_ms': _mean(comparable),
        'comparable_median_ms': _median(comparable),
        'confirmed_setup_session_count': len(tagged_setup),
        'confirmed_setup_mean_ms': _mean(tagged_setup),
        'routine_labelled_sessions': len(classified_routine),
        'unclassified_sessions': len(unclassified),
        'latest_report_session_count': len(last),
        'latest_report_startup_context': last_tag,
        'latest_vs_earlier_ratio': ratio,
        'latest_comparison_suppressed_setup': bool(last and last_tag in setup_names),
        'latest_comparison_is_single_run': len(last) == 1,
        'cause_verified': False, 'context_is_user_supplied': True,
        'comparison_is_not_causal': True,
        'raw_paths_disclosed': False, 'trainer_launched': False,
        'game_memory_accessed': False, 'detached_helpers_fully_verified': False,
    }
