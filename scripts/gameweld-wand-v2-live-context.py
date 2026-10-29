#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only Steam game-session context audit for GameWeld.

Matches exported Steam/PREFIX markers for the selected game; this does not
prove the true game executable, attach WeMod or modify a Steam setting.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

GAME_ID_KEYS = ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")
EXCLUDED = frozenset(("steam", "steamwebhelper", "bash", "python", "python3", "gameweld", "wandd"))

def read_environment(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    result: dict[str, str] = {}
    wanted = {s.encode("ascii") for s in (*GAME_ID_KEYS, "STEAM_COMPAT_DATA_PATH", "WINEPREFIX")}
    for field in raw.split(b"\0"):
        key, sep, value = field.partition(b"=")
        if sep and key in wanted:
            result[key.decode("ascii")] = value.decode("utf-8", "replace")
    return result

def process_executable_hint(cmdline: bytes, game_exe: Path) -> bool:
    wanted = game_exe.name.casefold()
    for part in cmdline.split(b"\0"):
        if not part:
            continue
        name = part.decode("utf-8", "replace").replace("\\", "/").rsplit("/", 1)[-1]
        if name.casefold() == wanted:
            return True
    return False

def inspect_context(appid: int, compatdata: Path, game_exe: Path,
                    proc_root: Path = Path("/proc"), uid: int | None = None) -> dict:
    result = dict(state="steam_session_not_verified", appid=appid,
                  matched_process_count=0, matching_pids=[],
                  executable_hint_count=0, exact_runtime_verified=False,
                  game_process_verified=False, monitor_attached=False,
                  steam_launch_options_changed=False, game_prefix_modified=False)
    if appid < 1 or compatdata.name != str(appid) or not (compatdata/"pfx/drive_c").is_dir():
        result["reason"] = "compatdata_not_ready_or_appid_mismatch"
        return result
    if not game_exe.is_absolute() or not game_exe.is_file():
        result["reason"] = "game_executable_not_verified"
        return result
    if uid is None:
        uid = os.geteuid()
    prefix = (compatdata/"pfx").resolve()
    compat = compatdata.resolve()
    try:
        pids = sorted((p for p in proc_root.iterdir() if p.name.isdecimal()), key=lambda p: int(p.name))
    except OSError:
        result["reason"] = "proc_read_unavailable"
        return result
    for proc in pids[:10000]:
        try:
            if proc.stat().st_uid != uid:
                continue
            name = (proc/"comm").read_text(encoding="utf8", errors="replace").strip().casefold()
            if name in EXCLUDED:
                continue
            env = read_environment(proc/"environ")
            supplied = [env[k] for k in GAME_ID_KEYS if k in env]
            if not supplied or any(v != str(appid) for v in supplied):
                continue
            if not env.get("STEAM_COMPAT_DATA_PATH") or not env.get("WINEPREFIX"):
                continue
            if Path(env["STEAM_COMPAT_DATA_PATH"]).resolve() != compat:
                continue
            if Path(env["WINEPREFIX"]).resolve() != prefix:
                continue
            result["matching_pids"].append(int(proc.name))
            try:
                if process_executable_hint((proc/"cmdline").read_bytes(), game_exe):
                    result["executable_hint_count"] += 1
            except OSError:
                pass
        except (OSError, ValueError):
            continue
    result["matched_process_count"] = len(result["matching_pids"])
    if result["matched_process_count"]:
        result["state"] = "steam_session_context_candidate"
        result["reason"] = "environment_matches_only_no_verified_windows_process_identity"
    else:
        result["reason"] = "no_matching_live_process_context"
    return result

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GameWeld read-only Steam context audit")
    p.add_argument("--appid", type=int, required=True)
    p.add_argument("--compatdata", type=Path, required=True)
    p.add_argument("--game-exe", type=Path, required=True)
    args = p.parse_args(argv)
    print(json.dumps(inspect_context(args.appid, args.compatdata, args.game_exe), sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
