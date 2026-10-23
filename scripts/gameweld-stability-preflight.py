#!/usr/bin/env python3
"""Read-only GameWeld 0.7.0 Stable upgrade and release-gate preflight.

Checks only GameWeld's own settings, cached records and assignment metadata.
Does not execute trainers, contact publishers, change settings, or prune mappings.
Export is opt-in and writes only a private report to XDG_STATE_HOME.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from itertools import islice
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

MAX_JSON = 2_000_000
MAX_TSV = 2_000_000
MAX_ROWS = 4096


def xdg(name: str, fallback: str) -> Path:
    return Path(os.environ.get(name) or (Path.home() / fallback))


def safe_file(path: Path, size: int) -> str:
    try:
        if path.is_symlink():
            return 'symlink'
        if not path.exists():
            return 'missing'
        if not path.is_file():
            return 'not-regular'
        if path.stat().st_size > size:
            return 'oversized'
        return 'ok'
    except OSError:
        return 'unreadable'


def read_json(path: Path, size=MAX_JSON):
    status = safe_file(path, size)
    if status != 'ok':
        return status, None
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        return ('ok', doc) if isinstance(doc, dict) else ('invalid-object', None)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return 'malformed', None


def scan():
    cfg = xdg('XDG_CONFIG_HOME', '.config') / 'gameweld'
    cache = xdg('XDG_CACHE_HOME', '.cache') / 'gameweld'
    data = xdg('XDG_DATA_HOME', '.local/share') / 'gameweld'
    issues=[]; evidence={}
    assignments=cfg/'local-trainers.tsv'; astat=safe_file(assignments, MAX_TSV)
    summary=Counter()
    assignments_for_launch=[]
    missing_group=defaultdict(list)
    def platform(key):
        base=key.split(':',1)[0].casefold()
        return {'steam':'Steam','heroic':'Heroic','lutris':'Lutris'}.get(base,'Other')
    def display(value,limit=180):
        # Keep diagnostic content on one Markdown line even if a local filename
        # contains control characters or Markdown punctuation.
        value=''.join(c if 32<=ord(c)<=126 or ord(c)>159 else ' ' for c in str(value))
        return value.replace('\\','\\\\').replace('`','\\`').replace('|','\\|')[:limit]
    if astat=='ok':
        seen={}
        try:
            text=assignments.read_text(encoding='utf-8')
            lines=text.splitlines()
            if len(lines)>MAX_ROWS:
                issues.append('Assignment list exceeds 4096 rows; not fully inspected')
            for num,line in enumerate(lines[:MAX_ROWS],1):
                if not line.strip():continue
                if '\t' not in line:
                    summary['invalid_rows']+=1
                    continue
                key, target=line.split('\t',1)
                if not key.strip() or not target.strip() or not Path(target).is_absolute():
                    summary['invalid_rows']+=1
                    continue
                summary['assignments']+=1
                if key in seen:
                    summary['duplicate_keys']+=1
                seen[key]=num
                p=Path(target)
                if p.is_symlink():
                    summary['symlink_targets']+=1
                    status='SYMLINK — REVIEW'
                elif not p.is_file():
                    summary['missing_targets']+=1
                    status='MISSING'
                    missing_group[str(p)].append(display(key))
                else:
                    status='PRESENT (launch untested)'
                if len(assignments_for_launch)<MAX_ROWS:
                    assignments_for_launch.append({'key':display(key),
                        'platform':platform(key),'trainer_name':display(p.name),
                        'path':display(target,512),'file_status':status})
        except (OSError, UnicodeError):
            astat='unreadable'
    if astat not in ('missing','ok'):
        issues.append(f'Assignment metadata: {astat}')
    if summary['invalid_rows'] or summary['duplicate_keys']:
        issues.append(f'Assignment records need review: {summary["invalid_rows"]} invalid, {summary["duplicate_keys"]} duplicate keys')
    if summary['missing_targets'] or summary['symlink_targets']:
        issues.append(f'Assigned trainer paths need review: {summary["missing_targets"]} missing, {summary["symlink_targets"]} symlinks')
    evidence['assignments']={'status':astat,**{k:int(summary[k]) for k in ('assignments','missing_targets','symlink_targets','invalid_rows','duplicate_keys')},
        'unique_missing_paths':len(missing_group),'missing_groups':[
            {'path':display(path,512),'game_keys':keys} for path,keys in sorted(missing_group.items())],
        'launch_manifest':assignments_for_launch,
        'platform_counts':dict(Counter(r['platform'] for r in assignments_for_launch))}

    pcfg, prefs=read_json(cfg/'update-monitor.json',MAX_JSON)
    if pcfg=='ok':
        if prefs.get('schema')!=1 or type(prefs.get('enabled')) is not bool or prefs.get('daily_budget',12) not in (4,8,12,24,48,96) or type(prefs.get('include_unassigned', True)) is not bool:
            pcfg='invalid-schema'
    if pcfg not in ('missing','ok'):
        issues.append(f'Update monitor preferences: {pcfg}')
    evidence['monitor_preferences']={'status':pcfg, 'budget':prefs.get('daily_budget',12) if pcfg=='ok' else None}
    cstat,cstate=read_json(cache/'update-monitor-state.json',MAX_JSON)
    cached=0
    if cstat=='ok':
        if cstate.get('schema')!=1 or not isinstance(cstate.get('games'),dict):
            cstat='invalid-schema'
        else:
            cached=len(cstate['games'])
            if cached>4096:
                cstat='excessive-games'
    if cstat not in ('missing','ok'):
        issues.append(f'Update monitor cache: {cstat}')
    evidence['monitor_cache']={'status':cstat,'titles':cached}
    repstat=safe_file(cache/'trainer-library-last.tsv',3_000_000)
    if repstat not in ('missing','ok'):
        issues.append(f'Trainer scan cache: {repstat}')
    evidence['trainer_scan']={'status':repstat}
    catstat,catalog=read_json(cfg/'trainer-catalog.json',MAX_JSON)
    catalog_entries=0
    if catstat=='ok':
        if catalog.get('schema') not in (1,2) or not isinstance(catalog.get('entries'),list):
            catstat='invalid-schema'
        else:
            catalog_entries=len(catalog['entries'])
    if catstat not in ('missing','ok'):
        issues.append(f'Imported trainer catalog: {catstat}')
    evidence['catalog']={'status':catstat,'entries':catalog_entries,'publisher_authenticated':False}
    key_stat,keys=read_json(cfg/'trusted-publisher-keys.json',32768)
    if key_stat=='ok' and (keys.get('schema') != 1 or not isinstance(keys.get('keys'),dict)):
        # It is still useful to warn on unexpected schema without modifying it.
        key_stat='unexpected-schema'
    if key_stat not in ('missing','ok'):
        issues.append(f'Pinned-key store: {key_stat}')
    evidence['keys']={'status':key_stat}
    staged=data/'trainers'
    receipts=0
    if staged.is_symlink():
        issues.append('Staging root is a symlink; review manually')
    elif staged.is_dir():
        # No recursion into arbitrary trees: GameWeld stages under bounded per-game dirs.
        try:
            for sub in islice(staged.iterdir(),512):
                if sub.is_symlink():
                    issues.append('Staged trainer directory symlink detected')
                    continue
                if sub.is_dir():
                    p=sub/'receipt.json'
                    st,receipt=read_json(p,8192)
                    if st=='ok':
                        receipts+=1
                        if receipt.get('schema')!=1:
                            issues.append('Staged receipt with unsupported schema detected')
                    elif st!='missing':
                        issues.append(f'Staged receipt: {st}')
        except OSError:
            issues.append('Cannot enumerate staged trainer receipts')
    evidence['staging']={'receipts_seen':receipts,'integrity_checked':False}
    return {'schema':1,'app':'GameWeld','version':'0.7.0','read_only':True,
            'generated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'status':'REVIEW' if issues else 'READY_FOR_FIELD_TEST',
            'issues':sorted(set(issues)),'checks':evidence,
            'limits':['Does not prove Steam/Heroic/Lutris real-game launch success',
                      'Does not authenticate publisher identity or catalog downloads',
                      'Does not hash staged trainer binaries; use Inspect Staged Trainer for integrity']}


def report_markdown(s):
    a=s['checks']['assignments']; m=s['checks']['monitor_cache'];p=s['checks']['monitor_preferences']
    lines=['# GameWeld 0.7.0 Stable — Stability & Field Release Gates','',f'Generated (UTC): {s["generated_utc"]}',
           f'Result: **{s["status"]}**','', '## Existing configuration (read-only)',
           f'- Assignments: {a["assignments"]}; missing paths: {a["missing_targets"]} across {a["unique_missing_paths"]} distinct targets; duplicate keys: {a["duplicate_keys"]}; invalid rows: {a["invalid_rows"]}; symlink paths: {a["symlink_targets"]}',
           f'- Automatic update preferences: {p["status"]}; daily limit: {p["budget"] if p["budget"] is not None else "not configured (default 12)"}',
           f'- Update cache: {m["status"]}; {m["titles"]} game titles',
           f'- Trainer scan cache: {s["checks"]["trainer_scan"]["status"]}',
           f'- Imported catalog: {s["checks"]["catalog"]["status"]} ({s["checks"]["catalog"]["entries"]} entries; **not authenticated**)',
           f'- Local key store: {s["checks"]["keys"]["status"]}',
           f'- Staged receipts detected: {s["checks"]["staging"]["receipts_seen"]} (integrity not checked)', '',
           '## Items needing review']
    lines.extend('- '+v for v in s['issues']) if s['issues'] else lines.append('- No configuration integrity warnings detected')
    if a['missing_groups']:
        lines+=['','## Missing files and affected game IDs']
        for group in a['missing_groups'][:48]:
            lines.append('- `'+group['path']+'` — '+str(len(group['game_keys']))+' assignment(s)')
            for key in group['game_keys'][:12]:
                lines.append('  - `'+key+'`')
    lines += ['', '## Field launch checklist — not automatically verified',
       'Mark these only after a **real game and trainer** were launched on the target machine. File existence and offline unit tests do not prove live compatibility.',
       '']
    if not a['launch_manifest']:
        lines.append('- No current manual assignments to exercise')
    for entry in a['launch_manifest'][:128]:
        lines.append('- [ ] **'+entry['platform']+'** `'+entry['key']+'` — '+entry['trainer_name']+'; '+entry['file_status'])
    if len(a['launch_manifest'])>128:
        lines.append('- … '+str(len(a['launch_manifest'])-128)+' additional mappings omitted from the Markdown checklist; present in JSON')
    lines += ['', '## Remaining release gates'] + ['- '+v for v in s['limits']]
    lines += ['', 'This preflight reads existing files only. Checklist entries are UNVERIFIED until manually tested. Export writes this report to the private GameWeld state directory; no games, trainers or settings are changed.','']
    return '\n'.join(lines)


def export_report(content):
    dest=xdg('XDG_STATE_HOME','.local/state')/'gameweld'/'stability-preflight.md'
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_symlink():
        raise ValueError('Refusing to export through a symlink')
    name=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=dest.parent,prefix='.stability-',delete=False) as fp:
            name=fp.name
            os.fchmod(fp.fileno(),0o600)
            fp.write(content)
            fp.flush();os.fsync(fp.fileno())
        os.replace(name,dest)
    finally:
        if name and os.path.exists(name):os.unlink(name)
    return dest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--export',action='store_true',help='Write one private Markdown report; otherwise inspect only')
    ap.add_argument('--json',action='store_true',help='Machine-readable summary on stdout')
    args=ap.parse_args()
    result=scan()
    if args.export:
        try:
            dest=export_report(report_markdown(result))
        except (OSError,ValueError) as exc:
            print('PREFLIGHT\tERROR\tCould not save report:',str(exc));return 2
        print(f'PREFLIGHT\t{result["status"]}\t{dest}\t{len(result["issues"])} warning(s)')
    elif args.json:
        print(json.dumps(result,indent=2))
    else:
        print(report_markdown(result))
    return 0

if __name__=='__main__':raise SystemExit(main())
