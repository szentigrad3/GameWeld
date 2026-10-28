#!/usr/bin/env python3
"""Inspect per-account Steam Launch Options, offer safe DeckCheatz merge and backup.
NEVER writes to Steam localconfig.vdf, even if Steam is closed.
"""
from __future__ import annotations
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
ACCOUNT = re.compile(r"[0-9]{1,20}\Z")
VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.+\Z")
DANGEROUS = re.compile(r"[;&|$()<>\x60\\\n\r]")
MAX_SIZE = 16 * 1024 * 1024
MAX_OPTION = 16384

class Blocked(ValueError):
    pass

def tokens(s: str):
    i, count, size = 0, 0, len(s)
    while i < size:
        if s[i].isspace():
            i += 1
            continue
        if s.startswith("//", i):
            end = s.find("\n", i + 2)
            i = size if end < 0 else end + 1
            continue
        if s.startswith("/*", i):
            end = s.find("*/", i + 2)
            if end < 0:
                raise Blocked("Unterminated VDF comment")
            i = end + 2
            continue
        if s[i] in "{}":
            token, i = s[i], i + 1
        elif s[i] == '"':
            chars = []
            i += 1
            while i < size:
                if s[i] == '"':
                    i += 1
                    break
                if s[i] == "\\" and i + 1 < size:
                    c = s[i + 1]
                    if c in ('"', "\\", "n", "r", "t"):
                        chars.append({"n": "\n", "r": "\r", "t": "\t"}.get(c, c))
                        i += 2
                        continue
                chars.append(s[i])
                i += 1
            else:
                raise Blocked("Unterminated VDF string")
            token = "".join(chars)
        else:
            start = i
            while i < size and not s[i].isspace() and s[i] not in '{}"':
                i += 1
            if i == start:
                raise Blocked("Invalid VDF syntax")
            token = s[start:i]
        count += 1
        if count > 500000:
            raise Blocked("VDF token limit exceeded")
        yield token

def parse_vdf(s: str) -> dict:
    stream = iter(tokens(s))
    def node(depth, nested):
        if depth > 80:
            raise Blocked("VDF nesting limit exceeded")
        result = {}
        while True:
            k = next(stream, None)
            if k is None:
                if nested:
                    raise Blocked("Missing VDF closing brace")
                return result
            if k == "}":
                if not nested:
                    raise Blocked("Unexpected VDF closing brace")
                return result
            if k == "{":
                raise Blocked("Unexpected VDF opening brace")
            v = next(stream, None)
            if v is None or v == "}":
                raise Blocked("Incomplete VDF entry")
            if v == "{":
                v = node(depth + 1, True)
            result.setdefault(k.casefold(), []).append(v)
    return node(0, False)

def only(node, key):
    values = node.get(key.casefold(), [])
    if len(values) > 1:
        raise Blocked("Duplicate VDF key: " + key)
    return values[0] if values else None

def launch_option(config: Path, appid: str) -> str:
    if (config.is_symlink() or not config.is_file() or
            not stat.S_ISREG(config.stat().st_mode) or
            config.stat().st_size > MAX_SIZE):
        raise Blocked("Unsafe or oversized Steam localconfig.vdf")
    with config.open("rb") as stream:
        data = stream.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise Blocked("Steam localconfig.vdf exceeds size limit")
    try:
        tree = parse_vdf(data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise Blocked("Steam localconfig.vdf has invalid UTF-8") from exc
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam",
                "apps", appid):
        if not isinstance(tree, dict):
            raise Blocked("Steam app entry has unexpected structure")
        tree = only(tree, key)
        if tree is None:
            raise Blocked("Steam on-disk config has no " + key +
                          " for this game/account; cannot verify original Launch Options. "
                          "Check the current field in Steam Properties. No backup or copy made.")
    if not isinstance(tree, dict):
        raise Blocked("Steam game entry is not a VDF object")
    value = only(tree, "LaunchOptions")
    if value is None:
        raise Blocked("Steam on-disk app entry has no LaunchOptions field; "
                      "an absent field is NOT proof that Steam's live Launch Options are empty. "
                      "Check the game in Steam Properties; no backup or copy made.")
    if not isinstance(value, str) or len(value) > MAX_OPTION:
        raise Blocked("Steam LaunchOptions value is invalid")
    return value

