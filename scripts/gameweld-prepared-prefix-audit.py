#!/usr/bin/env python3
"""GameWeld shared prepared-WeMod archive preflight (offline/read-only).

Works for all game providers: the archive is inspected as a candidate *managed
WeMod environment*, never as a replacement for the selected game's prefix.
No network, execution, extraction, Steam writes, or game-prefix operations.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
import zipfile

MAX_ARCHIVE_BYTES = 3 * 1024 ** 3
MAX_ENTRIES = 40000
MAX_UNPACKED_BYTES = 12 * 1024 ** 3
MAX_MEMBER_BYTES = 2 * 1024 ** 3
MAX_RATIO = 600
MAX_PATH_LENGTH = 512
RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.I)
HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")


class UnsafePreparedPrefix(ValueError):
    pass


def inspect_zip_members(archive: zipfile.ZipFile) -> tuple[int, int]:
    members = archive.infolist()
    if not members or len(members) > MAX_ENTRIES:
        raise UnsafePreparedPrefix("Empty archive or too many entries")
    seen: set[str] = set()
    decompressed = 0
    compressed = 0
    for info in members:
        name = info.filename
        if (not name or len(name) > MAX_PATH_LENGTH or
                name.startswith("/") or "\\" in name or
                "\x00" in name or re.match(r"^[A-Za-z]:", name)):
            raise UnsafePreparedPrefix("Absolute, Windows or invalid archive path")
        parts = PurePosixPath(name).parts
        if (not parts or any(part in (".", "..", "") for part in name.rstrip("/").split("/"))
                or any(":" in part or part.endswith((" ", ".")) or RESERVED.fullmatch(part)
                       for part in parts)):
            raise UnsafePreparedPrefix("Path traversal, Windows reserved or invalid member")
        normalized = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
        if normalized in seen:
            raise UnsafePreparedPrefix("Duplicate/case-colliding archive entries")
        seen.add(normalized)
        if info.flag_bits & 1:
            raise UnsafePreparedPrefix("Encrypted archive entry")
        mode = (info.external_attr >> 16) & 0o170000
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise UnsafePreparedPrefix("Links or special files are forbidden")
        if info.is_dir() != (mode == stat.S_IFDIR) and mode not in (0,):
            raise UnsafePreparedPrefix("Directory/file type mismatch")
        if info.file_size < 0 or info.compress_size < 0:
            raise UnsafePreparedPrefix("Invalid negative ZIP sizes")
        if info.file_size > MAX_MEMBER_BYTES:
            raise UnsafePreparedPrefix("Individual member is too large")
        if info.file_size > 0 and info.compress_size == 0:
            raise UnsafePreparedPrefix("Unbounded ZIP expansion")
        if info.file_size > MAX_RATIO * max(1, info.compress_size):
            raise UnsafePreparedPrefix("Excessive member compression ratio")
        decompressed += info.file_size
        compressed += info.compress_size
        if decompressed > MAX_UNPACKED_BYTES:
            raise UnsafePreparedPrefix("Total unpacked archive size exceeds limit")
    if decompressed > MAX_RATIO * max(1, compressed):
        raise UnsafePreparedPrefix("Excessive aggregate compression ratio")
    return len(members), decompressed



def classify_zip_collisions(archive: zipfile.ZipFile) -> tuple[dict[str, int], list[str]]:
    """Classify filename conflicts without reading, executing or extracting members.

    Examples are escaped and capped so untrusted ZIP filenames cannot inject
    terminal control characters or flood the diagnostic display.
    """
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise UnsafePreparedPrefix("Too many entries for collision inspection")
    seen: dict[str, tuple[str, bool]] = {}
    counts = {"exact_duplicate": 0, "case_collision": 0,
              "unicode_collision": 0, "file_directory_conflict": 0}
    examples: list[str] = []
    for info in entries:
        current = info.filename.rstrip("/")
        key = unicodedata.normalize("NFC", current).casefold()
        if key not in seen:
            seen[key] = (current, info.is_dir())
            continue
        previous, previous_dir = seen[key]
        if previous_dir != info.is_dir():
            reason = "file_directory_conflict"
        elif previous == current:
            reason = "exact_duplicate"
        elif unicodedata.normalize("NFC", previous) == unicodedata.normalize("NFC", current):
            reason = "unicode_collision"
        else:
            reason = "case_collision"
        counts[reason] += 1
        if len(examples) < 5:
            # A filename is untrusted input, not a command or formatted path.
            examples.append(f"{reason}: {ascii(previous)[:160]} vs {ascii(current)[:160]}")
    return counts, examples



def compare_case_collision_bytes(archive: zipfile.ZipFile) -> dict[str, int]:
    """Bounded read-only comparison of ZIP members with case-only name collisions.

    A matching hash here proves ONLY that two ZIP member payloads match.
    It never establishes publisher authenticity, compatibility, or permission
    to stage/merge files. No members are extracted or written to disk.
    """
    limit_per_member = 32 * 1024 * 1024
    limit_total_read = 256 * 1024 * 1024
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise UnsafePreparedPrefix("Too many ZIP entries to compare safely")
    first: dict[str, zipfile.ZipInfo] = {}
    result = {
        "identical_payload": 0, "different_payload": 0,
        "size_mismatch": 0, "comparison_skipped": 0,
    }
    used_bytes = 0

    def digest(info: zipfile.ZipInfo) -> str:
        nonlocal used_bytes
        h = hashlib.sha256()
        size = 0
        with archive.open(info, "r") as stream:
            while True:
                data = stream.read(min(1024 * 1024, info.file_size - size + 1))
                if not data:
                    break
                size += len(data)
                used_bytes += len(data)
                if size > info.file_size or used_bytes > limit_total_read:
                    raise UnsafePreparedPrefix("Collision comparison exceeded size limit")
                h.update(data)
        if size != info.file_size:
            raise UnsafePreparedPrefix("Collision member length mismatch")
        return h.hexdigest()

    for item in entries:
        key = unicodedata.normalize("NFC", item.filename.rstrip("/")).casefold()
        previous = first.get(key)
        if previous is None:
            first[key] = item
            continue
        if item.filename.rstrip("/") == previous.filename.rstrip("/"):
            continue
        if (item.is_dir() or previous.is_dir() or
                ((item.external_attr >> 16) & 0o170000) not in (0, stat.S_IFREG) or
                ((previous.external_attr >> 16) & 0o170000) not in (0, stat.S_IFREG) or
                item.flag_bits & 1 or previous.flag_bits & 1):
            result["comparison_skipped"] += 1
            continue
        if item.file_size != previous.file_size:
            result["size_mismatch"] += 1
            continue
        if (item.file_size > limit_per_member or
                previous.file_size > limit_per_member or
                used_bytes + item.file_size + previous.file_size > limit_total_read):
            result["comparison_skipped"] += 1
            continue
        # CRCs alone are insufficient: compare independent SHA-256 hashes.
        try:
            matching = digest(previous) == digest(item)
        except (OSError, RuntimeError, EOFError, zipfile.BadZipFile, UnsafePreparedPrefix):
            result["comparison_skipped"] += 1
            continue
        result["identical_payload" if matching else "different_payload"] += 1
    return result


def archive_report(path: Path, *, expected_sha256: str | None = None) -> str:
    if path.is_symlink() or not path.is_file():
        raise UnsafePreparedPrefix("Use an existing regular non-symlinked ZIP file")
    size = path.stat().st_size
    if size == 0 or size > MAX_ARCHIVE_BYTES:
        raise UnsafePreparedPrefix("Archive is empty or exceeds 3 GiB limit")
    if expected_sha256 is not None and not HEX64.fullmatch(expected_sha256):
        raise UnsafePreparedPrefix("Expected SHA-256 must be 64 hex characters")

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    computed = digest.hexdigest()
    try:
        with zipfile.ZipFile(path) as archive:
            count, uncompressed = inspect_zip_members(archive)
            bad_member = archive.testzip()  # verify CRC of every entry; read-only
            if bad_member is not None:
                raise UnsafePreparedPrefix("Archive contains an entry with a failed CRC")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise UnsafePreparedPrefix("Archive is invalid or cannot be safely read") from exc

    lines = [
        "GAMEWELD — SHARED WEMOD PREFIX ARCHIVE SAFETY AUDIT",
        "Scope: reusable prefix template cache for Steam, Heroic and Lutris; actual game launch contexts remain separate",
        "Safety: read-only; no extraction, execution, installation or prefix modifications",
        f"Archive size: {size} bytes",
        f"Archive entries: {count}",
        f"Declared uncompressed size: {uncompressed} bytes",
        "Archive structural checks: PASS (paths, links, size, ratios, encryption, CRC)",
        f"Computed SHA-256: {computed}",
    ]
    if expected_sha256 is None:
        lines.append("Publisher integrity verification: NOT AVAILABLE (no independently trusted digest)")
    elif computed.lower() == expected_sha256.lower():
        lines.append("Digest comparison: MATCHES supplied digest (publisher identity NOT verified)")
    else:
        lines.append("Digest comparison: MISMATCH — DO NOT INSTALL")
    lines += [
        "Windows registry, CLR execution and account-data safety: NOT VERIFIED",
        "Trainer compatibility depends on the game; all games are not guaranteed supported",
        "Installation status: NOT AUTHORIZED; no archive extraction or game-prefix replacement",
        "Next gate: confirm provenance, stage into a separate managed directory, "
        "preserve account data, and require user approval and rollback checks.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    try:
        print(archive_report(args.archive, expected_sha256=args.expected_sha256))
    except (UnsafePreparedPrefix, OSError) as exc:
        parser.exit(2, f"Prepared prefix archive BLOCKED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
