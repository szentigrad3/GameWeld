#!/usr/bin/env python3
"""Opt-in automatic Steam DeckCheatz one-shot registration and Steam handoff.

NEVER writes Steam's live config. With explicit consent, requests a graceful
Steam shutdown, waits until Steam is closed, atomically installs one per-game
one-shot shim in saved LaunchOptions, arms DeckCheatz, then asks Steam to launch
the game. Original localconfig bytes and original option are backed up.
The persistent shim passes through Steam's exact argv when not armed.

This is a private experimental build, not a guaranteed trainer attachment.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

LEX = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')
TARGET = ("userlocalconfigstore", "software", "valve", "steam", "apps")
MAX_VDF = 16 * 1024 * 1024

class SetupBlocked(ValueError):
    pass

def peer(filename: str, label: str):
    source = Path(__file__).resolve().with_name(filename)
    if source.is_symlink() or not source.is_file():
        raise SetupBlocked("GameWeld setup helper unavailable")
    spec = importlib.util.spec_from_file_location(label, source)
    if not spec or not spec.loader:
        raise SetupBlocked("GameWeld setup helper not importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def steam_is_running(proc=Path("/proc")) -> bool:
    try:
        pids = list(proc.iterdir())
    except OSError:
        raise SetupBlocked("Cannot safely inspect running Steam processes")
    for p in pids:
        if not p.name.isdecimal():
            continue
        try:
            if p.stat(follow_symlinks=False).st_uid != os.getuid():
                continue
            comm = (p / "comm").read_text(errors="replace").strip()
            if comm in {"steam", "steamwebhelper"}:
                return True
        except OSError:
            continue
    return False

def stop_steam_gracefully(steam_cmd: str, *, duration=90):
    if not steam_is_running():
        return False
    try:
        result = subprocess.run([steam_cmd, "-shutdown"], check=False,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupBlocked("Steam's graceful shutdown command did not complete") from exc
    if result.returncode:
        raise SetupBlocked("Steam refused its graceful shutdown request")
    end = time.monotonic() + duration
    while steam_is_running() and time.monotonic() < end:
        time.sleep(.5)
    if steam_is_running():
        raise SetupBlocked("Steam is still running; no Steam settings were edited")
    return True

def read_config_bytes(config: Path) -> bytes:
    if config.is_symlink() or not config.is_file():
        raise SetupBlocked("Symlinked or absent Steam localconfig is unsafe")
    info = config.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_size > MAX_VDF):
        raise SetupBlocked("Steam localconfig owner/size/type is unsafe")
    data = config.read_bytes()
    if len(data) > MAX_VDF:
        raise SetupBlocked("Steam localconfig is too large")
    return data

def saved_option_value(raw: bytes, appid: str, options) -> str | None:
    """Read the exact game's saved option, distinguishing absent from empty.

    Read-only callers may use None as a SETUP NEEDED hint. Only the closed-
    Steam registration path is permitted to treat absence as an empty baseline.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SetupBlocked("Invalid UTF-8 Steam configuration") from exc
    if text.startswith("\ufeff"):
        raise SetupBlocked("Unsupported UTF-8 BOM in Steam config")
    node = options.parse_vdf(text)
    for key in (*TARGET, appid):
        if not isinstance(node, dict):
            raise SetupBlocked("Unexpected Steam config nesting")
        node = options.only(node, key)
        if node is None:
            raise SetupBlocked("Steam game config entry is missing")
    if not isinstance(node, dict):
        raise SetupBlocked("Steam game config entry is not a VDF object")
    value = options.only(node, "LaunchOptions")
    if value is not None and (not isinstance(value, str)
                              or len(value) > 16384):
        raise SetupBlocked("Steam Launch Options have an unsafe value")
    return value


