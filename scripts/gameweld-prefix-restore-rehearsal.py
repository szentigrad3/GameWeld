#!/usr/bin/env python3
"""Verify a GameWeld backup by restoring ONLY into an isolated rehearsal area.

This developer-only tool deliberately has no option for a destination prefix:
it never writes Steam/Heroic/Lutris files, does not provide real rollback, and
does not execute restored files or follow archived symlinks.
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
import tarfile
import tempfile
from typing import Callable

CHUNK = 1024 * 1024
RESERVE = 512 * 1024 * 1024
REHEARSAL_AREA = "restore-rehearsals"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class RehearsalRefused(ValueError):
    pass


def load_backup():
    script = Path(__file__).with_name("gameweld-prefix-backup.py")
    if not script.is_file() or script.is_symlink():
        raise RehearsalRefused("GameWeld backup verifier is missing")
    spec = importlib.util.spec_from_file_location("gameweld_backup_rehearsal", script)
    if spec is None or spec.loader is None:
        raise RehearsalRefused("Could not import backup verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_member(name: str) -> str:
    """Parse member names, never trusting tarfile.extract() path semantics."""
    if not isinstance(name, str) or not name.startswith("prefix/"):
        raise RehearsalRefused("Non-prefix backup TAR member")
    relative = name[len("prefix/"):]
    if (not relative or len(relative) > 1024 or "\x00" in relative or
            "\\" in relative or any(ord(c) < 32 for c in relative) or
            any(part in ("", ".", "..") for part in relative.split("/"))):
        raise RehearsalRefused("Invalid backup TAR member path")
    return relative


def rehearsal_restore(
    backup_dir: Path,
    *,
    backup_root: Path,
    approved: bool,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    """Make and verify a PRIVATE disposable copy; source prefix is never opened."""
    if not approved:
        raise RehearsalRefused("Explicit --approve-rehearsal is required")
    backup = load_backup()
    try:
        verified = backup.verify_backup(backup_dir, backup_root=backup_root)
        root = backup.private_backup_root(backup_root)
    except (backup.BackupRefused, OSError, tarfile.TarError, ValueError) as exc:
        raise RehearsalRefused("Backup did not pass independent verification") from exc
    saved = Path(verified["backup_path"])
    archive_path = saved / "prefix.tar"
    manifest_path = saved / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {entry["path"]: entry for entry in manifest["file_hashes"]}

    area = root / REHEARSAL_AREA
    target = area / saved.name
    if (area.is_symlink() or (area.exists() and not area.is_dir()) or
            target.is_symlink() or target.exists()):
        raise RehearsalRefused("Restore rehearsal destination already exists or is unsafe")
    if area.exists() and stat.S_IMODE(area.stat().st_mode) & 0o077:
        raise RehearsalRefused("Restore rehearsal area must be private")
    try:
        free = shutil.disk_usage(root).free
    except OSError as exc:
        raise RehearsalRefused("Cannot check free disk space") from exc
    if free < verified["verified_bytes"] + RESERVE:
        raise RehearsalRefused("Insufficient disk space for independent restore rehearsal")
    # An existing private backup root is required; never create one by surprise.
    area.mkdir(mode=0o700, exist_ok=True)
    if area.is_symlink():
        raise RehearsalRefused("Rehearsal directory was replaced by a symlink")

    work = Path(tempfile.mkdtemp(prefix=".incoming-", dir=area))
    try:
        payload = work / "payload"
        payload.mkdir(mode=0o700)
        seen: set[str] = set()
        kinds: dict[str, str] = {}
        copied = 0
        file_count = 0
        symlinks = 0
        if progress:
            progress("RESTORE_TEST", 0, verified["verified_bytes"])
        with tarfile.open(archive_path, mode="r") as snapshot:
            # Phase one: validate ALL member names/types and ancestry before writes.
            members = snapshot.getmembers()
            if len(members) != manifest["entries"]:
                raise RehearsalRefused("Backup TAR member count changed")
            for item in members:
                relative = safe_member(item.name)
                if relative in seen:
                    raise RehearsalRefused("Duplicate paths in backup TAR")
                seen.add(relative)
                if item.isdir():
                    kind = "directory"
                elif item.isfile():
                    kind = "file"
                elif item.issym():
                    kind = "symlink"
                else:
                    raise RehearsalRefused("Unsupported backup TAR object type")
                kinds[relative] = kind
            for name in seen:
                parts = name.split("/")
                for i in range(1, len(parts)):
                    ancestor = "/".join(parts[:i])
                    if kinds.get(ancestor, "directory") != "directory":
                        raise RehearsalRefused("Backup contains a non-directory parent")

            # Phase two: copy payload bytes ourselves. Never call extractall.
            for item in members:
                relative = safe_member(item.name)
                destination = payload.joinpath(*relative.split("/"))
                if item.isdir():
                    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                elif item.issym():
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    # Preserve raw Wine links as link ENTRIES, never resolve them.
                    os.symlink(item.linkname, destination)
                    symlinks += 1
                else:
                    check = expected.get(relative)
                    if check is None or item.size != check["size"]:
                        raise RehearsalRefused("Backup file missing from SHA-256 manifest")
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    source = snapshot.extractfile(item)
                    if source is None:
                        raise RehearsalRefused("Cannot read archived file")
                    digest = hashlib.sha256()
                    written = 0
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    fd = os.open(destination, flags, 0o600)
                    with source, os.fdopen(fd, "wb") as sink:
                        while True:
                            piece = source.read(CHUNK)
                            if not piece:
                                break
                            written += len(piece)
                            copied += len(piece)
                            if written > item.size or copied > verified["verified_bytes"]:
                                raise RehearsalRefused("Backup data exceeded verified limits")
                            sink.write(piece)
                            digest.update(piece)
                        sink.flush()
                        os.fsync(sink.fileno())
                    if written != check["size"] or digest.hexdigest() != check["sha256"]:
                        raise RehearsalRefused("Restored file failed its expected SHA-256")
                    file_count += 1
                    if progress:
                        progress("RESTORE_TEST", copied, verified["verified_bytes"])
        if (copied != verified["verified_bytes"] or
                file_count != verified["verified_files"] or
                symlinks != verified["symlinks_not_followed"]):
            raise RehearsalRefused("Restored counts do not match independent verification")

        # An externally replaced source TAR after validation cannot be trusted.
        digest = hashlib.sha256()
        with archive_path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
        if digest.hexdigest() != manifest["archive_sha256"]:
            raise RehearsalRefused("Backup TAR changed during restore rehearsal")
        result = {
            "restored_test_path": str(target),
            "source_backup": str(saved),
            "files_verified": file_count,
            "symlinks_preserved_without_following": symlinks,
            "bytes_verified": copied,
            "status": "REHEARSAL PASSED — TEST COPY ONLY",
            "real_game_prefix_changed": False,
            "can_restore_real_game": False,
            "transactional_apply_implemented": False,
            "game_runtime_verified_idle": False,
            "trainer_attached": False,
        }
        with (work / "rehearsal.json").open("x", encoding="utf-8") as output:
            json.dump(result, output, sort_keys=True, indent=2)
            output.write("\n")
        os.chmod(work / "rehearsal.json", 0o600)
        if target.exists() or target.is_symlink():
            raise RehearsalRefused("Rehearsal destination collision before commit")
        os.rename(work, target)
        if progress:
            progress("RESTORE_TEST_COMPLETE", copied, verified["verified_bytes"])
        return result
    finally:
        if work.exists() and not work.is_symlink():
            shutil.rmtree(work)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path, required=True)
    default_root = Path(os.environ.get("XDG_STATE_HOME") or
                        str(Path.home() / ".local/state")) / "gameweld/prefix-backups"
    parser.add_argument("--backup-root", type=Path, default=default_root)
    parser.add_argument("--approve-rehearsal", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearsal_restore(
            args.backup_dir, backup_root=args.backup_root,
            approved=args.approve_rehearsal
        )
    except (RehearsalRefused, OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(2, f"GameWeld restore rehearsal BLOCKED — {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
