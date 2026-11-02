"""GameWeld: bounded, offline Steam inventory and safe local preferences.

No Steam API, game launch, registry writes or process inspection is required.
"""
import json
import os
import re
import stat
from pathlib import Path

MAX_INPUT = 192 * 1024
MAX_SETTINGS = 64 * 1024
MAX_GAMES = 6000
APPID_NAME = re.compile(r'appmanifest_([1-9][0-9]{0,9})\.acf\Z')
TOKEN = re.compile(r'\s*(?:(//[^\n]*(?:\n|$))|([{}])|"((?:\\.|[^"\\])*)"|([^\s{}"]+))', re.S)


def steamapps_default():
    return Path.home() / '.local/share/Steam/steamapps'


def settings_path():
    xdg = os.environ.get('XDG_CONFIG_HOME', '')
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / '.config'
    return base / 'gameweld' / 'desktop.json'


def read_file(path, limit=MAX_INPUT):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError('unsafe_or_oversized_file')
        data = os.read(fd, limit + 1)
        if len(data) > limit:
            raise ValueError('oversized_file')
        return data
    finally:
        os.close(fd)


def parse_vdf(source):
    """Parse Valve KeyValues (nested maps, comments and escaped quoted text).

    Parser input is always bounded upstream. Reject malformed syntax rather than
    guessing game names or library paths from partial data.
    """
    if not isinstance(source, str) or len(source) > MAX_INPUT:
        raise ValueError('invalid_vdf_length')
    values = []
    pos = 0
    while pos < len(source):
        if source[pos:].isspace():
            break
        token = TOKEN.match(source, pos)
        if token is None:
            raise ValueError('invalid_vdf_token')
        pos = token.end()
        if token.group(1):
            continue
        if token.group(2):
            values.append(token.group(2))
        else:
            value = token.group(3) if token.group(3) is not None else token.group(4)
            # Valve's escaped slash and quote sequences; leave other backslashes intact.
            value = re.sub(r'\\([\\"])', lambda m: m.group(1), value)
            values.append(value)
        if len(values) > 32000:
            raise ValueError('vdf_token_limit')
    offset = 0

    def parse_object(depth=0, closing=False):
        nonlocal offset
        if depth > 24:
            raise ValueError('vdf_nesting_limit')
        result = {}
        while offset < len(values):
            key = values[offset]
            offset += 1
            if key == '}':
                if not closing:
                    raise ValueError('unexpected_vdf_close')
                return result
            if key == '{' or offset >= len(values):
                raise ValueError('invalid_vdf_key')
            value = values[offset]
            offset += 1
            if value == '{':
                result[key] = parse_object(depth + 1, True)
            elif value == '}':
                raise ValueError('invalid_vdf_value')
            else:
                result[key] = value
        if closing:
            raise ValueError('unclosed_vdf_block')
        return result

    result = parse_object()
    if offset != len(values):
        raise ValueError('trailing_vdf_tokens')
    return result


def _text_map(obj):
    return obj if isinstance(obj, dict) else {}


def libraries(steamapps=None):
    root = Path(steamapps).expanduser() if steamapps is not None else steamapps_default()
    found = [root]
    try:
        obj = parse_vdf(read_file(root / 'libraryfolders.vdf').decode('utf-8-sig'))
        obj = _text_map(_text_map(obj).get('libraryfolders', obj))
        for name, val in obj.items():
            if not name.isdecimal():
                continue
            raw = val.get('path') if isinstance(val, dict) else val
            if not isinstance(raw, str) or not raw or len(raw) > 2048 or '\0' in raw:
                continue
            target = Path(raw)
            if not target.is_absolute():
                continue
            path = target / 'steamapps'
            if path not in found:
                found.append(path)
    except (OSError, ValueError, UnicodeError):
        pass
    return found[:64]


