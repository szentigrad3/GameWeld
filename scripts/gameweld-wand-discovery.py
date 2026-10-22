#!/usr/bin/env python3
"""Bounded read-only discovery of *installed* Wand/WeMod Wine/Proton clients.

The tool never creates a prefix, launches Wine, edits a file, or calls a network service.
Only prefixes containing a concrete Wand/WeMod resources/app.asar are returned.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

SPEC = importlib.util.spec_from_file_location(
    "gameweld_wand_compat_audit_discovery", Path(__file__).with_name("gameweld-wand-compat-audit.py")
)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit)

MAX_PREFIXES = 2500
MAX_ENTRIES_PER_ROOT = 1500
MAX_CONFIG_FILES = 500
MAX_CONFIG_BYTES = 2_000_000


def safe_dirs(parent: Path, limit: int = MAX_ENTRIES_PER_ROOT) -> list[Path]:
    if not parent.is_dir() or parent.is_symlink():
        return []
    try:
        return sorted((p for p in parent.iterdir() if p.is_dir() and not p.is_symlink()),
                      key=lambda p: p.name.lower())[:limit]
    except OSError:
        return []


def steam_libraries(home: Path) -> list[Path]:
    roots = [home / ".local/share/Steam", home / ".steam/steam",
             home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
             home / ".var/app/com.valvesoftware.Steam/data/Steam"]
    libraries = list(roots)
    for root in roots:
        conf = root / "steamapps/libraryfolders.vdf"
        try:
            if conf.stat().st_size > MAX_CONFIG_BYTES:
                continue
            raw = conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for value in re.findall(r'"path"\s+"([^"\r\n]+)"', raw, re.I):
            path = Path(value.replace("\\\\", "\\")).expanduser()
            if path.is_absolute():
                libraries.append(path)
    return libraries


def heroic_prefixes(home: Path) -> list[Path]:
    """Only consult known Heroic configuration directories; never crawl the disk."""
    candidates = []
    configs = [home / ".config/heroic/GamesConfig",
               home / ".var/app/com.heroicgameslauncher.hgl/config/heroic/GamesConfig",
               home / ".var/app/com.heroicgameslauncher.hgl/.config/heroic/GamesConfig"]

    def visit(value: object, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                if k.lower() in ("wineprefix", "wine_prefix", "prefix") and isinstance(v, str):
                    candidate = Path(os.path.expandvars(v)).expanduser()
                    if candidate.is_absolute():
                        candidates.append(candidate)
                else:
                    visit(v, depth + 1)
        elif isinstance(value, list):
            for v in value[:300]:
                visit(v, depth + 1)

    total = 0
    for directory in configs:
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            files = sorted(directory.glob("*.json"))
        except OSError:
            continue
        for path in files:
            if total >= MAX_CONFIG_FILES:
                return candidates
            total += 1
            try:
                if path.is_symlink() or path.stat().st_size > MAX_CONFIG_BYTES:
                    continue
                visit(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return candidates


def lutris_prefixes(home: Path) -> list[Path]:
    conf_roots = [home / ".config/lutris/games", home / ".var/app/net.lutris.Lutris/config/lutris/games"]
    prefixes = []
    total = 0
    for directory in conf_roots:
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            configs = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
        except OSError:
            continue
        for f in configs:
            if total >= MAX_CONFIG_FILES:
                return prefixes
            total += 1
            try:
                if f.is_symlink() or f.stat().st_size > MAX_CONFIG_BYTES:
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Read simple literal 'prefix:' paths only. Do not execute YAML tags.
            for match in re.finditer(r'^\s*(?:wineprefix|prefix):\s*[\'\"]?([^\'\"#\r\n]+)', text, re.M | re.I):
                value = match.group(1).strip()
                value = value.replace("$HOME", str(home))
                candidate = Path(value).expanduser()
                if candidate.is_absolute():
                    prefixes.append(candidate)
    return prefixes


def potential_prefixes(home: Path):
    """Yield (location, source) without walking arbitrary trees."""
    direct = [home / ".wine", home / ".local/share/wineprefixes",
              home / ".local/share/lutris/prefixes", home / ".local/share/lutris/games",
              home / ".var/app/net.lutris.Lutris/data/lutris/prefixes",
              home / ".local/share/bottles/bottles",
              home / ".var/app/com.usebottles.bottles/data/bottles/bottles",
              home / "Games", home / "games", home / "Games/Heroic/Prefixes",
              home / "Games/Heroic", home / "Games/Lutris",
              home / ".local/share/heroic/prefixes"]
    yield home / ".wine", "Wine"
    for p in safe_dirs(home):
        if p.name.startswith(".wine-") or p.name.startswith(".wine_"):
            yield p, "Wine"
    for root in direct:
        yield root, "Wine / Lutris / Heroic / Bottles"
        for d in safe_dirs(root):
            yield d, "Wine / Lutris / Heroic / Bottles"
            for sub in ("pfx", "prefix", "wineprefix"):
                yield d / sub, "Wine / Lutris / Heroic / Bottles"
    for conf in heroic_prefixes(home):
        yield conf, "Heroic"
    for conf in lutris_prefixes(home):
        yield conf, "Lutris"
    for library in steam_libraries(home):
        comp = library / "steamapps/compatdata"
        for d in safe_dirs(comp):
            yield d / "pfx", "Steam Proton"


def discover(home: Path | None = None) -> dict:
    home = (home or Path.home()).expanduser().resolve()
    seen_prefixes: set[str] = set()
    seen_installs: set[str] = set()
    found: list[dict] = []
    checked = 0
    truncated = False
    for path, source in potential_prefixes(home):
        if checked >= MAX_PREFIXES:
            truncated = True
            break
        try:
            # Require a real prefix; don't accidentally instantiate one.
            prefix = audit._prefix_root(path)
            if not prefix.is_dir() or not (prefix / "drive_c").is_dir():
                continue
            real = prefix.resolve(strict=True)
            token = str(real)
            if token in seen_prefixes:
                continue
            seen_prefixes.add(token)
            checked += 1
            for root in audit.candidates(real, None):
                real_root = root.resolve(strict=True)
                if str(real_root) in seen_installs or not audit._under(real_root, real / "drive_c"):
                    continue
                asar = real_root / "resources/app.asar"
                if asar.is_symlink() or not asar.is_file() or not os.access(asar, os.R_OK):
                    continue
                seen_installs.add(str(real_root))
                brand = "Wand" if "wand" in str(real_root).lower() else "WeMod"
                found.append({"product": brand, "source": source, "version": real_root.name,
                              "prefix": token, "install": str(real_root)})
        except (ValueError, OSError, RuntimeError, PermissionError):
            continue
    found.sort(key=lambda x: (x["product"] != "Wand", x["product"].lower(), x["source"].lower(),
                              x["prefix"].lower(), x["version"].lower()), reverse=False)
    return {"schema": 1, "ok": True, "read_only": True, "scanned_prefixes": checked,
            "truncated": truncated, "installations": found}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tsv", action="store_true", help="Strict safe five-field machine protocol for GTK")
    parser.add_argument("--home", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = discover(args.home)
    if args.tsv:
        for item in result["installations"][:200]:
            fields = [item[k] for k in ("product", "source", "version", "prefix", "install")]
            if any("\t" in f or "\n" in f or "\r" in f for f in fields):
                continue
            print("FOUND\t" + "\t".join(fields))
        print(f'STATUS\t{len(result["installations"])}\t{result["scanned_prefixes"]}\t{int(result["truncated"])}')
    elif args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f'Found {len(result["installations"])} Wand/WeMod installation(s) in {result["scanned_prefixes"]} existing prefixes.')
        for row in result["installations"]:
            print(f'{row["product"]} {row["version"]} ({row["source"]}): {row["prefix"]}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
