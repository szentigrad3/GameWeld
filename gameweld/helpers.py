"""Bounded, read-only observation of processes using one owned temporary WINEPREFIX.

No PIDs, paths, environment strings or process arguments leave this module in
shareable report fields. Matching is limited to an exact private WINEPREFIX
marker. Reaping arbitrary Wine processes is explicitly never attempted.
"""
import os
import stat
import time

PROC_LIMIT = 4096
ENV_LIMIT = 131072
STAT_LIMIT = 8192
MAX_IDENTITIES = 128


def _read(pid, field, limit):
    fd = os.open(f'/proc/{pid}/{field}', os.O_RDONLY |
                 getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        return os.read(fd, limit + 1)
    finally:
        os.close(fd)


def _proc_identity(pid):
    raw = _read(pid, 'stat', STAT_LIMIT)
    if len(raw) > STAT_LIMIT:
        return None
    end = raw.rfind(b')')
    if end < 0:
        return None
    fields = raw[end+2:].split()
    if len(fields) < 20:
        return None
    try:
        return pid, int(fields[19]), fields[0]  # Linux /proc stat starttime, state
    except ValueError:
        return None


def snapshot_active(prefix):
    """Return ephemeral identities and counters, no host-private values in JSON."""
    if not isinstance(prefix, str) or not os.path.isabs(prefix) or len(prefix) > 4096:
        raise ValueError('invalid_owned_prefix')
    own_uid = os.getuid()
    marked = set()
    unreadable = 0
    truncated = False
    visited = 0
    try:
        listing = os.scandir('/proc')
    except OSError:
        return {'ids': set(), 'unreadable': 0, 'truncated': False, 'available': False}
    marker = b'WINEPREFIX=' + os.fsencode(prefix)
    with listing as entries:
        for item in entries:
            if not item.name.isascii() or not item.name.isdecimal():
                continue
            visited += 1
            if visited > PROC_LIMIT:
                truncated = True
                break
            pid = int(item.name)
            if pid == os.getpid():
                continue
            try:
                if os.stat(item.path, follow_symlinks=False).st_uid != own_uid:
                    continue
                before = _proc_identity(pid)
                if before is None:
                    continue
                env = _read(pid, 'environ', ENV_LIMIT)
                if len(env) > ENV_LIMIT:
                    truncated = True
                    continue
                after = _proc_identity(pid)
                if before is None or after is None or after[:2] != before[:2]:
                    continue
                if marker in env.split(b'\0'):
                    if len(marked) >= MAX_IDENTITIES:
                        truncated = True
                        break
                    marked.add((pid, before[1]))
            except (FileNotFoundError, ProcessLookupError):
                continue
            except (OSError, ValueError):
                unreadable += 1
    return {'ids': marked, 'unreadable': unreadable,
            'truncated': truncated, 'available': True}


def identity_states(identities):
    if not isinstance(identities, (set, frozenset)) or len(identities) > MAX_IDENTITIES:
        raise ValueError('invalid_identity_set')
    result = {'gone': 0, 'live': 0, 'zombie': 0, 'unknown': 0}
    for pid, birth in identities:
        try:
            now = _proc_identity(pid)
        except (FileNotFoundError, ProcessLookupError):
            result['gone'] += 1
            continue
        except OSError:
            result['unknown'] += 1
            continue
        if now is None:
            result['unknown'] += 1
        elif now[1] != birth:
            result['gone'] += 1  # PID recycled; prior identity is absent
        elif now[2] in (b'X', b'x', b'Z'):
            result['zombie'] += 1
        elif now[2] in (b'R', b'S', b'D', b'T', b't', b'I', b'P'):
            result['live'] += 1
        else:
            result['unknown'] += 1
    return result


def review(active):
    """Two post-exit reads; only previously observed exact-prefix identities."""
    if active is None:
        return {'state': 'not_observed', 'observed_identities': 0,
                'observed_identities_absent_twice': False,
                'all_detached_helpers_reaped_verified': False,
                'raw_process_details_disclosed': False}
    marked = active['ids']
    first = identity_states(marked)
    time.sleep(0.12)
    second = identity_states(marked)
    absent = (bool(marked) and all(obs['gone'] == len(marked)
                                  for obs in (first, second)))
    state = ('previously_observed_identities_absent_twice' if absent else
             'no_marked_identities_observed' if not marked else
             'observed_identities_still_present_or_unknown')
    return {'state': state, 'observed_identities': len(marked),
            'active_census_env_unreadable': active['unreadable'],
            'active_census_truncated': active['truncated'],
            'active_census_available': active['available'],
            'post_exit_identity_observations': [first, second],
            'observed_identities_absent_twice': absent,
            'unseen_helpers_not_excluded': True,
            'all_detached_helpers_reaped_verified': False,
            'raw_process_details_disclosed': False}