def _valid_dirname(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        return False
    if value in ('.', '..') or '/' in value or '\\' in value or '\0' in value:
        return False
    return True


def installed_games(steamapps=None):
    found = {}
    for index, folder in enumerate(libraries(steamapps)):
        try:
            manifests = sorted(folder.glob('appmanifest_*.acf'))[:MAX_GAMES]
        except OSError:
            continue
        for path in manifests:
            match = APPID_NAME.fullmatch(path.name)
            if match is None:
                continue
            try:
                object_ = parse_vdf(read_file(path).decode('utf-8-sig'))
                state = _text_map(_text_map(object_).get('AppState', object_))
                appid = int(match.group(1))
                if state.get('appid') != str(appid):
                    continue
                name = state.get('name', '')
                if not isinstance(name, str) or not name.strip() or len(name) > 240:
                    continue
                install = state.get('installdir', '')
                folder_name = install if _valid_dirname(install) else None
                buildid = state.get('buildid')
                buildid = buildid if isinstance(buildid, str) and buildid.isdecimal() else None
                entry = {'appid': appid, 'title': name.strip(), 'buildid': buildid,
                         'library': 'primary' if index == 0 else 'secondary',
                         'installdir': folder_name,
                         '_steamapps': str(folder)}
                if appid not in found:
                    found[appid] = entry
            except (OSError, ValueError, UnicodeError, TypeError):
                continue
    return sorted(found.values(), key=lambda game: (game['title'].casefold(), game['appid']))


def valid_settings(data):
    data = data if isinstance(data, dict) else {}
    raw_ids = data.get('favourites', [])
    if not isinstance(raw_ids, list):
        raw_ids = []
    favs = sorted({v for v in raw_ids[:500] if type(v) is int and 0 < v <= 9999999999})
    root = data.get('steamapps', str(steamapps_default()))
    if not isinstance(root, str) or not root or len(root) > 2048 or '\0' in root:
        root = str(steamapps_default())
    notes = {}
    raw_notes = data.get('notes', {})
    if isinstance(raw_notes, dict):
        for k, v in list(raw_notes.items())[:500]:
            if (isinstance(k, str) and k.isdecimal() and 0 < int(k) <= 9999999999
                    and isinstance(v, str) and len(v) <= 1200 and '\0' not in v):
                if v.strip():
                    notes[str(int(k))] = v.strip()
    sort = data.get('sort', 'title')
    return {'favourites': favs, 'steamapps': root, 'notes': notes,
            'sort': sort if sort in ('title', 'appid', 'favourites') else 'title'}


def load_settings(path=None):
    try:
        data = json.loads(read_file(Path(path) if path is not None else settings_path(), MAX_SETTINGS))
        return valid_settings(data)
    except (OSError, ValueError, UnicodeError, TypeError):
        return valid_settings(None)


def save_settings(data, path=None):
    file = Path(path) if path is not None else settings_path()
    if file.parent.is_symlink() or file.is_symlink():
        raise ValueError('unsafe_settings_path')
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if file.parent.is_symlink() or file.is_symlink():
        raise ValueError('unsafe_settings_path')
    blob = (json.dumps(valid_settings(data), sort_keys=True) + '\n').encode('utf-8')
    if len(blob) > MAX_SETTINGS:
        raise ValueError('settings_size_limit')
    tmp = file.parent / ('.desktop-' + os.urandom(10).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(blob)
            out.flush()
            os.fsync(out.fileno())
        if file.is_symlink():
            raise ValueError('unsafe_settings_path')
        os.replace(tmp, file)
    finally:
        tmp.unlink(missing_ok=True)


def find_games(games, query='', favourites=None, only_favourites=False, sort='title'):
    word = str(query).strip().casefold()[:200]
    fav = set(favourites or ())
    result = [g for g in games
              if (not word or word in g['title'].casefold() or word in str(g['appid']))
              and (not only_favourites or g['appid'] in fav)]
    if sort == 'appid':
        return sorted(result, key=lambda g: g['appid'])
    if sort == 'favourites':
        return sorted(result, key=lambda g: (g['appid'] not in fav, g['title'].casefold(), g['appid']))
    return sorted(result, key=lambda g: (g['title'].casefold(), g['appid']))
