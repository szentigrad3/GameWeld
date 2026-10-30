#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only Steam game-session context audit for GameWeld.

Correlates a Wine game process with exact AppID and prefix identity, Linux
executable and mapped Wine modules. This does not verify a Win32 PID or
authorize a WeMod attachment. Steam settings and processes remain unchanged.
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


WINE_LOADERS = frozenset(("wine-preloader", "wine64-preloader"))
MAX_PROC_BYTES = 2 * 1024 * 1024

def read_small(path: Path) -> bytes | None:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_PROC_BYTES + 1)
        return data if len(data) <= MAX_PROC_BYTES else None
    except OSError:
        return None

def exact_identity(env: dict[str, str], appid: int, compat: Path, prefix: Path) -> bool:
    ids = [env[k] for k in GAME_ID_KEYS if k in env]
    if not ids or any(value != str(appid) for value in ids):
        return False
    if not env.get("STEAM_COMPAT_DATA_PATH") or not env.get("WINEPREFIX"):
        return False
    try:
        return (Path(env["STEAM_COMPAT_DATA_PATH"]).resolve(strict=True) == compat
                and Path(env["WINEPREFIX"]).resolve(strict=True) == prefix)
    except (OSError, RuntimeError):
        return False

def argv_parts(cmdline: bytes | None) -> list[str]:
    if cmdline is None:
        return []
    return [p.decode("utf-8", "replace").strip('"') for p in cmdline.split(b"\0") if p]

def exact_full_exe_in_argv(args: list[str], game_exe: Path) -> bool:
    for item in args:
        candidate = Path(item)
        if not candidate.is_absolute():
            continue
        try:
            if candidate.is_file() and candidate.resolve(strict=True) == game_exe:
                return True
        except (OSError, RuntimeError):
            continue
    return False

def wine_modules_mapped(proc: Path) -> bool:
    maps = read_small(proc / "maps")
    if maps is None:
        return False
    low = maps.lower()
    return any(marker in low for marker in (b"/wine", b"/proton", b"/ntdll.dll", b"/kernel32.dll"))

def process_start_ticks(proc: Path) -> int | None:
    raw = read_small(proc / "stat")
    if not raw:
        return None
    text = raw.decode("utf-8", "replace")
    end = text.rfind(") ")
    if end < 0:
        return None
    # Kernel field 22: after 'pid (comm) ' the first field is field 3.
    parts = text[end + 2:].split()
    if len(parts) <= 19:
        return None
    try:
        value = int(parts[19])
        return value if value >= 0 else None
    except ValueError:
        return None

def game_comm_matches(comm: str, game_name: str) -> bool:
    # Linux TASK_COMM_LEN is 16 bytes including the terminating NUL.
    try:
        truncated = game_name.encode("utf-8")[:15].decode("utf-8")
    except UnicodeError:
        return False
    return bool(truncated and comm.casefold() in (truncated.casefold(), game_name.casefold()))

def linux_loader_basename(proc: Path) -> str:
    try:
        return (proc / "exe").readlink().name.casefold()
    except (OSError, RuntimeError):
        return ""

def stable_process(proc: Path, start_ticks: int, uid: int) -> bool:
    try:
        return proc.stat().st_uid == uid and process_start_ticks(proc) == start_ticks
    except OSError:
        return False

def inspect_context(appid: int, compatdata: Path, game_exe: Path,
                    proc_root: Path = Path("/proc"), uid: int | None = None) -> dict:
    result = dict(state="steam_session_not_verified", appid=appid,
                  matched_process_count=0, matching_pids=[],
                  executable_hint_count=0, exact_runtime_verified=False,
                  game_process_verified=False, monitor_attached=False,
                  trainer_attachment_verified=False,
                  steam_launch_options_changed=False, game_prefix_modified=False,
                  wrapper_full_exe_pids=[], wine_server_pids=[],
                  game_process_candidate_pids=[], candidate_linux_pid=None,
                  candidate_start_time_ticks=None,
                  exact_prefix_identity_crosschecked=False,
                  linux_game_process_identity_correlated=False,
                  pid_reuse_rejections=0, unreadable_process_environment_count=0)
    if appid < 1 or compatdata.name != str(appid) or not (compatdata / "pfx/drive_c").is_dir():
        result["reason"] = "compatdata_not_ready_or_appid_mismatch"
        return result
    if not game_exe.is_absolute() or not game_exe.is_file():
        result["reason"] = "game_executable_not_verified"
        return result
    try:
        compat = compatdata.resolve(strict=True)
        prefix = (compatdata / "pfx").resolve(strict=True)
        game_exe = game_exe.resolve(strict=True)
    except (OSError, RuntimeError):
        result["reason"] = "selected_paths_not_resolvable"
        return result
    if uid is None:
        uid = os.geteuid()
    try:
        pids = sorted((p for p in proc_root.iterdir() if p.name.isdecimal()),
                      key=lambda p: int(p.name))
    except OSError:
        result["reason"] = "proc_read_unavailable"
        return result

    candidates: list[tuple[int, int]] = []
    for proc in pids[:10000]:
        try:
            if proc.stat().st_uid != uid:
                continue
            raw_env = read_small(proc / "environ")
            if not raw_env:
                result["unreadable_process_environment_count"] += 1
                continue
            env = read_environment(proc / "environ")
            if not exact_identity(env, appid, compat, prefix):
                continue
            pid = int(proc.name)
            result["matching_pids"].append(pid)
            comm = ((read_small(proc / "comm") or b"")
                    .decode("utf-8", "replace").strip())
            cmdline = read_small(proc / "cmdline")
            args = argv_parts(cmdline)
            if process_executable_hint(cmdline or b"", game_exe):
                result["executable_hint_count"] += 1
            if exact_full_exe_in_argv(args, game_exe):
                result["wrapper_full_exe_pids"].append(pid)
            loader = linux_loader_basename(proc)
            if comm.casefold() == "wineserver" and loader == "wineserver":
                result["wine_server_pids"].append(pid)
            # A launch wrapper can reference the real .exe without itself
            # being the game. Require a matching Wine process identity.
            if loader not in WINE_LOADERS or not game_comm_matches(comm, game_exe.name):
                continue
            if not process_executable_hint(cmdline or b"", game_exe):
                continue
            if not wine_modules_mapped(proc):
                continue
            start = process_start_ticks(proc)
            if start is None or not stable_process(proc, start, uid):
                result["pid_reuse_rejections"] += 1
                continue
            if not exact_identity(read_environment(proc / "environ"), appid, compat, prefix):
                result["pid_reuse_rejections"] += 1
                continue
            candidates.append((pid, start))
        except (OSError, ValueError, RuntimeError):
            continue

    result["matched_process_count"] = len(result["matching_pids"])
    result["game_process_candidate_pids"] = [pid for pid, _ in candidates]
    if len(candidates) == 1:
        result["state"] = "linux_game_process_candidate_correlated"
        result["reason"] = "win32_process_identity_and_runtime_attach_not_verified"
        result["candidate_linux_pid"], result["candidate_start_time_ticks"] = candidates[0]
        result["exact_prefix_identity_crosschecked"] = True
        result["linux_game_process_identity_correlated"] = True
    elif len(candidates) > 1:
        result["state"] = "ambiguous_game_process_candidates"
        result["reason"] = "multiple_exact_prefix_wine_game_processes"
    elif result["matching_pids"]:
        result["state"] = "steam_session_context_candidate"
        result["reason"] = "no_verified_linux_wine_game_process"
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
