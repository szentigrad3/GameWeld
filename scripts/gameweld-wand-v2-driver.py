#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Experimental GameWeld GTK -> Steam -> DeckCheatz v2 handoff driver.

Only the real Steam client can launch a game. Never edit launch options,
compatibility settings or prefix files. The actual Windows observer and its
attachment proof must be implemented by the separately distributed rewrite;
a successful Linux anchor is not trainer attachment.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

APP_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
ENDPOINT = re.compile(r"(?:127\.0\.0\.1|localhost):([0-9]{1,5})\Z")


def load_sibling(filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(
        "gameweld_v2_driver_" + filename.replace(".", "_").replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError("required_gameweld_component_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blocked(appid: int, reason: str, **fields) -> dict:
    return {
        "appid": appid, "state": "gameweld_v2_blocked",
        "reason": reason, "win32_pid_verified": False,
        "monitor_attached": False, "trainer_attachment_verified": False,
        "trainer_cleanup_verified": False,
        "steam_launch_options_changed": False,
        "steam_configuration_written": False,
        **fields,
    }


def read_profile(appid: int, path: Path) -> dict:
    """Read user-managed config, never execute strings from config as a shell."""
    try:
        st = path.lstat()
        if not path.is_file() or path.is_symlink() or st.st_uid != os.geteuid():
            return {}
        if st.st_mode & 0o077 or st.st_size > 65536:
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        profiles = payload.get("games")
        if not isinstance(profiles, dict):
            return {}
        profile = profiles.get(str(appid))
        return profile if isinstance(profile, dict) else {}
    except (OSError, ValueError, UnicodeError, TypeError):
        return {}


def validate_install(game_exe: Path, install_dir: Path) -> tuple[Path, Path, Path] | None:
    """Allow a selected PE file only within the selected Steam common/game."""
    try:
        real_exe = game_exe.resolve(strict=True)
        real_install = install_dir.resolve(strict=True)
        if not real_exe.is_file() or not real_install.is_dir():
            return None
        if not real_exe.is_relative_to(real_install):
            return None
        if not real_exe.name.casefold().endswith(".exe"):
            return None
        with real_exe.open("rb") as f:
            if f.read(2) != b"MZ":
                return None
        if real_install.parent.name != "common" or real_install.parent.parent.name != "steamapps":
            return None
        return real_exe, real_install, real_install.parents[2]
    except (OSError, RuntimeError, ValueError, IndexError):
        return None


def validate_profile(profile: dict) -> tuple[Path, Path, str] | None:
    try:
        client = Path(profile["client_exe"])
        rewrite = Path(profile["rewrite_root"])
        endpoint = profile["monitor_endpoint"]
        if not isinstance(endpoint, str) or (m := ENDPOINT.fullmatch(endpoint)) is None:
            return None
        if not 1 <= int(m.group(1)) <= 65535:
            return None
        if not client.is_absolute() or not rewrite.is_absolute():
            return None
        client = client.resolve(strict=True)
        rewrite = rewrite.resolve(strict=True)
        if (not client.is_file() or not rewrite.is_dir()
                or not (rewrite / "src/wand_launcher/entrypoint.py").is_file()):
            return None
        with client.open("rb") as fp:
            if fp.read(2) != b"MZ":
                return None
        return client, rewrite, endpoint
    except (KeyError, TypeError, ValueError, RuntimeError, OSError):
        return None


def get_game(aio, appid: int, steam_root: Path, real_exe: Path):
    """Require the exact EXE already selected by the GameWeld GTK frontend."""
    found = aio.discover(appid, steam_root)
    exe = found.get("_game_exe")
    prefix = found.get("_compatdata")
    if found.get("state") != "linux_game_candidate_discovered":
        return None
    if exe != real_exe or not isinstance(prefix, Path):
        return None
    return prefix, found


def run(argv=None, *, aio=None, anchor=None, context=None, session=None,
        steam_spawn=None, pause=time.sleep, profile_reader=read_profile) -> dict:
    p = argparse.ArgumentParser(description="Development-only GameWeld Steam v2 driver")
    p.add_argument("--appid", required=True)
    p.add_argument("--game-exe", type=Path, required=True)
    p.add_argument("--install-dir", type=Path, required=True)
    p.add_argument("--steam-root", type=Path)
    p.add_argument("--config", type=Path)
    p.add_argument("--launch-steam", action="store_true")
    p.add_argument("--check-only", action="store_true")
    a = p.parse_args(argv)
    if APP_ID.fullmatch(a.appid) is None:
        return blocked(0, "invalid_steam_appid")
    appid = int(a.appid)
    selected = validate_install(a.game_exe, a.install_dir)
    if selected is None:
        return blocked(appid, "selected_steam_game_executable_invalid")
    exe, install, steam_root = selected
    if a.steam_root is not None:
        try:
            if a.steam_root.resolve(strict=True) != steam_root:
                return blocked(appid, "selected_steam_library_mismatch")
        except (OSError, RuntimeError):
            return blocked(appid, "selected_steam_library_missing")
    config = a.config
    if config is None:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        config = base / "gameweld/wand-v2.json"
    profile = validate_profile(profile_reader(appid, config))
    if profile is None:
        return blocked(appid, "deckcheatz_v2_profile_not_configured")
    client, rewrite, endpoint = profile
    if TOKEN.fullmatch(os.environ.get("WAND_MONITOR_SESSION_TOKEN", "")) is None:
        return blocked(appid, "trusted_monitor_session_token_missing")
    if aio is None:
        aio = load_sibling("gameweld-wand-v2-aio.py")
    if anchor is None:
        anchor = load_sibling("gameweld-wand-v2-live-anchor.py")
    if context is None:
        context = load_sibling("gameweld-wand-v2-live-context.py")
    if session is None:
        session = load_sibling("gameweld-wand-v2-session.py")
    if steam_spawn is None:
        def steam_spawn(ident):
            return subprocess.Popen(
                ["steam", "-applaunch", str(ident)], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=True)

    current = get_game(aio, appid, steam_root, exe)
    if current is None and not a.launch_steam:
        return blocked(appid, "steam_game_not_running")
    if a.check_only:
        return blocked(appid, "integration_check_only_no_win32_proof",
                       linux_game_candidate_found=current is not None)
    if current is None:
        # Preflight all static monitor settings BEFORE launching a Steam game.
        try:
            steam_spawn(appid)
        except OSError:
            return blocked(appid, "normal_steam_launch_failed")
        for _ in range(45):
            pause(2)
            current = get_game(aio, appid, steam_root, exe)
            if current is not None:
                break
        if current is None:
            return blocked(appid, "steam_game_process_not_observed_after_launch")

    compat, evidence = current
    # Pin the exact PID/start ticks that were just discovered. A restart
    # between discovery and this check must fail closed.
    pid = evidence.get("candidate_linux_pid")
    ticks = evidence.get("candidate_start_time_ticks")
    if type(pid) is not int or type(ticks) is not int:
        return blocked(appid, "game_linux_identity_missing")
    res = anchor.verify_anchor(appid, compat, exe, pid=pid, start_ticks=ticks,
                               samples=3, interval_ms=400)
    if res.get("state") != "linux_runtime_anchor_stable":
        return blocked(appid, "game_linux_identity_not_stable")

    # Existing upstream monitor must be provided separately and authenticated
    # by DeckCheatz; this driver does NOT manufacture a Win32 observer.
    args = ["--appid", str(appid), "--compatdata", str(compat),
            "--client", str(client), "--game-exe", str(exe),
            "--monitor-endpoint", endpoint, "--rewrite-root", str(rewrite)]
    status = io.StringIO()
    try:
        with redirect_stdout(status):
            code = session.run(args)
    except (OSError, RuntimeError, ValueError):
        return blocked(appid, "guarded_monitor_bridge_failed")
    try:
        payload = json.loads(status.getvalue())
    except (ValueError, TypeError):
        return blocked(appid, "guarded_monitor_report_invalid")
    if code != 0 or not isinstance(payload, dict):
        return blocked(appid, "guarded_monitor_bridge_rejected")
    # An upstream observer's JSON is not a protected Win32 handle/verified
    # attachment. GameWeld must never report the GUI action as successful.
    return blocked(appid, "windows_attachment_and_cleanup_not_independently_verified",
                   linux_game_candidate_found=True,
                   upstream_session_state=payload.get("state"))


def main() -> int:
    report = run()
    print(json.dumps(report, sort_keys=True))
    # The GTK UI may only show success after independently verified Windows
    # identity, game attachment and cleanup. No such proof exists here yet.
    return 2


if __name__ == "__main__":
    sys.exit(main())
