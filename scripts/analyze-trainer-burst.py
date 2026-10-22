#!/usr/bin/env python3
import argparse
import ast
import collections
import pathlib
import re

EPOCH_RE = re.compile(r'^(?P<t>[0-9.]+) TRAINER_EPOCH(?: .*baseline_threads=(?P<n>\S+))?')
PEAK_RE = re.compile(r'^(?P<t>[0-9.]+) BURST_PEAK threads=(?P<n>\d+) delta=(?P<d>-?\d+)')
REC_RE = re.compile(r'^(?P<t>[0-9.]+) BURST_RECOVERED threads=(?P<n>\d+) peak=(?P<p>\d+) duration=(?P<d>[0-9.]+)')
THREAD_ADD_RE = re.compile(r'^(?P<t>[0-9.]+) THREAD_ADD tid=(?P<tid>\d+) comm=(?P<comm>.+?) state=(?P<state>.+?) wchan=(?P<wchan>.+)$')
THREAD_REM_RE = re.compile(r'^(?P<t>[0-9.]+) THREAD_REMOVE tid=(?P<tid>\d+) comm=(?P<comm>.+?) last_state=(?P<state>.+?) lifetime=(?P<life>\S+)$')
MAP_ADD_RE = re.compile(r'^(?P<t>[0-9.]+) BURST_MAP_ADD (?P<line>.+)$')
MAP_REM_RE = re.compile(r'^(?P<t>[0-9.]+) BURST_MAP_REMOVE (?P<line>.+)$')
MAP_LINE_RE = re.compile(r'^(?P<addr>[0-9a-fA-F]+-[0-9a-fA-F]+)\s+(?P<perms>\S+)\s+(?P<offset>\S+)\s+(?P<dev>\S+)\s+(?P<inode>\S+)(?:\s+(?P<path>.*))?$')
THREADS_RE = re.compile(r'^(?P<t>[0-9.]+) THREADS (?P<a>\d+|\?)->(?P<b>\d+|\?)')
INITIAL_RE = re.compile(r'^initial_threads=(?P<n>\d+)$')


def unquote_repr(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        return s


def parse_map(line):
    m = MAP_LINE_RE.match(line)
    if not m:
        return None
    d = m.groupdict()
    d['path'] = d.get('path') or ''
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trace')
    args = ap.parse_args()
    lines = pathlib.Path(args.trace).read_text(errors='replace').splitlines()

    epoch = None
    baseline = None
    peaks = []
    recovered = None
    adds = []
    removes = []
    map_adds = []
    map_removes = []
    old_thread_transitions = []
    initial_threads = None

    for raw in lines:
        m = INITIAL_RE.match(raw)
        if m:
            initial_threads = int(m.group('n'))
            if baseline is None:
                baseline = initial_threads
            continue
        m = EPOCH_RE.match(raw)
        if m:
            epoch = float(m.group('t'))
            try: baseline = int(m.group('n')) if m.group('n') else baseline
            except Exception: pass
            continue
        m = PEAK_RE.match(raw)
        if m:
            peaks.append((float(m.group('t')), int(m.group('n')), int(m.group('d'))))
            continue
        m = REC_RE.match(raw)
        if m:
            recovered = (float(m.group('t')), int(m.group('n')), int(m.group('p')), float(m.group('d')))
            continue
        m = THREAD_ADD_RE.match(raw)
        if m:
            adds.append((float(m.group('t')), int(m.group('tid')), unquote_repr(m.group('comm')), unquote_repr(m.group('state')), unquote_repr(m.group('wchan'))))
            continue
        m = THREAD_REM_RE.match(raw)
        if m:
            removes.append((float(m.group('t')), int(m.group('tid')), unquote_repr(m.group('comm')), unquote_repr(m.group('state')), m.group('life')))
            continue
        m = MAP_ADD_RE.match(raw)
        if m:
            rec = parse_map(m.group('line'))
            if rec: map_adds.append((float(m.group('t')), rec))
            continue
        m = MAP_REM_RE.match(raw)
        if m:
            rec = parse_map(m.group('line'))
            if rec: map_removes.append((float(m.group('t')), rec))
            continue
        m = THREADS_RE.match(raw)
        if m:
            old_thread_transitions.append((float(m.group('t')), m.group('a'), m.group('b')))

    print('Wand Native trainer-init burst analysis')
    print(f'trace={args.trace}')
    print(f'trainer_epoch={epoch if epoch is not None else "not-seen"}')
    print(f'baseline_threads={baseline if baseline is not None else "unknown"}')
    if peaks:
        best = max(peaks, key=lambda x: x[1])
        print(f'peak_threads={best[1]} peak_time={best[0]:.3f} delta={best[2]}')
    elif old_thread_transitions:
        vals = []
        for _, a, b in old_thread_transitions:
            for x in (a, b):
                if x.isdigit(): vals.append(int(x))
        print(f'peak_threads={max(vals) if vals else "unknown"} source=legacy_THREADS')
    else:
        print('peak_threads=not-seen')
    if recovered:
        print(f'recovered_time={recovered[0]:.3f} recovered_threads={recovered[1]} duration={recovered[3]:.3f}')
    elif epoch is not None and baseline is not None and old_thread_transitions:
        legacy_recovery = next(((t, int(b)) for t, a, b in old_thread_transitions if b.isdigit() and int(b) <= baseline and t > epoch), None)
        if legacy_recovery:
            print(f'recovered_time={legacy_recovery[0]:.3f} recovered_threads={legacy_recovery[1]} duration={legacy_recovery[0]-epoch:.3f} source=legacy_THREADS')
        else:
            print('recovered_time=not-seen')
    else:
        print('recovered_time=not-seen')

    print('\n===== transient thread identities =====')
    if adds:
        counts = collections.Counter(x[2] for x in adds)
        for comm, count in counts.most_common():
            print(f'{count:4d} {comm}')
        print(f'total_adds={len(adds)} total_removes={len(removes)}')
    else:
        print('No per-TID identities in this trace (requires 0.1.38+).')

    print('\n===== burst map additions =====')
    if map_adds:
        path_counts = collections.Counter(rec['path'] or '<anonymous>' for _, rec in map_adds)
        for path, count in path_counts.most_common(40):
            print(f'{count:4d} {path}')
        anon_exec = sum(1 for _, r in map_adds if not r['path'] and 'x' in r['perms'])
        file_exec = sum(1 for _, r in map_adds if r['path'] and 'x' in r['perms'])
        print(f'total_map_adds={len(map_adds)} total_map_removes={len(map_removes)} anonymous_exec_adds={anon_exec} file_exec_adds={file_exec}')
    else:
        print('No full burst map deltas in this trace (requires 0.1.38+).')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
