#!/usr/bin/env python3
"""Read-only Steam-owned game vs WeMod Linux runtime-context comparison.

Run while the game and WeMod (even a white window) are still present.
Uses only the newest GameWeld session record for an exact, validated AppID.
Does not read unrelated processes, dump secrets, enter namespaces, run Wine,
launch a game, change Steam settings, or touch a prefix.

Only current-user processes from the latest recorded session are inspected.
A PID may have been reused since the log was written: results are observations,
not verified identities. A Wine launcher may hand off to a child; a missing
PID does NOT prove WeMod exited or never displayed a window.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
APPID_IN_LOG = re.compile(r"^GAMEWELD_STEAM_WEMOD_V1: appid=(\d+)$", re.M)
GAME_PIDS = re.compile(r"^GAME_PROCESS_IDENTITY_OBSERVED: ([0-9,]+)$", re.M)
WEMOD_PID = re.compile(r"^WEMOD_LAUNCHER_RUNNING: pid (\d+)", re.M)
WEMOD_REQ_PID = re.compile(r"^WEMOD_PROCESS_REQUESTED: pid (\d+)", re.M)
MAX_FILE = 128 * 1024
ENV_ALLOW = (
    "STEAM_COMPAT_DATA_PATH",
    "WINEPREFIX",
    "STEAM_COMPAT_TOOL_PATHS",
    "SteamAppId",
    "SteamGameId",
    "STEAM_COMPAT_APP_ID",
    "DISPLAY",
    "XAUTHORITY",
    "XDG_RUNTIME_DIR",
    "LD_LIBRARY_PATH",
    "STEAM_RUNTIME",
    "PRESSURE_VESSEL_RUNTIME",
    "PRESSURE_VESSEL_PREFIX",
    "WINESERVER",
    "WINELOADER",
)


def latest_log(appid: str, *, state_dir: Path) -> Path | None:
    if not APPID.fullmatch(appid):
        raise ValueError("Invalid Steam AppID")
    base = state_dir / "gameweld" / "steam-wemod"
    try:
        choices = [
            p for p in base.glob(f"{appid}-*.log")
            if p.is_file() and not p.is_symlink() and not p.name.endswith(".proton.log")
        ]
        return max(choices, key=lambda p: p.stat().st_mtime) if choices else None
    except OSError:
        return None


def ids_from_session(log: Path, appid: str) -> tuple[int | None, int | None]:
    if log.is_symlink() or not log.is_file() or log.stat().st_size > MAX_FILE:
        return None, None
    try:
        body = log.read_text(errors="replace")
    except OSError:
        return None, None
    if not (m := APPID_IN_LOG.search(body)) or m.group(1) != appid:
        return None, None
    mg = GAME_PIDS.search(body)
    mw = WEMOD_PID.search(body) or WEMOD_REQ_PID.search(body)
    game_pid = int(mg.group(1).split(",")[0]) if mg else None
    wemod_pid = int(mw.group(1)) if mw else None
    return game_pid, wemod_pid


def process_status(pid: int | None, *, proc_root: Path = Path("/proc")) -> dict:
    if pid is None or pid < 1:
        return {"process_observed": False, "reason": "not_recorded_in_session"}
    d = proc_root / str(pid)
    try:
        if d.stat().st_uid != os.getuid():
            return {"process_observed": False, "reason": "not_same_user"}
        comm = (d / "comm").read_text(errors="replace").strip()
        environ = (d / "environ").read_bytes()
        if len(environ) > 512 * 1024:
            return {"process_observed": False, "reason": "environment_too_large"}
        pairs = {}
        for entry in environ.split(b"\0"):
            key, delimiter, value = entry.partition(b"=")
            if not delimiter:
                continue
            try:
                name = key.decode("ascii")
                if name in ENV_ALLOW:
                    pairs[name] = os.fsdecode(value)
            except UnicodeError:
                continue
        # Linux namespaces differ when the Proton game runs in a
        # pressure-vessel container and the second program did not enter it.
        mount_ns = os.readlink(d / "ns/mnt")
        exe = os.path.basename(os.readlink(d / "exe"))
        return {
            "process_observed": True,
            "pid": pid,
            "executable_name": exe,
            "task_name": comm,
            "mount_namespace": mount_ns,
            "steam_container_indicators_present": any(
                pairs.get(k) for k in ("STEAM_RUNTIME", "PRESSURE_VESSEL_RUNTIME",
                                       "PRESSURE_VESSEL_PREFIX")
            ),
            "ld_library_path_present": bool(pairs.get("LD_LIBRARY_PATH")),
            "wineprefix_present": bool(pairs.get("WINEPREFIX")),
            "proton_tool_paths_present": bool(pairs.get("STEAM_COMPAT_TOOL_PATHS")),
            "steam_appid_present": any(
                pairs.get(k) for k in ("SteamAppId", "SteamGameId",
                                       "STEAM_COMPAT_APP_ID")
            ),
            "x11_display_present": bool(pairs.get("DISPLAY")),
            "x11_authority_present": bool(pairs.get("XAUTHORITY")),
            "x11_runtime_dir_present": bool(pairs.get("XDG_RUNTIME_DIR")),
            # Raw paths/cookies/tokens are never serialized.
        }
    except OSError:
        return {"process_observed": False, "reason": "process_no_longer_available"}


def audit(appid: str, *, state_dir: Path, proc_root: Path = Path("/proc")) -> dict:
    selected = latest_log(appid, state_dir=state_dir)
    if selected is None:
        return {"appid": appid, "mode": "read_only",
                "status": "NO_SESSION_LOG", "actions_performed": "none"}
    gp, wp = ids_from_session(selected, appid)
    game = process_status(gp, proc_root=proc_root)
    wemod = process_status(wp, proc_root=proc_root)
    ns_match = (
        game["mount_namespace"] == wemod["mount_namespace"]
        if game.get("process_observed") and wemod.get("process_observed") else None
    )
    return {
        "appid": appid,
        "mode": "read_only",
        "session_log": selected.name,
        "game": game,
        "wemod_launcher": wemod,
        "same_mount_namespace": ns_match,
        "steam_runtime_difference_indicated": ns_match is False,
        "interpretation": (
            "A differing mount namespace is evidence that the two processes "
            "are not in the same Linux mount/runtime context. This may matter "
            "for Chromium child-process startup, but does not by itself "
            "diagnose or repair a white window. A missing WeMod launcher PID "
            "may simply mean Wine handed off to a child process."
        ),
        "actions_performed": "none",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", default="2353250")
    args = p.parse_args()
    if not APPID.fullmatch(args.appid):
        print(json.dumps({"status": "INVALID_APPID", "mode": "read_only"}))
        return 2
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    print(json.dumps(audit(args.appid, state_dir=base), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
