"""Bounded read-only Steam inventory and local preferences."""
import json
import os
import re
import stat
from pathlib import Path

FIELDS = re.compile(r'"([^"\r\n]+)"\s+"([^"\r\n]*)"')
NAME = re.compile(r'appmanifest_([0-9]{1,10})\.acf')

def steamapps_default():
    return Path.home() / ".local/share/Steam/steamapps"

def settings_path():
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    root = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return root / "gameweld" / "desktop.json"

def read_file(path, limit=131072):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError("unsafe_file")
        data = os.read(fd, limit + 1)
        if len(data) > limit:
            raise ValueError("oversized_file")
        return data
    finally:
        os.close(fd)

def libraries(steamapps=None):
    root = Path(steamapps).expanduser() if steamapps else steamapps_default()
    result = [root]
    try:
        source = read_file(root / "libraryfolders.vdf").decode("utf-8", "replace")
        for key, value in FIELDS.findall(source):
            if key.lower() == "path" and len(value) < 4096:
                item = Path(value.replace("\\\\", "\\")) / "steamapps"
                if item not in result:
                    result.append(item)
    except (OSError, ValueError):
        pass
    return result[:64]

def installed_games(steamapps=None):
    collected = {}
    for folder in libraries(steamapps):
        try:
            matches = sorted(folder.glob("appmanifest_*.acf"))[:4000]
        except OSError:
            continue
        for path in matches:
            match = NAME.fullmatch(path.name)
            if not match:
                continue
            try:
                fields = dict(FIELDS.findall(read_file(path).decode("utf-8", "replace")))
                title = fields.get("name", "").strip()
                appid = int(match.group(1))
                buildid = fields.get("buildid", "")
                if title and len(title) <= 240 and appid > 0:
                    collected[appid] = {"appid": appid, "title": title,
                                       "buildid": buildid if buildid.isdecimal() else None}
            except (OSError, ValueError):
                continue
    return sorted(collected.values(), key=lambda x: (x["title"].casefold(), x["appid"]))

def valid_settings(raw):
    raw = raw if isinstance(raw, dict) else {}
    ids = raw.get("favourites", [])
    if not isinstance(ids, list):
        ids = []
    favs = sorted({i for i in ids[:500] if type(i) is int and 0 < i < 10000000000})
    path = raw.get("steamapps", str(steamapps_default()))
    if not isinstance(path, str) or not path or "\0" in path or len(path) > 2048:
        path = str(steamapps_default())
    return {"favourites": favs, "steamapps": path}

def load_settings(path=None):
    path = Path(path) if path else settings_path()
    try:
        return valid_settings(json.loads(read_file(path, 16384)))
    except (OSError, ValueError, TypeError, UnicodeError):
        return valid_settings(None)

def save_settings(raw, path=None):
    path = Path(path) if path else settings_path()
    parent = path.parent
    if parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe_settings_symlink")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe_settings_symlink")
    payload = (json.dumps(valid_settings(raw), sort_keys=True) + "\n").encode("utf-8")
    temporary = parent / (".settings-" + os.urandom(12).hex())
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("unsafe_settings_symlink")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def find_games(games, query="", favourites=None, only_favourites=False):
    term = str(query).strip().casefold()[:200]
    favs = set(favourites or [])
    return [game for game in games
            if (not term or term in game["title"].casefold() or term in str(game["appid"]))
            and (not only_favourites or game["appid"] in favs)]