def replace_launch_option(raw: bytes, appid: str, expected: str | None,
                          new: str, options) -> bytes:
    """Replace the exact option, or insert it into an existing app entry.

    Missing entries are inserted only after closed-Steam preflight by the
    caller. Unrelated VDF bytes, comments, and other games are left intact.
    Duplicate or altered entries always block.
    """
    saved = saved_option_value(raw, appid, options)
    if saved != expected:
        raise SetupBlocked("Steam Launch Options changed; no edit made")
    text = raw.decode("utf-8")
    stack = []
    pending = None
    locations = []
    app_closings = []
    for m in LEX.finditer(text):
        tok = m.group()
        if tok.startswith("//") or tok.startswith("/*"):
            continue
        if tok == "{":
            if pending is None:
                raise SetupBlocked("Unexpected VDF opening brace")
            stack.append(pending.casefold())
            pending = None
            continue
        if tok == "}":
            if pending is not None or not stack:
                raise SetupBlocked("Unexpected VDF closing brace")
            if tuple(stack) == (*TARGET, appid):
                app_closings.append(m.start())
            stack.pop()
            continue
        if tok.startswith('"'):
            value = next(options.tokens(tok), None)
        else:
            value = tok
        if pending is None:
            pending = value
        else:
            if (tuple(stack) == (*TARGET, appid) and
                    pending.casefold() == "launchoptions"):
                if not tok.startswith('"'):
                    raise SetupBlocked("Steam LaunchOptions value must be quoted")
                if value != expected:
                    raise SetupBlocked("Steam LaunchOptions changed while preparing")
                locations.append((m.start(), m.end()))
            pending = None
    if pending is not None or stack or len(app_closings) != 1:
        raise SetupBlocked("No unique exact game VDF entry; no edit made")
    escaped = json.dumps(new, ensure_ascii=False)
    if expected is None:
        if locations:
            raise SetupBlocked("An unexpected Steam LaunchOptions field appeared")
        # No pre-existing key: retain the original app entry verbatim and add
        # the sole new pair just before its closing brace.
        at = app_closings[0]
        changed = (text[:at] + ' "LaunchOptions" ' + escaped + ' ' +
                   text[at:]).encode("utf-8")
    else:
        if len(locations) != 1:
            raise SetupBlocked("No unique exact game LaunchOptions token; no edit made")
        start, end = locations[0]
        changed = (text[:start] + escaped + text[end:]).encode("utf-8")
    if len(changed) > MAX_VDF:
        raise SetupBlocked("Steam config would exceed size limit")
    # Verify the modified structure with the same strict parser.
    node = options.parse_vdf(changed.decode("utf-8"))
    for key in (*TARGET, appid):
        node = options.only(node, key)
    if options.only(node, "LaunchOptions") != new:
        raise SetupBlocked("Written option failed VDF round-trip verification")
    return changed

def secure_dir(path: Path):
    for p in (path.parent, path):
        if p.is_symlink():
            raise SetupBlocked("Symlinked private backup directory")
        p.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = p.stat()
        if info.st_uid != os.getuid() or (stat.S_IMODE(info.st_mode) & 0o077):
            raise SetupBlocked("Private Steam setup backup is not mode 0700")

def save_exclusive(path: Path, data: bytes):
    if path.is_symlink():
        raise SetupBlocked("Symlinked backup refused")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise SetupBlocked("Existing protected Steam config backup conflicts")
        return False
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return True

