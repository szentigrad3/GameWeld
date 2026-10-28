#!/usr/bin/env python3
"""Opt-in Steam-compatible single-session DeckCheatz wrapper for GameWeld.

Steam Launch Options require ONE-TIME explicit manual installation:
    /usr/bin/python3 /abs/path/to/gameweld-deckcheatz-session.py run --appid ID -- %command%

When GameWeld arms this ID, the next Steam invocation runs the already installed
DeckCheatz 1.x launcher with Steam's exact argv. The token is atomically consumed
BEFORE starting DeckCheatz. Otherwise we use os.execvpe on the original Steam argv:
no Steam config/prefix changes, no resident service, no lingering trainer switch.

This does NOT restore the literal text in Steam's UI after game exit. Steam's
one-time launch option stays configured; normal execution is restored by the
one-shot token. Never externally edit Steam's live localconfig.vdf.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import hashlib
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

APPID_PATTERN = re.compile(r"[1-9][0-9]{0,9}\Z")
MAX_STEAM_ID = 2**32
ARM_TTL_SECONDS = 600
MAX_STATE_SIZE = 8192
SCHEMA = 1


class SessionBlocked(ValueError):
    pass


def valid_appid(text: str) -> bool:
    return (bool(APPID_PATTERN.fullmatch(text)) and
            int(text) < MAX_STEAM_ID)


def private_root(state_root: Path | None = None) -> Path:
    if state_root is None:
        supplied = os.environ.get("XDG_STATE_HOME", "")
        if supplied and not Path(supplied).is_absolute():
            raise SessionBlocked("XDG_STATE_HOME must be an absolute path")
        state_root = Path(supplied) if supplied else Path.home() / ".local/state"
    if not state_root.is_absolute():
        raise SessionBlocked("Private session state root must be absolute")
    result = state_root / "gameweld/steam-session-tokens"
    for directory in (result.parent, result):
        if directory.is_symlink():
            raise SessionBlocked("Refusing symlinked state directories")
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if directory.stat().st_uid != os.getuid():
            raise SessionBlocked("Session state directory belongs to another user")
    if stat.S_IMODE(result.stat().st_mode) & 0o077:
        raise SessionBlocked("Private session token directory must be mode 0700")
    return result


def paths(appid: str, root: Path):
    if not valid_appid(appid):
        raise SessionBlocked("Invalid Steam AppID")
    return root / (appid + ".json"), root / (appid + ".lock")


def lock_for(file: Path):
    if file.is_symlink():
        raise SessionBlocked("Refusing symlinked session lock")
    fd = os.open(file, os.O_CREAT | os.O_RDWR |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise SessionBlocked("Session lock must be a regular file")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def read_token(path: Path):
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_STATE_SIZE:
        raise SessionBlocked("Unsafe or oversized pending session token")
    with path.open(encoding="utf-8") as stream:
        item = json.load(stream)
    if (not isinstance(item, dict) or item.get("schema") != SCHEMA or
            item.get("appid") != path.stem or
            not isinstance(item.get("expiry"), (int, float)) or
            not isinstance(item.get("launcher"), str)):
        raise SessionBlocked("Malformed pending session token")
    return item


def save_token(path: Path, record: dict):
    fd, temp = tempfile.mkstemp(prefix=".session-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(record, output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, 0o600)
        if path.is_symlink():
            raise SessionBlocked("Refusing symlinked pending session token")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def validate_launcher(path: Path) -> Path:
    if not path.is_absolute() or path.name != "wemod":
        raise SessionBlocked("DeckCheatz launcher must be an absolute 'wemod' path")
    if path.is_symlink():
        source = path.parent / "src/wemod.py"
        if (source.is_symlink() or not source.is_file() or
                path.resolve(strict=True) != source.resolve(strict=True) or
                not source.resolve(strict=True).is_relative_to(path.parent.resolve(strict=True))):
            raise SessionBlocked("DeckCheatz launcher symlink must point to in-tree src/wemod.py")
    if not path.is_file() or not os.access(path, os.X_OK):
        raise SessionBlocked("DeckCheatz launcher is absent or not executable")
    return path


def arm(appid: str, launcher: Path, *, state_root=None, now=None) -> dict:
    launcher = validate_launcher(launcher)
    now = time.time() if now is None else now
    root = private_root(state_root)
    path, lock = paths(appid, root)
    fd = lock_for(lock)
    try:
        prior = read_token(path)
        if prior and prior["expiry"] > now:
            raise SessionBlocked("Session already armed for this Steam AppID; no duplicate launch")
        record = {"schema": SCHEMA, "appid": appid, "launcher": str(launcher),
                  "expiry": now + ARM_TTL_SECONDS}
        save_token(path, record)
    finally:
        os.close(fd)
    return {"result": "SINGLE_SESSION_ARMED", "appid": appid,
            "expires_in_seconds": ARM_TTL_SECONDS,
            "steam_launch_options_changed": False,
            "steam_game_launched": False,
            "original_steam_launch_options_modified": False,
            "next_steam_launch_only": True}


def consume(appid: str, *, state_root=None, now=None):
    now = time.time() if now is None else now
    root = private_root(state_root)
    path, lock = paths(appid, root)
    fd = lock_for(lock)
    try:
        item = read_token(path)
        if item is not None:
            # Consume once even if it expired or the subsequent launcher fails.
            path.unlink()
        if not item or item["expiry"] <= now:
            return None
        return validate_launcher(Path(item["launcher"]))
    finally:
        os.close(fd)


def status(appid: str, *, state_root=None, now=None):
    now = time.time() if now is None else now
    root = private_root(state_root)
    path, lock = paths(appid, root)
    fd = lock_for(lock)
    try:
        item = read_token(path)
    finally:
        os.close(fd)
    return {"appid": appid, "session_armed": bool(item and item["expiry"] > now),
            "steam_launch_options_changed": False}


def disarm(appid: str, *, state_root=None):
    root = private_root(state_root)
    path, lock = paths(appid, root)
    fd = lock_for(lock)
    try:
        if path.is_symlink():
            raise SessionBlocked("Refusing symlinked pending token")
        had_token = path.exists()
        if had_token:
            path.unlink()
    finally:
        os.close(fd)
    return {"appid": appid, "pending_session_cancelled": had_token,
            "steam_launch_options_changed": False}


def invoke(appid: str, game_argv: list[str], *, state_root=None,
           now=None, spawn=subprocess.call, passthrough=os.execvpe):
    if not game_argv or not game_argv[0] or game_argv[0].startswith("--"):
        raise SessionBlocked("Steam did not provide an executable game command")
    launcher = consume(appid, state_root=state_root, now=now)
    if launcher is None:
        # Exact original Steam-built argv and environment; process replaced.
        passthrough(game_argv[0], game_argv, os.environ.copy())
        return 0
    env = os.environ.copy()
    env["WINEDLLOVERRIDES"] = "version=n,b"
    env["WEMOD_LOG"] = str(launcher.parent / "wemod.log")
    # Wait for wrapper/game completion. The token was consumed BEFORE this;
    # even a crash, SIGKILL, or game crash cannot leave another launch armed.
    return spawn([str(launcher), *game_argv], env=env)


def installed_wrapper_path(data_root: Path | None = None) -> Path:
    if data_root is None:
        raw = os.environ.get("XDG_DATA_HOME", "")
        if raw and not Path(raw).is_absolute():
            raise SessionBlocked("XDG_DATA_HOME must be absolute")
        data_root = Path(raw) if raw else Path.home() / ".local/share"
    if not data_root.is_absolute():
        raise SessionBlocked("Data root must be absolute")
    return data_root / "gameweld/steam-session-launcher/steam-session.py"


def install_wrapper(*, destination: Path | None = None,
                    source: Path | None = None) -> dict:
    """Explicit opt-in copy to a persistent user-owned path, NEVER Steam."""
    dest = destination or installed_wrapper_path()
    source = source if source is not None else Path(__file__).resolve(strict=True)
    if source.is_symlink() or not source.is_file() or not dest.is_absolute():
        raise SessionBlocked("Session wrapper source/destination is unsafe")
    if dest.parent.is_symlink():
        raise SessionBlocked("Session wrapper destination must not be a symlink")
    dest.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if dest.parent.stat().st_uid != os.getuid():
        raise SessionBlocked("Session wrapper directory belongs to a different user")
    code = source.read_bytes()
    if not code.startswith(b"#!/usr/bin/env python3") or b"def invoke(" not in code:
        raise SessionBlocked("Unexpected session wrapper source layout")
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or not dest.is_file() or dest.read_bytes() != code:
            raise SessionBlocked("A different session wrapper already exists. "
                                 "Preserve the installed version until no games use it.")
        return {"result": "SESSION_WRAPPER_ALREADY_INSTALLED",
                "wrapper": str(dest), "steam_launch_options_changed": False}
    fd, staging = tempfile.mkstemp(prefix=".session-wrapper-", dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(code)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging, 0o700)
        if dest.exists() or dest.is_symlink():
            raise SessionBlocked("Another session wrapper was installed concurrently")
        os.rename(staging, dest)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
    return {"result": "SESSION_WRAPPER_INSTALLED", "wrapper": str(dest),
            "sha256": hashlib.sha256(code).hexdigest(),
            "steam_launch_options_changed": False,
            "requires_one_time_manual_steam_setup": True}


def verify_steam_option(appid: str, *, wrapper: Path | None = None,
                        steam_root: Path | None = None,
                        steam_account: str | None = None) -> dict:
    """Read saved Steam config, not the potentially newer client UI state."""
    import importlib.util
    location = Path(__file__).with_name("gameweld-steam-launch-options-preserve.py")
    # Installed runtime copy lacks this helper; preserve-only inspection is
    # performed by GameWeld checkout, never by the standalone Steam wrapper.
    spec = importlib.util.spec_from_file_location("gw_session_verify", location)
    if not spec or not spec.loader:
        raise SessionBlocked("Steam option verification helper is unavailable")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    config, account = mod.find_config(appid, steam_root, steam_account)
    original = mod.launch_option(config, appid)
    wrapper = wrapper or installed_wrapper_path()
    args = shlex.split(original)
    try:
        i = args.index(str(wrapper))
    except ValueError:
        i = -1
    configured = (
        i > 0 and args[i - 1] == "/usr/bin/python3" and
        args[i + 1:i + 6] == ["run", "--appid", appid, "--", "%command%"] and
        args.count("%command%") == 1
    )
    if configured:
        prefix = args[:i - 1]
        configured = all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.+", item)
                         for item in prefix)
    return {"appid": appid, "steam_account": account,
            "session_wrapper_installed_in_saved_options": bool(configured),
            "steam_launch_options_changed": False,
            "live_steam_ui_verified": False,
            "warning": "This reads saved Steam configuration, not the live client cache."}


def compose(original: str, wrapper: Path, appid: str,
            *, python: Path = Path("/usr/bin/python3")) -> tuple[str | None, str]:
    """Conservatively create a one-time Steam launch option.

    Full wrapper nesting (MangoHud/Gamescope/scripts) requires manual planning.
    Original Launch Options remain safely backed up by the separate helper.
    """
    if not valid_appid(appid):
        raise SessionBlocked("Invalid Steam AppID")
    if not wrapper.is_absolute() or not python.is_absolute():
        raise SessionBlocked("Session wrapper and interpreter paths must be absolute")
    import importlib.util
    helper_path = Path(__file__).with_name("gameweld-steam-launch-options-preserve.py")
    spec = importlib.util.spec_from_file_location("gw_session_merge", helper_path)
    if not spec or not spec.loader:
        raise SessionBlocked("Launch-options merge validator unavailable")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # Feed the same restrictive merge policy used by GameWeld's existing GUI.
    # Shell quoting for the app ID/wrapper path is handled without interpolation.
    launch = f"{shlex.quote(str(python))} {shlex.quote(str(wrapper))} run --appid {appid} -- %command%"
    proposal, status_text = helper.merge(original, launch)
    return proposal, status_text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for mode in ("arm", "status", "disarm", "run", "recipe", "install", "verify"):
        cmd = commands.add_parser(mode)
        cmd.add_argument("--appid", required=True)
        if mode == "arm":
            cmd.add_argument("--launcher", type=Path, required=True)
        if mode == "recipe":
            cmd.add_argument("--original", required=True)
            cmd.add_argument("--wrapper", type=Path, default=installed_wrapper_path())
        if mode == "verify":
            cmd.add_argument("--steam-root", type=Path)
            cmd.add_argument("--steam-account")
        if mode == "run":
            cmd.add_argument("steam_command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not valid_appid(args.appid):
        parser.error("Invalid Steam AppID")
    try:
        if args.action == "install":
            result = install_wrapper()
        elif args.action == "verify":
            result = verify_steam_option(args.appid,
                                         steam_root=args.steam_root,
                                         steam_account=args.steam_account)
        elif args.action == "arm":
            result = arm(args.appid, args.launcher)
        elif args.action == "disarm":
            result = disarm(args.appid)
        elif args.action == "status":
            result = status(args.appid)
        elif args.action == "recipe":
            command, state = compose(args.original, args.wrapper, args.appid)
            result = {"appid": args.appid, "proposed_launch_option": command,
                      "merge_status": state, "steam_launch_options_changed": False,
                      "one_time_steam_manual_install_required": True}
        else:
            cmd = args.steam_command
            if cmd and cmd[0] == "--":
                cmd = cmd[1:]
            return invoke(args.appid, cmd)
        print(json.dumps(result, indent=2))
        return 0
    except (SessionBlocked, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"GameWeld Steam session: BLOCKED — {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
