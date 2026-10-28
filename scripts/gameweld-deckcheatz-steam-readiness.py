#!/usr/bin/env python3
"""Read-only per-game DeckCheatz Steam launch integration check.

Steam's active client may hold an unsaved launch option; this inspects the
saved localconfig.vdf only. Never edits Steam or starts a game.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import sys

def import_peer(filename, label):
    location = Path(__file__).resolve().with_name(filename)
    if location.is_symlink() or not location.is_file():
        raise ValueError("Required GameWeld inspector is unavailable")
    spec = importlib.util.spec_from_file_location(label, location)
    if not spec or not spec.loader:
        raise ValueError("Could not read GameWeld inspector")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def classify_saved_option(option: str, launcher: Path, shim: Path, appid: str) -> dict:
    """No guessing when a custom command has ambiguous shell syntax."""
    info = {"launch_options_source": "saved_steam_localconfig",
            "live_client_options_verified": False,
            "steam_options_modified": False, "appid": appid}
    if not option.strip():
        return {**info, "state": "needs_setup", "reason": "No saved Steam wrapper"}
    try:
        parts = shlex.split(option)
    except ValueError:
        return {**info, "state": "needs_setup", "reason": "Invalid saved option quotes"}
    if parts.count("%command%") != 1:
        return {**info, "state": "needs_setup",
                "reason": "Missing or repeated %command% placeholder"}
    marker = parts.index("%command%")
    if marker < 1:
        return {**info, "state": "needs_setup", "reason": "No DeckCheatz wrapper"}
    # The actual saved Steam command may have extra custom wrappers or game
    # arguments. Only recognize the launcher when it immediately precedes
    # %command%, or the exact installed session shim sequence does.
    def identical(candidate: str, target: Path) -> bool:
        try:
            selected = Path(candidate).expanduser()
            return selected.is_absolute() and selected.resolve(strict=True) == target.resolve(strict=True)
        except OSError:
            return False
    if identical(parts[marker - 1], launcher):
        return {**info, "state": "direct_wrapper_configured",
                "custom_options_present": len(parts) > 2}
    if marker >= 5 and parts[marker - 5:marker] == [
            str(shim), "run", "--appid", appid, "--"]:
        # Preceding interpreter must be from a small approved list; this
        # doesn't install a shim or claim that Steam's live cache matches.
        interp = parts[marker - 6] if marker >= 6 else ""
        if interp in ("/usr/bin/python3", "/usr/bin/python"):
            return {**info, "state": "one_shot_shim_configured",
                    "custom_options_present": len(parts) > 7}
    return {**info, "state": "needs_setup",
            "reason": "No verified DeckCheatz Steam wrapper"}

def readiness(appid: str, launcher: Path, *, steam_root=None, steam_account=None) -> dict:
    options = import_peer("gameweld-steam-launch-options-preserve.py", "gw_steam_read")
    shimmod = import_peer("gameweld-deckcheatz-session.py", "gw_shim_read")
    try:
        cfg, account = options.find_config(appid, steam_root, steam_account)
        original = options.launch_option(cfg, appid)
        result = classify_saved_option(original, launcher, shimmod.installed_wrapper_path(), appid)
        result["steam_account"] = account
        return result
    except (OSError, ValueError) as exc:
        return {"appid": appid, "state": "unknown", "reason": str(exc),
                "launch_options_source": "saved_steam_localconfig",
                "live_client_options_verified": False,
                "steam_options_modified": False}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", required=True)
    p.add_argument("--launcher", required=True, type=Path)
    p.add_argument("--steam-root", type=Path)
    p.add_argument("--steam-account")
    args = p.parse_args(argv)
    try:
        report = readiness(args.appid, args.launcher,
                           steam_root=args.steam_root, steam_account=args.steam_account)
    except (OSError, ValueError) as exc:
        report = {"appid": args.appid, "state": "unknown", "reason": str(exc),
                  "steam_options_modified": False}
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