def atomic_replace(config: Path, data: bytes, expected_digest: str):
    current = read_config_bytes(config)
    if hashlib.sha256(current).hexdigest() != expected_digest:
        raise SetupBlocked("Steam config changed since snapshot; aborting")
    if steam_is_running():
        raise SetupBlocked("Steam restarted during setup; refusing live config edit")
    mode = stat.S_IMODE(config.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=".gameweld-vdf-", dir=config.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if steam_is_running() or hashlib.sha256(read_config_bytes(config)).hexdigest() != expected_digest:
            raise SetupBlocked("Steam restarted or config changed before commit")
        os.replace(temp, config)
        dfd = os.open(config.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def register_steam_shim(appid: str, *, state_root: Path | None = None):
    if steam_is_running():
        raise SetupBlocked("Steam must be closed before automatic registration")
    options = peer("gameweld-steam-launch-options-preserve.py", "gw_auto_steam_options")
    session = peer("gameweld-deckcheatz-session.py", "gw_auto_steam_session")
    cfg, account = options.find_config(appid, None, None)
    # Steam is confirmed closed. A missing option on disk is now an explicit
    # empty baseline, not evidence about a running client's cached options.
    previous = read_config_bytes(cfg)
    saved = saved_option_value(previous, appid, options)
    original = saved if saved is not None else ""
    session.install_wrapper()
    wrapper = session.installed_wrapper_path()
    proposed, decision = session.compose(original, wrapper, appid)
    if decision == "ALREADY_CONFIGURED":
        return {"result": "already_configured", "appid": appid,
                "steam_launch_options_registered": True}
    if not proposed or not decision.startswith("SAFE_"):
        raise SetupBlocked("Custom launch syntax is too complex to preserve automatically: " + decision)
    updated = replace_launch_option(previous, appid, saved, proposed, options)
    base = (state_root or Path(os.environ.get("XDG_STATE_HOME") or
            (Path.home() / ".local/state"))) / "gameweld/automatic-steam-setup" / account
    if not base.is_absolute():
        raise SetupBlocked("Private state directory must be absolute")
    secure_dir(base)
    lock = base / (appid + ".lock")
    if lock.is_symlink():
        raise SetupBlocked("Symlinked Steam setup lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if steam_is_running():
            raise SetupBlocked("Steam started before backup; no edit made")
        full_backup = base / (appid + ".original-localconfig.vdf")
        save_exclusive(full_backup, previous)
        # The client is fully closed: saved on-disk LaunchOptions is current.
        # This is not evidence about an older, potentially bad historical backup.
        options.save_backup(appid, account, original, verified_empty=(original == ""))
        digest = hashlib.sha256(previous).hexdigest()
        atomic_replace(cfg, updated, digest)
    finally:
        os.close(fd)
    if saved_option_value(read_config_bytes(cfg), appid, options) != proposed:
        raise SetupBlocked("Steam registration could not be verified")
    return {"result": "automatic_steam_wrapper_installed", "appid": appid,
            "steam_launch_options_registered": True,
            "original_localconfig_backed_up": True,
            "original_user_options_preserved": True,
            "steam_was_closed_for_change": True}

def remove_exact_launch_option(raw: bytes, appid: str, expected: str, options) -> bytes:
    """Remove only GameWeld's inserted key when the original field was absent."""
    if not isinstance(expected, str) or not expected:
        raise SetupBlocked("Cannot remove an unverified Steam option")
    if saved_option_value(raw, appid, options) != expected:
        raise SetupBlocked("Saved Steam wrapper changed; original cannot be restored")
    text = raw.decode("utf-8")
    stack, pending, key_start, locations = [], None, None, []
    for m in LEX.finditer(text):
        tok = m.group()
        if tok.startswith("//") or tok.startswith("/*"):
            continue
        if tok == "{":
            if pending is None:
                raise SetupBlocked("Unexpected VDF opening brace")
            stack.append(pending.casefold())
            pending, key_start = None, None
            continue
        if tok == "}":
            if pending is not None or not stack:
                raise SetupBlocked("Unexpected VDF closing brace")
            stack.pop()
            continue
        value = next(options.tokens(tok), None) if tok.startswith('"') else tok
        if pending is None:
            pending, key_start = value, m.start()
        else:
            if (tuple(stack) == (*TARGET, appid) and
                    pending.casefold() == "launchoptions"):
                if not tok.startswith('"') or value != expected:
                    raise SetupBlocked("Saved Steam wrapper changed during restore")
                locations.append((key_start, m.end()))
            pending, key_start = None, None
    if stack or pending is not None or len(locations) != 1:
        raise SetupBlocked("Cannot locate exactly one saved Steam wrapper")
    start, end = locations[0]
    # Registration inserted a single leading/trailing space around the pair.
    # Remove those too when still present to restore the original exact bytes.
    if start > 0 and text[start - 1] == " " and text[end:end + 1] == " ":
        start, end = start - 1, end + 1
    updated = (text[:start] + text[end:]).encode("utf-8")
    if saved_option_value(updated, appid, options) is not None:
        raise SetupBlocked("Removing Steam wrapper failed validation")
    return updated


def read_private_snapshot(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SetupBlocked("Managed original Steam snapshot is missing or unsafe")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > MAX_VDF):
            raise SetupBlocked("Managed original Steam snapshot has unsafe permissions")
        data = source.read(MAX_VDF + 1)
    if len(data) > MAX_VDF:
        raise SetupBlocked("Managed original Steam snapshot is oversized")
    return data


def restore_steam_shim(appid: str, *, state_root: Path | None = None):
    """Restore only our exact option, after Steam has been fully closed.

    The saved entire original VDF is used as evidence, never copied over
    Steam's current VDF (which may contain changes to other games).
    """
    if steam_is_running():
        raise SetupBlocked("Steam must be closed before automatic restoration")
    options = peer("gameweld-steam-launch-options-preserve.py", "gw_restore_options")
    session = peer("gameweld-deckcheatz-session.py", "gw_restore_session")
    cfg, account = options.find_config(appid, None, None)
    base = (state_root or Path(os.environ.get("XDG_STATE_HOME") or
            (Path.home() / ".local/state"))) / "gameweld/automatic-steam-setup" / account
    if not base.is_absolute() or base.is_symlink():
        raise SetupBlocked("Unsafe private backup directory")
    secure_dir(base)
    snapshot = read_private_snapshot(base / (appid + ".original-localconfig.vdf"))
    saved_original = saved_option_value(snapshot, appid, options)
    original = saved_original if saved_original is not None else ""
    # The separately protected per-game original must agree with the exact
    # full config snapshot; never promote an unverified legacy value.
    if options.load_backup(appid, account) != original:
        raise SetupBlocked("Managed original Steam backups disagree")
    proposed, decision = session.compose(
        original, session.installed_wrapper_path(), appid)
    if not proposed or not decision.startswith("SAFE_"):
        raise SetupBlocked("Cannot reconstruct the exact managed Steam wrapper")
    lock = base / (appid + ".lock")
    if lock.is_symlink():
        raise SetupBlocked("Symlinked Steam setup lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if steam_is_running():
            raise SetupBlocked("Steam restarted before restoration")
        previous = read_config_bytes(cfg)
        current = saved_option_value(previous, appid, options)
        if current != proposed:
            raise SetupBlocked("Current Steam options differ from managed wrapper; no restore")
        updated = (remove_exact_launch_option(previous, appid, proposed, options)
                   if saved_original is None else
                   replace_launch_option(previous, appid, proposed, original, options))
        # No pending one-shot trainer token may survive restoration.
        session.disarm(appid)
        atomic_replace(cfg, updated, hashlib.sha256(previous).hexdigest())
    finally:
        os.close(fd)
    if saved_option_value(read_config_bytes(cfg), appid, options) != saved_original:
        raise SetupBlocked("Restored Steam option could not be verified")
    return {"result": "automatic_original_steam_option_restored", "appid": appid,
            "original_option_was_absent": saved_original is None,
            "other_game_settings_preserved": True,
            "one_shot_disarmed": True, "steam_was_closed_for_change": True}


def auto_launch(appid: str, launcher: Path, steam: str):
    session = peer("gameweld-deckcheatz-session.py", "gw_auto_arm_session")
    session.arm(appid, launcher)
    try:
        subprocess.Popen([steam, "-applaunch", appid],
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    except OSError as exc:
        session.disarm(appid)
        raise SetupBlocked("Steam launch request could not be started") from exc
    return {"result": "steam_launch_requested", "appid": appid,
            "steam_owned_execution": True, "game_window_verified": False,
            "wemod_attachment_verified": False,
            "one_shot_armed": True}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", required=True)
    p.add_argument("--launcher", type=Path)
    p.add_argument("--confirm", action="store_true")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--shutdown-and-launch", action="store_true")
    mode.add_argument("--shutdown-and-restore", action="store_true")
    args = p.parse_args(argv)
    session = peer("gameweld-deckcheatz-session.py", "gw_auto_session_validate")
    try:
        if not session.valid_appid(args.appid):
            raise SetupBlocked("Invalid Steam AppID")
        if not args.confirm or not (args.shutdown_and_launch or args.shutdown_and_restore):
            raise SetupBlocked("Explicit opt-in for graceful Steam shutdown and restart required")
        if args.shutdown_and_launch and args.launcher is None:
            raise SetupBlocked("DeckCheatz launcher is required to play with WeMod")
        launcher = (session.validate_launcher(args.launcher)
                    if args.shutdown_and_launch else None)
        steam = shutil.which("steam")
        if not steam:
            raise SetupBlocked("Native Steam executable unavailable")
        did_shutdown = stop_steam_gracefully(steam)
        if args.shutdown_and_restore:
            result = restore_steam_shim(args.appid)
            restarted = False
            try:
                subprocess.Popen([steam], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True, close_fds=True)
                restarted = True
            except OSError:
                pass
            print(json.dumps({**result, "steam_shutdown_requested": did_shutdown,
                              "steam_restart_requested": restarted}, indent=2))
            return 0
        result = register_steam_shim(args.appid)
        launch = auto_launch(args.appid, launcher, steam)
        print(json.dumps({**result, "launch": launch,
                          "steam_shutdown_requested": did_shutdown}, indent=2))
        return 0
    except (SetupBlocked, OSError, ValueError, session.SessionBlocked) as exc:
        print(json.dumps({"result": "blocked", "reason": str(exc),
                          "steam_launch_requested": False,
                          "unrelated_processes_terminated": False}, indent=2))
        return 2

if __name__ == "__main__":
    sys.exit(main())
