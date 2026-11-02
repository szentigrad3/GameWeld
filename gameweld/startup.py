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
    """Aggregates individual successful sessions; avoids averaging report means."""
    history = load_history(path)
    ordered = [(_sessions(e['summary']), e['recorded_at_utc']) for e in history]
    values = [n for group, _ in ordered for n in group]
    if not values:
        state = 'no_successful_sessions'
    elif len(values) < 3:
        state = 'limited_session_sample'
    else:
        state = 'startup_trend_available'
    last = ordered[-1][0] if ordered else []
    prior = [n for group, _ in ordered[:-1] for n in group]
    ratio = round(_mean(last) / _mean(prior), 3) if last and prior and _mean(prior) else None
    return {
        'operation': 'gameweld-startup-trend', 'schema_version': 1,
        'state': state, 'saved_reports': len(history),
        'successful_session_count': len(values),
        'session_weighted_mean_ms': _mean(values), 'session_median_ms': _median(values),
        'session_min_ms': round(min(values), 3) if values else None,
        'session_max_ms': round(max(values), 3) if values else None,
        'latest_report_session_count': len(last), 'latest_vs_earlier_ratio': ratio,
        'latest_comparison_is_single_run': len(last) == 1,
        'cause_verified': False, 'comparison_is_not_causal': True,
        'raw_paths_disclosed': False, 'trainer_launched': False,
        'game_memory_accessed': False, 'detached_helpers_fully_verified': False,
    }
