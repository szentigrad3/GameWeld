#!/usr/bin/env python3
"""Optional, isolated, checksum-verified legacy WeMod client staging.

This tool NEVER launches a game, modifies any Proton/Wine prefix, applies an
Enhancer patch, or replaces GameWeld's managed DeckCheatz WeMod install.
It stages official 11.6.0 for a separately controlled compatibility experiment.
The published package hash was independently pinned by coproton.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
from urllib.request import urlopen
from urllib.error import HTTPError
import zipfile

VERSION = "11.6.0"
PACKAGE_URL = f"https://storage-cdn.wemod.com/app/releases/stable/WeMod-{VERSION}-full.nupkg"
SHA256 = "5b94ae5592e698b13cbc06fae4c096fe2438cbd362daac3f842e13190bf836ba"
PREFIX = "lib/net45/"
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024
MAX_UNPACKED_BYTES = 1500 * 1024 * 1024
MAX_FILES = 20000


def installation_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and not Path(xdg).is_absolute():
        raise ValueError("XDG_DATA_HOME must be absolute")
    return (Path(xdg) if xdg else Path.home() / ".local/share") / "gameweld" / "wemod-compat" / VERSION


def installed(path: Path) -> bool:
    return (path / "WeMod.exe").is_file() and (path / "resources/app.asar").is_file()


def verified_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, Path]]:
    files: list[tuple[zipfile.ZipInfo, Path]] = []
    seen: set[str] = set()
    total = 0
    for info in archive.infolist():
        if not info.filename.startswith(PREFIX) or info.is_dir():
            continue
        rel = info.filename[len(PREFIX):]
        parts = PurePosixPath(rel).parts
        if (not parts or any(p in (".", "..") for p in parts)
                or rel.startswith("/") or "\\" in rel or ":" in rel):
            raise ValueError("Unsafe archive path")
        key = rel.lower()
        if key in seen:
            raise ValueError("Duplicate case-insensitive archive path")
        seen.add(key)
        if ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
            raise ValueError("Archive contains symlink")
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise ValueError("Archive exceeds uncompressed size limit")
        files.append((info, Path(*parts)))
        if len(files) > MAX_FILES:
            raise ValueError("Archive has too many files")
    required = {"wemod.exe", "resources/app.asar"}
    if not required.issubset(seen):
        raise ValueError("Expected WeMod.exe and resources/app.asar not found")
    return files


def unpack(package: Path, destination: Path) -> None:
    """Extract only lib/net45 into an empty staging directory."""
    if destination.exists():
        raise ValueError("Staging destination already exists")
    destination.mkdir(mode=0o700, parents=True)
    with zipfile.ZipFile(package) as archive:
        members = verified_members(archive)
        for info, rel in members:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    if not installed(destination):
        raise ValueError("Extracted package is incomplete")
    with (destination / "WeMod.exe").open("rb") as exe:
        if exe.read(2) != b"MZ":
            raise ValueError("WeMod.exe is not a Windows PE executable")


def download(package: Path, url: str = PACKAGE_URL, expected_sha: str = SHA256) -> None:
    digest = hashlib.sha256()
    size = 0
    with urlopen(url, timeout=45) as response, package.open("xb") as output:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise ValueError("WeMod package exceeds download limit")
            output.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != expected_sha:
        raise ValueError("Official WeMod package SHA-256 mismatch; rejected")


def copy_verified_package(source: Path, destination: Path) -> None:
    """Copy a user-supplied official archive into private staging; verify pinned hash."""
    if not source.is_file() or source.is_symlink():
        raise ValueError("Local package must be an existing regular .nupkg file (not a symlink)")
    if source.suffix.lower() != ".nupkg":
        raise ValueError("Local package must be the original .nupkg archive")
    digest = hashlib.sha256()
    amount = 0
    with source.open("rb") as src, destination.open("xb") as dst:
        while chunk := src.read(1024 * 1024):
            amount += len(chunk)
            if amount > MAX_DOWNLOAD_BYTES:
                raise ValueError("Local package exceeds maximum accepted size")
            digest.update(chunk)
            dst.write(chunk)
    if digest.hexdigest() != SHA256:
        raise ValueError("Local package SHA-256 mismatch; refusing unverified WeMod archive")


def stage(destination: Path, package_path: Path | None = None) -> None:
    if destination.exists():
        if installed(destination):
            print(f"WeMod {VERSION} already staged: {destination}")
            return
        raise ValueError(f"Refusing to replace existing destination: {destination}")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".wemod-stage-", dir=destination.parent) as td:
        temp = Path(td)
        package = temp / "original.nupkg"
        unpacked = temp / "client"
        if package_path is not None:
            print(f"Validating user-supplied WeMod archive: {package_path}", flush=True)
            copy_verified_package(package_path, package)
        else:
            print("Downloading pinned official WeMod package and checking SHA-256...", flush=True)
            try:
                download(package)
            except HTTPError as exc:
                if exc.code == 403:
                    raise ValueError(
                        "Official WeMod CDN returned HTTP 403 (Forbidden). No package was staged. "
                        "If you already have the original WeMod-11.6.0-full.nupkg, "
                        "use 'stage --confirm --package /absolute/path/to/file.nupkg'."
                    ) from exc
                raise
        print("Package SHA-256 verified; extracting portable lib/net45 client...", flush=True)
        unpack(package, unpacked)
        manifest = {
            "tool": "gameweld-isolated-wemod-baseline",
            "version": VERSION,
            "package_sha256": SHA256,
            "exe_sha256": hashlib.sha256((unpacked / "WeMod.exe").read_bytes()).hexdigest(),
            "asar_sha256": hashlib.sha256((unpacked / "resources/app.asar").read_bytes()).hexdigest(),
        }
        marker = unpacked / ".gameweld-baseline.json"
        marker.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        marker.chmod(0o600)
        # Atomic rename on same filesystem. No changes to current installation.
        unpacked.rename(destination)
    print(f"WeMod {VERSION} staged separately at: {destination}")
    print("This is an UNPATCHED client; no game, trainer, or prefix was launched.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "stage"))
    parser.add_argument("--confirm", action="store_true",
                        help="Explicitly approve downloading or importing the pinned client")
    parser.add_argument("--package", type=Path,
                        help="Use an existing official 11.6.0 full .nupkg instead of downloading; exact SHA-256 required")
    args = parser.parse_args()
    try:
        destination = installation_path()
        if args.action == "status":
            print(f"Legacy WeMod version: {VERSION}")
            print(f"Official package: {PACKAGE_URL}")
            print(f"Expected SHA-256: {SHA256}")
            print(f"Separate staging destination: {destination}")
            print(f"Already staged: {'yes' if installed(destination) else 'no'}")
            print("Status is read-only. The existing DeckCheatz WeMod is never replaced.")
            return 0
        if args.package is not None and args.action != "stage":
            raise ValueError("--package is only valid with stage")
        if not args.confirm:
            raise ValueError("Staging requires explicit --confirm")
        stage(destination, package_path=args.package)
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"GameWeld legacy WeMod staging: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
