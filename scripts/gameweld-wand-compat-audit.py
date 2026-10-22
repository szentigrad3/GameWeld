#!/usr/bin/env python3
"""Read-only audit of local Wand/WeMod Electron installations in Wine/Proton.

This helper intentionally does NOT patch binaries, app.asar, license state,
subscriptions, Electron fuses, or launch a process. Requires an explicit scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

BRANDS = ("Wand", "WeMod")
MAX_PROFILE_DIRS = 256
MAX_VERSION_DIRS = 256


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def _children(root: Path, *, pattern: str = "*") -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        return []
    try:
        return sorted((p for p in root.glob(pattern) if p.is_dir() and not p.is_symlink()),
                      key=lambda p: p.name.casefold())[:MAX_VERSION_DIRS]
    except OSError:
        return []


def _prefix_root(prefix: Path) -> Path:
    if (prefix / "drive_c").is_dir():
        return prefix
    if (prefix / "pfx" / "drive_c").is_dir():
        return prefix / "pfx"
    raise ValueError("Expected a Wine prefix containing drive_c/ (or pfx/drive_c/)")


def candidates(prefix: Path | None, install: Path | None) -> list[Path]:
    if install is not None:
        root = install.parent if install.name.lower() == "resources" else install
        if root.name.lower() == "app.asar":
            root = root.parent.parent
        return [root]

    assert prefix is not None
    drive = _prefix_root(prefix) / "drive_c"
    roots: list[Path] = []
    users = drive / "users"
    for user in _children(users)[:MAX_PROFILE_DIRS]:
        local = user / "AppData" / "Local"
        for brand in BRANDS:
            roots.append(local / brand)
            roots.append(local / "Programs" / brand)
    for vendor in (drive / "Program Files", drive / "Program Files (x86)"):
        for brand in BRANDS:
            roots.append(vendor / brand)

    seen: set[Path] = set()
    found: list[Path] = []
    for root in roots:
        if root.is_symlink() or not _under(root, drive):
            continue
        for candidate in [root, *_children(root, pattern="app-*")]:
            if not _under(candidate, drive):
                continue
            real = candidate.resolve(strict=False)
            if real not in seen and (candidate / "resources" / "app.asar").is_file():
                seen.add(real)
                found.append(candidate)
    return found


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def assess(root: Path, *, include_paths: bool, hash_files: bool) -> dict:
    res = root / "resources"
    asar = res / "app.asar"
    backup = res / "app.asar.backup"
    unpacked_backup = res / "app.asar.unpacked.backup"
    incomplete = res / ".incomplete-patch"
    unpacked = res / "app.asar.unpacked"

    if not asar.is_file():
        raise ValueError("No resources/app.asar was found in selected installation")
    if not os.access(asar, os.R_OK):
        raise ValueError("resources/app.asar is unreadable")
    exists_backup = backup.is_file()
    exists_unpacked_backup = unpacked_backup.is_dir()
    exists_marker = incomplete.exists()

    if exists_marker:
        status = "incomplete_patch_marker"
    elif exists_backup and exists_unpacked_backup:
        status = "enhancer_backup_pair_present"
    elif exists_backup or exists_unpacked_backup:
        status = "partial_enhancer_backup"
    else:
        status = "no_enhancer_backup_detected"

    data = {
        "product": "Wand" if "wand" in str(root).casefold() else "WeMod" if "wemod" in str(root).casefold() else "unknown",
        "install_name": root.name,
        "state": status,
        "asar_bytes": asar.stat().st_size,
        "app_asar": True,
        "app_asar_unpacked": unpacked.is_dir(),
        "app_asar_backup": exists_backup,
        "app_asar_unpacked_backup": exists_unpacked_backup,
        "incomplete_patch_marker": exists_marker,
        "compatibility": "read_only_inspection_only",
    }
    if include_paths:
        data["install_path"] = str(root.resolve(strict=False))
        data["asar_path"] = str(asar.resolve(strict=False))
    if hash_files:
        data["asar_sha256"] = sha256_file(asar)
        if exists_backup:
            data["backup_sha256"] = sha256_file(backup)
            data["asar_matches_backup"] = data["asar_sha256"] == data["backup_sha256"]
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    scoped = ap.add_mutually_exclusive_group(required=True)
    scoped.add_argument("--prefix", type=Path, help="Explicit Wine/Proton prefix or compat-data directory")
    scoped.add_argument("--install", type=Path, help="Exact Windows Wand/WeMod app version directory")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON")
    ap.add_argument("--show-paths", action="store_true", help="Include local paths in output (private)")
    ap.add_argument("--hash", action="store_true", help="Stream SHA256 of app.asar and any backup")
    args = ap.parse_args(argv)
    try:
        root = args.prefix if args.prefix is not None else args.install
        if not root.is_dir():
            raise ValueError("Specified directory does not exist")
        roots = candidates(args.prefix, args.install)
        data = [assess(p, include_paths=args.show_paths, hash_files=args.hash) for p in roots]
    except (ValueError, OSError, PermissionError) as e:
        if args.json:
            print(json.dumps({"schema": 1, "ok": False, "error": str(e), "installations": []}))
        else:
            print(f"GameWeld Wand audit: {e}", file=sys.stderr)
        return 2

    payload = {"schema": 1, "ok": bool(data), "read_only": True, "installations": data}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not data:
        print("No Wand/WeMod app.asar installations found in the selected scope.")
    else:
        for d in data:
            print(f"{d['product']} {d['install_name']}: {d['state']} ")
            if "install_path" in d:
                print(f"  {d['install_path']}")
            if "asar_sha256" in d:
                print(f"  SHA256 {d['asar_sha256']}")
    return 0 if data else 3


if __name__ == "__main__":
    sys.exit(main())
