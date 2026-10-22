#!/usr/bin/env python3
"""GameWeld trainer update pipeline (0.8.0 dev1).

Read-only official-page discovery and opt-in, catalog-pinned installs.
No arbitrary web search results are treated as executable download sources.
A catalog checksum establishes agreement with its publisher/catalog, not a malware guarantee.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import datetime
import subprocess
import contextlib
import fcntl
import stat
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SOURCE_HOST = 'flingtrainer.com'
# Official provider destinations. Platform-managed services retain responsibility for
# in-app trainer licensing, downloads and updates. No credential scraping.
PROVIDERS = {
    'fling': {'name':'FLiNG', 'mode':'standalone', 'home':'https://flingtrainer.com/'},
    'hextrainer': {'name':'HexTrainer', 'mode':'standalone', 'home':'https://hextrainer.com/trainers'},
    'cheatevolution': {'name':'Cheat Evolution', 'mode':'managed', 'home':'https://cheatevolution.com/downloads.php'},
    'aurora': {'name':'Cheat Happens Aurora', 'mode':'managed', 'home':'https://www.cheathappens.com/trainers.asp'},
    'wand': {'name':'Wand / WeMod', 'mode':'managed', 'home':'https://wand.com/'},
}
PUBLISHER_HOSTS = {
    'fling': frozenset(('flingtrainer.com', 'www.flingtrainer.com')),
    'hextrainer': frozenset(('hextrainer.com', 'www.hextrainer.com')),
    'cheatevolution': frozenset(('cheatevolution.com', 'www.cheatevolution.com')),
    'aurora': frozenset(('cheathappens.com', 'www.cheathappens.com')),
    'wand': frozenset(('wand.com', 'www.wand.com')),
}

def source_capabilities():
    """Read-only capability summary. A publisher page is not a verified binary feed.

    All providers intentionally lack any bundled official release-signing key.
    Locally pinned keys are visible as local configuration, not official endorsement.
    """
    keys=read_trust_store()
    audit=catalog_audit()
    records=[]
    for provider,info in PROVIDERS.items():
        managed=info['mode']=='managed'
        records.append({
            'provider':provider,'name':info['name'],'mode':info['mode'],
            'home':info['home'],'capability':'publisher-app-managed' if managed else 'publisher-pages-only',
            'signed_official_feed_bundled':False,
            'pinned_local_key':provider in keys,
            'pinned_key_fingerprint':keys[provider]['fingerprint'] if provider in keys else None,
            'download_policy':'explicit-approval-and-imported-catalog' if not managed else 'publisher-app-responsible',
        })
    return {'schema':1,'network_requests':0,'catalog_status':audit['catalog_status'],
            'catalog_entries':audit.get('entry_count',0),'catalog_reason':audit.get('reason'),
            'providers':records,
            'warning':'Publisher pages and locally pinned keys are not independently authenticated official release feeds.'}

def provider_url(provider, game):
    if provider not in PROVIDERS: raise UpdateError('Unknown trainer provider')
    if provider == 'fling': return official_search_url(game)
    # Neither undocumented APIs nor guessed direct download paths are used.
    return PROVIDERS[provider]['home']

def publisher_host(url, provider):
    parsed = urllib.parse.urlsplit(url)
    return (provider in PUBLISHER_HOSTS and parsed.scheme == 'https'
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443) and parsed.hostname in PUBLISHER_HOSTS[provider])

def provider_report(provider, game, html=None):
    if provider not in PROVIDERS: raise UpdateError('Unknown trainer provider')
    info = PROVIDERS[provider]
    if provider == 'aurora' and html is not None:
        # Only publisher-advertised version, never assert local comparison.
        m=re.search(r'\bVersion\s+(\d+(?:\.\d+){2,4})\b',html,re.I)
        report=provider_report(provider,game)
        if m:
            report['publisher_version']=m.group(1)
            report['detail']='Publisher lists AurorAI '+m.group(1)+'; local version not compared.'
        return report
    if info['mode'] == 'managed':
        return {'provider':provider, 'name':info['name'], 'mode':info['mode'],
                'status':'managed-in-app', 'url':info['home'],
                'detail':'The publisher app manages its own trainer downloads/updates.'}
    if provider == 'hextrainer':
        if html is None:
            return {'provider':provider,'name':info['name'],'mode':info['mode'],
                    'status':'official-catalog', 'url':info['home'],
                    'detail':'Browse the official game trainer index. Per-game update verification requires publisher metadata.'}
        parser=PageLinks(); parser.feed(html)
        want=game_tokens(game); matches=[];seen=set()
        for title, href in parser.links:
            url=urllib.parse.urljoin(info['home'],href)
            if (not publisher_host(url,provider) or
                not re.fullmatch(r'/trainers/[a-z0-9-]+/?',urllib.parse.urlsplit(url).path)):
                continue
            overlap=1.0 if want and game_tokens(title)==want else 0
            if overlap >= .8 and url not in seen:
                seen.add(url);matches.append({'title':title[:180],'url':url,'score':round(overlap,2)})
        matches.sort(key=lambda x:(-x['score'],x['title']))
        return {'provider':provider,'name':info['name'],'mode':info['mode'],
                'status':'official-match' if matches else 'official-catalog',
                'url':matches[0]['url'] if matches else info['home'],
                'matches':matches[:5],
                'detail':'Publisher trainer page found; binary version remains unverified.' if matches else 'No exact game title confirmed on this page.'}
    if html is not None:
        matches=parse_official_results(html,game)
        return {'provider':provider,'name':info['name'],'mode':info['mode'],
                'status':'official-match' if matches else 'not-confirmed',
                'url':matches[0]['url'] if matches else provider_url(provider,game),
                'matches':matches,
                'detail':'Publisher trainer page found; binary version remains unverified.' if matches else 'No exact release confirmed.'}
    return {'provider':provider,'name':info['name'],'mode':info['mode'],
            'status':'official-search', 'url':provider_url(provider,game),
            'detail':'Review official standalone trainer releases.'}

class PageText(HTMLParser):
    """Extract visible publisher text and bounded table rows, never URLs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=0; self.parts=[]; self.rows=[]
        self.in_row=False; self.in_cell=False; self.current=[]; self.cell=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','template'):
            self.hidden+=1
        if self.hidden: return
        if tag=='tr':
            self.in_row=True; self.current=[]
        elif tag in ('th','td') and self.in_row:
            self.in_cell=True;self.cell=[]
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','template'):
            if self.hidden: self.hidden-=1
            return
        if self.hidden:return
        if tag in ('th','td') and self.in_cell:
            self.current.append(' '.join(' '.join(self.cell).split())[:240]);self.in_cell=False
        elif tag=='tr' and self.in_row:
            if self.current and len(self.rows)<120: self.rows.append(self.current[:10])
            self.current=[];self.in_row=False;self.in_cell=False
    def handle_data(self,value):
        if self.hidden:return
        self.parts.append(value)
        if self.in_cell:self.cell.append(value)