def find_config(appid: str, root: Path | None, account: str | None):
    if not APPID.fullmatch(appid) or int(appid) >= 2**32:
        raise Blocked("Invalid Steam AppID")
    if account and not ACCOUNT.fullmatch(account):
        raise Blocked("Invalid Steam account selector")
    roots = ([root] if root is not None else
             [Path.home() / ".local/share/Steam", Path.home() / ".steam/root"])
    found, visited = [], set()
    for base in roots:
        try:
            base = base.expanduser().resolve(strict=True)
        except OSError:
            continue
        if base in visited:
            continue
        visited.add(base)
        userdata = base / "userdata"
        if userdata.is_symlink() or not userdata.is_dir():
            continue
        for user in userdata.iterdir():
            if not user.name.isdecimal() or user.is_symlink() or not user.is_dir():
                continue
            if account and user.name != account:
                continue
            cfg = user / "config/localconfig.vdf"
            if cfg.exists() or cfg.is_symlink():
                found.append((cfg, user.name))
    if len(found) != 1:
        raise Blocked("Need one Steam account localconfig.vdf; use --steam-account if multiple")
    return found[0]

def merge(original: str, recipe: str):
    old = original.strip()
    if not old:
        return recipe, "SAFE_EMPTY"
    if old == recipe:
        return old, "ALREADY_CONFIGURED"
    if len(old) > MAX_OPTION or DANGEROUS.search(old):
        return None, "MANUAL_COMPLEX_SHELL"
    try:
        parts = shlex.split(old)
    except ValueError:
        return None, "MANUAL_INVALID_QUOTES"
    # Steam users often quote path/value tokens differently from the copied
    # recipe; recognize the *same argv* without overwriting working options.
    if parts == shlex.split(recipe):
        return old, "ALREADY_CONFIGURED"
    if any("wemod" in p.lower() or "deckcheatz" in p.lower() for p in parts):
        return None, "MANUAL_EXISTING_TRAINER"
    if parts.count("%command%") == 1:
        pos = parts.index("%command%")
        if any(not VARIABLE.fullmatch(p) for p in parts[:pos]):
            return None, "MANUAL_OTHER_WRAPPERS"
        if any(p.split("=", 1)[0] in ("WINEDLLOVERRIDES", "WEMOD_LOG")
               for p in parts[:pos]):
            return None, "MANUAL_ENV_COLLISION"
        if any(not p.startswith("-") for p in parts[pos + 1:]):
            return None, "MANUAL_ARGUMENTS"
        at = old.index("%command%")
        before, after = old[:at].rstrip(), old[at + 9:]
        return ((before + " " if before else "") + recipe + after,
                "SAFE_ENV_AND_ARGUMENTS")
    if "%command%" in old or any("%" in p for p in parts):
        return None, "MANUAL_PLACEHOLDER"
    if parts and all(p.startswith("-") and len(p) > 1 for p in parts):
        return recipe + " " + old, "SAFE_GAME_FLAGS"
    return None, "MANUAL_UNKNOWN_COMMAND"

