#!/usr/bin/env python3
"""GameWeld 0.7.0 RC4.2: local filename evidence and advisory compatibility comparison.

A publisher search match is never a version comparison. Installed/update comparisons
are allowed only for GameWeld's own checksum-verified receipt and the same provider.
No trainer is downloaded, executed, replaced or reassigned by this module.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time

MODULE = Path(__file__).with_name('gameweld-trainer-updates.py')
spec = importlib.util.spec_from_file_location('gameweld_updates', MODULE)
updates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updates)
MAX_GAMES = 256
DAILY_GAME_BUDGET = 12
ALLOWED_BUDGETS = (4, 8, 12, 24, 48, 96)
BATCH_LIMIT = 6
CHECK_INTERVAL = 24 * 3600
MAX_AGE = 90 * 24 * 3600
MANAGER_RECHECK = 6 * 3600
RECOVERY_DAILY_LIMIT = 4   # Metadata-only, per day, independent of discovery budget.
RECOVERY_MIN_INTERVAL = 6 * 3600
MANAGER_NAMES = {'hextrainer.exe':'HexTrainer', 'aurora.exe':'Cheat Happens Aurora',
                 'cheatevolution.exe':'Cheat Evolution', 'wand.exe':'Wand', 'wemod.exe':'WeMod'}
VERSION_PATTERN = re.compile(r'^\d+(?:\.\d+){1,4}$')


def locations():
    cfg = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'gameweld' / 'update-monitor.json'
    cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'gameweld' / 'update-monitor-state.json'
    lock = cache.with_name('update-monitor.lock')
    return cfg, cache, lock


def read_json(path, default):
    if not path.is_file():
        return default
    if path.is_symlink() or path.stat().st_size > 1_000_000:
        raise updates.UpdateError('Update monitor file is unsafe or too large')
    try:
        result = json.loads(path.read_text('utf-8'))
    except (UnicodeError, ValueError):
        raise updates.UpdateError('Update monitor data is invalid; no changes made')
    if not isinstance(result, dict) or result.get('schema') != 1:
        raise updates.UpdateError('Invalid update-monitor state schema')
    return result


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise updates.UpdateError('Refusing to write through a symlink')
    name = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.gameweld-update-', delete=False) as tmp:
            name = tmp.name
            os.fchmod(tmp.fileno(), 0o600)
            json.dump(data, tmp, indent=2, sort_keys=True, ensure_ascii=False)
            tmp.write('\n'); tmp.flush(); os.fsync(tmp.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def normal_game(name):
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 300) or any(ord(c) < 32 for c in name):
        raise updates.UpdateError('Invalid watched game title')
    return name.strip()


def prefs():
    c, _, _ = locations()
    doc = read_json(c, {'schema': 1, 'enabled': True, 'daily_budget': DAILY_GAME_BUDGET, 'include_unassigned': True})
    if type(doc.get('enabled')) is not bool or type(doc.get('daily_budget', DAILY_GAME_BUDGET)) is not int or doc.get('daily_budget', DAILY_GAME_BUDGET) not in ALLOWED_BUDGETS:
        raise updates.UpdateError('Invalid update-monitor preference')
    if type(doc.get('include_unassigned', True)) is not bool:
        raise updates.UpdateError('Invalid discovery preference')
    doc.setdefault('daily_budget', DAILY_GAME_BUDGET)
    doc.setdefault('include_unassigned', True)
    return doc


def state():
    _, c, _ = locations()
    doc = read_json(c, {'schema': 1, 'games': {}, 'day': '', 'used': 0})
    if not isinstance(doc.get('games'), dict) or type(doc.get('used', 0)) is not int or not 0 <= doc.get('used',0) <= 100000:
        raise updates.UpdateError('Invalid update-monitor state')
    return doc


def provider_of_assignment(path):
    """Only strong filename evidence; unknown does not silently mean FLiNG."""
    if not path:
        return 'unknown'
    filename = Path(path).name.lower()
    if filename in ('hextrainer.exe', 'aurora.exe', 'cheatevolution.exe', 'wand.exe', 'wemod.exe'):
        return {'hextrainer.exe':'hextrainer-manager', 'aurora.exe':'aurora-manager',
                'cheatevolution.exe':'cheatevolution-manager', 'wand.exe':'wand-manager',
                'wemod.exe':'wand-manager'}[filename]
    if 'hextrainer' in filename:
        return 'hextrainer'
    if 'fling' in filename or re.search(r'\bplus\s+\d+\s+trainer\b', filename):
        return 'fling'
    return 'unknown'


def version_tuple(version):
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(x) for x in version.split('.'))


def verified_local_receipt(game, assignment, provider):
    """Prove an existing executable is managed by GameWeld and matches its receipt."""
    if not assignment or provider not in ('fling','hextrainer'):
        return None
    try:
        import hashlib
        trainer = Path(assignment).resolve(strict=True)
        data_root = (Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'gameweld'/'trainers').resolve()
        if not trainer.is_file() or not trainer.is_relative_to(data_root):
            return None
        receipt_file = trainer.parent/'receipt.json'
        if not receipt_file.is_file() or receipt_file.is_symlink() or receipt_file.stat().st_size > 8192:
            return None
        receipt = json.loads(receipt_file.read_text('utf-8'))
        if (receipt.get('schema') != 1 or receipt.get('provider') != provider
                or updates.game_tokens(receipt.get('game','')) != updates.game_tokens(game)
                or receipt.get('file') != trainer.name or version_tuple(receipt.get('version')) is None):
            return None
        sha = hashlib.sha256(trainer.read_bytes()).hexdigest()
        if sha != receipt.get('exe_sha256'):
            return None
        return {'version':receipt['version'], 'id':receipt.get('id',''), 'provider':provider}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def detect_managers(include_wand=True):
    """Merge scan MANAGER rows and manually ASSIGNED manager frontends.

    File presence is evidence only; no executable is run or trusted for updates.
    Wand prefix discovery is read-only and bounded by its existing scanner.
    """
    root = Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache') / 'gameweld'
    report = root / 'trainer-library-last.tsv'
    found = {}
    try:
        if report.is_file() and not report.is_symlink() and report.stat().st_size <= 3_000_000:
            with report.open('r', encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    cols = line.rstrip('\r\n').split('\t')
                    if len(cols) < 7 or cols[0] != 'ROW' or cols[1] not in ('MANAGER','ASSIGNED'):
                        continue
                    candidate = Path(cols[6]); name = candidate.name.lower()
                    if name not in MANAGER_NAMES or candidate.is_symlink() or not candidate.is_file():
                        continue
                    if name == 'hextrainer.exe' and candidate.parent.name.lower() != 'hextrainer':
                        continue
                    if candidate.stat().st_size <= 0:
                        continue
                    identity = str(candidate.resolve(strict=True))
                    if identity not in found:
                        found[identity] = {'name':MANAGER_NAMES[name], 'path':identity,
                                           'provider':name.removesuffix('.exe'),
                                           'status':'installed-unverified-version',
                                           'evidence':'trainer-library-'+cols[1].lower()}
                    if len(found) >= 32:
                        break
    except (OSError, ValueError):
        pass
    if include_wand:
        try:
            spec = importlib.util.spec_from_file_location('gameweld_wand_discovery_monitor',
                         Path(__file__).with_name('gameweld-wand-discovery.py'))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for item in module.discover()['installations'][:16]:
                    path = item.get('install','')
                    prefix = item.get('prefix','')
                    if not isinstance(path,str) or not path or not isinstance(prefix,str) or not prefix:
                        continue
                    # Multiple Windows profiles within one Wine prefix are one
                    # runtime installation group, not three separate managers.
                    key = 'wand-prefix:' + prefix + ':' + str(item.get('product','Wand')) + ':' + str(item.get('version',''))
                    if key not in found:
                        found[key] = {'name':item.get('product','Wand'), 'path':path,
                                      'prefix':prefix, 'paths':[path],
                                      'provider':'wand', 'status':'installed-unverified-version',
                                      'installation_version':item.get('version',''),
                                      'evidence':'read-only-prefix-discovery'}
                    elif path not in found[key]['paths']:
                        found[key]['paths'].append(path)
        except (OSError, ValueError, RuntimeError, ImportError, KeyError):
            pass
    return sorted(found.values(), key=lambda x:(x['name'].lower(),x['path']))[:48]


def _has_release_lead(item):
    if item.get('catalog'):
        return True
    return any(isinstance(x,dict) and x.get('status') == 'official-match'
               for x in item.get('sources',[]))


def coverage(s, games=None, assignments=None, now=None):
    """Counts describe *titles*, not requests. Split assigned/unassigned precisely."""
    entries = {k:v for k,v in s.get('games',{}).items() if isinstance(v,dict)}
    cutoff = int(time.time() if now is None else now) - CHECK_INTERVAL
    if games is None:
        names = list(entries)
        assigned = sum(bool(v.get('has_assignment',True)) for v in entries.values())
        recently = sum(type(v.get('checked_at')) is int and v['checked_at'] >= cutoff
                       for v in entries.values())
    else:
        names = list(dict.fromkeys(games))
        assigned = sum(bool((assignments or {}).get(n)) for n in names)
        recently = sum(isinstance(entries.get(n),dict) and
                       type(entries[n].get('checked_at')) is int and entries[n]['checked_at'] >= cutoff
                       for n in names)
    assigned_entries = [v for v in entries.values() if v.get('has_assignment',True)]
    unassigned_entries = [v for v in entries.values() if not v.get('has_assignment',True)]
    unassigned_leads = sum(_has_release_lead(v) for v in unassigned_entries)
    unassigned_no_leads = sum(not _has_release_lead(v) and not v.get('errors') for v in unassigned_entries)
    unassigned_failed = sum(not _has_release_lead(v) and bool(v.get('errors')) for v in unassigned_entries)
    assigned_no_leads = sum(not _has_release_lead(v) for v in assigned_entries)
    return {'library_total':len(names), 'library_assigned':assigned,
            'library_unassigned':len(names)-assigned,
            'checked_in_window':recently, 'awaiting_checks':max(0,len(names)-recently),
            'checked_assigned':len(assigned_entries), 'checked_unassigned':len(unassigned_entries),
            'unassigned_leads':unassigned_leads, 'unassigned_without_leads':unassigned_no_leads,
            'unassigned_inconclusive':unassigned_failed, 'assigned_without_leads':assigned_no_leads,
            # Legacy field keeps meaning as total titles with no lead (not unassigned-only).
            'checked_without_leads':unassigned_no_leads+unassigned_failed+assigned_no_leads}


def ordered_due(names, mapping, s, now, force):
    """Fair bounded scan: two assigned and two unassigned when both are due.

    Managers already checked get the normal 24-hour TTL. An assigned game's
    publisher update never prevents the unmatched game queue from advancing.
    """
    assigned=[]; unassigned=[]
    for name in names:
        old=s['games'].get(name,{})
        prov=provider_of_assignment(mapping.get(name,''))
        known=old.get('has_assignment',bool(mapping.get(name)))
        changed=(prov != old.get('assigned_provider','unknown') or bool(mapping.get(name)) != known)
        # One-time refresh of RC2 publisher-only entries, even when their old
        # 24-hour TTL has not expired. This still uses the daily budget and is
        # attempted at most once, including when the publisher is unreachable.
        missing_evidence = (old and not old.get('rc4_metadata_checked') and
            any(isinstance(src,dict) and src.get('status') == 'official-match'
                for src in old.get('sources',[])))
        if not force and not changed and not missing_evidence and now-int(old.get('checked_at',0)) < CHECK_INTERVAL:
            continue
        (assigned if mapping.get(name) else unassigned).append(name)
    for part in (assigned,unassigned):
        part.sort(key=lambda n:(int(s['games'].get(n,{}).get('checked_at',0)),n.lower()))
    order=[]
    while assigned or unassigned:
        order.extend(assigned[:2]);del assigned[:2]
        order.extend(unassigned[:2]);del unassigned[:2]
    return order


def _game_name_key(value):
    # Apostrophes and punctuation differences must not turn CONTROL into
    # CONTROL Resonant. Compare the complete normalized title, not overlap.
    return re.sub(r'[^a-z0-9]','',str(value).lower().replace('®',''))


def _package_game(package):
    # FLiNG distribution format: <title>.v<supported-version>.Plus.N.Trainer-FLiNG
    found = re.match(r'^(.*?)\.v\d[^.]*',str(package),re.I)
    return found.group(1) if found else ''


def _label_range(text):
    # This is a *filename label*, not the game's installed version and not
    # a cryptographic binary version. x/wildcards are inexact.
    found=re.findall(r'v(\d+(?:\.\d+){0,3})(?:\.x)?',str(text),re.I)
    if not found:return None
    return [tuple(map(int,token.split('.'))) for token in found[:2]]


def possible_compatibility_candidate(game, local_name, releases):
    """A wider publisher compatibility range is only a review lead.

    Neither a release date nor a wider supported game range is proof of a
    newer trainer executable. Never pass this to the verified-download path.
    """
    if not local_name or 'trainer' not in local_name.lower():return None
    current=_label_range(local_name)
    if not current:return None
    current_upper=current[-1]
    for release in releases[:8]:
        if not isinstance(release,dict):continue
        candidate=release.get('name','')
        if _game_name_key(_package_game(candidate))!=_game_name_key(game):continue
        declared=_label_range(candidate)
        if not declared:continue
        published_upper=declared[-1]
        n=max(len(current_upper),len(published_upper))
        a=current_upper+(0,)*(n-len(current_upper))
        b=published_upper+(0,)*(n-len(published_upper))
        if b>a:
            return {'local_label':local_name[:170], 'publisher_package':candidate[:170],
                    'publisher_date':release.get('published',''),
                    'reason':'Possible broader game-version support (filename labels only)'}
    return None


def local_filename_evidence(game, assignment):
    """Read-only *label* inference; never claim this is the executable's version.

    Refuse multi-game manager EXEs and unrelated game names. For real paths,
    mark existence explicitly; path contents are never loaded or executed.
    """
    if not isinstance(assignment,str) or not assignment or len(assignment)>4096:
        return {'status':'not-assigned','source':'none','label':''}
    path=Path(assignment)
    name=path.name[:190]
    provider=provider_of_assignment(assignment)
    if provider.endswith('-manager'):
        return {'status':'multi-game-manager','source':'filename-only','label':''}
    if provider != 'fling':
        return {'status':'unsupported-provider','source':'filename-only','label':''}
    # Strong title boundary: never let CONTROL match CONTROL Resonant.
    prefix=re.split(r'(?i)[ ._-]+v\d',name,maxsplit=1)[0]
    parts=_label_range(name)
    if not parts:
        without_suffix=re.split(r'(?i)[ ._-]+plus[ ._-]+\d+',name,maxsplit=1)[0]
        status='version-label-missing' if _game_name_key(without_suffix)==_game_name_key(game) else 'title-mismatch'
        return {'status':status,'source':'filename-only','label':''}
    if _game_name_key(prefix)!=_game_name_key(game):
        return {'status':'title-mismatch','source':'filename-only','label':''}
    # Different from a trainer build version: these indicate game compatibility.
    matched=re.findall(r'(?i)v\d+(?:\.\d+){0,3}(?:\.x)?',name)
    label='–'.join(matched[:2])
    return {'status':'filename-label','source':'trainer-filename-unverified',
            'label':label[:70], 'filename':name}


def compare_publisher_compatibility(game, local, releases):
    """Three-way advisory comparison; never a verified update decision."""
    if not isinstance(local,dict) or local.get('status')!='filename-label':
        return {'status':'unable-to-compare','reason':'Local trainer compatibility label unavailable'}
    own=_label_range(local.get('label',''))
    if not own:
        return {'status':'unable-to-compare','reason':'Local filename has no usable compatibility range'}
    eligible=[]
    for entry in releases[:8]:
        if not isinstance(entry,dict):continue
        label=entry.get('name','')
        if _game_name_key(_package_game(label))!=_game_name_key(game):continue
        vers=_label_range(label)
        if not vers:continue
        eligible.append((vers[-1],entry))
    if not eligible:
        return {'status':'publisher-package-unavailable', 'reason':'No clean matching publisher package'}
    higher,listing=max(eligible,key=lambda x:(x[0],x[1].get('published','')))
    current=own[-1]
    n=max(len(current),len(higher))
    a=current+(0,)*(n-len(current));b=higher+(0,)*(n-len(higher))
    if b>a:
        return {'status':'possible-expansion','reason':'Publisher filename advertises broader game compatibility; not a verified trainer update',
                'publisher_package':listing['name'][:170], 'publisher_date':listing.get('published',''),
                'local_label':local['label']}
    if b==a:
        return {'status':'same-advertised-range','reason':'Latest listed game compatibility is no broader (filenames only)',
                'publisher_package':listing['name'][:170], 'local_label':local['label']}
    return {'status':'local-range-higher','reason':'Local filename advertises a higher game compatibility bound; review manually',
            'publisher_package':listing['name'][:170], 'local_label':local['label']}


def sync_cached_local_assignments(s, names, mapping):
    """Update local-only evidence even when the daily publisher budget is full.

    Do not overwrite network results, confirmed receipts or manager inventory.
    Changes are persisted under the monitor lock by callers.
    """
    changed=0
    for name in names[:MAX_GAMES]:
        entry=s.get('games',{}).get(name)
        if not isinstance(entry,dict):continue
        assignment=mapping.get(name,'')
        provider=provider_of_assignment(assignment)
        evidence=local_filename_evidence(name,assignment)
        # A user may remove or reassign a trainer while a cached page is valid.
        fields={'assigned_provider':provider,'has_assignment':bool(assignment),
                'assignment_name':Path(assignment).name[:190] if assignment else '',
                'local_evidence':evidence,
                'verified_local':verified_local_receipt(name,assignment,provider)}
        if any(entry.get(k)!=v for k,v in fields.items()):
            entry.update(fields);changed+=1
    return changed


def refresh_local_only(games, assignments, *, clock=None):
    """Explicit offline local-evidence refresh; zero publisher/network checks."""
    now=int(time.time() if clock is None else clock)
    _,cache,lock_path=locations();lock_path.parent.mkdir(parents=True,exist_ok=True)
    if lock_path.is_symlink():raise updates.UpdateError('Unsafe lock path')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        policy=prefs();s=state()
        names=list(dict.fromkeys(normal_game(x) for x in games))[:MAX_GAMES]
        mapping={normal_game(k):v for k,v in assignments.items() if isinstance(v,str)}
        changed=sync_cached_local_assignments(s,names,mapping)
        write_json(cache,s)
        result={'changed_titles':changed,'checked_titles':len(names),
                'summary':f'Local trainer evidence refreshed for {changed} cached titles; no publisher checks or executable launches. '+update_summary(s,policy),
                'queue':queue_rows(s),'coverage':coverage(s),'used':s.get('used',0),
                'budget':policy['daily_budget'],'enabled':policy['enabled'],
                'include_unassigned':policy['include_unassigned'], 'managers':s.get('managers',[])}
        return result


def queue_rows(s):
    result = []
    for name, item in sorted(s.get('games', {}).items()):
        if not isinstance(item, dict):
            continue
        provider = item.get('assigned_provider','unknown')
        local = item.get('verified_local')
        if provider.endswith('-manager'):
            result.append({'game':name,'provider':provider.removesuffix('-manager'),
                           'status':'manager-review','detail':'Manager detected; no game-specific version comparison'})
            continue
        for entry in item.get('catalog', []):
            if not isinstance(entry, dict):
                continue
            source_provider = entry.get('provider','fling')
            if entry.get('status') == 'installed':
                status='up-to-date'
            elif entry.get('status') == 'available':
                # Only compare GameWeld-managed, receipt-verified versions from the *same* publisher.
                current = version_tuple(local.get('version')) if isinstance(local,dict) and local.get('provider') == source_provider else None
                candidate = version_tuple(entry.get('version'))
                if current is not None and candidate is not None:
                    length=max(len(current),len(candidate))
                    a=current+(0,)*(length-len(current)); b=candidate+(0,)*(length-len(candidate))
                    status='update-available' if b>a else 'up-to-date' if b==a else 'older-catalog'
                else:
                    status='verified-download-ready'
            else:
                continue
            result.append({'game':name,'provider':source_provider,'status':status,
                           'version':entry.get('version',''),'installed_version':local.get('version','') if isinstance(local,dict) else '',
                           'id':entry.get('id',''), 'assigned_provider':provider,
                           'verification':'locally-imported-catalog-checksum-not-publisher-authenticated'})
        for source in item.get('sources', []):
            if not isinstance(source,dict):
                continue
            if source.get('status') == 'official-match':
                # Unassigned games are discovery leads, *not* installed-trainer updates.
                raw_releases=source.get('publisher_releases',[])
                releases=[r for r in raw_releases[:8] if isinstance(r,dict) and
                          isinstance(r.get('name'),str) and updates._package_name(r['name']) and
                          isinstance(r.get('published'),str) and updates._release_date(r['published']) == r['published']]
                # The local label comes from the assigned filename, not a
                # verified build version; comparison remains strictly advisory.
                eligible=bool(item.get('has_assignment',True) and provider=='fling' and source.get('provider')=='fling')
                local_evidence=item.get('local_evidence')
                if eligible and not isinstance(local_evidence,dict):
                    # Old RC4.1 cache: use a clearly unverified filename label.
                    local_evidence=local_filename_evidence(name,item.get('assignment_name',''))
                comparison=(compare_publisher_compatibility(name,local_evidence,releases)
                            if eligible else {'status':'not-applicable','reason':'Unassigned game or different trainer provider'})
                candidate=(comparison if comparison['status']=='possible-expansion' else None)
                result.append({'game':name,'provider':source.get('provider',''),
                               'status':'compatibility-review' if candidate else 'publisher-review',
                               'version':'unverified', 'candidate':candidate,
                               'comparison':comparison,'local_evidence':local_evidence if eligible else None,
                               'installed_version':(local_evidence.get('label','')+' [filename only]') if eligible and isinstance(local_evidence,dict) and local_evidence.get('label') else '',
                               'discovery':not item.get('has_assignment', True),
                               'assigned_provider':provider,'url':source.get('url',''),
                               'publisher_game_version':source.get('publisher_game_version',''),
                               'publisher_updated':source.get('publisher_updated',''),
                               'publisher_releases':releases,
                               'publisher_metadata_status':source.get('publisher_metadata_status','legacy-cache-no-status')})
        if item.get('errors') and not item.get('catalog') and not item.get('sources'):
            result.append({'game':name,'provider':provider,'status':'unable-to-check'})
    rank={'update-available':0,'verified-download-ready':1,'compatibility-review':2,'publisher-review':3,'manager-review':4,'unable-to-check':4,'up-to-date':5,'older-catalog':6}
    return sorted(result, key=lambda x:(rank.get(x['status'],9),x['game'].lower(),x.get('provider','')))



def cached_publisher_page(s, game, provider='fling'):
    """Return an exact game publisher PAGE from the local cache, never a download.

    Ignore wrong-game titles, non-HTTPS urls, unapproved domains, redirects,
    and arbitrary cache content. No network or state mutations occur.
    """
    if provider not in ('fling','hextrainer'):
        raise updates.UpdateError('Only supported standalone trainer publisher pages can be opened')
    normalized=_game_name_key(normal_game(game))
    for title,item in s.get('games',{}).items():
        if _game_name_key(title)!=normalized or not isinstance(item,dict):continue
        for source in item.get('sources',[]):
            if not isinstance(source,dict) or source.get('provider')!=provider or source.get('status')!='official-match':continue
            url=source.get('url','')
            if not isinstance(url,str) or not updates.publisher_host(url,provider):continue
            parts=updates.urllib.parse.urlsplit(url)
            if parts.query or parts.fragment:continue
            path=parts.path
            valid=(re.fullmatch(r'/trainer/[a-z0-9-]+/?',path) if provider=='fling' else
                   re.fullmatch(r'/trainers/[a-z0-9-]+/?',path))
            # A cached row must also point to that game's page, not merely
            # another path on the same approved host.
            slug=path.strip('/').split('/')[-1].removesuffix('-trainer')
            if valid and _game_name_key(slug)==normalized:return url
    return None

def update_dashboard(s, policy=None):
    """Offline, read-only grouped view of update evidence for the whole library.

    A publisher page/compatibility range never implies a verified executable.
    A catalog URL/hash alone never establishes publisher provenance.  Manager
    installations are grouped separately from game-specific trainer releases.
    """
    rows=queue_rows(s)
    groups={'available_trainers':[], 'trainer_updates':[], 'manager_apps':[]}
    seen=set()
    for row in rows:
        game=row.get('game','')
        kind=row.get('status','')
        if kind=='manager-review':
            # A manager app is not a verified game-specific update.
            continue
        elif kind in ('compatibility-review','update-available','verified-download-ready','up-to-date','older-catalog'):
            section='trainer_updates'
        elif kind=='publisher-review' and row.get('discovery'):
            section='available_trainers'
        elif kind=='publisher-review':
            section='trainer_updates'
        else:
            continue
        key=(section,game.casefold(),str(row.get('provider','')).casefold(),kind)
        if key in seen:continue
        seen.add(key)
        status={
            'publisher-review':'PUBLISHER PAGE ONLY',
            'compatibility-review':'POSSIBLE COMPATIBILITY EXPANSION',
            'verified-download-ready':'IMPORTED CATALOG ENTRY — ORIGIN NOT VERIFIED',
            'update-available':'CATALOG VERSION CANDIDATE — CHECK PROVENANCE',
            'up-to-date':'LOCALLY STAGED VERSION MATCHES CATALOG',
            'older-catalog':'CATALOG ADVERTISES OLDER VERSION',
        }.get(kind,'REVIEW ONLY')
        publisher_url=row.get('url','')
        provider=row.get('provider','')
        if not isinstance(publisher_url,str) or not updates.publisher_host(publisher_url,provider):
            publisher_url=None
        groups[section].append({'game':game,'provider':provider,'status':kind,
            'label':status,'publisher_page':publisher_url,
            'installed_label':row.get('installed_version',''),
            'advertised_compatibility':row.get('publisher_game_version',''),
            'published':row.get('publisher_updated',''),
            'packages_listed':len(row.get('publisher_releases',[])),
            'authenticated_download':False,
            'warning':'Publisher evidence only; no automatic download approved' if kind in ('publisher-review','compatibility-review') else 'Check the independently established catalog key provenance before staging'})
    for manager in s.get('managers',[]):
        if not isinstance(manager,dict):continue
        name=manager.get('name','Unknown manager')
        if not isinstance(name,str) or not name.strip():continue
        groups['manager_apps'].append({'name':name[:100],
            'status':'INSTALLED — LOCAL VERSION UNVERIFIED',
            'update_channel':'Publisher application manages updates',
            'authenticated_download':False})
    names={key:{x['name'] for x in value} if key=='manager_apps' else {x['game'] for x in value} for key,value in groups.items()}
    counts={key:len(val) for key,val in names.items()}
    # The `manager_apps` count tracks distinct product names; installation
    # paths stay in the detailed report and never masquerade as new updates.
    def describe(section, limit=4):
        items=groups[section]
        if not items:return 'No cached entries in this category.'
        lines=[]
        for item in items[:limit]:
            if section=='manager_apps':
                lines.append(item['name']+' — detected; update/version not verified')
            else:
                game=item['game'].replace('\n',' ')
                lines.append(game+' — '+item['label'].lower() +
                    ('; '+str(item['packages_listed'])+' publisher-listed packages' if item['packages_listed'] else '') +
                    ('; '+item['advertised_compatibility'][:90] if item['advertised_compatibility'] else ''))
        if len(items)>limit:lines.append(f'... and {len(items)-limit} more')
        return '\n'.join(lines)
    summary=(f"{counts['available_trainers']} discovered game leads · "
             f"{counts['trainer_updates']} assigned trainer records to review · "
             f"{counts['manager_apps']} distinct manager products · "
             "0 publisher-authenticated automatic downloads")
    return {'schema':1,'network_requests':0,'summary':summary,'counts':counts,
        'available':describe('available_trainers'),
        'updates':describe('trainer_updates'),
        'managers':describe('manager_apps'),
        'groups':groups,'budget_used':s.get('used',0),
        'warning':'Review-only publisher evidence. Signed catalogs require independently verified key origin. No download or assignment changes.'}


def update_summary(s, policy):
    q=queue_rows(s)
    counts={status:sum(r['status']==status for r in q) for status in ('update-available','verified-download-ready','compatibility-review','publisher-review','manager-review','up-to-date','unable-to-check')}
    leads=sum(r.get('discovery',False) for r in q)
    progress=coverage(s)
    managers=s.get('managers',[])
    return (f"Automatic checks {'on' if policy['enabled'] else 'paused'} · "
            f"{counts['update-available']} confirmed newer · {counts['verified-download-ready']} pinned release(s) to review · "
            f"{counts['compatibility-review']} possible compatibility expansions · "
            f"{counts['publisher-review']+counts['compatibility-review']} publisher pages (not confirmed updates) · {leads} unassigned-game leads · "
            f"{counts['manager-review']} manager checks · "
            f"{progress['checked_unassigned']} unassigned titles checked ({progress['unassigned_leads']} leads, "
            f"{progress['unassigned_without_leads']} no leads, {progress['unassigned_inconclusive']} inconclusive) · "
            f"{len(managers)} installed managers detected · "
            f"{s.get('used',0)}/{policy['daily_budget']} checks today")


def queue_details(s, limit=12):
    labels={'update-available':'NEWER VERIFIED','verified-download-ready':'PINNED / UNCOMPARED',
            'publisher-review':'PAGE ONLY','compatibility-review':'POSSIBLE COMPATIBILITY EXPANSION','manager-review':'MANAGER','up-to-date':'INSTALLED',
            'older-catalog':'OLDER CATALOG','unable-to-check':'UNAVAILABLE'}
    q=queue_rows(s)
    lines=[]
    for x in q[:limit]:
        vers=f" {x['installed_version']} → {x['version']}" if x.get('installed_version') and x.get('version') else ''
        label=labels.get(x['status'],x['status'])
        if x.get('discovery') and x['status']=='publisher-review':
            label='PAGE ONLY'
        note=' (possible trainer for unassigned game)' if x.get('discovery') else ''
        if x.get('publisher_updated'): note+=' (publisher updated '+str(x['publisher_updated'])+')'
        if x.get('publisher_releases'): note+=f" ({len(x['publisher_releases'])} publisher-listed packages; unverified)"
        if x.get('candidate'):note+=' (filename range comparison only; not verified download)'
        elif x.get('comparison',{}).get('status') in ('unable-to-compare','same-advertised-range'):note+=' ('+x['comparison']['status']+'; filename evidence only)'
        lines.append(f"{label}: {x['game']} — {x.get('provider','unknown')}{vers}{note}")
    if len(q)>limit:
        lines.append(f"… and {len(q)-limit} more results")
    for manager in s.get('managers', [])[:8]:
        if isinstance(manager,dict):
            lines.append('APP DETECTED: '+manager.get('name','Unknown')+' — installed, version not verified')
    return '\n'.join(lines) or 'No confirmed releases or publisher pages to review yet.'


def perform_scan(games, *, assignments=None, force=False, live=True, clock=None, provider_checker=None, catalog_checker=None):
    now = int(time.time() if clock is None else clock)
    today = datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%d')
    _, cache, lock_path = locations()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_symlink():
        raise updates.UpdateError('Unsafe lock path')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        policy = prefs()
        s = state()
        if s.get('day') != today:
            s['day'] = today
            s['used'] = 0
        # Bounded state, graceful refusal for malformed record timestamps.
        s['games'] = {k:v for k,v in s['games'].items() if isinstance(v,dict)
                      and type(v.get('checked_at')) is int and 0 <= now-v['checked_at'] < MAX_AGE}
        normalized = list(dict.fromkeys(normal_game(g) for g in games))[:MAX_GAMES]
        mapping = {normal_game(k):v for k,v in (assignments or {}).items() if isinstance(v,str)}
        if not policy['include_unassigned']:
            normalized = [name for name in normalized if mapping.get(name)]
        # Refresh slow prefix discovery no more often than every six hours.
        if s.get('manager_inventory_schema',0) < 3 or now - int(s.get('managers_checked_at',0)) >= MANAGER_RECHECK or 'managers' not in s:
            s['managers'] = detect_managers()
            s['managers_checked_at'] = now
            s['manager_inventory_schema'] = 3
        if not policy['enabled']:
            write_json(cache,s)
            return {'enabled':False,'checked':[],'deferred':normalized,'queue':queue_rows(s),
                    'used':s['used'],'budget':policy['daily_budget'],'include_unassigned':policy['include_unassigned'],
                    'coverage':coverage(s,normalized,mapping,now),'managers':s['managers'],'summary':update_summary(s,policy)}
        # Fairness is part of the scheduler, not simply the summary: allocate
        # scan slots to unassigned games even while assigned titles have work.
        due = ordered_due(normalized, mapping, s, now, force)
        # Reconcile trainer assignments and filename evidence every time,
        # including when the daily budget has already been exhausted.
        sync_cached_local_assignments(s,normalized,mapping)
        checked=[];deferred=[]
        available = min(BATCH_LIMIT,max(0,policy['daily_budget']-s['used']))
        for name in due:
            old=s['games'].get(name,{})
            selected_provider=provider_of_assignment(mapping.get(name, ''))
            has_assignment=bool(mapping.get(name))
            if available <= 0:
                deferred.append(name);continue
            s['used']+=1;available-=1
            fresh={'checked_at':now,'rc3_metadata_checked':True,'rc4_metadata_checked':True,'catalog':[],'sources':[],'errors':[],
                   'assigned_provider': selected_provider,'has_assignment':has_assignment,
                   'verified_local':verified_local_receipt(name,mapping.get(name,''),selected_provider),
                   'assignment_name':Path(mapping.get(name,'')).name[:190] if mapping.get(name) else '',
                   'local_evidence':local_filename_evidence(name,mapping.get(name,''))}
            s['games'][name]=fresh
            # Manager cannot be compared against per-game FLiNG trainer results.
            if selected_provider.endswith('-manager'):
                checked.append(name);write_json(cache,s);continue
            try:
                catalog=(catalog_checker or updates.check_catalog)(name)
                fresh['catalog']=[{k:v for k,v in entry.items() if k in ('id','provider','version','status','game')}
                                  for entry in catalog if isinstance(entry,dict)]
            except (OSError,ValueError,updates.UpdateError) as exc:
                fresh['errors'].append('Catalog: '+str(exc)[:160])
            try:
                checker=provider_checker or updates.check_providers
                provider_list = [selected_provider] if selected_provider in ('fling','hextrainer') else ['fling','hextrainer']
                if checker is updates.check_providers:
                    reports=checker(name,providers=provider_list,live=live)
                else:
                    # Existing Test 8 injected fixtures use (game, live=...), retain compatibility.
                    reports=checker(name,live=live)
                fresh['sources']=[{'provider':r.get('provider',''),'status':r.get('status',''),
                                   'url':r.get('url',''),'detail':str(r.get('detail',''))[:180],
                                   'publisher_game_version':str(r.get('publisher_game_version',''))[:90],
                                   'publisher_updated':str(r.get('publisher_updated',''))[:12],
                                   'publisher_options':r.get('publisher_options',None),
                                   'publisher_metadata_status':str(r.get('publisher_metadata_status', 'not-fetched'))[:48],
                                   'publisher_releases':r.get('publisher_releases',[])[:8] if isinstance(r.get('publisher_releases'),list) else []}
                                  for r in reports if isinstance(r,dict)]
            except (OSError,ValueError,updates.UpdateError) as exc:
                fresh['errors'].append('Publisher: '+str(exc)[:160])
            checked.append(name)
            write_json(cache,s)
        write_json(cache,s)
        return {'enabled':True,'checked':checked,'deferred':deferred,'queue':queue_rows(s),
                'coverage':coverage(s,normalized,mapping,now),'managers':s['managers'],
                'used':s['used'],'budget':policy['daily_budget'],'include_unassigned':policy['include_unassigned'],'summary':update_summary(s,policy)}


def recover_publisher_metadata(*, clock=None, fetcher=None, live=True):
    """Recheck up to four existing exact publisher pages without search crawling.

    This is a separately capped, explicit recovery action, never a bypass of
    the normal discovery scheduler. It neither downloads nor executes trainers.
    Preserve valid cache evidence if a publisher page temporarily fails.
    """
    now=int(time.time() if clock is None else clock)
    today=datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%d')
    _, cache, lock_path=locations()
    cache.parent.mkdir(parents=True,exist_ok=True)
    if lock_path.is_symlink():raise updates.UpdateError('Unsafe lock path')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        policy=prefs();s=state()
        if not policy['enabled']:
            return {'enabled':False,'recovered':[],'summary':'Automatic checks are paused. Resume before recovering publisher metadata.',
                    'budget':policy['daily_budget'],'used':s.get('used',0),'include_unassigned':policy['include_unassigned']}
        if s.get('recovery_day')!=today:
            s['recovery_day']=today;s['recovery_used']=0
        remaining=max(0,RECOVERY_DAILY_LIMIT-int(s.get('recovery_used',0)))
        checked=[];errors=[]
        pending=[]
        for game,item in s.get('games',{}).items():
            if not isinstance(item,dict):continue
            for idx,src in enumerate(item.get('sources',[])):
                if not isinstance(src,dict) or src.get('provider')!='fling' or src.get('status')!='official-match':continue
                url=src.get('url','')
                if (not updates.publisher_host(url,'fling') or
                    not re.fullmatch(r'/trainer/[a-z0-9-]+-trainer/?', updates.urllib.parse.urlsplit(url).path)):
                    continue
                status=src.get('publisher_metadata_status','not-checked')
                if status=='extracted' and src.get('publisher_releases'):continue
                if now-int(src.get('metadata_recovered_at',0))<RECOVERY_MIN_INTERVAL:continue
                pending.append((0 if item.get('has_assignment',False) else 1,game,idx,url))
        pending.sort(key=lambda v:(v[0],v[1].casefold()))
        for _,game,idx,url in pending[:remaining]:
            src=s['games'][game]['sources'][idx]
            s['recovery_used']+=1
            src['metadata_recovered_at']=now
            try:
                if not live:
                    raise updates.UpdateError('Network disabled; recovery not attempted')
                if fetcher is None:
                    with updates.open_trusted(url,host_rule=lambda u:updates.publisher_host(u,'fling'),timeout=7) as response:
                        body=response.read(updates.MAX_HTML_BYTES+1)
                else:
                    body=fetcher(url)
                if len(body)>updates.MAX_HTML_BYTES:raise updates.UpdateError('Publisher page too large')
                result=updates.publisher_page_metadata('fling',body.decode('utf-8','replace') if isinstance(body,bytes) else body)
                for k in ('publisher_game_version','publisher_updated','publisher_metadata_status'):
                    if k in result:src[k]=result[k]
                if result.get('publisher_releases'):
                    src['publisher_releases']=result['publisher_releases']
                if 'publisher_metadata_status' not in result:
                    src['publisher_metadata_status']='page-unrecognized'
                checked.append(game)
            except (OSError,ValueError,TimeoutError,updates.UpdateError) as exc:
                src['publisher_metadata_status']='fetch-error'
                errors.append(game+': '+str(exc)[:100])
            write_json(cache,s)
        summary=(f"Publisher metadata recovery: {len(checked)} checked, {len(errors)} failed, "
                 f"{s.get('recovery_used',0)}/{RECOVERY_DAILY_LIMIT} metadata checks today; "
                 f"normal discovery budget remains {s.get('used',0)}/{policy['daily_budget']}.")
        return {'enabled':True,'recovered':checked,'errors':errors,'queue':queue_rows(s),
                'used':s.get('used',0),'budget':policy['daily_budget'],
                'include_unassigned':policy['include_unassigned'],
                'recovery_used':s.get('recovery_used',0),'recovery_budget':RECOVERY_DAILY_LIMIT,
                'summary':summary,'details':queue_details(s)}


def export_report(s=None, policy=None):
    """Save a complete local read-only audit, without downloading any binaries."""
    s = state() if s is None else s
    policy = prefs() if policy is None else policy
    dest = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state') / 'gameweld' / 'automation-report.md'
    stats = coverage(s)
    q = queue_rows(s)
    def clean(value):
        value = str(value).replace('\r',' ').replace('\n',' ').replace('|','\\|')
        return ''.join(c for c in value if ord(c) >= 32)[:350]
    sections = ['# GameWeld Automation Report', '',
                'Generated (UTC): '+datetime.now(timezone.utc).isoformat(timespec='seconds'),
                '', '## Coverage', '',
                '- '+update_summary(s, policy),
                f"- Distinct checked titles in cache: {stats['checked_assigned']+stats['checked_unassigned']}",
                f"- Assigned titles checked: {stats['checked_assigned']}",
                f"- Unassigned titles checked: {stats['checked_unassigned']}",
                f"- Unassigned titles with a lead: {stats['unassigned_leads']}",
                f"- Unassigned titles checked without leads: {stats['unassigned_without_leads']}",
                f"- Unassigned titles inconclusive (check error): {stats['unassigned_inconclusive']}",
                f"- Assigned titles without release leads: {stats['assigned_without_leads']}",
                f"- All checked titles without a release lead: {stats['checked_without_leads']}",
                '', '## Update and discovery queue', '',
                '| Game | Provider | Status | Installed | Publisher release | Game compatibility | Publisher updated | Official page |',
                '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for item in q:
        sections.append('| '+' | '.join(clean(item.get(x,'')) for x in ('game','provider','status','installed_version','version','publisher_game_version','publisher_updated','url'))+' |')
    if not q: sections.append('| None yet | — | No confirmed results | — | — | — | — | — |')
    releases = [(x['game'],x.get('provider',''),release)
                for x in q if x.get('status') in ('publisher-review','compatibility-review')
                for release in x.get('publisher_releases',[])[:8]
                if isinstance(release,dict)]
    sections += ['', '## Publisher-listed packages (not verified downloads)', '']
    for game, provider, release in releases[:80]:
        sections.append('- '+clean(game)+' / '+clean(provider)+': '+clean(release.get('name',''))+
                        ' (listed '+clean(release.get('published','unknown'))+')')
    if not releases: sections.append('- No package listings could be extracted from fetched publisher pages')
    sections += ['', '## Local trainer filename evidence (not executable versions)', '']
    for row in q:
        if row.get('status') not in ('publisher-review','compatibility-review'):continue
        if row.get('discovery'):continue
        ev=row.get('local_evidence') or {}
        cmp=row.get('comparison') or {}
        sections.append('- '+clean(row['game'])+': '+clean(ev.get('label','unknown'))+
                        ' (source '+clean(ev.get('source','none'))+', '+clean(ev.get('status','unavailable'))+')'+
                        '; comparison: '+clean(cmp.get('status','not-checked'))+
                        '; '+clean(cmp.get('reason','')))
    sections += ['', '## Publisher metadata diagnostics', '',
                 f"- Metadata-only recovery checks today: {s.get('recovery_used',0)}/{RECOVERY_DAILY_LIMIT} (separate from discovery budget)"]
    for row in q:
        if row.get('status') in ('publisher-review','compatibility-review'):
            sections.append('- '+clean(row['game'])+' / '+clean(row.get('provider',''))+': '+
                            clean(row.get('publisher_metadata_status','legacy-cache-no-status'))+
                            ('; '+str(len(row.get('publisher_releases',[])))+' clean packages' if row.get('publisher_releases') else '; 0 clean packages'))
    sections += ['', '## Compatibility expansion candidates (not confirmed trainer updates)', '']
    candidates=[x for x in q if x.get('status')=='compatibility-review' and x.get('candidate')]
    for row in candidates:
        c=row['candidate']
        sections.append('- '+clean(row['game'])+': '+clean(c['local_label'])+' → '+clean(c['publisher_package'])+
                        ' — '+clean(c['reason'])+'; publisher-listed '+clean(c.get('publisher_date','unknown')))
    if not candidates:sections.append('- None found')
    sections += ['', '## Detected trainer managers', '']
    for item in s.get('managers', []):
        if isinstance(item,dict):
            sections.append('- '+clean(item.get('name','Unknown'))+' — present, local executable version not verified ('+clean(item.get('path',''))+')' +
                            ('; installation folder version '+clean(item['installation_version']) if item.get('installation_version') else '') +
                            '; evidence: '+clean(item.get('evidence','scanner')) +
                            ('; Wine prefix: '+clean(item.get('prefix',''))+
                             '; Windows installation paths: '+str(len(item.get('paths',[])))
                             if item.get('prefix') else ''))
    if not s.get('managers'): sections.append('- None in the last Trainer Library scan')
    sections += ['', '## Verification policy', '',
                 '- Publisher-listed package names and update dates are *untrusted informational evidence*, not verified updates or downloads.',
                 '- Local trainer labels are parsed from filenames, not executable version resources; all compatibility comparisons are advisory and never authorize installation.',
                 '- Compatibility expansion candidates compare filename labels only; they are not confirmed newer trainers, security verification, or download authorization.',
                 '- A publisher page is only a lead, never proof of a newer version.',
                 '- A locally imported catalog SHA256 verifies downloaded bytes against that catalog; it does not authenticate the catalog publisher.',
                 '- No executables are downloaded, launched, installed, updated or assigned by this report.', '']
    write_text_safely(dest, '\n'.join(sections))
    return dest


def write_text_safely(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise updates.UpdateError('Refusing to overwrite a report symlink')
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix='.gameweld-report-',delete=False) as f:
            tmp=f.name;os.fchmod(f.fileno(),0o600);f.write(value);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp and os.path.exists(tmp):os.unlink(tmp)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='cmd',required=True)
    scan=sub.add_parser('scan');scan.add_argument('--game',action='append',default=[]);scan.add_argument('--trainer-path',action='append',default=[]);scan.add_argument('--force',action='store_true');scan.add_argument('--offline',action='store_true');scan.add_argument('--compact',action='store_true')
    sync=sub.add_parser('sync-local');sync.add_argument('--game',action='append',default=[]);sync.add_argument('--trainer-path',action='append',default=[]);sync.add_argument('--compact',action='store_true')
    setp=sub.add_parser('set-enabled');setp.add_argument('value',choices=['on','off'])
    budget=sub.add_parser('set-budget');budget.add_argument('value',type=int)
    discovery=sub.add_parser('set-discovery');discovery.add_argument('value',choices=['on','off'])
    st=sub.add_parser('status');st.add_argument('--compact',action='store_true')
    dash=sub.add_parser('dashboard');dash.add_argument('--compact',action='store_true')
    page=sub.add_parser('publisher-page');page.add_argument('--game',required=True);page.add_argument('--provider',choices=('fling','hextrainer'),default='fling');page.add_argument('--plain',action='store_true')
    report=sub.add_parser('report');report.add_argument('--compact',action='store_true')
    recovery=sub.add_parser('recover-metadata');recovery.add_argument('--compact',action='store_true')
    args=p.parse_args(argv)
    try:
        if args.cmd in ('set-enabled','set-budget','set-discovery'):
            c,_,_=locations(); policy=prefs()
            if args.cmd=='set-enabled': policy['enabled']=args.value=='on'
            elif args.cmd=='set-discovery': policy['include_unassigned']=args.value=='on'
            else:
                if args.value not in ALLOWED_BUDGETS: raise updates.UpdateError('Allowed daily check budgets: 4, 8, 12, 24, 48, 96')
                policy['daily_budget']=args.value
            write_json(c,policy)
            result={'enabled':policy['enabled'],'budget':policy['daily_budget'],'include_unassigned':policy['include_unassigned'],'changed':True,
                    'summary':f"Automatic release checks {'enabled' if policy['enabled'] else 'paused'}; daily budget {policy['daily_budget']} checks."}
        elif args.cmd=='recover-metadata':
            result=recover_publisher_metadata()
        elif args.cmd in ('scan','sync-local'):
            if args.trainer_path and len(args.trainer_path)!=len(args.game):
                raise updates.UpdateError('Each watched game requires a matching trainer path')
            assignments=dict(zip(args.game,args.trainer_path))
            if args.cmd=='scan':result=perform_scan(args.game,assignments=assignments,force=args.force,live=not args.offline)
            else:result=refresh_local_only(args.game,assignments)
        elif args.cmd=='dashboard':
            result=update_dashboard(state(), prefs())
        elif args.cmd=='publisher-page':
            result={'url':cached_publisher_page(state(),args.game,args.provider)}
        else:
            s=state();policy=prefs()
            result={'enabled':policy['enabled'],'queue':queue_rows(s),'used':s.get('used',0),
                    'budget':policy['daily_budget'],'include_unassigned':policy['include_unassigned'],
                    'coverage':coverage(s),'managers':s.get('managers',[]),'summary':update_summary(s,policy),'details':queue_details(s)}
            if args.cmd=='report':
                path=export_report(s,policy)
                result['report_path']=str(path)
                result['summary']='Automation report saved: '+str(path)
        if args.cmd in ('scan','sync-local'): result['details']=queue_details(state())
        if getattr(args,'compact',False) and args.cmd=='dashboard':
            result={k:result[k] for k in ('summary','available','updates','managers','counts','network_requests')}
        elif getattr(args,'compact',False):
            result={'summary':result.get('summary',''), 'enabled':result.get('enabled',False),
                    'budget':result.get('budget',DAILY_GAME_BUDGET),
                    'include_unassigned':result.get('include_unassigned',True),
                    'details':result.get('details',''), 'coverage':result.get('coverage',{}),
                    'manager_count':len(result.get('managers',[]))}
        if args.cmd=='publisher-page' and args.plain:
            print(result['url'] or '')
        else:
            print(json.dumps(result,ensure_ascii=False))
        return 0
    except (OSError, ValueError, updates.UpdateError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
