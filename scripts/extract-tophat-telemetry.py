#!/usr/bin/env python3
import argparse
import hashlib
import os
import pathlib
import re
import zipfile
from datetime import datetime, timezone

ASCII_RE = re.compile(rb'[\x20-\x7e]{4,}')
UTF16_RE = re.compile(rb'(?:[\x20-\x7e]\x00){4,}')
DIAG_RE = re.compile(
    r'(error|fail|failed|failure|exception|unsupported|denied|invalid|abort|crash|wine|proton|'
    r'inject|injection|trainer|plugin|hook|attach|process|thread|dll|module|loader|loadlibrary|'
    r'ntstatus|status|win32|kernel|telemetry|trace|tophat|contract|lua|capture|security|access)',
    re.I,
)
SENSITIVE_RE = re.compile(r'(?i)(authorization|bearer|access[_ -]?token|refresh[_ -]?token|password|secret)(\s*[:=]\s*)(\S+)')


def parse_iso(value):
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return None


def trace_value(lines, key):
    prefix = key + '='
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def prefix_from_trainerlib(value):
    if not value:
        return None
    p = pathlib.Path(value)
    parts = p.parts
    for i, part in enumerate(parts):
        if part == 'pfx':
            return pathlib.Path(*parts[: i + 1])
    return None


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def printable_strings(data):
    out = []
    seen = set()
    for m in ASCII_RE.finditer(data):
        s = m.group().decode('ascii', 'replace').strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    for m in UTF16_RE.finditer(data):
        try:
            s = m.group().decode('utf-16le', 'replace').strip()
        except Exception:
            continue
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def redact(s):
    return SENSITIVE_RE.sub(lambda m: m.group(1) + m.group(2) + '<redacted>', s)


def select_files(prefix, start_ts, end_ts):
    roots = []
    users = prefix / 'drive_c' / 'users'
    if users.is_dir():
        roots.extend(users.glob('*/AppData/Local/Wand/logs/tophat'))
    files = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.iterdir():
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if start_ts is not None and st.st_mtime < start_ts - 15:
                continue
            if end_ts is not None and st.st_mtime > end_ts + 120:
                continue
            files.append((st.st_mtime, p))
    if not files:
        for root in roots:
            if root.is_dir():
                for p in root.iterdir():
                    if p.is_file():
                        try:
                            files.append((p.stat().st_mtime, p))
                        except OSError:
                            pass
        files.sort(reverse=True)
        files = files[:6]
    else:
        files.sort()
    return [p for _, p in files]


def main():
    ap = argparse.ArgumentParser(description='Extract bounded, read-only diagnostics from Tophat OTLP telemetry files.')
    ap.add_argument('--trace', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--bundle')
    ap.add_argument('--max-diagnostic-strings', type=int, default=500)
    ap.add_argument('--max-context-strings', type=int, default=120)
    args = ap.parse_args()

    trace = pathlib.Path(args.trace)
    report = pathlib.Path(args.report)
    lines = trace.read_text(errors='replace').splitlines()
    trainerlib = trace_value(lines, 'trainerlib')
    prefix = prefix_from_trainerlib(trainerlib)
    wall_start = parse_iso(trace_value(lines, 'wall_start') or '')
    wall_end = parse_iso(trace_value(lines, 'wall_end') or '')

    report.parent.mkdir(parents=True, exist_ok=True)
    selected = select_files(prefix, wall_start, wall_end) if prefix else []

    with report.open('w', encoding='utf-8') as out:
        out.write('Wand Native Tophat telemetry extraction\n')
        out.write(f'trace={trace}\n')
        out.write(f'prefix={prefix if prefix else "unresolved"}\n')
        out.write(f'wall_start={trace_value(lines, "wall_start") or "unknown"}\n')
        out.write(f'wall_end={trace_value(lines, "wall_end") or "unknown"}\n')
        out.write(f'files_selected={len(selected)}\n\n')

        if not selected:
            out.write('NO_TOPHAT_TELEMETRY_FILES_FOUND\n')

        for idx, p in enumerate(selected, 1):
            try:
                data = p.read_bytes()
                st = p.stat()
            except OSError as exc:
                out.write(f'===== file {idx} read error =====\npath={p}\nerror={exc}\n\n')
                continue
            all_strings = printable_strings(data)
            diag = [redact(x) for x in all_strings if DIAG_RE.search(x)]
            context = [redact(x) for x in all_strings if not DIAG_RE.search(x)]
            out.write(f'===== file {idx} =====\n')
            out.write(f'path={p}\n')
            out.write(f'size={len(data)}\n')
            out.write(f'mtime={datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()}\n')
            out.write(f'sha256={sha256(p)}\n')
            out.write(f'printable_strings={len(all_strings)}\n')
            out.write(f'diagnostic_strings={len(diag)}\n')
            out.write('--- diagnostic strings ---\n')
            if not diag:
                out.write('NONE\n')
            for item in diag[: args.max_diagnostic_strings]:
                out.write(item[:2000].replace('\n', '\\n') + '\n')
            if len(diag) > args.max_diagnostic_strings:
                out.write(f'... truncated {len(diag)-args.max_diagnostic_strings} diagnostic strings ...\n')
            out.write('--- first non-diagnostic strings ---\n')
            for item in context[: args.max_context_strings]:
                out.write(item[:1000].replace('\n', '\\n') + '\n')
            out.write('\n')

    if args.bundle and selected:
        bundle = pathlib.Path(args.bundle)
        bundle.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(report, arcname=report.name)
            for p in selected:
                # Keep the account directory in the archive name to distinguish
                # steamuser/szentigrade telemetry without exposing the host prefix.
                user = 'unknown-user'
                parts = p.parts
                try:
                    ui = parts.index('users')
                    user = parts[ui + 1]
                except Exception:
                    pass
                zf.write(p, arcname=f'raw/{user}/{p.name}')
    print(report)
    if args.bundle and pathlib.Path(args.bundle).is_file():
        print(args.bundle)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
