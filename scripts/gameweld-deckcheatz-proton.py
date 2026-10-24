#!/usr/bin/env python3
"""Read-only Proton locator for the experimental GameWeld DeckCheatz preview.

Never launches Proton, modifies Steam, guesses between equally ranked tools or
bundles DeckCheatz. Reuses GameWeld's existing Steam compatibility resolver.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")


def load_steam_resolver():
    source = Path(__file__).with_name("gameweld-steam-shortcuts.py")
    spec = importlib.util.spec_from_file_location("gw_steam_shortcuts_for_deckcheatz", source)
    if spec is None or spec.loader is None:
        raise ValueError("GameWeld Steam shortcut resolver is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verified_proton(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    if p.is_dir():
        p = p / "proton"
    try:
        if p.name == "proton" and p.is_file() and os.access(p, os.X_OK):
            return str(p.resolve(strict=True))
    except OSError:
        pass
    return ""


def resolve(args) -> dict:
    if not APPID.fullmatch(args.appid) or int(args.appid) >= 2**32:
        raise ValueError("Invalid Steam AppID")
    root = Path(args.steam_root).expanduser().resolve(strict=True)
    install = Path(args.install_dir).expanduser().resolve(strict=True)
    steamapps = install.parent.parent
    if install.parent.name != "common" or steamapps.name != "steamapps":
        raise ValueError("Steam install must be under steamapps/common")
    if not (steamapps / ("appmanifest_" + args.appid + ".acf")).is_file():
        raise ValueError("The selected game has no matching Steam manifest")
    if not (root / "steamapps").is_dir():
        raise ValueError("Steam root has no steamapps directory")

    resolver = load_steam_resolver()
    libraries = resolver.steam_library_roots(root)
    game_library = steamapps.parent.resolve()
    if game_library not in libraries:
        libraries.append(game_library)

    found: dict[str, dict] = {}

    def offer(path, source, score):
        launcher = verified_proton(path)
        if launcher:
            old = found.get(launcher)
            if old is None or score > old["score"]:
                found[launcher] = {"path": launcher, "source": source, "score": score}

    # A concrete tool path associated with this game should win over generic
    # installed Proton versions.
    offer(args.preferred_path, "game-discovery-compat-tool", 110)
    if args.preferred_name:
        offer(resolver._resolve_tool_path(root, libraries, args.preferred_name),
              "game-discovery-tool-name", 100)

    compat = Path(args.compatdata).expanduser() if args.compatdata else None
    if compat and compat.name == args.appid and (compat / "pfx").is_dir():
        _, hint = resolver._compatdata_runtime_hint(compat)
        offer(hint, "game-prefix-config-info", 90)

    # Respect Steam's explicit AppID tool mappings. Multiple user mappings
    # with conflicting Proton paths remain ambiguous instead of being guessed.
    userdata = root / "userdata"
    if userdata.is_dir():
        for userdir in sorted(userdata.iterdir()):
            if not userdir.is_dir() or not userdir.name.isdecimal():
                continue
            name, scope, _, _, _ = resolver._compat_tool_mapping(
                root, userdir, int(args.appid))
            if name and scope == "exact":
                offer(resolver._resolve_tool_path(root, libraries, name),
                      "steam-appid-mapping", 105)

    # A single installed Proton can be selected unambiguously, but never
    # arbitrarily pick a version when multiple are installed.
    dirs = resolver._tool_dirs(root, libraries)
    for directory in dirs:
        try:
            entries = list(directory.iterdir())[:1024]
        except OSError:
            continue
        for child in entries:
            if child.is_dir():
                offer(child, "installed-proton-candidate", 10)

    ranked = sorted(found.values(), key=lambda x: (-x["score"], x["path"]))
    selected = ""
    reason = "No compatible Proton launcher file found"
    if ranked:
        highest = ranked[0]["score"]
        top = [row for row in ranked if row["score"] == highest]
        if len(top) == 1:
            selected = top[0]["path"]
            reason = "Resolved " + top[0]["source"]
        else:
            reason = "Multiple equally supported Proton launchers; manual choice required"
    return {
        "mode": "read_only", "appid": args.appid,
        "selected": selected, "reason": reason,
        "candidate_count": len(ranked), "candidates": ranked[:15],
        "steam_launch_options_modified": False, "game_launched": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", required=True)
    p.add_argument("--steam-root", required=True)
    p.add_argument("--install-dir", required=True)
    p.add_argument("--compatdata", default="")
    p.add_argument("--preferred-name", default="")
    p.add_argument("--preferred-path", default="")
    args = p.parse_args()
    try:
        print(json.dumps(resolve(args), indent=2))
    except (ValueError, OSError) as exc:
        print(json.dumps({"mode": "read_only", "selected": "",
                          "reason": str(exc), "candidate_count": 0,
                          "game_launched": False,
                          "steam_launch_options_modified": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