# The HTML's visible table cells are untrusted *informational* publisher
# evidence. Never derive executable URLs, checksums or installation commands.
FLING_FILE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z0-9][A-Za-z0-9_.-]{5,155}\.Trainer-FLiNG)\b',re.I)
ISO_DATE = re.compile(r'\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b')
SIZE_LABEL = re.compile(r'^\s*(\d{1,6}(?:[.,]\d{1,3})?)\s*(KB|MB|GB)\s*$',re.I)

def _release_date(value):
    from datetime import date
    m=ISO_DATE.search(value)
    if not m:return None
    try:return date(*map(int,m.groups())).isoformat()
    except ValueError:return None

def _package_name(cell):
    # No headings or leading download counts: a package must be an entire
    # filename cell, apart from whitespace, rather than a substring of a row.
    name=cell.strip()
    if len(name)>180 or not FLING_FILE.fullmatch(name):return None
    return name[:170]

def _release_from_row(row):
    if not row:return None
    # Publisher tables may have a separate Download/icon cell before File.
    # Require one unambiguous *entire cell* filename; skip confusing rows.
    names=[_package_name(cell) for cell in row]
    names=[n for n in names if n]
    if len(names)!=1:return None
    name=names[0]
    date_value=None
    for cell in row:
        if not date_value:date_value=_release_date(cell)
    if not date_value:return None
    record={'name':name,'published':date_value}
    # Size is a quoted publisher claim, not a downloaded-file verification.
    for cell in row:
        m=SIZE_LABEL.fullmatch(cell)
        if m:
            record['publisher_file_size']=m.group(1)+' '+m.group(2).upper()
            break
    return record

def _text_release_rows(text, existing_names=()):
    """Recover older FLiNG flat-text tables, even alongside unrelated HTML tables.

    Only a *whole* recognizable FLiNG filename immediately followed by a
    publisher-formatted date is accepted. Never read download URLs from HTML.
    The 96-character bound rejects dates from unrelated page prose.
    """
    seen={str(n).casefold() for n in existing_names}
    items=[]
    # Match from the beginning of a package token, not the preceding header or
    # a download-count cell. FLING_FILE itself is intentionally restrictive.
    for match in FLING_FILE.finditer(text[:40000]):
        name=_package_name(match.group(1))
        if not name or name.casefold() in seen:continue
        following=text[match.end():match.end()+96]
        # FLiNG's flat markup inserts the date after the filename; require
        # it to be the next meaningful token, not a distant unrelated date.
        date_match=re.match(r'\s*(20\d{2}[-./]\d{1,2}[-./]\d{1,2})(?!\d)',following)
        if not date_match:continue
        published=_release_date(date_match.group(1))
        if not published:continue
        seen.add(name.casefold())
        items.append({'name':name,'published':published})
        if len(items)>=8:break
    return items


def publisher_page_metadata(provider, html):
    """Parse bounded release metadata from visible official-page HTML.

    The report stores clean, structured filename/date/size claims only;
    it never extracts untrusted download links, executable hashes or commands.
    """
    if provider not in ('fling','hextrainer') or not isinstance(html,str):return {}
    parser=PageText();parser.feed(html[:MAX_HTML_BYTES])
    text=' '.join(' '.join(parser.parts).split())
    result={}
    if provider=='fling':
        m=re.search(r'Game\s+Version\s*:\s*(.{1,110}?)(?=\s*[·|]\s*Last\s+Updated\s*:|\s+Last\s+Updated\s*:|\s+Download\b|\s+Options\b|$)',text,re.I)
        if m:
            version=m.group(1).strip(' \t·|')
            if len(version)<=90 and not re.search(r'[<>]',version):result['publisher_game_version']=version
        m=re.search(r'Last\s+Updated\s*:\s*(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})',text,re.I)
        if m:
            from datetime import date
            try:result['publisher_updated']=date(*map(int,m.groups())).isoformat()
            except ValueError:pass
        seen=set();releases=[]
        for row in parser.rows:
            release=_release_from_row(row)
            if not release or release['name'].casefold() in seen:continue
            seen.add(release['name'].casefold());releases.append(release)
            if len(releases)>=8:break
        # Some FLiNG templates render the download listing as visible text,
        # while unrelated page widgets still contain HTML table rows. RC4
        # mistakenly disabled text recovery in that common combination.
        # Always try a strictly bounded, token-validated fallback. Never use
        # downloaded counters or table headers as part of package filenames.
        if len(releases)<8:
            releases.extend(_text_release_rows(text, seen)[:8-len(releases)])
        if releases:
            result['publisher_releases']=releases
            result['publisher_metadata_status']='extracted'
        elif FLING_FILE.search(text):
            result['publisher_metadata_status']='unrecognized-layout'
        elif re.search(r'\bDownload\b',text,re.I):
            result['publisher_metadata_status']='no-package-listed'
        elif re.search(r'\b(?:Game\s+Version|Last\s+Updated)\b',text,re.I):
            result['publisher_metadata_status']='listing-not-visible'
    else:
        m=re.search(r'\b(\d{1,3}) trainer options\b',text,re.I)
        if m:result['publisher_options']=int(m.group(1))
    return result



