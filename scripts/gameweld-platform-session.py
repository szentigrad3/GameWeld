#!/usr/bin/env python3
"""Read-only game-process identity evidence for platform-owned Steam launches.

A matching AppID wrapper is *not* the real game. Require the same user's
executable process name, exact selected Steam AppID and Steam compatdata path.
Do not report trainer attach or Steam supervisor ownership based only on this
read-only observation. No game, Steam or trainer operation is executed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
MAX_PID = 8192
MAX_ENV = 131072
MAX_CMDLINE = 32768


def matching_game_processes(appid: str, game_exe: Path, compatdata: Path,
                            proc_root: Path = Path("/proc")) -> list[int]:
    if not APPID.fullmatch(appid):
        return []
    if game_exe.suffix.casefold() != ".exe" or not game_exe.is_file():
        return []
    if compatdata.name != appid or compatdata.parent.name != "compatdata":
        return []
    try:
        prefix = str(compatdata.resolve(strict=True))
        name = game_exe.name.casefold()
        entries = sorted((p for p in proc_root.iterdir() if p.name.isascii()
                          and p.name.isdecimal()), key=lambda p: int(p.name))
    except OSError:
        return []
    result: list[int] = []
    expected_id = {f"{key}={appid}".encode() for key in
                   ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")}
    expected_pfx = str((compatdata / "pfx").resolve())
    def exact_prefix_match(variables: set[bytes]) -> bool:
        # Steam/Proton may pass an XDG symlink path or WINEPREFIX instead of
        # STEAM_COMPAT_DATA_PATH to the actual Wine child. Require realpath
        # equality to the precise selected game's prefix, never a substring.
        for raw in variables:
            key, sep, value = raw.partition(b"=")
            if not sep or key not in (b"STEAM_COMPAT_DATA_PATH", b"WINEPREFIX"):
                continue
            raw_value = os.fsdecode(value)
            if not raw_value.startswith("/"):
                continue
            target = prefix if key == b"STEAM_COMPAT_DATA_PATH" else expected_pfx
            if os.path.realpath(raw_value) == target:
                return True
        return False
    for path in entries[:MAX_PID]:
        try:
            if path.stat().st_uid != os.getuid():
                continue
            env = (path / "environ").read_bytes()[:MAX_ENV + 1]
            if len(env) > MAX_ENV:
                continue
            variables = set(env.split(b"\0"))
            if not variables.intersection(expected_id) or not exact_prefix_match(variables):
                continue
            comm = (path / "comm").read_text(errors="replace").strip().casefold()
            if not comm or len(name) < 5:
                continue
            # Linux task comm is limited to 15 visible bytes. Long names need
            # additional argv evidence, not just the common truncated prefix.
            if len(name) <= 15:
                if comm != name:
                    continue
            else:
                if comm != name[:15]:
                    continue
                cmdline = (path / "cmdline").read_bytes()[:MAX_CMDLINE].decode(
                    "utf-8", errors="replace").casefold()
                if name not in cmdline:
                    continue
            result.append(int(path.name))
        except (OSError, ValueError, UnicodeError):
            continue
    return result


def observe(appid: str, game_exe: Path, compatdata: Path,
            proc_root: Path = Path("/proc")) -> dict:
    matches = matching_game_processes(appid, game_exe, compatdata, proc_root)
    return {
        "appid": appid,
        "state": "GAME_PROCESS_IDENTITY_OBSERVED" if matches else "UNCONFIRMED",
        "game_process_pids": matches,
        "game_window_verified": False,
        "steam_supervisor_verified": False,
        "trainer_attached_verified": False,
        "game_exe": str(game_exe),
        "compatdata": str(compatdata),
        "read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--game-exe", type=Path, required=True)
    parser.add_argument("--compatdata", type=Path, required=True)
    args = parser.parse_args()
    report = observe(args.appid, args.game_exe, args.compatdata)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["game_process_pids"] else 2


if __name__ == "__main__":
    sys.exit(main())
