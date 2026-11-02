"""Privacy-minimised, local IPC benchmark summaries.

Only predefined numeric metrics and state names survive ingestion. Never persist
fixture paths, process identities, Wine stderr, env vars, or challenge strings.
All writes are explicit and owned by the current desktop user.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import stat
from pathlib import Path
from .core import read_file

SCHEMA = 1
MAX_STORE = 128 * 1024
MAX_REPORT = 128 * 1024
MAX_ENTRIES = 64
STARTUP_CONTEXTS = ('unclassified', 'routine', 'mono_setup', 'gecko_setup', 'other_setup')

def validate_context(value):
    if type(value) is not str or value not in STARTUP_CONTEXTS:
        raise ValueError('invalid_startup_context')
    return value

VALID_STATES = frozenset(('isolated_ipc_benchmark_verified',
                          'isolated_ipc_benchmark_failed',
                          'isolated_ipc_benchmark_cancelled', 'consent_required'))
VALID_ATTEMPTS = frozenset(('owned_win64_v2_protocol_verified',
                            'owned_win64_v2_protocol_failed',
                            'consent_required', 'fixture_integrity_failed',
                            'system_wine_unavailable'))
VALID_ERR = frozenset(('none', 'not_started', 'timeout', 'cancelled',
                       'protocol_incomplete', 'unexpected_protocol_response',
                       'stdin_unavailable', 'stdout_limit', 'stderr_limit',
                       'fixture_or_launcher_error'))


def history_path():
    xdg = os.environ.get('XDG_STATE_HOME', '')
    root = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / '.local/state'
    return root / 'gameweld' / 'benchmarks.json'


def _metric(value):
    if type(value) not in (int, float):
        return None
    if not math.isfinite(value) or not 0 <= value <= 300000:
        return None
    return round(float(value), 3)


def _count(value, bound):
    return type(value) is int and 0 <= value <= bound


def sanitise_benchmark(report):
    """Validate an untrusted report and retain *only* a compact allowlist."""
    if not isinstance(report, dict) or report.get('operation') != 'gameweld-ipc-benchmark':
        raise ValueError('not_a_gameweld_benchmark')
    if report.get('schema_version') != 1 or type(report.get('state')) is not str or report['state'] not in VALID_STATES:
        raise ValueError('invalid_benchmark_schema_or_state')
    requested = report.get('runs_requested')
    attempts = report.get('attempts')
    if not _count(requested, 3) or requested < 1 or not isinstance(attempts, list) or len(attempts) > requested:
        raise ValueError('invalid_benchmark_attempt_count')
    if report.get('runs_completed') != len(attempts):
        raise ValueError('inconsistent_benchmark_attempt_count')
    clean = []
    for a in attempts:
        if not isinstance(a, dict) or type(a.get('state')) is not str or a['state'] not in VALID_ATTEMPTS:
            raise ValueError('invalid_benchmark_attempt')
        state = a['state']
        if state == 'owned_win64_v2_protocol_verified' and not (
            a.get('ready_verified') is True and a.get('ping_pong_verified') is True and
            a.get('status_verified') is True and a.get('stop_ack_verified') is True and
            a.get('launcher_exit_zero') is True and a.get('owned_launcher_reaped') is True and
            a.get('temporary_prefix_cleanup_verified') is True):
            raise ValueError('unsubstantiated_success')
        timings = a.get('roundtrip_ms', {})
        if not isinstance(timings, dict):
            raise ValueError('invalid_roundtrip')
        helper = a.get('observed_helper_review', {})
        if helper is None:
            helper = {}
        if not isinstance(helper, dict):
            raise ValueError('invalid_helper_review')
        observed = helper.get('observed_identities', 0)
        if not _count(observed, 128):
            observed = 0
        clean.append({
            'state': state,
            'startup_ms': _metric(a.get('startup_elapsed_ms')),
            'session_ms': _metric(a.get('session_elapsed_ms')),
            'ping_ms': _metric(timings.get('ping')),
            'status_ms': _metric(timings.get('status')),
            'stop_ms': _metric(timings.get('stop')),
            'observed_identities': observed,
            'observed_absent_twice': helper.get('observed_identities_absent_twice') is True,
            'error_category': a.get('error_category') if type(a.get('error_category')) is str and a['error_category'] in VALID_ERR else 'other',
        })
    verified = len(clean) == requested and requested > 0 and all(
        a['state'] == 'owned_win64_v2_protocol_verified' for a in clean)
    if (report['state'] == 'isolated_ipc_benchmark_verified') != verified:
        raise ValueError('inconsistent_benchmark_success')
    starts = [a['startup_ms'] for a in clean if a['startup_ms'] is not None]
    summary = {
        'schema_version': SCHEMA, 'state': report['state'],
        'runs_requested': requested, 'runs_completed': len(clean),
        'successful_runs': sum(a['state'] == 'owned_win64_v2_protocol_verified' for a in clean),
        'startup_mean_ms': round(sum(starts)/len(starts), 3) if starts else None,
        'startup_min_ms': min(starts) if starts else None,
        'startup_max_ms': max(starts) if starts else None,
        'attempts': clean,
        'trainer_launched': False, 'game_memory_accessed': False,
        'detached_helpers_fully_verified': False,
    }
    encoded = json.dumps(summary, sort_keys=True, separators=(',', ':')).encode()
    summary['id'] = hashlib.sha256(encoded).hexdigest()[:20]
    return summary


def read_report(path):
    try:
        report = json.loads(read_file(Path(path), MAX_REPORT))
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('unreadable_or_invalid_benchmark_file') from exc
    return sanitise_benchmark(report)


def _validated_summary(summary):
    """Regenerate exact allowlisted bytes; reject unknown nested history keys."""
    if not isinstance(summary, dict) or set(summary) != {
        'schema_version', 'state', 'runs_requested', 'runs_completed',
        'successful_runs', 'startup_mean_ms', 'startup_min_ms',
        'startup_max_ms', 'attempts', 'trainer_launched',
        'game_memory_accessed', 'detached_helpers_fully_verified', 'id'}:
        raise ValueError('unknown_summary_fields')
    if summary['schema_version'] != SCHEMA or not isinstance(summary['attempts'], list):
        raise ValueError('invalid_stored_summary')
    reconstructed = []
    for attempt in summary['attempts']:
        if not isinstance(attempt, dict) or set(attempt) != {
            'state', 'startup_ms', 'session_ms', 'ping_ms', 'status_ms',
            'stop_ms', 'observed_identities', 'observed_absent_twice',
            'error_category'}:
            raise ValueError('unexpected_stored_attempt')
        good = attempt['state'] == 'owned_win64_v2_protocol_verified'
        reconstructed.append({
            'state': attempt['state'],
            'ready_verified': good, 'ping_pong_verified': good,
            'status_verified': good, 'stop_ack_verified': good,
            'launcher_exit_zero': good, 'owned_launcher_reaped': good,
            'temporary_prefix_cleanup_verified': good,
            'startup_elapsed_ms': attempt['startup_ms'],
            'session_elapsed_ms': attempt['session_ms'],
            'roundtrip_ms': {'ping': attempt['ping_ms'],
                             'status': attempt['status_ms'],
                             'stop': attempt['stop_ms']},
            'observed_helper_review': {
                'observed_identities': attempt['observed_identities'],
                'observed_identities_absent_twice': attempt['observed_absent_twice']},
            'error_category': attempt['error_category'],
        })
    canonical = sanitise_benchmark({
        'operation': 'gameweld-ipc-benchmark', 'schema_version': SCHEMA,
        'state': summary['state'], 'runs_requested': summary['runs_requested'],
        'runs_completed': summary['runs_completed'], 'attempts': reconstructed})
    if canonical != summary:
        raise ValueError('stored_history_integrity_failed')
    return canonical


def _validate_stored(item):
    if not isinstance(item, dict) or not {'recorded_at_utc', 'summary'} <= set(item) or (set(item) - {'recorded_at_utc', 'summary', 'startup_context'}):
        raise ValueError('invalid_history_entry')
    context = validate_context(item.get('startup_context', 'unclassified'))
    stamp = item['recorded_at_utc']
    if not isinstance(stamp, str) or len(stamp) > 40:
        raise ValueError('invalid_history_timestamp')
    try:
        moment = dt.datetime.fromisoformat(stamp)
        if moment.tzinfo is None:
            raise ValueError('timestamp_without_timezone')
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid_history_timestamp') from exc
    return {'recorded_at_utc': stamp, 'summary': _validated_summary(item['summary']),
            'startup_context': context}


def load_history(path=None):
    path = Path(path) if path is not None else history_path()
    try:
        content = json.loads(read_file(path, MAX_STORE))
    except FileNotFoundError:
        return []
    except (OSError, TypeError, ValueError, UnicodeError) as exc:
        raise ValueError('history_file_unreadable') from exc
    if not isinstance(content, dict) or content.get('schema_version') != SCHEMA:
        raise ValueError('invalid_history_schema')
    entries = content.get('entries')
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError('invalid_history_entries')
    return [_validate_stored(entry) for entry in entries]


def _secure_write(path, payload):
    if len(payload) > MAX_STORE:
        raise ValueError('history_storage_limit')
    parent = path.parent
    if parent.is_symlink() or path.is_symlink():
        raise ValueError('history_symlink_rejected')
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if parent.is_symlink() or path.is_symlink():
        raise ValueError('history_symlink_rejected')
    # Refuse replacing anything other than a regular, current-user-owned file.
    if path.exists():
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise ValueError('history_file_not_owned_regular')
    tmp = parent / ('.history-' + os.urandom(12).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError('history_symlink_rejected')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def record_summary(summary, *, path=None, startup_context='unclassified'):
    startup_context = validate_context(startup_context)
    summary = _validated_summary(summary)
    path = Path(path) if path is not None else history_path()
    entries = load_history(path)
    if any(e['summary']['id'] == summary['id'] for e in entries):
        return {'state': 'already_recorded', 'history_count': len(entries), 'id': summary['id']}
    entry = {'recorded_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
             'summary': summary, 'startup_context': startup_context}
    entries = (entries + [entry])[-MAX_ENTRIES:]
    payload = (json.dumps({'schema_version': SCHEMA, 'entries': entries},
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    _secure_write(path, payload)
    return {'state': 'summary_recorded', 'history_count': len(entries), 'id': summary['id']}


def annotate_summary(summary, startup_context, *, path=None):
    """Change an explicit human-supplied startup context, not timing or hash.

    The exact validated report ID must exist. No loose substring or file names
    are stored. Historic entries without context are supported unchanged.
    """
    context = validate_context(startup_context)
    valid = _validated_summary(summary)
    path = Path(path) if path is not None else history_path()
    entries = load_history(path)
    matched = 0
    for entry in entries:
        if entry['summary']['id'] == valid['id']:
            entry['startup_context'] = context
            matched += 1
    if matched != 1:
        return {'operation': 'gameweld-history-annotation', 'schema_version': 1,
                'state': 'summary_not_recorded', 'startup_context': context,
                'raw_paths_disclosed': False, 'trainer_launched': False}
    payload = (json.dumps({'schema_version': SCHEMA, 'entries': entries},
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    _secure_write(path, payload)
    return {'operation': 'gameweld-history-annotation', 'schema_version': 1,
            'state': 'context_recorded', 'id': valid['id'],
            'startup_context': context, 'cause_verified': False,
            'raw_paths_disclosed': False, 'trainer_launched': False}



def annotate_latest(startup_context, *, path=None):
    """Explicitly label the newest saved benchmark; never infer from its timing."""
    context = validate_context(startup_context)
    path = Path(path) if path is not None else history_path()
    entries = load_history(path)
    if not entries:
        return {'operation': 'gameweld-history-annotation', 'schema_version': 1,
                'state': 'no_saved_benchmarks', 'startup_context': context,
                'raw_paths_disclosed': False, 'trainer_launched': False}
    entries[-1]['startup_context'] = context
    payload = (json.dumps({'schema_version': SCHEMA, 'entries': entries},
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    _secure_write(path, payload)
    return {'operation': 'gameweld-history-annotation', 'schema_version': 1,
            'state': 'context_recorded', 'id': entries[-1]['summary']['id'],
            'startup_context': context, 'cause_verified': False,
            'raw_paths_disclosed': False, 'trainer_launched': False}


def history_report(*, path=None):
    entries = load_history(path)
    all_sessions = [attempt['startup_ms'] for entry in entries
                    for attempt in entry['summary']['attempts']
                    if attempt['state'] == 'owned_win64_v2_protocol_verified'
                    and type(attempt['startup_ms']) in (int,float)]
    means = [e['summary'].get('startup_mean_ms') for e in entries]
    means = [m for m in means if type(m) in (int,float) and math.isfinite(m)]
    return {'operation': 'gameweld-benchmark-history', 'schema_version': SCHEMA,
            'state': 'history_loaded', 'record_count': len(entries),
            'success_count': sum(e['summary'].get('state')=='isolated_ipc_benchmark_verified' for e in entries),
            'startup_mean_of_recorded_sessions_ms': round(sum(means)/len(means), 2) if means else None,
            'startup_session_count': len(all_sessions),
            'contexts': {context: sum(e['startup_context'] == context for e in entries)
                         for context in STARTUP_CONTEXTS},
            'startup_weighted_mean_ms': round(sum(all_sessions)/len(all_sessions), 2) if all_sessions else None,
            'records': [{'recorded_at_utc': e['recorded_at_utc'],
                         'id': e['summary']['id'], 'state': e['summary']['state'],
                         'runs_completed': e['summary']['runs_completed'],
                         'startup_context': e['startup_context'],
                         'startup_mean_ms': e['summary'].get('startup_mean_ms')}
                        for e in entries],
            'raw_paths_disclosed': False, 'trainer_launched': False,
            'game_memory_accessed': False, 'detached_helpers_fully_verified': False}


def compare_summaries(left, right):
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError('invalid_comparison')
    a, b = left.get('startup_mean_ms'), right.get('startup_mean_ms')
    if (a is not None and _metric(a) is None) or (b is not None and _metric(b) is None):
        raise ValueError('invalid_comparison_metric')
    difference = round(b-a, 3) if type(a) in (int,float) and type(b) in (int,float) else None
    return {'operation': 'gameweld-benchmark-comparison', 'schema_version': SCHEMA,
            'state': 'comparison_ready', 'old_mean_ms': a, 'new_mean_ms': b,
            'change_ms': difference, 'faster': difference < 0 if difference is not None else None,
            'comparison_is_not_causal': True, 'raw_paths_disclosed': False,
            'game_memory_accessed': False, 'trainer_launched': False}
