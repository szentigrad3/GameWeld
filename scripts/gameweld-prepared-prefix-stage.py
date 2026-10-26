#!/usr/bin/env python3
"""Stage a cached third-party WeMod archive WITHOUT installing it into a game.

Private development preflight only. Nothing in this file writes a game prefix,
launches a runner, modifies a provider, or verifies trainer compatibility.
Untrusted archives stay in an isolated, user-private GameWeld cache subtree.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from typing import Callable

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CHUNK = 1024 * 1024
RESERVE_BYTES = 512 * 1024 * 1024
FORBIDDEN_ANCESTORS = {"steamapps", "compatdata", "pfx"}


class StageRefused(ValueError):
    pass


def safe_root(root: Path) -> Path:
    """Require a dedicated cache layout and reject symlinked ancestry."""
    if (not root.is_absolute() or root.name != "prepared-wemod" or
            root.parent.name != "gameweld"):
        raise StageRefused("Staging requires an absolute GameWeld prepared-wemod cache")
    if any(part.casefold() in FORBIDDEN_ANCESTORS for part in root.parts):
        raise StageRefused("Refusing a cache inside a Steam library or game prefix")
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise StageRefused("Symlinked cache directories are forbidden")
    if root.exists():
        if not root.is_dir():
            raise StageRefused("Cache root is not a directory")
        if stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise StageRefused("Cache root must not be accessible by other users")
    return root


def load_audit():
    script = Path(__file__).resolve().with_name("gameweld-prepared-prefix-audit.py")
    if script.is_symlink() or not script.is_file():
        raise StageRefused("Prepared ZIP archive inspector is missing")
    spec = importlib.util.spec_from_file_location("prepared_stage_audit", script)
    if spec is None or spec.loader is None:
        raise StageRefused("Could not load prepared ZIP archive inspector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_cached_archive(
    archive_path: Path,
    *,
    cache_root: Path,
    approved: bool,
    expected_sha256: str | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    """Create an isolated payload + manifest; never apply anything to a game."""
    if not approved:
        raise StageRefused("Explicit --approve-stage is required")
    root = safe_root(cache_root)
    archive = Path(archive_path)
    downloads = root / "downloads"
    if (not archive.is_absolute() or archive.parent != downloads or
            not HEX64.fullmatch(archive.stem) or archive.suffix != ".zip"):
        raise StageRefused("Select a SHA-256-addressed ZIP from GameWeld downloads")
    if (downloads.is_symlink() or not downloads.is_dir() or
            archive.is_symlink() or not archive.is_file() or
            not stat.S_ISREG(archive.stat().st_mode)):
        raise StageRefused("Missing or symlinked cached archive")
    if (expected_sha256 is not None and
            (not HEX64.fullmatch(expected_sha256.lower()) or
             expected_sha256.lower() != archive.stem)):
        raise StageRefused("Supplied expected checksum does not match cache name")

    source_record = None
    record_file = downloads / (archive.stem + ".source.json")
    if record_file.exists():
        if record_file.is_symlink() or record_file.stat().st_size > 4096:
            raise StageRefused("Cached archive source record is unsafe")
        try:
            source_record = json.loads(record_file.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise StageRefused("Cached source record is invalid") from exc
        if (not isinstance(source_record, dict) or
                source_record.get("sha256") != archive.stem or
                source_record.get("source") != "DeckCheatz/BuiltPrefixes-dev" or
                not isinstance(source_record.get("asset_name"), str) or
                not source_record["asset_name"].lower().endswith(".zip") or
                not isinstance(source_record.get("release_tag"), str)):
            raise StageRefused("Cached source record does not identify this archive")
    audit = load_audit()
    if not 0 < archive.stat().st_size <= audit.MAX_ARCHIVE_BYTES:
        raise StageRefused("Invalid cached archive size")
    # Hash + CRC are verified before any staging path is created.
    if sha256_file(archive) != archive.stem:
        raise StageRefused("Cached archive bytes do not match its SHA-256 name")
    try:
        with zipfile.ZipFile(archive) as source:
            count, unpacked = audit.inspect_zip_members(source)
            if source.testzip() is not None:
                raise StageRefused("Cached ZIP has a failed CRC")
    except (audit.UnsafePreparedPrefix, zipfile.BadZipFile,
            zipfile.LargeZipFile, RuntimeError, EOFError) as exc:
        raise StageRefused("Cached archive failed structural or CRC verification") from exc

    target_base = root / "staging"
    target = target_base / archive.stem
    if (target_base.is_symlink() or (target_base.exists() and
                                    not target_base.is_dir()) or
            target.exists() or target.is_symlink()):
        raise StageRefused("Staging destination is unsafe or already exists")
    try:
        free = shutil.disk_usage(root).free
    except OSError as exc:
        raise StageRefused("Cannot verify staging disk capacity") from exc
    if free < unpacked + RESERVE_BYTES:
        raise StageRefused("Insufficient free space for isolated staged contents")

    target_base.mkdir(mode=0o700, exist_ok=True)
    if target_base.is_symlink():
        raise StageRefused("Staging destination was replaced by a symlink")
    # The only mutable subtree is a freshly created private staging directory.
    work = Path(tempfile.mkdtemp(prefix=".incoming-", dir=target_base))
    try:
        payload = work / "payload"
        payload.mkdir(mode=0o700)
        manifest_files = []
        copied = 0
        if progress:
            progress("STAGE", 0, unpacked)
        with zipfile.ZipFile(archive) as source:
            # The ZIP could have been replaced since preflight: revalidate.
            audit.inspect_zip_members(source)
            for member in source.infolist():
                relative = member.filename.rstrip("/")
                dest = payload.joinpath(*relative.split("/"))
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest = hashlib.sha256()
                size = 0
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(dest, flags, 0o600)
                with os.fdopen(fd, "wb") as sink, source.open(member) as entry:
                    while True:
                        data = entry.read(CHUNK)
                        if not data:
                            break
                        size += len(data)
                        copied += len(data)
                        if size > member.file_size or copied > unpacked:
                            raise StageRefused("Archive expanded beyond its declared size")
                        sink.write(data)
                        digest.update(data)
                    sink.flush()
                    os.fsync(sink.fileno())
                if size != member.file_size:
                    raise StageRefused("Unpacked entry length mismatch")
                manifest_files.append({
                    "path": relative, "bytes": size, "sha256": digest.hexdigest()
                })
                if progress:
                    progress("STAGE", copied, unpacked)
        if copied != sum(f["bytes"] for f in manifest_files):
            raise StageRefused("Staged manifest and file sizes disagree")
        if sha256_file(archive) != archive.stem:
            raise StageRefused("Cache archive changed during staging")
        result = {
            "stage_path": str(target),
            "source_archive_sha256": archive.stem,
            "source_release": source_record.get("release_tag") if source_record else None,
            "source_asset": source_record.get("asset_name") if source_record else None,
            "source_repo": source_record.get("source") if source_record else None,
            "archive_entries": count,
            "unpacked_bytes": unpacked,
            "files": manifest_files,
            "publisher_authenticity": "UNVERIFIED",
            "game_compatibility": "UNVERIFIED",
            "installed_to_game": False,
            "trainer_verified": False,
            "apply_supported": False,
            "requires_game_prefix": False,
        }
        with (work / "manifest.json").open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if target.exists() or target.is_symlink():
            raise StageRefused("Staging destination appeared before commit")
        os.rename(work, target)
        if progress:
            progress("STAGED", unpacked, unpacked)
        return result
    finally:
        if work.exists() and not work.is_symlink():
            shutil.rmtree(work)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--single-cached", action="store_true",
                        help="Use only if exactly one managed downloaded ZIP exists")
    parser.add_argument("--cache-root", type=Path,
                        default=Path(os.environ.get("XDG_CACHE_HOME") or
                                     str(Path.home() / ".cache")) /
                        "gameweld/prepared-wemod")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--approve-stage", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)

    def on_progress(stage: str, current: int, total: int) -> None:
        print(f"PROGRESS\t{stage}\t{current}\t{total}", flush=True)
    try:
        if args.single_cached and args.archive is not None:
            raise StageRefused("Specify one source: --archive or --single-cached")
        if args.single_cached:
            downloads = args.cache_root / "downloads"
            if not downloads.is_dir() or downloads.is_symlink():
                raise StageRefused("No managed prepared ZIP has been downloaded")
            archives = list(downloads.glob("*.zip"))
            if len(archives) != 1:
                raise StageRefused("Exactly one cached ZIP is required for automatic staging")
            archive_file = archives[0]
        else:
            if args.archive is None:
                raise StageRefused("Select an archive or use --single-cached")
            archive_file = args.archive
        result = stage_cached_archive(
            archive_file, cache_root=args.cache_root,
            approved=args.approve_stage, expected_sha256=args.expected_sha256,
            progress=on_progress if args.progress else None
        )
    except (StageRefused, OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Prepared prefix staging: BLOCKED — {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
