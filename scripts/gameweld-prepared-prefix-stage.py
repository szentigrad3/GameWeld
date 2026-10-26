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




def select_cached_release(cache_root: Path, release_url: str) -> Path:
    """Select only the archive matching the explicitly chosen release asset.

    Download metadata is advisory. stage_cached_archive rehashes the bytes
    against the content-addressed filename and audits every ZIP member.
    """
    import importlib.util
    script = Path(__file__).resolve().with_name(
        "gameweld-prepared-prefix-cache.py")
    if script.is_symlink() or not script.is_file():
        raise StageRefused("GameWeld prepared cache validator is unavailable")
    spec = importlib.util.spec_from_file_location(
        "gameweld_prepared_cache_selection", script)
    if spec is None or spec.loader is None:
        raise StageRefused("Cannot load GameWeld release validator")
    cache_validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cache_validator)
    try:
        tag, asset = cache_validator.validate_release_url(release_url)
    except (ValueError, OSError) as exc:
        raise StageRefused("Invalid selected DeckCheatz release") from exc
    downloads = cache_root / "downloads"
    if downloads.is_symlink() or not downloads.is_dir():
        raise StageRefused(
            "Selected prepared release has not been downloaded. "
            "Use Step 1 — Download selected prepared setup first.")
    records = list(downloads.glob("*.source.json"))
    if len(records) > 256:
        raise StageRefused("Too many cached release records to select safely")
    matches = []
    for record in records:
        if record.is_symlink() or not record.is_file() or record.stat().st_size > 4096:
            raise StageRefused("Unsafe cached release metadata; inspect cache manually")
        try:
            info = json.loads(record.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise StageRefused("Unreadable cached release metadata") from exc
        if not isinstance(info, dict):
            raise StageRefused("Invalid cached release metadata")
        digest = record.name.removesuffix(".source.json")
        if (len(digest) != 64 or
                any(char not in "0123456789abcdef" for char in digest) or
                info.get("sha256") != digest or
                info.get("source") != "DeckCheatz/BuiltPrefixes-dev"):
            raise StageRefused("Cached release record has inconsistent provenance")
        if info.get("release_tag") == tag and info.get("asset_name") == asset:
            archive = downloads / (digest + ".zip")
            if (archive.is_symlink() or not archive.is_file() or
                    archive.stat().st_size != info.get("bytes")):
                raise StageRefused("Selected ZIP is missing or changed; re-download")
            matches.append(archive)
    if not matches:
        raise StageRefused(
            "Selected prepared release is not downloaded. "
            "Use Step 1 — Download selected prepared setup, then stage it.")
    if len(matches) != 1:
        raise StageRefused(
            "Multiple cached copies of the selected release are present; "
            "refusing to choose one automatically")
    return matches[0]


def select_single_cached_zip(cache_root: Path) -> Path:
    """Distinguish a missing download from multiple cached releases.

    Only names are considered here; stage_cached_archive performs the strict
    symlink, content hash and ZIP structure checks before extraction.
    """
    downloads = cache_root / "downloads"
    if not downloads.is_dir() or downloads.is_symlink():
        raise StageRefused(
            "No prepared ZIP downloaded yet. Step 1: choose a release and click "
            "'Download selected prepared setup (cache only)'."
        )
    archives = list(downloads.glob("*.zip"))
    if not archives:
        raise StageRefused(
            "No prepared ZIP downloaded yet. Step 1: choose a release and click "
            "'Download selected prepared setup (cache only)'."
        )
    if len(archives) > 1:
        raise StageRefused(
            "Multiple prepared ZIPs are cached; automatic staging cannot choose safely. "
            "Select one explicitly with --archive, or move unused ZIPs out of "
            "GameWeld's cache after reviewing them."
        )
    return archives[0]



def cache_status(cache_root: Path) -> str:
    """Summarize cached ZIPs and sidecar matches without URLs or local paths.

    This never downloads, hashes a huge ZIP, stages, or reads any game data.
    Exact byte SHA-256 and CRC validation still happens during staging.
    """
    root = safe_root(cache_root)
    downloads = root / "downloads"
    lines = [
        "GAMEWELD PREPARED .NET CACHE — READ-ONLY DIAGNOSTIC",
        "No archive downloaded, staged or installed by this command.",
    ]
    if not downloads.is_dir() or downloads.is_symlink():
        return "\n".join(lines + [
            "Status: NO CACHE DOWNLOAD FOLDER",
            "If Step 1 reported success, check it and Step 2 were launched "
            "with the same XDG_CACHE_HOME."
        ])
    archives = list(downloads.glob("*.zip"))
    records = list(downloads.glob("*.source.json"))
    lines.append(f"ZIP archives found: {len(archives)}")
    lines.append(f"Source metadata records found: {len(records)}")
    if len(archives) > 256 or len(records) > 256:
        raise StageRefused("Too many cached objects to diagnose safely")
    covered = set()
    broken = 0
    for record in sorted(records):
        if record.is_symlink() or not record.is_file() or record.stat().st_size > 4096:
            broken += 1
            continue
        try:
            info = json.loads(record.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError):
            broken += 1
            continue
        digest = record.name.removesuffix(".source.json")
        if not isinstance(info, dict) or not HEX64.fullmatch(digest) or info.get("sha256") != digest:
            broken += 1
            continue
        archive = downloads / (digest + ".zip")
        covered.add(archive.name)
        good_file = (archive.is_file() and not archive.is_symlink() and
                     type(info.get("bytes")) is int and
                     archive.stat().st_size == info["bytes"])
        tag, asset = info.get("release_tag"), info.get("asset_name")
        valid_name = lambda name: (
            isinstance(name, str) and 0 < len(name) <= 128 and
            all(ch.isascii() and (ch.isalnum() or ch in "._+-") for ch in name)
        )
        if not valid_name(tag) or not valid_name(asset):
            broken += 1
            continue
        lines.append(f"Cached release: {tag} / {asset} — " +
                     ("ZIP FOUND + SIZE MATCH" if good_file
                      else "ZIP MISSING OR SIZE MISMATCH"))
    if broken:
        lines.append(f"Invalid or unreadable metadata records: {broken}")
    orphan = sum(1 for a in archives if a.name not in covered)
    if orphan:
        lines.append(f"ZIP(s) without matching metadata records: {orphan}")
    if not archives:
        lines.append("Status: NO FINISHED ZIP. A selected catalog entry is not a download.")
    elif not records or orphan:
        lines.append("Status: At least one ZIP lacks source identification. "
                     "Do not download again yet; keep the existing archive for inspection.")
    else:
        lines.append("Status: Cache entries listed above. Compare the release name "
                     "with your selected dropdown; staging verifies full hashes/CRC.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--single-cached", action="store_true",
                        help="Use only if exactly one managed downloaded ZIP exists")
    parser.add_argument("--release-asset-url",
                        help="Select exact downloaded DeckCheatz release from GUI")
    parser.add_argument("--cache-root", type=Path,
                        default=Path(os.environ.get("XDG_CACHE_HOME") or
                                     str(Path.home() / ".cache")) /
                        "gameweld/prepared-wemod")
    parser.add_argument("--cache-status", action="store_true",
                        help="Show safe read-only ZIP/source metadata summary")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--approve-stage", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)

    def on_progress(stage: str, current: int, total: int) -> None:
        print(f"PROGRESS\t{stage}\t{current}\t{total}", flush=True)
    try:
        if args.cache_status:
            if (args.archive is not None or args.single_cached or
                    args.release_asset_url is not None or args.approve_stage):
                raise StageRefused("Cache status cannot be combined with staging actions")
            print(cache_status(args.cache_root))
            return 0
        if sum((args.archive is not None, args.single_cached,
                args.release_asset_url is not None)) != 1:
            raise StageRefused(
                "Select exactly one archive source, cached ZIP, or release")
        if args.release_asset_url is not None:
            archive_file = select_cached_release(
                args.cache_root, args.release_asset_url)
        elif args.single_cached:
            archive_file = select_single_cached_zip(args.cache_root)
        else:
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
