#!/usr/bin/env python3
"""Conservative, read-only Windows EXE resolver for an installed Steam game.

GameWeld's Play with WeMod route must not need a file picker. Refuse ambiguous
or unsafe targets rather than silently running setup, uninstallers, launchers,
anti-cheat helpers, or executables outside the selected Steam game directory.
Does not start Steam, Wine, Proton, the trainer, or the game.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
SKIP_DIRS = frozenset({
    "_commonredist", "redist", "redistributables", "support", "directx",
    "engine", "content", "saved", "data", "docs", "documentation",
    "mods", "plugins", "dotnet", "prerequisites", "tools", "backup",
    "crashreport", "crashreports", "easyanticheat", "battleye",
})
BAD_NAMES = (
    "unins", "uninstall", "setup", "install", "crash", "report",
    "redist", "prereq", "vcredist", "dxsetup", "easyanticheat",
    "battleye", "benchmark", "updater", "update", "config",
    "launcher", "support", "editor", "test", "unitycrash",
)
MAX_FILES = 2000
MAX_DIRS = 96
MAX_DEPTH = 4


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def valid_exe(path: Path, root: Path) -> bool:
    """Require a real, regular Windows PE executable within the exact game."""
    try:
        if path.is_symlink() or path.suffix.casefold() != ".exe":
            return False
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            return False
        if path.stat().st_size < 64:
            return False
        with path.open("rb") as stream:
            return stream.read(2) == b"MZ"
    except (OSError, ValueError):
        return False


def score_exe(path: Path, root: Path, title: str) -> int:
    base = normalized(path.stem)
    directory = normalized(root.name)
    game = normalized(title)
    if not base or any(bad in base for bad in BAD_NAMES):
        return -1000
    relative = path.relative_to(root)
    score = 0
    if base == directory or (game and base == game):
        score += 170
    elif (directory and (directory in base or base in directory) and len(base) >= 5) or (
        game and (game in base or base in game) and len(base) >= 5
    ):
        score += 100
    if path.parent == root:
        score += 35
    parts = {p.casefold() for p in relative.parts[:-1]}
    if "binaries" in parts and ("win64" in parts or "win32" in parts):
        score += 20
    if base.endswith("win64shipping") or base.endswith("win32shipping"):
        score += 35
    elif base.endswith("shipping"):
        score += 10
    if "server" in base or "dedicated" in base:
        score -= 140
    return score


def resolve(appid: str, install: Path, title: str, preferred: str = "") -> dict:
    result = {"mode": "read_only", "appid": appid, "selected": "",
              "reason": "", "candidate_count": 0, "ambiguous": False}
    if not APPID.fullmatch(appid):
        result["reason"] = "Invalid Steam AppID"
        return result
    try:
        root = install.expanduser().resolve(strict=True)
        steamapps = root.parent.parent
        if root.parent.name != "common" or steamapps.name != "steamapps" or not root.is_dir():
            raise ValueError("Not an installed Steam game's steamapps/common directory")
        if not (steamapps / ("appmanifest_" + appid + ".acf")).is_file():
            raise ValueError("Steam appmanifest for the selected game is missing")
    except (OSError, ValueError) as exc:
        result["reason"] = str(exc)
        return result

    if preferred:
        target = Path(preferred).expanduser()
        if valid_exe(target, root):
            result.update(selected=str(target.resolve()), reason="Verified game-discovery target",
                          candidate_count=1)
            return result

    candidates: list[tuple[int, Path]] = []
    visited_dirs = 0
    scanned_files = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        visited_dirs += 1
        depth = len(Path(current).relative_to(root).parts)
        if visited_dirs > MAX_DIRS:
            break
        dirs[:] = sorted(
            d for d in dirs if depth < MAX_DEPTH
            and not (Path(current) / d).is_symlink()
            and d.casefold() not in SKIP_DIRS
        )
        for filename in sorted(names):
            scanned_files += 1
            if scanned_files > MAX_FILES:
                break
            if not filename.casefold().endswith(".exe"):
                continue
            path = Path(current) / filename
            if valid_exe(path, root):
                candidates.append((score_exe(path, root, title), path))
        if scanned_files > MAX_FILES:
            break

    candidates.sort(key=lambda v: (-v[0], str(v[1]).casefold()))
    result["candidate_count"] = len(candidates)
    # Use a unique high-confidence name match. A sole root executable is safe
    # when no other runnable Windows EXE exists within the bounded game tree.
    if candidates:
        best_score, best = candidates[0]
        runner_up = candidates[1][0] if len(candidates) > 1 else -1000
        if (best_score >= 100 and best_score - runner_up >= 30) or (
            len(candidates) == 1 and best.parent == root and best_score >= 35
        ):
            result.update(selected=str(best.resolve()),
                          reason="Unique matching installed game EXE")
        else:
            result["ambiguous"] = len(candidates) > 1
            result["reason"] = "No unique safe game EXE match; GameWeld will not guess"
    else:
        result["reason"] = "No usable Windows game EXE found in the installed Steam game"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--preferred", default="")
    args = parser.parse_args()
    outcome = resolve(args.appid, args.install_dir, args.title, args.preferred)
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome["selected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