class OfficialFileLinkParser(HTMLParser):
    """Pair a FLiNG package anchor with its *own* table row's published date.

    Browsing evidence only; no redirect is followed and no bytes are downloaded.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.row=None;self.cell=None;self.anchor=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='tr':self.row=[];self.cell=None
        elif tag in ('td','th') and self.row is not None:
            self.cell={'parts':[],'links':[]};self.anchor=None
        elif tag=='a' and self.cell is not None:
            self.anchor={'href':attrs.get('href',''),'parts':[]}
    def handle_data(self, data):
        if self.cell is not None:self.cell['parts'].append(data)
        if self.anchor is not None:self.anchor['parts'].append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.anchor is not None:
            self.cell['links'].append((' '.join(' '.join(self.anchor['parts']).split()),self.anchor['href']))
            self.anchor=None
        elif tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append({'text':' '.join(' '.join(self.cell['parts']).split()),'links':self.cell['links']})
            self.cell=None;self.anchor=None
        elif tag=='tr' and self.row is not None:
            if len(self.rows)<120:self.rows.append(self.row)
            self.row=None;self.cell=None;self.anchor=None


def _fling_download_link(url):
    """Accept only an unchanged first-party HTTPS opaque /downloads/ locator."""
    try:
        p=urllib.parse.urlsplit(url)
        return (p.scheme=='https' and p.hostname in ('flingtrainer.com','www.flingtrainer.com')
                and p.port in (None,443) and not p.username and not p.password
                and not p.query and not p.fragment and
                re.fullmatch(r'/downloads/(?:[a-zA-Z0-9,_\-.]|%2[Cc]){8,220}/?',p.path) is not None)
    except ValueError:return False


def _fling_matching_game(package, game):
    prefix=re.split(r'\.v\d',package,maxsplit=1,flags=re.I)[0]
    norm=lambda value:re.sub(r'[^a-z0-9]','',str(value).casefold().replace('®',''))
    return norm(prefix)==norm(game)


def official_page_links(game,page,html):
    """Return informational package links directly represented by official HTML.

    A publisher link and a publication date do not establish SHA256, signer identity
    or safety. They are NOT eligible for GameWeld's approved staging operation.
    """
    if not isinstance(game,str) or not game or len(game)>190:raise UpdateError('Invalid game title')
    if not isinstance(page,str) or not publisher_host(page,'fling'):raise UpdateError('Not an official FLiNG HTTPS page')
    url=urllib.parse.urlsplit(page)
    slug=safe_slug(game.replace("'",'').replace('’','').replace('®',''))
    if (url.query or url.fragment or not re.fullmatch(r'/trainer/[a-z0-9-]+-trainer/?',url.path)
        or url.path.rstrip('/')!='/trainer/'+slug+'-trainer'):
        raise UpdateError('Official page does not match the selected game title')
    if not isinstance(html,str) or len(html)>MAX_HTML_BYTES:raise UpdateError('Official page invalid or too large')
    parsed=OfficialFileLinkParser();parsed.feed(html)
    results=[];seen=set()
    for row in parsed.rows:
        cells=[c['text'] for c in row]
        record=_release_from_row(cells)
        if not record or not _fling_matching_game(record['name'],game):continue
        # An anchor must sit inside the exact filename cell, never a nearby
        # advertisement, attachment, another trainer or a download-count cell.
        loc=[]
        for cell in row:
            if _package_name(cell['text'])!=record['name']:continue
            for label,href in cell['links']:
                if label!=record['name']:continue
                target=urllib.parse.urljoin(page,href)
                if _fling_download_link(target):loc.append(target)
        if len(set(loc))!=1 or record['name'].casefold() in seen:continue
        seen.add(record['name'].casefold())
        results.append(dict(record,official_link=loc[0],status='PUBLISHER LINK ONLY — SHA256 NOT VERIFIED'))
        if len(results)>=8:break
    return {'game':game,'page':page,'releases':results,'count':len(results),
            'authenticated':False,'downloaded':False,
            'warning':'First-party page links are informational only. No publisher-authenticated checksum or executable safety verified. Review in a browser; never use these as verified catalog entries.'}

def check_providers(game, providers=None, live=False):
    reports=[]
    for provider in (providers or PROVIDERS):
        if provider not in PROVIDERS:raise UpdateError('Unknown trainer provider')
        html=None
        # On startup check only metadata from the official FLiNG search.
        # No guessed downloads and no rapid crawling of the other publisher sites.
        if live and provider in ('fling','hextrainer','aurora'):
            try:
                with open_trusted(provider_url(provider,game),
                                  host_rule=lambda u:publisher_host(u,provider), timeout=5) as response:
                    bits=response.read(MAX_HTML_BYTES+1)
                if len(bits)>MAX_HTML_BYTES:raise UpdateError('Official page too large')
                html=bits.decode('utf-8','replace')
            except (UpdateError, urllib.error.URLError, OSError, TimeoutError):
                reports.append({'provider':provider,'name':PROVIDERS[provider]['name'],
                                'mode':PROVIDERS[provider]['mode'],'status':'unavailable',
                                'url':provider_url(provider,game), 'detail':'Official search not reachable; no update claimed.'})
                continue
        report = provider_report(provider, game, html)
        # One additional bounded read of the exact official page: useful date and
        # supported game versions, NEVER evidence that a local EXE needs an update.
        if live and report.get('status') == 'official-match' and publisher_host(report.get('url',''),provider):
            try:
                with open_trusted(report['url'],host_rule=lambda u:publisher_host(u,provider),timeout=5) as response:
                    bits=response.read(MAX_HTML_BYTES+1)
                if len(bits)<=MAX_HTML_BYTES:
                    md=publisher_page_metadata(provider,bits.decode('utf-8','replace'))
                    report.update(md)
                    if provider=='fling' and not md.get('publisher_metadata_status'):
                        report['publisher_metadata_status']='page-unrecognized'
                else:
                    report['publisher_metadata_status']='page-too-large'
            except (UpdateError,urllib.error.URLError,OSError,TimeoutError):
                report['publisher_metadata_status']='fetch-error'
        reports.append(report)
    return reports

MAX_HTML_BYTES = 2_000_000
MAX_ARCHIVE_BYTES = 250_000_000
MAX_UNPACKED_BYTES = 600_000_000
MAX_FILES = 150

class UpdateError(Exception):
    pass

def safe_slug(s):
    text = re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')
    return text[:110] or 'unknown'

def game_tokens(game):
    return set(re.findall(r'[a-z0-9]+', game.lower())) - {'the', 'edition', 'game', 'trainer', 'complete', 'remastered'}

def official_search_url(game):
    return f'https://{SOURCE_HOST}/?s={urllib.parse.quote_plus(game + " trainer")}'

def _official_host(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.username is None and p.password is None and p.port in (None,443) and (p.hostname == SOURCE_HOST or p.hostname == 'www.' + SOURCE_HOST)

class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed): super().__init__(); self.allowed=allowed
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        if not self.allowed(newurl):
            raise UpdateError('Download redirected outside the approved publisher host')
        return super().redirect_request(req,fp,code,msg,hdrs,newurl)

def open_trusted(url, host_rule=_official_host, timeout=12):
    if not host_rule(url): raise UpdateError('URL is outside an approved HTTPS publisher host')
    opener=urllib.request.build_opener(RestrictedRedirect(host_rule))
    req=urllib.request.Request(url,headers={'User-Agent':'GameWeld/0.8.0-dev1 (+read-only trainer release check)','Accept':'text/html,application/zip,application/octet-stream'})
    return opener.open(req,timeout=timeout)

class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.active=None;self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.active=dict(attrs).get('href');self.text=[]
    def handle_data(self, data):
        if self.active is not None:self.text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append((' '.join(' '.join(self.text).split()), self.active));self.active=None;self.text=[]

def parse_official_results(html, game):
    parser=PageLinks();parser.feed(html)
    want=game_tokens(game)
    if not want:return []
    found={}
    for title,href in parser.links:
        url=urllib.parse.urljoin('https://'+SOURCE_HOST+'/',href)
        if not _official_host(url) or not re.search(r'/trainer/[^/?#]+/?', urllib.parse.urlsplit(url).path):continue
        supplied=game_tokens(title)
        if not supplied:continue
        overlap=len(want & supplied)/len(want)
        if overlap<0.8:continue
        key=url.split('#')[0].split('?')[0]
        if key not in found:found[key]={'title':title[:180], 'url':key, 'score':round(overlap,2)}
    return sorted(found.values(),key=lambda x:(-x['score'],x['title']))[:6]

def discover(game, offline_html=None):
    if offline_html is not None:html=offline_html
    else:
        with open_trusted(official_search_url(game)) as response:
            html=response.read(MAX_HTML_BYTES+1)
        if len(html)>MAX_HTML_BYTES:raise UpdateError('Official search page was too large')
        html=html.decode('utf-8','replace')
    return parse_official_results(html,game)

def paths():
    data=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'gameweld/trainers'
    conf=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'gameweld/trainer-catalog.json'
    return data,conf

# RC6: OPTIONAL publisher-key-pinned catalog format. A user-pinned public key
# establishes continuity with that key, NOT that the key belongs to the publisher.
# There are deliberately no fabricated built-in FLiNG/HexTrainer public keys.
ED25519_SPKI_PREFIX = bytes.fromhex('302a300506032b6570032100')
FINGERPRINT = re.compile(r'[a-f0-9]{64}\Z')


def trust_path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'gameweld/trusted-publisher-keys.json'


def public_key_der(pem):
    if isinstance(pem,bytes):pem=pem.decode('ascii','strict')
    match=re.fullmatch(r'\s*-----BEGIN PUBLIC KEY-----\s*([A-Za-z0-9+/=\s]+)\s*-----END PUBLIC KEY-----\s*',pem)
    if not match:raise UpdateError('Expected an Ed25519 PUBLIC KEY PEM, not a certificate or private key')
    try: der=base64.b64decode(''.join(match.group(1).split()),validate=True)
    except (ValueError,binascii.Error) as exc:raise UpdateError('Invalid PEM base64') from exc
    if len(der)!=44 or not der.startswith(ED25519_SPKI_PREFIX):
        raise UpdateError('Only an Ed25519 subjectPublicKeyInfo key is supported')
    return der


def public_key_pem(der):
    b=base64.b64encode(der).decode('ascii')
    return '-----BEGIN PUBLIC KEY-----\n'+b+'\n-----END PUBLIC KEY-----\n'


def _read_bounded_json(path,limit):
    if path.is_symlink():raise UpdateError('Symlinked security metadata is rejected')
    if not path.is_file():return None
    if path.stat().st_size>limit:raise UpdateError('Security metadata exceeds size limit')
    def unique_pairs(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise UpdateError('Duplicate key in security metadata JSON')
            d[k]=v
        return d
    try:return json.loads(path.read_text('utf-8'),object_pairs_hook=unique_pairs)
    except (ValueError,UnicodeError) as exc:raise UpdateError('Malformed security metadata JSON') from exc


def read_trust_store():
    doc=_read_bounded_json(trust_path(),32768)
    if doc is None:return {}
    if not isinstance(doc,dict) or doc.get('schema')!=1 or not isinstance(doc.get('keys'),dict):
        raise UpdateError('Malformed pinned-key store')
    keys=doc['keys']
    if len(keys)>len(PROVIDERS):raise UpdateError('Pinned-key store contains too many providers')
    for provider,record in keys.items():
        if provider not in PROVIDERS or not isinstance(record,dict):raise UpdateError('Invalid pinned provider key')
        if record.keys()!={'der','fingerprint'}:raise UpdateError('Unexpected pinned key fields')
        try:der=base64.b64decode(record['der'],validate=True)
        except (TypeError,ValueError,binascii.Error) as exc:raise UpdateError('Corrupt pinned key') from exc
        if len(der)!=44 or not der.startswith(ED25519_SPKI_PREFIX) or hashlib.sha256(der).hexdigest()!=record['fingerprint']:
            raise UpdateError('Pinned key fingerprint mismatch')
    return keys


def _write_trust_store(keys):
    path=trust_path();path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():raise UpdateError('Symlinked trust store rejected')
    # Atomically replace a private, user-owned trust file. Never rewrite when auditing.
    fd,name=tempfile.mkstemp(prefix='.pinned-keys-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump({'schema':1,'keys':keys},f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def fingerprint_key(key_path):
    p=Path(key_path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>4096:raise UpdateError('Unsafe public-key file')
    return hashlib.sha256(public_key_der(p.read_bytes())).hexdigest()


def pin_key(provider,key_path,expected,confirm=False):
    if not confirm:raise UpdateError('Explicit key-pinning approval is required')
    if provider not in PROVIDERS:raise UpdateError('Unknown provider')
    if not isinstance(expected,str) or not FINGERPRINT.fullmatch(expected):raise UpdateError('Expected an independently verified SHA256 fingerprint')
    key=Path(key_path)
    if key.is_symlink() or not key.is_file() or key.stat().st_size>4096:raise UpdateError('Unsafe public-key file')
    der=public_key_der(key.read_bytes());fingerprint=hashlib.sha256(der).hexdigest()
    if fingerprint!=expected:raise UpdateError('Public key fingerprint does not match the independently supplied fingerprint')
    store=read_trust_store()
    if provider in store and store[provider]['fingerprint']!=fingerprint:
        raise UpdateError('Key rotation rejected; remove old pin explicitly before installing a different key')
    store[provider]={'der':base64.b64encode(der).decode('ascii'),'fingerprint':fingerprint}
    _write_trust_store(store)
    return {'provider':provider,'fingerprint':fingerprint,'warning':'A pinned key does not independently establish publisher identity'}


def unpin_key(provider,confirm=False):
    if not confirm:raise UpdateError('Explicit unpin approval required')
    store=read_trust_store()
    if provider not in store:raise UpdateError('Provider key not pinned')
    del store[provider];_write_trust_store(store)
    return {'removed':provider,'warning':'Future unsigned catalogs for this provider may become eligible for review again'}


def _signed_payload(doc):
    return json.dumps({k:v for k,v in doc.items() if k!='signature'},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')


def _utc_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ',value):
        raise UpdateError('Signed catalog requires an ISO UTC issue/expiry date')
    try:return datetime.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    except ValueError as exc:raise UpdateError('Invalid signed catalog date') from exc


def _verify_signed_manifest(doc,keys):
    required={'schema','provider','issued_at','expires_at','key_fingerprint','entries','signature'}
    if set(doc)!=required or doc.get('schema')!=2:raise UpdateError('Unsupported signed catalog envelope')
    provider=doc.get('provider')
    if provider not in PROVIDERS:raise UpdateError('Unknown signed catalog provider')
    record=keys.get(provider)
    if not record:raise UpdateError('No independently pinned public key for signed catalog provider')
    if doc.get('key_fingerprint')!=record['fingerprint']:raise UpdateError('Signed catalog key is not the pinned publisher key')
    issued=_utc_date(doc.get('issued_at'));expires=_utc_date(doc.get('expires_at'));now=datetime.datetime.now(datetime.timezone.utc)
    if issued>now+datetime.timedelta(minutes=5) or expires<=now or expires-issued>datetime.timedelta(days=90) or expires<=issued:
        raise UpdateError('Signed catalog is expired, future-dated or has an excessive validity window')
    signature=doc.get('signature')
    try:raw=base64.b64decode(signature,validate=True)
    except (TypeError,ValueError,binascii.Error) as exc:raise UpdateError('Invalid catalog signature encoding') from exc
    if len(raw)!=64:raise UpdateError('Invalid Ed25519 signature length')
    payload=_signed_payload(doc)
    with tempfile.TemporaryDirectory(prefix='gameweld-signature-') as tmp:
        tmp=Path(tmp);keyfile=tmp/'key.pem';message=tmp/'manifest.json';sigfile=tmp/'manifest.sig'
        keyfile.write_text(public_key_pem(base64.b64decode(record['der'])),'ascii')
        message.write_bytes(payload);sigfile.write_bytes(raw)
        try:
            cp=subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(keyfile),'-rawin','-in',str(message),'-sigfile',str(sigfile)],
                              capture_output=True,timeout=8,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:raise UpdateError('OpenSSL Ed25519 verification unavailable') from exc
        if cp.returncode!=0:raise UpdateError('Ed25519 signature verification failed')
    entries=validate_catalog({'schema':1,'entries':doc['entries']})
    if any(e['provider']!=provider for e in entries):raise UpdateError('Signed catalog mixes providers')
    return [dict(e,_provenance='key-pinned-signature',_fingerprint=record['fingerprint']) for e in entries]


def import_signed_catalog(source,confirm=False):
    """Offline atomic verified import; preserve previous catalog for manual recovery."""
    if not confirm:raise UpdateError('Explicit signed catalog import approval required')
    incoming=Path(source)
    doc=_read_bounded_json(incoming,2_000_000)
    if doc is None or not isinstance(doc,dict) or doc.get('schema')!=2:
        raise UpdateError('Only signed schema 2 catalogs can be imported by this action')
    entries=_verify_signed_manifest(doc,read_trust_store())
    _,destination=paths()
    if destination.is_symlink() or destination.parent.is_symlink():raise UpdateError('Unsafe catalog destination')
    old=_read_bounded_json(destination,2_000_000)
    if old is not None and isinstance(old,dict) and old.get('schema')==2 and old.get('provider')==doc['provider']:
        old_time=_utc_date(old.get('issued_at'))
        new_time=_utc_date(doc.get('issued_at'))
        if new_time<old_time or (new_time==old_time and old!=doc):
            raise UpdateError('Older/equivocal signed catalog rejected; potential rollback')
        if old==doc:
            return {'imported':len(entries),'provider':doc['provider'],'status':'already-imported','fingerprint':doc['key_fingerprint']}
    destination.parent.mkdir(parents=True,exist_ok=True)
    backup=destination.with_name(destination.name+'.previous')
    if backup.is_symlink():raise UpdateError('Symlink catalog backup rejected')
    payload=(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode('utf-8')
    fd,name=tempfile.mkstemp(prefix='.signed-catalog-',dir=str(destination.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600)
        if old is not None:
            # Preserve one prior active catalog, with no trust-level reinterpretation.
            backupfd,backupname=tempfile.mkstemp(prefix='.old-catalog-',dir=str(destination.parent))
            try:
                with os.fdopen(backupfd,'wb') as f:
                    f.write(destination.read_bytes());f.flush();os.fsync(f.fileno())
                os.chmod(backupname,0o600);os.replace(backupname,backup)
            finally:
                if os.path.exists(backupname):os.unlink(backupname)
        os.replace(name,destination)
    finally:
        if os.path.exists(name):os.unlink(name)
    return {'imported':len(entries),'provider':doc['provider'],'status':'key-pinned-signature',
            'fingerprint':doc['key_fingerprint'],'previous_catalog_preserved':old is not None}


def catalog_audit(path=None):
    _,default=paths();p=Path(path) if path else default
    keys=read_trust_store()
    if not p.is_file():return {'catalog_status':'missing','key_count':len(keys),'provider_keys':{k:v['fingerprint'] for k,v in keys.items()}}
    try:
        entries=read_catalog(p)
        mode='key-pinned-signature' if _read_bounded_json(p,2_000_000).get('schema')==2 else 'legacy-unsigned'
        return {'catalog_status':mode,'entry_count':len(entries),'key_count':len(keys),'provider_keys':{k:v['fingerprint'] for k,v in keys.items()}}
    except UpdateError as e:
        return {'catalog_status':'rejected','reason':str(e),'key_count':len(keys),'provider_keys':{k:v['fingerprint'] for k,v in keys.items()}}


def validate_catalog(doc):
    if not isinstance(doc,dict) or doc.get('schema')!=1 or not isinstance(doc.get('entries'),list):raise UpdateError('Unsupported catalog schema')
    if len(doc['entries'])>10000:raise UpdateError('Catalog too large')
    ids=set(); entries=[]
    for raw in doc['entries']:
        if not isinstance(raw,dict):raise UpdateError('Invalid catalog entry')
        needed=['id','game','version','url','sha256']
        if any(not isinstance(raw.get(k),str) or not raw[k] for k in needed):raise UpdateError('Catalog entry missing required fields')
        if len(raw['id'])>120 or not re.fullmatch(r'[a-zA-Z0-9_.-]+',raw['id']) or raw['id'] in ids:raise UpdateError('Invalid or duplicate catalog ID')
        ids.add(raw['id'])
        if not re.fullmatch(r'[0-9a-f]{64}',raw['sha256']):raise UpdateError('Invalid SHA256')
        provider=raw.get('provider','fling')
        if provider not in ('fling','hextrainer','cheatevolution','aurora','wand'):
            raise UpdateError('Unknown catalog provider')
        if not publisher_host(raw['url'],provider):raise UpdateError('Catalog uses a non-official download URL')
        path=urllib.parse.urlsplit(raw['url']).path.lower()
        if not path.endswith(('.zip','.exe')):raise UpdateError('Catalog entry must name a ZIP or EXE')
        entries.append(dict(raw,provider=provider))
    return entries

def read_catalog(path):
    doc=_read_bounded_json(path,2_000_000)
    if doc is None:return []
    if not isinstance(doc,dict):raise UpdateError('Catalog must be a JSON object')
    keys=read_trust_store()
    if doc.get('schema')==2:return _verify_signed_manifest(doc,keys)
    entries=validate_catalog(doc)
    # No downgrade to an unsigned catalog once the user has pinned the provider.
    if any(entry['provider'] in keys for entry in entries):
        raise UpdateError('Unsigned catalog rejected for a key-pinned provider')
    return [dict(entry,_provenance='legacy-unsigned') for entry in entries]

def read_receipt(destination):
    """Do not follow a symlinked receipt or read an unbounded JSON file."""
    try:
        p=destination/'receipt.json'
        if p.is_symlink() or p.stat().st_size>32768:return None
        doc=json.loads(p.read_text('utf-8'))
        return doc if isinstance(doc,dict) else None
    except (OSError,ValueError,UnicodeError):return None


def verified_staged_file(destination, expected=None):
    """Verify a staged trainer without executing it. Catalog trust is separate."""
    if destination.is_symlink() or not destination.is_dir():return None
    receipt=read_receipt(destination)
    if not receipt or receipt.get('schema')!=1:return None
    filename=receipt.get('file')
    if (not isinstance(filename,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,218}\.exe',filename)
        or not isinstance(receipt.get('exe_sha256'),str)
        or not re.fullmatch(r'[a-f0-9]{64}',receipt['exe_sha256'])):return None
    if expected:
        for key in ('game','id','provider','version','url','sha256'):
            if receipt.get(key)!=expected.get(key):return None
    target=destination/filename
    try:
        if target.is_symlink() or not target.is_file():return None
        if target.stat().st_size>MAX_ARCHIVE_BYTES:return None
        sha=hashlib.sha256()
        with target.open('rb') as f:
            for data in iter(lambda:f.read(256*1024),b''):sha.update(data)
        if sha.hexdigest()!=receipt['exe_sha256'] or not looks_like_pe(target):return None
        return target
    except OSError:return None


def stage_status(game, entry_id, catalog=None):
    """Return locally staged/backup evidence; a manifest does not authenticate the publisher."""
    root,default=paths()
    entries=read_catalog(Path(catalog) if catalog else default)
    matches=[e for e in entries if e['id']==entry_id and game_tokens(e['game'])==game_tokens(game)]
    if len(matches)!=1:raise UpdateError('No exact game/catalog entry')
    item=matches[0]
    dest=root/safe_slug(item['game'])/safe_slug(item['id'])
    backup=dest.with_name(dest.name+'.previous')
    for path in (dest.parent,dest,backup):
        if path.is_symlink():raise UpdateError('Symlink staging path rejected')
    main=verified_staged_file(dest)
    main_receipt=read_receipt(dest)
    main_game=(isinstance(main_receipt,dict) and main_receipt.get('game')==item['game']
               and main_receipt.get('id')==item['id'] and main_receipt.get('provider')==item['provider'])
    old=verified_staged_file(backup)
    old_receipt=read_receipt(backup)
    backup_game=(isinstance(old_receipt,dict) and old_receipt.get('game')==item['game']
                 and old_receipt.get('id')==item['id'] and old_receipt.get('provider')==item['provider'])
    return {'game':item['game'],'id':item['id'],'catalog_version':item['version'],
            'current': 'verified-locally' if main and main_game else 'missing-or-unverified',
            'current_version': main_receipt.get('version') if main and main_game else None,
            'catalog_match':bool(main and main_game and all(main_receipt.get(k)==item.get(k) for k in ('game','id','provider','version','url','sha256'))),
            'current_path':str(main) if main and main_game else None,
            'backup':'verified-locally' if old and backup_game else ('invalid' if backup.exists() else 'absent'),
            'backup_version':old_receipt.get('version') if old and backup_game else None,
            'can_rollback':bool(main and main_game and old and backup_game),
            'provenance':'local-checksum-only; catalog publisher authenticity not established'}


@contextlib.contextmanager
def stage_lock(parent):
    if parent.is_symlink():raise UpdateError('Symlink staging directory rejected')
    parent.mkdir(parents=True,exist_ok=True)
    flags=os.O_RDWR|os.O_CREAT
    if hasattr(os,'O_NOFOLLOW'):flags|=os.O_NOFOLLOW
    try: fd=os.open(parent/'.stage.lock',flags,0o600)
    except OSError as exc:raise UpdateError('Cannot open stage lock') from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise UpdateError('Invalid staging lock')
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def rollback(game, entry_id, catalog=None, confirm=False):
    """Swap two already staged, locally verified versions; never touch assignments."""
    if not confirm:raise UpdateError('Explicit rollback approval is required')
    root,default=paths()
    entries=read_catalog(Path(catalog) if catalog else default)
    matches=[e for e in entries if e['id']==entry_id and game_tokens(e['game'])==game_tokens(game)]
    if len(matches)!=1:raise UpdateError('No exact game/catalog entry')
    item=matches[0]
    dest=root/safe_slug(item['game'])/safe_slug(item['id'])
    backup=dest.with_name(dest.name+'.previous')
    with stage_lock(dest.parent):
        status=stage_status(game,entry_id,catalog)
        if not status['can_rollback']:raise UpdateError('No locally verified current and previous trainer to swap')
        # Both sides must be real directories: a symlink must never become the
        # destination of an atomic rename. A temporary sibling permits undo.
        tmp=Path(tempfile.mkdtemp(prefix='.swap-trainer-',dir=str(dest.parent)))
        tmp.rmdir()
        moved=False;promoted=False
        try:
            os.replace(dest,tmp);moved=True
            os.replace(backup,dest);promoted=True
            os.replace(tmp,backup)
        except Exception:
            if promoted and not backup.exists() and dest.exists():os.replace(dest,backup)
            if moved and tmp.exists() and not dest.exists():os.replace(tmp,dest)
            raise
        restored=verified_staged_file(dest)
        if not restored:raise UpdateError('Rolled-back trainer failed local post-swap verification')
        return {'restored':str(restored),'previous_saved':str(backup),
                'message':'Local checksum passed; existing game assignments were not changed'}

def check_catalog(game, catalog=None):
    root,default=paths(); entries=read_catalog(Path(catalog) if catalog else default)
    want=game_tokens(game); found=[]
    for entry in entries:
        if safe_slug(entry['game'])!=safe_slug(game) and game_tokens(entry['game'])!=want:continue
        d=root/safe_slug(entry['game'])/safe_slug(entry['id'])
        record=read_receipt(d)
        current=bool(record and record.get('sha256')==entry['sha256'] and verified_staged_file(d,entry))
        found.append({'id':entry['id'],'game':entry['game'],'provider':entry['provider'],'version':entry['version'],'url':entry['url'],'sha256':entry['sha256'],'installed':bool(current),'status':'installed' if current else 'available','catalog_provenance':entry.get('_provenance','legacy-unsigned')})
    return found

def copy_limited(response,target,max_size):
    total=0;sha=hashlib.sha256()
    with target.open('wb') as dst:
        while True:
            part=response.read(256*1024)
            if not part:break
            total+=len(part)
            if total>max_size:raise UpdateError('Trainer download exceeds size limit')
            sha.update(part);dst.write(part)
        dst.flush();os.fsync(dst.fileno())
    return sha.hexdigest()

def safe_zip_extract(source,destination):
    with zipfile.ZipFile(source) as z:
        infos=z.infolist()
        if len(infos)>MAX_FILES:raise UpdateError('Trainer ZIP contains too many files')
        total=0;executables=[]
        for info in infos:
            p=Path(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or '\x00' in info.filename:raise UpdateError('Unsafe archive path')
            if ((info.external_attr>>16)&0o170000)==0o120000:raise UpdateError('Archive symlink rejected')
            total+=info.file_size
            if total>MAX_UNPACKED_BYTES:raise UpdateError('Archive extraction exceeds size limit')
            if info.is_dir():continue
            if p.suffix.lower() not in {'.exe','.txt','.md','.ini','.json','.dll','.png','.jpg'}:raise UpdateError('Unexpected archive file type')
            if p.suffix.lower()=='.exe':executables.append(info)
        if len(executables)!=1:raise UpdateError('Archive must contain exactly one Windows trainer EXE')
        exe=executables[0];out=destination/Path(exe.filename).name
        with z.open(exe) as src, out.open('xb') as dst:shutil.copyfileobj(src,dst)
        if not looks_like_pe(out):raise UpdateError('Archive does not contain a valid Windows EXE header')
        return out

def looks_like_pe(p):
    try:
        with p.open('rb') as f:
            head=f.read(64)
            if len(head)<64 or not head.startswith(b'MZ'):return False
            loc=int.from_bytes(head[0x3c:0x40],'little')
            if loc<64 or loc>1000000:return False
            f.seek(loc);return f.read(4)==b'PE\0\0'
    except OSError:return False

def _install_locked(game, entry_id, catalog, confirm=False, response_factory=open_trusted):
    if not confirm:raise UpdateError('Explicit installation approval is required')
    root,default=paths();matches=[e for e in read_catalog(Path(catalog) if catalog else default) if e['id']==entry_id and game_tokens(e['game'])==game_tokens(game)]
    if len(matches)!=1:raise UpdateError('No exact game/catalog entry')
    item=matches[0];dest=root/safe_slug(item['game'])/safe_slug(item['id'])
    if dest.is_symlink() or dest.parent.is_symlink():raise UpdateError('Symlink destination rejected')
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gameweld-trainer-',dir=str(dest.parent)) as work:
        work=Path(work);archive=work/('download.exe' if item['url'].lower().endswith('.exe') else 'download.zip')
        downloader = response_factory
        # Actual network downloads use strict provider host checks on EVERY redirect.
        if response_factory is open_trusted:
            downloader=lambda url: open_trusted(url,lambda u: publisher_host(u,item['provider']),timeout=15)
        with downloader(item['url']) as source: got=copy_limited(source,archive,MAX_ARCHIVE_BYTES)
        if got!=item['sha256']:raise UpdateError('Downloaded SHA256 does not match catalog; nothing installed')
        if archive.suffix=='.zip': exe=safe_zip_extract(archive,work)
        else:
            if not looks_like_pe(archive):raise UpdateError('Download is not a Windows EXE')
            exe=archive
        suffix='.exe'; name=safe_slug(item['game'])+'-'+safe_slug(item['version'])+suffix
        save=work/name
        if exe!=save:os.replace(exe,save)
        receipt={'schema':1,'game':item['game'],'id':item['id'],'provider':item['provider'],'version':item['version'],'sha256':got,'url':item['url'],'file':name,'exe_sha256':hashlib.sha256(save.read_bytes()).hexdigest()}
        (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n','utf-8')
        archive.unlink(missing_ok=True)
        if dest.exists():
            if dest.is_symlink():raise UpdateError('Symlink destination rejected')
            # Keep existing version for rollback rather than overwriting it.
            if read_receipt(dest)==receipt and verified_staged_file(dest,item):return str(dest/name)
            base=dest.parent/(dest.name+'.previous')
            if base.exists():raise UpdateError('Previous rollback copy exists: resolve it before updating')
            os.replace(dest,base)
            try:os.replace(work,dest)
            except Exception:
                os.replace(base,dest);raise
        else:os.replace(work,dest)
        return str(dest/name)

def install(game, entry_id, catalog, confirm=False, response_factory=open_trusted):
    if not confirm:raise UpdateError('Explicit installation approval is required')
    root,default=paths()
    entries=read_catalog(Path(catalog) if catalog else default)
    matches=[e for e in entries if e['id']==entry_id and game_tokens(e['game'])==game_tokens(game)]
    if len(matches)!=1:raise UpdateError('No exact game/catalog entry')
    parent=root/safe_slug(matches[0]['game'])
    with stage_lock(parent):
        return _install_locked(game,entry_id,catalog,confirm,response_factory)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('discover','check','official-url'):
        q=sub.add_parser(cmd);q.add_argument('--game',required=True);q.add_argument('--plain',action='store_true');q.add_argument('--catalog') if cmd=='check' else None; q.add_argument('--provider',default='fling',choices=list(PROVIDERS))
        if cmd=='check':q.add_argument('--official',action='store_true');q.add_argument('--all-providers',action='store_true');q.add_argument('--catalog-provider',choices=list(PROVIDERS))
    for cmd in ('install','stage-status','rollback'):
        i=sub.add_parser(cmd);i.add_argument('--game',required=True);i.add_argument('--id',required=True);i.add_argument('--catalog')
        if cmd in ('install','rollback'):i.add_argument('--confirm',action='store_true')
    f=sub.add_parser('fingerprint-key');f.add_argument('--key',required=True)
    t=sub.add_parser('pin-key');t.add_argument('--provider',required=True,choices=list(PROVIDERS));t.add_argument('--key',required=True);t.add_argument('--expected-fingerprint',required=True);t.add_argument('--confirm',action='store_true')
    u=sub.add_parser('unpin-key');u.add_argument('--provider',required=True,choices=list(PROVIDERS));u.add_argument('--confirm',action='store_true')
    a=sub.add_parser('trust-report');a.add_argument('--catalog');a.add_argument('--plain',action='store_true')
    s=sub.add_parser('sources');s.add_argument('--plain',action='store_true')
    i=sub.add_parser('import-signed');i.add_argument('--file',required=True);i.add_argument('--confirm',action='store_true')
    r=sub.add_parser('publisher-files');r.add_argument('--game',required=True);r.add_argument('--page',required=True);r.add_argument('--html-file');r.add_argument('--plain',action='store_true')
    args=p.parse_args(argv)
    try:
        if args.cmd=='fingerprint-key':print(json.dumps({'sha256':fingerprint_key(args.key),'warning':'Verify against a trusted independent publisher channel'}))
        elif args.cmd=='pin-key':print(json.dumps(pin_key(args.provider,args.key,args.expected_fingerprint,args.confirm)))
        elif args.cmd=='unpin-key':print(json.dumps(unpin_key(args.provider,args.confirm)))
        elif args.cmd=='import-signed':print(json.dumps(import_signed_catalog(args.file,args.confirm)))
        elif args.cmd=='trust-report':
            result=catalog_audit(args.catalog)
            if args.plain:
                print('TRUST\t'+result['catalog_status']+'\t'+str(result['key_count'])+'\t'+str(result.get('entry_count',0))+'\t'+result.get('reason','').replace('\t',' ').replace('\n',' '))
            else:print(json.dumps(result))
        elif args.cmd=='sources':
            record=source_capabilities()
            if args.plain:
                print('SUMMARY\t'+record['catalog_status']+'\t'+str(record['catalog_entries']))
                for info in record['providers']:
                    print('PROVIDER\t'+info['provider']+'\t'+info['capability']+'\t'+('user-key-pinned' if info['pinned_local_key'] else 'no-key-pinned')+'\t'+info['home'])
            else:print(json.dumps(record,sort_keys=True))
        elif args.cmd=='publisher-files':
            # Test fixtures are explicit and read-only; the normal path fetches
            # only the exact requested first-party page with bounded redirects.
            if args.html_file:
                fixture=Path(args.html_file)
                if fixture.is_symlink() or fixture.stat().st_size>MAX_HTML_BYTES:raise UpdateError('Fixture invalid or too large')
                content=fixture.read_text('utf-8')
            else:
                official_page_links(args.game,args.page,'') # Validate URL before networking
                with open_trusted(args.page,host_rule=lambda u:publisher_host(u,'fling'),timeout=8) as resp:
                    data=resp.read(MAX_HTML_BYTES+1)
                if len(data)>MAX_HTML_BYTES:raise UpdateError('Publisher page too large')
                content=data.decode('utf-8','replace')
            result=official_page_links(args.game,args.page,content)
            if args.plain:
                print('PAGE\t'+result['page'])
                for row in result['releases']:
                    print('FILE\t'+row['name']+'\t'+row['published']+'\t'+row['official_link'])
                print('NOTICE\t'+result['warning'])
            else:print(json.dumps(result))
        elif args.cmd=='official-url':print(provider_url(args.provider,args.game))
        elif args.cmd=='discover':
            results=discover(args.game) if args.provider=='fling' else provider_report(args.provider,args.game).get('matches',[])
            if args.plain:
                print('OFFICIAL\t'+provider_url(args.provider,args.game))
                for r in results:print('MATCH\t'+r['title'].replace('\t',' ')+'\t'+r['url'])
            else:print(json.dumps({'official_search':provider_url(args.provider,args.game),'results':results}))
        elif args.cmd=='check':
            results=check_catalog(args.game,args.catalog)
            if args.catalog_provider:results=[r for r in results if r['provider']==args.catalog_provider]
            if args.plain:
                for r in results:print('CATALOG\t'+r['id']+'\t'+r['version'].replace('\t',' ')+'\t'+r['status']+'\t'+r['sha256']+'\t'+r['url']+'\t'+r['catalog_provenance'])
                if args.official:
                    reports=check_providers(args.game, list(PROVIDERS) if args.all_providers else [args.provider], live=True)
                    for report in reports:
                        # Tabs/newlines never come from untrusted page text into GUI protocol.
                        detail=report['detail'].replace('\t',' ').replace('\n',' ')
                        print('SOURCE\t'+report['provider']+'\t'+report['status']+'\t'+detail+'\t'+report['url'])
                        for match in report.get('matches',[])[:3]:
                            print('OFFICIAL\t'+match['title'].replace('\t',' ')+'\t'+match['url'])
            else:print(json.dumps({'game':args.game,'entries':results,'providers':check_providers(args.game, list(PROVIDERS) if args.all_providers else [args.provider]),'official_search':provider_url(args.provider,args.game)}))
        elif args.cmd=='install':print(json.dumps({'installed':install(args.game,args.id,args.catalog,args.confirm)}))
        elif args.cmd=='stage-status':print(json.dumps(stage_status(args.game,args.id,args.catalog)))
        elif args.cmd=='rollback':print(json.dumps(rollback(args.game,args.id,args.catalog,args.confirm)))
        return 0
    except (UpdateError,ValueError,urllib.error.URLError,OSError,zipfile.BadZipFile) as e:
        print(json.dumps({'error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
