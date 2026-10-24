#!/usr/bin/env python3
"""Read-only Steam Proton prefix prerequisites for WeMod 11.6.0.

The existing GameWeld WeMod handoff intentionally does not bootstrap a
separate Proton prefix or modify Steam settings. This checks whether the
selected game's existing prefix advertises real .NET Framework >= 4.8.

Never invokes Wine, winetricks, Steam, a game, or WeMod. Never installs .NET,
copies a prefix, changes registry keys, logs login tokens, or writes to the
prefix. Registry presence is evidence, not proof a renderer actually works.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
VDF_PATH = re.compile(r'^\s*"path"\s+"((?:[^"\\]|\\.)*)"\s*$', re.I)
FULL_KEY = r"Software\\Microsoft\\NET Framework Setup\\NDP\\v4\\Full"
MAX_REGISTRY_BYTES = 32 * 1024 * 1024
NET48_RELEASE_MIN = 528040


def steam_libraries(home: Path) -> list[Path]:
    candidates = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".steam/root",
    ]
    seen: set[str] = set()
    roots: list[Path] = []
    def add(path: Path) -> None:
        try:
            resolved = path.expanduser().resolve(strict=True)
            if not resolved.is_dir():
                return
            name = str(resolved)
            if name not in seen:
                seen.add(name)
                roots.append(resolved)
        except OSError:
            return
    for c in candidates:
        add(c)
        config = c / "steamapps/libraryfolders.vdf"
        try:
            if not config.is_file() or config.stat().st_size > 1024 * 1024:
                continue
            for line in config.read_text(errors="replace").splitlines():
                m = VDF_PATH.fullmatch(line)
                if m:
                    raw = m.group(1).replace("\\\\", "\\")
                    if raw.startswith("/"):
                        add(Path(raw))
        except OSError:
            continue
    return roots


def find_prefixes(appid: str, *, home: Path | None = None,
                  steam_roots: list[Path] | None = None) -> list[Path]:
    if not APPID.fullmatch(appid):
        raise ValueError("Invalid Steam AppID")
    roots = steam_roots if steam_roots is not None else steam_libraries(
        home or Path.home()
    )
    results: list[Path] = []
    seen: set[str] = set()
    for root in roots[:96]:
        folder = root / "steamapps" / "compatdata" / appid
        try:
            folder = folder.resolve(strict=True)
            if folder.name != appid or folder.parent.name != "compatdata":
                continue
            if not (folder / "pfx").is_dir():
                continue
            resolved = str(folder)
            if resolved not in seen:
                seen.add(resolved)
                results.append(folder)
        except OSError:
            continue
    return results


def read_framework_registry(system_reg: Path) -> dict:
    """Check only HKLM's .NET Framework v4 Full registry key, bounded to 32MB."""
    if not system_reg.is_file() or system_reg.is_symlink():
        return {"state": "system_reg_missing_or_unreadable", "net48_verified": False}
    try:
        if system_reg.stat().st_size > MAX_REGISTRY_BYTES:
            return {"state": "registry_too_large_to_inspect", "net48_verified": False}
        # Wine's .reg files hold escaped backslashes, not executable registry
        # scripts. Read only, and never output other values.
        content = system_reg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"state": "system_reg_missing_or_unreadable", "net48_verified": False}
    inside = False
    values: dict[str, int] = {}
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("["):
            name = trimmed.split("]", 1)[0].lstrip("[")
            inside = name.casefold() == FULL_KEY.casefold()
            continue
        if not inside:
            continue
        m = re.fullmatch(
            r'"(Release|Install)"=dword:([0-9a-fA-F]{8})',
            trimmed, flags=re.I,
        )
        if m:
            values[m.group(1).casefold()] = int(m.group(2), 16)
    release = values.get("release")
    install = values.get("install")
    if release is None:
        return {"state": "net48_release_not_detected", "net48_verified": False}
    installed = install is None or install == 1
    meets = release >= NET48_RELEASE_MIN and installed
    return {
        "state": "registry_indicates_net48_or_later" if meets else
                 "registry_below_net48_or_not_installed",
        "net48_verified": False,
        "registry_indicates_net48": meets,
        "release_value": release,
        "registry_install_value": install,
    }


def inspect(appid: str, *, home: Path | None = None,
            steam_roots: list[Path] | None = None) -> dict:
    results = []
    for folder in find_prefixes(appid, home=home, steam_roots=steam_roots):
        system_reg = folder / "pfx/system.reg"
        result = read_framework_registry(system_reg)
        result["compatdata"] = str(folder)
        results.append(result)
    return {
        "mode": "read_only",
        "appid": appid,
        "matching_prefixes": results,
        "result": "prefixes_found" if results else "no_matching_prefix_found",
        "interpretation": (
            "A .NET 4.8 registry Release entry is evidence of installation, "
            "not proof the framework works or that WeMod can draw. Missing "
            "registry evidence does not prove .NET is absent. Never edit the "
            "game prefix based on this report without explicit approval."
        ),
        "actions_performed": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.appid), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"mode": "read_only", "status": "BLOCKED",
                          "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