def recipe_for(launcher: Path | None, *, session_appid: str | None = None):
    if session_appid:
        source = Path(__file__).with_name("gameweld-deckcheatz-session.py")
        spec = importlib.util.spec_from_file_location("gw_one_time_recipe", source)
        if not spec or not spec.loader:
            raise Blocked("GameWeld session wrapper helper unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        installed = module.installed_wrapper_path()
        if (installed.is_symlink() or not installed.is_file() or
                installed.read_bytes() != source.read_bytes()):
            raise Blocked("Install or update the explicit GameWeld per-user session "
                          "wrapper before preparing this Steam option")
        proposal, reason = module.compose("", installed, session_appid)
        if reason != "SAFE_EMPTY" or not proposal:
            raise Blocked("Cannot create safe Steam session wrapper command")
        return proposal
    module_path = Path(__file__).with_name("gameweld-deckcheatz-steam-options.py")
    spec = importlib.util.spec_from_file_location("gw_wrapped_steam_recipe", module_path)
    if not spec or not spec.loader:
        raise Blocked("DeckCheatz recipe helper not installed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if launcher:
        return module.build_recipe(launcher)["launch_option"]
    home = Path.home()
    data = os.environ.get("XDG_DATA_HOME")
    if data and not Path(data).is_absolute():
        raise Blocked("XDG_DATA_HOME must be absolute")
    for candidate in module.candidates(home, Path(data) if data else home / ".local/share"):
        try:
            return module.build_recipe(candidate)["launch_option"]
        except (module.RecipeBlocked, OSError):
            continue
    raise Blocked("No executable DeckCheatz wrapper found")

def backup_file(appid: str, account: str, root: Path | None):
    state = root or Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local/state"))
    if not state.is_absolute():
        raise Blocked("State root must be absolute")
    return state / "gameweld/steam-option-backups" / account / (appid + ".json")

def verified_baseline_file(appid: str, account: str, root: Path | None = None) -> Path:
    """Separate current-settings snapshot; never rebrands a legacy original."""
    return backup_file(appid, account, root).with_name(appid + ".verified-current.json")


def read_backup_record(appid: str, account: str, path: Path) -> tuple[dict, bytes]:
    """Secure, bounded read of an existing protected record."""
    if path.is_symlink() or not path.is_file():
        raise Blocked("Original options backup missing or unsafe")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or info.st_size > 100000):
                raise Blocked("Original options backup has unsafe permissions or size")
            raw = stream.read(100001)
        if len(raw) > 100000:
            raise Blocked("Original options backup is oversized")
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Blocked("Existing original-command backup is invalid; no changes made") from exc
    if not isinstance(value, dict):
        raise Blocked("Existing original-command backup is not a JSON object")
    if (value.get("appid") != appid or value.get("account") != account
            or not isinstance(value.get("original"), str)):
        raise Blocked("Backup metadata does not match selected account and game")
    return value, raw


def read_verified_baseline(appid: str, account: str,
                           root: Path | None = None) -> str | None:
    """Read only an explicitly checked CURRENT empty original, not legacy history."""
    current = verified_baseline_file(appid, account, root)
    if not current.exists() and not current.is_symlink():
        return None
    record, _ = read_backup_record(appid, account, current)
    if (record.get("version") != 2
            or record.get("snapshot_kind") != "verified_current_before_setup"
            or record.get("original") != ""
            or record.get("live_empty_confirmed") is not True):
        raise Blocked("Verified current-settings snapshot has invalid metadata")
    legacy, raw = read_backup_record(appid, account, backup_file(appid, account, root))
    if (legacy.get("version") != 1 or legacy.get("original") != ""
            or legacy.get("live_empty_confirmed") is True
            or record.get("legacy_backup_sha256") != hashlib.sha256(raw).hexdigest()):
        raise Blocked("Legacy original changed since current-settings snapshot; "
                      "restore is blocked")
    return ""


def save_verified_current_baseline(appid: str, account: str, root: Path | None = None) -> Path:
    """Safely attest *current* empty options, retaining unverified historical data."""
    legacy, raw = read_backup_record(appid, account, backup_file(appid, account, root))
    if (legacy.get("version") != 1 or legacy.get("original") != ""
            or legacy.get("live_empty_confirmed") is True):
        raise Blocked("Existing backup is not the recognized unverified-empty legacy record")
    path = verified_baseline_file(appid, account, root)
    payload = {
        "version": 2, "appid": appid, "account": account,
        "original": "", "live_empty_confirmed": True,
        "snapshot_kind": "verified_current_before_setup",
        "legacy_backup_sha256": hashlib.sha256(raw).hexdigest(),
    }
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if read_verified_baseline(appid, account, root) != "":
            raise Blocked("Existing current-settings snapshot conflicts; no changes made")
        return path
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path


def save_backup(appid: str, account: str, old: str, root: Path | None = None,
                *, verified_empty: bool = False, return_status: bool = False):
    """Create a private original once, or reuse a validated exact match.

    Existing backups are NEVER replaced. A changed original is a conflict,
    not permission to overwrite history. Exact-match retries are idempotent.
    """
    if old == "" and not verified_empty:
        raise Blocked("Empty Steam original must be verified in the live Steam UI "
                      "before a restorable backup can be created")
    if not APPID.fullmatch(appid) or not ACCOUNT.fullmatch(account):
        raise Blocked("Invalid game/account backup identifiers")
    path = backup_file(appid, account, root)
    for directory in (path.parent.parent.parent, path.parent.parent, path.parent):
        if directory.is_symlink():
            raise Blocked("Symlinked backup directory refused")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise Blocked("Symlinked backup location refused")
    for directory in (path.parent.parent.parent, path.parent.parent, path.parent):
        info = directory.stat()
        if info.st_uid != os.getuid():
            raise Blocked("Backup directory is not owned by the current user")
        # Existing GameWeld state may have been created 0755 by other tools;
        # the dedicated backup container and account directory MUST be 0700.
        if (directory != path.parent.parent.parent and
                stat.S_IMODE(info.st_mode) & 0o077):
            raise Blocked("Private Steam backup directory exposes other users")
    payload = {"version": 1, "appid": appid, "account": account, "original": old,
               "live_empty_confirmed": bool(old == "" and verified_empty)}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        # Must read and validate the actual existing record before reporting
        # a successful retry. Never truncate it or create a new backup.
        legacy, _ = read_backup_record(appid, account, path)
        if (legacy.get("version") == 1 and legacy.get("original") == ""
                and legacy.get("live_empty_confirmed") is not True):
            if old != "" or not verified_empty:
                raise Blocked(
                    "Legacy unverified-empty backup cannot be reconciled with "
                    "nonempty or unverified CURRENT Steam Launch Options. "
                    "Original remains protected; review Steam Properties.")
            existing_current = read_verified_baseline(appid, account, root)
            if existing_current == "":
                current_path = verified_baseline_file(appid, account, root)
                return (current_path, True) if return_status else current_path
            # This does NOT certify what the original options historically
            # were. It records a new, explicit current empty baseline only.
            current_path = save_verified_current_baseline(appid, account, root)
            return (current_path, False) if return_status else current_path
        saved_original = load_backup(appid, account, root)
        if saved_original != old:
            raise Blocked(
                "Existing original-command backup differs from Steam's saved "
                "Launch Options. The original backup is protected and unchanged; "
                "use Restore Original or review this game's Steam Properties "
                "before trying setup again.")
        return (path, True) if return_status else path
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return (path, False) if return_status else path

def load_backup(appid: str, account: str, root: Path | None = None) -> str:
    current = read_verified_baseline(appid, account, root)
    if current is not None:
        return current
    value, _ = read_backup_record(appid, account, backup_file(appid, account, root))
    if value.get("version") != 1:
        raise Blocked("Backup version does not match protected original")
    if value["original"] == "" and value.get("live_empty_confirmed") is not True:
        raise Blocked("A previous GameWeld version saved an unverified EMPTY original. "
                      "Refusing to copy this as a restore command; check Steam Properties manually.")
    return value["original"]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preview", action="store_true")
    action.add_argument("--save-original", action="store_true")
    action.add_argument("--restore-original", action="store_true")
    parser.add_argument("--appid", required=True)
    parser.add_argument("--steam-root", type=Path)
    parser.add_argument("--steam-account")
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="json")
    parser.add_argument("--session-wrapper", action="store_true",
                        help="Generate one-shot GameWeld Steam wrapper instead of permanent DeckCheatz")
    parser.add_argument("--verified-empty-in-steam", action="store_true",
                        help="Only after manually checking that the CURRENT Steam Properties "
                             "Launch Options field for the selected account/game is empty")
    args = parser.parse_args(argv)
    try:
        cfg, account = find_config(args.appid, args.steam_root, args.steam_account)
        if args.restore_original:
            old = load_backup(args.appid, account)
            verified_current = verified_baseline_file(args.appid, account)
            result = {"result": "COPY_ORIGINAL_TO_STEAM_MANUALLY",
                      "appid": args.appid, "steam_account": account,
                      "original_launch_option": old,
                      "restore_source": ("verified_current_before_setup"
                                         if verified_current.exists() else
                                         "protected_original_backup"),
                      "historical_original_unverified": verified_current.exists(),
                      "steam_launch_options_changed": False}
        else:
            old = launch_option(cfg, args.appid)
            proposed, decision = merge(
                old, recipe_for(args.launcher,
                                session_appid=args.appid if args.session_wrapper else None))
            # The running Steam client may hold a different, not-yet-persisted
            # LaunchOptions value. Even an explicit empty string on disk does
            # not prove the current Steam Properties field is empty.
            if old == "" and not args.verified_empty_in_steam:
                proposed, decision = None, "NEEDS_STEAM_UI_EMPTY_CHECK"
            result = {"result": "PREVIEW_ONLY" if args.preview else "ORIGINAL_BACKUP_SAVED",
                      "appid": args.appid, "steam_account": account,
                      "original_launch_option": old,
                      "proposed_launch_option": proposed,
                      "merge_status": decision, "requires_manual_review": proposed is None,
                      "steam_launch_options_changed": False,
                      "launch_recipe_type": "single_session_shim" if args.session_wrapper
                                            else "permanent_deckcheatz",
                      "steam_config_file": str(cfg)}
            if args.save_original:
                if decision == "NEEDS_STEAM_UI_EMPTY_CHECK":
                    raise Blocked("Steam on-disk LaunchOptions are empty. "
                                  "Verify the CURRENT game's field in Steam Properties "
                                  "is also empty, then explicitly confirm before backup.")
                if proposed is None:
                    raise Blocked("Steam Launch Options have unsupported syntax; "
                                  "cannot safely back up an unverified merge.")
                path, reused = save_backup(
                    args.appid, account, old,
                    verified_empty=args.verified_empty_in_steam,
                    return_status=True)
                result["backup_file"] = str(path)
                result["backup_reused"] = reused
                if path == verified_baseline_file(args.appid, account):
                    result["result"] = ("VERIFIED_CURRENT_BASELINE_REUSED" if reused
                                        else "VERIFIED_CURRENT_BASELINE_SAVED")
                    result["legacy_historical_original_unverified"] = True
                else:
                    result["result"] = ("ORIGINAL_BACKUP_REUSED" if reused
                                        else "ORIGINAL_BACKUP_SAVED")
        if args.format == "text":
            print(result.get("proposed_launch_option") or result.get("original_launch_option") or "")
        else:
            print(json.dumps(result, indent=2))
    except (Blocked, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, "GameWeld Steam options: BLOCKED — " + str(exc) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
