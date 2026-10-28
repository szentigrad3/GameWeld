#!/usr/bin/env python3
"""Read-only, redacted diagnosis for Steam says Running but game window is absent.

Never launches/kills processes, modifies a prefix, or changes Steam options.
Uses verified same-AppID process evidence; historical log events are context
only and never count as successful game or trainer startup.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
ERRORS = ("traceback", "exception", "tclerror", "tkinter", "file not found",
          "permission denied", "failed to", "error_code=43", "error:")


def peer(filename: str, name: str):
    source = Path(__file__).resolve().with_name(filename)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Required installed GameWeld inspector missing")
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load installed GameWeld inspector")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def kind_from_cmdline(parts: list[bytes]) -> str | None:
    if not parts:
        return None
    # Paths and full command lines are not returned to the caller.
    names = {os.path.basename(x.decode("utf-8", "replace")).casefold()
             for x in parts[:24] if x}
    if "steam-session.py" in names:
        return "gameweld_one_shot_steam_shim"
    if "wemod" in names or "wemod.py" in names or "wemod.exe" in names:
        return "deckcheatz_or_wemod"
    if any(x.startswith("proton") for x in names):
        return "proton"
    return None


def recognized_launchers(proc_root: Path = Path("/proc"), limit: int = 16) -> list[dict]:
    result = []
    try:
        entries = proc_root.iterdir()
    except OSError:
        return result
    for proc in entries:
        if not proc.name.isdecimal():
            continue
        try:
            if proc.stat(follow_symlinks=False).st_uid != os.getuid():
                continue
            with (proc / "cmdline").open("rb") as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                continue
            kind = kind_from_cmdline(raw.split(b"\0"))
            if not kind:
                continue
            comm = (proc / "comm").read_text(errors="replace")[:64].strip()
            result.append({"pid": int(proc.name), "kind": kind,
                           "comm": re.sub(r"[^A-Za-z0-9_().-]", "_", comm)[:32]})
        except OSError:
            continue
    return sorted(result, key=lambda x: x["pid"])[:limit]


def log_indicators(path: Path) -> dict:
    """Inspect small tail without revealing log lines, secrets, or full paths."""
    try:
        if path.is_symlink():
            raise ValueError("symlink")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("unsafe log")
        with path.open("rb") as source:
            if info.st_size > 65536:
                source.seek(-65536, 2)
            sample = source.read(65536).decode("utf-8", "replace").casefold()
    except (OSError, ValueError):
        return {"found": False}
    return {
        "found": True,
        "size_bytes": info.st_size,
        "error_indicators": {word: sample.count(word) for word in ERRORS
                             if word in sample},
        "note": "Only diagnostic keyword counts; log contents not exported",
    }


def diagnose(appid: str, root: Path, install_dir: Path | None = None) -> dict:
    if not APPID.fullmatch(appid) or int(appid) >= 2**32:
        raise ValueError("Invalid Steam AppID")
    handoff = peer("gameweld-steam-handoff.py", "gw_stall_handoff")
    result = {
        "steam_appid": appid,
        "mode": "read_only",
        "steam_options_changed": False,
        "processes_terminated": False,
        "trainer_attachment_verified": False,
        "visible_game_window_verified": False,
    }
    if install_dir is None:
        try:
            auto = peer("gameweld-deckcheatz-autodetect.py", "gw_stall_auto")
            install_dir = auto.find_install(root, appid)[0]
        except (OSError, ValueError):
            install_dir = None
    life = handoff.game_session_lifecycle(appid, install_dir)
    result["game_install_manifest_resolved"] = install_dir is not None
    result["lifecycle"] = life
    result["recognized_launcher_processes"] = recognized_launchers()
    result["steam_events_historical_only"] = handoff.SteamLogProbe(root).summary(
        appid, historical=True)
    candidates = [Path.home() / ".local/share/gameweld/deckcheatz/wemod.log",
                  Path.home() / "wemod-launcher/wemod.log"]
    log_results = [log_indicators(x) for x in candidates]
    result["deckcheatz_logs"] = [x for x in log_results if x["found"]]
    if life["game_executable_candidates"] > 0:
        result["assessment"] = "game_exe_observed_window_and_trainer_unverified"
    elif life["total_appid_associated_processes"] > 0:
        result["assessment"] = "appid_processes_only_possible_wrapper_or_proton_stall"
    else:
        result["assessment"] = "no_exact_appid_game_exe_or_process_observed"
    result["note"] = ("Steam Running can reflect a wrapper/reaper only. "
                      "A missing game EXE is not proof it is permanently stuck. "
                      "Do not launch duplicates or kill unrelated Wine processes.")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", default="3008130")
    p.add_argument("--steam-root", type=Path, required=True)
    p.add_argument("--install-dir", type=Path)
    args = p.parse_args(argv)
    try:
        result = diagnose(args.appid, args.steam_root, args.install_dir)
    except (ValueError, OSError) as exc:
        p.exit(2, "GameWeld read-only diagnosis BLOCKED: " + str(exc) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
