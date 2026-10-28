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
from datetime import datetime, timezone
import stat
import shlex
import time

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
        "modified_utc": datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat(),
        "age_seconds_at_scan": max(0, int(time.time() - info.st_mtime)),
        "error_indicators": {word: sample.count(word) for word in ERRORS
                             if word in sample},
        "note": "Historical log keyword counts only; errors are not tied to this launch",
    }



def saved_steam_option_state(appid: str) -> dict:
    """Summarize current saved option shape without leaking commands or paths."""
    try:
        options = peer("gameweld-steam-launch-options-preserve.py", "gw_stall_saved_options")
        cfg, _account = options.find_config(appid, None, None)
        saved = options.launch_option(cfg, appid)
    except (OSError, ValueError) as exc:
        return {"state": "unknown", "reason_category": type(exc).__name__,
                "live_steam_cache_verified": False}
    try:
        tokens = shlex.split(saved)
    except ValueError:
        return {"state": "invalid_saved_quoting", "live_steam_cache_verified": False}
    if not tokens:
        state = "empty_saved_options"
    elif any(Path(x).name == "steam-session.py" for x in tokens):
        state = "gameweld_one_shot_shim_saved"
    elif any(Path(x).name.casefold() in ("wemod", "wemod.py") for x in tokens):
        state = "deckcheatz_wrapper_saved"
    else:
        state = "other_custom_steam_options"
    return {"state": state,
            "placeholder_count": tokens.count("%command%"),
            "live_steam_cache_verified": False,
            "raw_option_text_included": False}


def pending_one_shot_state(appid: str) -> dict:
    """Read the token without creating private dirs or disarming it."""
    raw = os.environ.get("XDG_STATE_HOME", "")
    state = Path(raw) if raw else Path.home() / ".local/state"
    if not state.is_absolute():
        return {"state": "unknown"}
    target = state / "gameweld/steam-session-tokens" / (appid + ".json")
    try:
        if target.is_symlink():
            return {"state": "unsafe_token_location"}
        with target.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 8192):
                return {"state": "unsafe_or_large_token"}
            record = json.loads(stream.read(8193).decode("utf-8"))
    except FileNotFoundError:
        return {"state": "no_pending_token"}
    except (OSError, ValueError, UnicodeError):
        return {"state": "unreadable_or_invalid_token"}
    if (not isinstance(record, dict) or record.get("schema") != 1
            or record.get("appid") != appid):
        return {"state": "unrecognized_token"}
    expires = record.get("expiry")
    if not isinstance(expires, (int, float)):
        return {"state": "invalid_expiration"}
    return {"state": "armed" if expires > time.time() else "expired",
            "minutes_until_expiry": max(0, int((expires - time.time()) / 60)),
            "launcher_path_included": False}


def saved_compatibility_tool_state(appid: str, steam_root: Path | None = None) -> dict:
    """Report selected legacy bridge without revealing Steam paths or config."""
    try:
        inspector = peer("gameweld-deckcheatz-steam-readiness.py",
                         "gw_stall_dc_compat_state")
        return inspector.saved_compatibility_bridge_state(
            appid, steam_root=steam_root)
    except (OSError, ValueError, ImportError, AttributeError):
        return {"state": "unverified", "source": "saved_steam_compatibility"}


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
    result["saved_steam_launch_options"] = saved_steam_option_state(appid)
    result["saved_steam_compatibility"] = saved_compatibility_tool_state(appid, root)
    result["pending_one_shot"] = pending_one_shot_state(appid)
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
