#!/usr/bin/env python3
"""Read-only WeMod/Wand client release audit for GameWeld PC2.

The purpose is to distinguish a version-specific blank Electron window from a
GPU/renderer defect. Never auto-download, downgrade, patch, execute, or delete
WeMod, its profile, game files, Steam settings, or the Proton prefix.

The version in Electron's app.asar/package.json may NOT be the distribution
version shown by WeMod's installer. Report the source explicitly.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import struct
import sys

MAX_ASAR_HEADER = 8 * 1024 * 1024
MAX_PACKAGE_JSON = 256 * 1024
VERSION_RE = re.compile(r"\d{1,4}(?:\.\d{1,5}){2,3}(?:[-+][A-Za-z0-9._-]+)?\Z")
PACKAGE_RE = re.compile(r"(?:WeMod|Wand)[._-](\d+(?:\.\d+){2,3})(?:[-.][A-Za-z0-9._-]+)?\.nupkg\Z", re.I)


def asar_package_json(archive: Path) -> dict | None:
    """Read only Electron ASAR root package.json (bounded Chromium pickle header).

    Header: 8-byte uint32 pickle (4, serialized header length), then the
    serialized UTF-8 JSON tree (pickle string), then packed file data.
    We reject path traversal and offsets outside the file.
    """
    try:
        if archive.is_symlink() or not archive.is_file():
            return None
        with archive.open("rb") as fp:
            raw = fp.read(8)
            if len(raw) != 8:
                return None
            size_pickle, header_size = struct.unpack("<II", raw)
            if size_pickle != 4 or not (8 <= header_size <= MAX_ASAR_HEADER):
                return None
            header = fp.read(header_size)
            if len(header) != header_size:
                return None
            payload_size, text_len = struct.unpack("<II", header[:8])
            if (text_len < 2 or text_len > MAX_ASAR_HEADER - 8
                    or payload_size < text_len + 4
                    or text_len + 8 > len(header)):
                return None
            tree = json.loads(header[8:8 + text_len].decode("utf-8"))
            package = tree.get("files", {}).get("package.json", {})
            if not isinstance(package, dict) or "files" in package:
                return None
            count = package.get("size")
            offset = package.get("offset")
            if not isinstance(count, int) or not (1 <= count <= MAX_PACKAGE_JSON):
                return None
            if not isinstance(offset, str) or not offset.isascii() or not offset.isdecimal():
                return None
            start = 8 + header_size + int(offset)
            if start < 8 + header_size or start + count > archive.stat().st_size:
                return None
            fp.seek(start)
            raw_package = fp.read(count)
            if len(raw_package) != count:
                return None
            data = json.loads(raw_package.decode("utf-8"))
            return data if isinstance(data, dict) else None
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError,
            json.JSONDecodeError, struct.error, AttributeError):
        return None


def inspect(client_dir: Path) -> dict:
    location = client_dir.expanduser().resolve(strict=True)
    if not location.is_dir():
        raise ValueError("Install path is not a directory")
    exe = next((location / n for n in (
        "WeMod.exe", "Wand.exe", "wemod.exe", "wand.exe")
        if (location / n).is_file() and not (location / n).is_symlink()), None)
    if exe is None:
        raise ValueError("No direct WeMod.exe/Wand.exe in this client folder")
    with exe.open("rb") as fp:
        if fp.read(2) != b"MZ":
            raise ValueError("Selected WeMod/Wand executable has no Windows PE signature")
    asar = location / "resources" / "app.asar"
    package = asar_package_json(asar)
    findings: list[dict[str, str]] = []
    if package:
        version = package.get("version")
        if isinstance(version, str) and VERSION_RE.fullmatch(version):
            findings.append({
                "version": version,
                "source": "electron_app_asar_package_json",
                "scope": "embedded application package; may differ from release version",
            })
    direct_pkg = location / "resources" / "app" / "package.json"
    try:
        if direct_pkg.is_file() and not direct_pkg.is_symlink() and direct_pkg.stat().st_size < MAX_PACKAGE_JSON:
            pkg = json.loads(direct_pkg.read_text(encoding="utf-8"))
            version = pkg.get("version")
            if isinstance(version, str) and VERSION_RE.fullmatch(version):
                findings.append({
                    "version": version,
                    "source": "unpacked_electron_package_json",
                    "scope": "embedded application package; may differ from release version",
                })
    except (OSError, UnicodeError, ValueError, AttributeError):
        pass
    # A package filename is more direct evidence of the distribution release,
    # but we never treat a random sibling archive as the installed binary.
    for p in sorted(location.glob("*.nupkg"))[:10]:
        match = PACKAGE_RE.fullmatch(p.name)
        if match and p.is_file() and not p.is_symlink():
            findings.append({
                "version": match.group(1),
                "source": "local_nupkg_filename",
                "scope": "nearby archive; NOT proof the executable came from it",
            })
    asar_backup = location / "resources" / "app.asar.backup"
    enhancer_proxy = location / "version.dll"
    backup_present = (asar_backup.is_file() and not asar_backup.is_symlink())
    proxy_present = (enhancer_proxy.is_file() and not enhancer_proxy.is_symlink())
    return {
        "mode": "read_only",
        "client_executable": str(exe),
        "resources_app_asar_found": asar.is_file() and not asar.is_symlink(),
        "dwritecore_present": (location / "DWriteCore.dll").is_file(),
        "enhancer_proxy_version_dll_present": proxy_present,
        "original_asar_backup_present": backup_present,
        "enhancer_runtime_note": (
            "If the installed version.dll is WeMod Enhancer's proxy, it requires "
            "WINEDLLOVERRIDES=version=n,b in the WeMod process. File presence "
            "alone does not prove a valid Enhancer patch."
        ),
        "dotnet_runtime_verified": False,
        "dotnet_runtime_note": (
            "This audit reads the client folder only. It does NOT establish "
            "whether .NET Framework 4.8 is installed in the game's Proton prefix."
        ),
        "reported_versions": findings,
        "release_version_verified": False,
        "version_note": (
            "Embedded Electron package or archive metadata are hints only; "
            "do not treat them as verified WeMod release provenance."
        ),
        "known_test_observation": (
            "Coproton's independent report says its WeMod 12.x builds draw blank "
            "under Proton while its version-pinned 11.6.0 build renders. "
            "This has not been verified on this GameWeld installation."
        ),
        "actions_performed": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.install_dir)
    except (OSError, ValueError) as exc:
        print(json.dumps({"mode": "read_only", "status": "BLOCKED",
                          "reason": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
