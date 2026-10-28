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

def saved_compatibility_bridge_state(appid: str, *, steam_root=None) -> dict:
    """Inspect SAVED per-title mapping without guessing the Steam live tool.

    A missing *exact* mapping commonly means Steam uses a default Proton.
    Neither that nor an old prefix's runtime proves the live Steam selection.
    The user-provided Steam root is inspected in addition to native roots.
    """
    info = {"source": "saved_steam_compatibility",
            "live_client_selection_verified": False,
            "steam_compatibility_modified": False}
    if not appid.isdecimal() or not 0 < int(appid) < 2**32:
        return {**info, "state": "invalid_appid"}
    home = Path.home()
    roots = ([Path(steam_root)] if steam_root is not None else []) + [
        home / ".steam/root", home / ".steam/steam",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    ]
    try:
        bridge = import_peer("gameweld-steam-compat-bridge.py", "gw_dc_bridge_selection")
        selection = bridge.steam_compat_selection(appid, steam_roots=roots)
    except (OSError, ValueError, ImportError, AttributeError):
        return {**info, "state": "resolver_unavailable"}
    if selection.startswith("GAMEWELD BRIDGE SELECTED"):
        return {**info, "state": "gameweld_bridge_selected",
                "exact_per_game_mapping": True}
    if selection.startswith("OTHER TOOL SELECTED"):
        return {**info, "state": "other_compatibility_tool_selected",
                "exact_per_game_mapping": True}
    if "conflicting saved tool mappings" in selection:
        return {**info, "state": "conflicting_saved_mappings",
                "exact_per_game_mapping": False}
    if "no saved exact game mapping readable" in selection:
        return {**info, "state": "no_exact_per_game_mapping",
                "exact_per_game_mapping": False,
                "explanation": "Steam may use a global/default compatibility tool. "
                               "The saved per-game mapping does not identify its live tool."}
    return {**info, "state": "unverified",
            "exact_per_game_mapping": False}


def readiness(appid: str, launcher: Path, *, steam_root=None, steam_account=None,
              compat_steam_root=None) -> dict:
    options = import_peer("gameweld-steam-launch-options-preserve.py", "gw_steam_read")
    shimmod = import_peer("gameweld-deckcheatz-session.py", "gw_shim_read")
    try:
        # Native and Flatpak Steam have different per-account userdata roots.
        # Never choose the first of several distinct files: that might read a
        # different user's saved options and launch the wrong configuration.
        home = Path.home()
        roots = [steam_root] if steam_root is not None else [
            home / ".local/share/Steam", home / ".steam/root",
            home / ".steam/steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        ]
        matches = {}
        for root in roots:
            try:
                cfg, account = options.find_config(appid, root, steam_account)
            except (OSError, ValueError):
                continue
            matches[str(cfg.resolve(strict=True))] = (cfg, account)
        if len(matches) != 1:
            raise ValueError("Steam saved options are missing or multiple accounts/clients match; "
                             "cannot authorize a trainer launch")
        cfg, account = next(iter(matches.values()))
        original = options.launch_option(cfg, appid)
        shim = shimmod.installed_wrapper_path()
        result = classify_saved_option(original, launcher, shim, appid)
        selection = saved_compatibility_bridge_state(
            appid, steam_root=compat_steam_root or steam_root)
        result["saved_compatibility"] = selection
        if selection["state"] == "gameweld_bridge_selected":
            result["state"] = "incompatible_bridge_selected"
            result["reason"] = (
                "Steam's saved per-game compatibility selection is GameWeld Bridge. "
                "DeckCheatz must receive Steam's actual Proton command, not a "
                "nested GameWeld Bridge launcher. In Steam > Properties > "
                "Compatibility, select a verified working Proton tool, restart "
                "Steam to reload saved settings, and retry. No game launched.")
            result["steam_account"] = account
            return result
        if result["state"] == "one_shot_shim_configured":
            # Saved text alone does not prove the installed shim still exists
            # or matches the source we reviewed. A stale shim could strand a
            # Steam launch even if the token arm action succeeds.
            source = Path(__file__).resolve().with_name("gameweld-deckcheatz-session.py")
            if (shim.is_symlink() or not shim.is_file() or source.is_symlink()
                    or not source.is_file() or shim.read_bytes() != source.read_bytes()):
                result["state"] = "needs_setup"
                result["reason"] = "Installed one-shot Steam shim missing or differs from GameWeld source"
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
    p.add_argument("--compat-steam-root", type=Path,
                   help="Game's Steam root to inspect for compatibility mapping only")
    args = p.parse_args(argv)
    try:
        report = readiness(args.appid, args.launcher,
                           steam_root=args.steam_root, steam_account=args.steam_account,
                           compat_steam_root=args.compat_steam_root)
    except (OSError, ValueError) as exc:
        report = {"appid": args.appid, "state": "unknown", "reason": str(exc),
                  "steam_options_modified": False}
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
