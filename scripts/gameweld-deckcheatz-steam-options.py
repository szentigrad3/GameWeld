#!/usr/bin/env python3
"""Generate a Steam launch-option recipe for installed DeckCheatz.

Read-only. This never changes Steam Launch Options, invokes DeckCheatz,
downloads a ZIP, launches a game, or edits a Proton prefix.

DeckCheatz's supported Steam integration wraps %command%; directly launching
WeMod.exe with Proton runinprefix is a separate experiment and is NOT
equivalent to the demonstrated working Steam route.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import stat
import sys


class RecipeBlocked(ValueError):
    pass


def candidates(home: Path, data_home: Path) -> list[Path]:
    choices = [
        data_home / "gameweld/deckcheatz/wemod",
        home / ".local/share/gameweld/deckcheatz/wemod",
        home / "wemod-launcher/wemod",
        home / "Games/wemod-launcher/wemod",
    ]
    return list(dict.fromkeys(choices))


def validate_launcher(path: Path) -> Path:
    if (not path.is_absolute() or path.name != "wemod" or
            path.is_symlink() or not path.is_file() or
            not stat.S_ISREG(path.stat().st_mode) or
            not os.access(path, os.X_OK)):
        raise RecipeBlocked("Select an installed executable DeckCheatz 'wemod' wrapper")
    return path


def build_recipe(launcher: Path, log_path: Path | None = None) -> dict:
    script = validate_launcher(launcher)
    log = log_path if log_path is not None else script.parent / "wemod.log"
    if not log.is_absolute() or not log.name.endswith(".log") or log.is_dir():
        raise RecipeBlocked("Log destination must be an absolute .log file path")
    if log.is_symlink():
        raise RecipeBlocked("Refusing a symlinked log destination")
    line = (
        'WINEDLLOVERRIDES="version=n,b" '
        + "WEMOD_LOG=" + shlex.quote(str(log)) + " "
        + shlex.quote(str(script)) + " %command%"
    )
    return {
        "mode": "DECKCHEATZ_STEAM_LAUNCH_OPTION",
        "launch_option": line,
        "source": "existing installed DeckCheatz launcher",
        "steam_launch_options_changed": False,
        "steam_bridge_used": False,
        "game_launched": False,
        "wemod_launched": False,
        "prefix_modified": False,
        "trainer_attachment_verified": False,
        "requires_manual_steam_launch_option": True,
        "note": "Copy this exact line into the selected Steam game's Properties > General > Launch Options. Preserve any other required game-specific options. This is not a live handoff command.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path,
                        help="Existing DeckCheatz wrapper file (default: discover managed install)")
    parser.add_argument("--log-path", type=Path,
                        help="Override log destination (defaults to wemod.log beside launcher)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        home = Path.home()
        raw_data = os.environ.get("XDG_DATA_HOME", "")
        if raw_data and not Path(raw_data).is_absolute():
            raise RecipeBlocked("XDG_DATA_HOME must be absolute")
        data_home = Path(raw_data) if raw_data else home / ".local/share"
        if args.launcher is not None:
            selected = validate_launcher(args.launcher)
        else:
            available = []
            for item in candidates(home, data_home):
                try:
                    available.append(validate_launcher(item))
                except (RecipeBlocked, OSError):
                    continue
            if len(available) == 0:
                raise RecipeBlocked("No installed DeckCheatz 'wemod' wrapper found")
            selected = available[0]
        result = build_recipe(selected, args.log_path)
    except (RecipeBlocked, OSError, ValueError) as exc:
        parser.exit(2, f"DeckCheatz Steam recipe BLOCKED — {exc}\n")
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["launch_option"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
