#!/usr/bin/env python3
"""Offline integrity probe for one quarantined prepared WeMod ZIP.

Read-only and intentionally separate from both the downloader and the stager.
A PASS does not approve case-colliding names, authenticity or game compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import zipfile

CHUNK = 1024 * 1024
HEX = set("0123456789abcdef")
SOURCE = "DeckCheatz/BuiltPrefixes-dev"


class IntegrityRefused(ValueError):
    pass


def _audit():
    p = Path(__file__).resolve().with_name("gameweld-prepared-prefix-audit.py")
    if p.is_symlink() or not p.is_file():
        raise IntegrityRefused("Shared ZIP metadata inspector unavailable")
    spec = importlib.util.spec_from_file_location("prepared_zip_integrity_audit", p)
    if spec is None or spec.loader is None:
        raise IntegrityRefused("Shared ZIP metadata inspector could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integrity_report(cache_root: Path) -> str:
    root = Path(cache_root)
    if (not root.is_absolute() or root.name != "prepared-wemod" or
            root.parent.name != "gameweld" or
            any(part.casefold() in {"steamapps", "compatdata", "pfx"}
                for part in root.parts) or
            any(part.is_symlink() for part in (root, *root.parents)) or
            not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077):
        raise IntegrityRefused("Private GameWeld cache root is missing or unsafe")
    rejected = root / "rejected"
    if (rejected.is_symlink() or not rejected.is_dir() or
            stat.S_IMODE(rejected.stat().st_mode) & 0o077):
        raise IntegrityRefused("Private rejected ZIP directory is missing or unsafe")
    archives = list(rejected.glob("*.zip"))
    if len(archives) != 1:
        raise IntegrityRefused("Expected exactly one quarantined ZIP (no automatic choice)")
    archive_path = archives[0]
    sha = archive_path.stem
    if len(sha) != 64 or any(c not in HEX for c in sha):
        raise IntegrityRefused("Rejected ZIP name is not a SHA-256 identifier")
    receipt = rejected / (sha + ".rejected.json")
    if (receipt.is_symlink() or not receipt.is_file() or
            receipt.stat().st_size > 4096):
        raise IntegrityRefused("Matching rejected ZIP receipt is missing or unsafe")
    try:
        meta = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise IntegrityRefused("Rejected ZIP receipt unreadable") from exc
    if (not isinstance(meta, dict) or meta.get("sha256") != sha or
            meta.get("source") != SOURCE or
            meta.get("status") != "REJECTED_NOT_STAGEABLE" or
            type(meta.get("bytes")) is not int):
        raise IntegrityRefused("Rejected ZIP receipt does not match archive identity")

    audit = _audit()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(archive_path, flags)
    try:
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or
                    before.st_size != meta["bytes"] or
                    not 0 < before.st_size <= audit.MAX_ARCHIVE_BYTES):
                raise IntegrityRefused("ZIP size or type differs from receipt")
            identity = (before.st_dev, before.st_ino, before.st_size,
                        before.st_mtime_ns, before.st_ctime_ns)
            digest = hashlib.sha256()
            for piece in iter(lambda: stream.read(CHUNK), b""):
                digest.update(piece)
            if digest.hexdigest() != sha:
                raise IntegrityRefused("SHA-256 does not match the local ZIP and receipt")

            stream.seek(0)
            entries_verified = 0
            uncompressed_read = 0
            try:
                with zipfile.ZipFile(stream) as archive:
                    counts, _ = audit.classify_zip_collisions(archive)
                    count, unpacked_limit = (
                        audit.check_other_zip_safety_without_approving_collisions(archive))
                    for entry in archive.infolist():
                        size = 0
                        with archive.open(entry, "r") as member:
                            while True:
                                buf = member.read(CHUNK)
                                if not buf:
                                    break
                                size += len(buf)
                                uncompressed_read += len(buf)
                                if (size > entry.file_size or
                                        uncompressed_read > unpacked_limit):
                                    raise IntegrityRefused("ZIP expanded beyond metadata limits")
                        if size != entry.file_size:
                            raise IntegrityRefused("ZIP member decompressed size mismatch")
                        # Python's ZipExtFile checks each member's CRC at EOF.
                        entries_verified += 1
            except (audit.UnsafePreparedPrefix, zipfile.BadZipFile,
                    zipfile.LargeZipFile, RuntimeError, EOFError,
                    NotImplementedError) as exc:
                raise IntegrityRefused(
                    "ZIP noncollision metadata, decompression or CRC verification FAILED"
                ) from exc
            if entries_verified != count or uncompressed_read != unpacked_limit:
                raise IntegrityRefused("ZIP entry inventory changed during inspection")
            after = os.fstat(stream.fileno())
            if (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns) != identity:
                raise IntegrityRefused("ZIP changed while being read")
    finally:
        if fd >= 0:
            os.close(fd)

    return "\n".join([
        "GAMEWELD — REJECTED ZIP CONTENT INTEGRITY (READ ONLY)",
        "Archive SHA-256 filename prefix: " + sha[:12],
        "Local ZIP SHA-256: MATCHES filename and private rejected receipt",
        "Other ZIP metadata safety rules: PASS (case collisions EXCLUDED)",
        f"ZIP CRC-32: PASS ({entries_verified} members; {uncompressed_read} decompressed bytes)",
        f"Case-colliding member names: {counts['case_collision']} — STILL BLOCKED",
        "Publisher authenticity and Windows/Proton runtime compatibility: UNVERIFIED",
        "Cache promotion, staging, extraction to disk and installation: NOT AUTHORIZED",
        "No network request, archive mutation or existing game-prefix changes.",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    cache = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache"))
    parser.add_argument("--cache-root", type=Path,
                        default=cache / "gameweld/prepared-wemod")
    args = parser.parse_args()
    try:
        print(integrity_report(args.cache_root))
    except (IntegrityRefused, OSError, ValueError) as exc:
        parser.exit(2, f"Rejected ZIP integrity: BLOCKED — {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
