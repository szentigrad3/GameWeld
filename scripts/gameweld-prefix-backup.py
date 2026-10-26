#!/usr/bin/env python3
"""Independent, opt-in game-prefix backup for the developing WeMod installer.

Default preview never writes. Explicit snapshots are stored OUTSIDE the game
and OUTSIDE the disposable prepared-prefix cache. This tool never restores,
installs, launches Wine, configures a provider, or modifies game-prefix files.
A user game-closed acknowledgement is NOT proof a runtime is idle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import tempfile
import uuid

STEAM_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
OTHER_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
PROVIDERS = ("steam", "heroic", "lutris")
MAX_FILES = 150000
MAX_TOTAL_BYTES = 40 * 1024 ** 3
SPACE_RESERVE = 512 * 1024 ** 2
CHUNK = 1024 * 1024


class BackupRefused(ValueError):
    pass


def private_backup_root(root: Path) -> Path:
    if (not root.is_absolute() or root.name != "prefix-backups" or
            root.parent.name != "gameweld"):
        raise BackupRefused("Backups require an absolute gameweld/prefix-backups path")
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise BackupRefused("Symlinked backup path is forbidden")
    if root.exists():
        if not root.is_dir():
            raise BackupRefused("Backup root is not a directory")
        if stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise BackupRefused("Backup root must be private (0700)")
    return root


def selected_prefix(prefix: Path, backups: Path) -> Path:
    if not prefix.is_absolute() or not prefix.is_dir() or prefix.is_symlink():
        raise BackupRefused("Select an existing absolute, non-symlinked prefix directory")
    if any(part.is_symlink() for part in (prefix, *prefix.parents)):
        raise BackupRefused("Symlinked game-prefix ancestry is forbidden")
    if prefix == Path("/") or prefix == Path.home():
        raise BackupRefused("Cannot back up the filesystem or entire home directory")
    if backups == prefix or prefix in backups.parents or backups in prefix.parents:
        raise BackupRefused("Backup destination and game prefix must not overlap")
    return prefix


def validate_game(provider: str, game_id: str) -> None:
    if provider not in PROVIDERS:
        raise BackupRefused("Unsupported game provider")
    pattern = STEAM_ID if provider == "steam" else OTHER_ID
    if not game_id or not pattern.fullmatch(game_id):
        raise BackupRefused("Unambiguous provider-specific game ID required")


def inventory(prefix: Path) -> tuple[list[dict], int]:
    """lstat-only traversal; never follows symlinks or reads file contents."""
    items: list[dict] = []
    total = 0
    def walk_error(exc):
        raise BackupRefused("Cannot inventory prefix") from exc

    for base, dirs, files in os.walk(prefix, topdown=True, followlinks=False,
                                      onerror=walk_error):
        directory = Path(base)
        for name in list(dirs) + files:
            child = directory / name
            info = child.lstat()
            relative = child.relative_to(prefix).as_posix()
            if stat.S_ISDIR(info.st_mode):
                kind = "directory"
            elif stat.S_ISLNK(info.st_mode):
                kind = "symlink"
                if name in dirs:
                    dirs.remove(name)
            elif stat.S_ISREG(info.st_mode):
                kind = "file"
                total += info.st_size
            else:
                raise BackupRefused("Special files in prefix are not supported")
            items.append({
                "path": relative,
                "kind": kind,
                "size": info.st_size if kind == "file" else 0,
                "device": info.st_dev,
                "inode": info.st_ino,
                "mtime_ns": info.st_mtime_ns,
            })
            if len(items) > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise BackupRefused("Prefix exceeds safe backup limits")
    items.sort(key=lambda i: i["path"])
    return items, total


def preview_backup(provider: str, game_id: str, prefix: Path,
                   backup_root: Path) -> dict:
    validate_game(provider, game_id)
    root = private_backup_root(backup_root)
    source = selected_prefix(prefix, root)
    items, total = inventory(source)
    return {
        "provider": provider,
        "game_id": game_id,
        "prefix": str(source),
        "entries": len(items),
        "regular_files": sum(item["kind"] == "file" for item in items),
        "symlinks": sum(item["kind"] == "symlink" for item in items),
        "total_file_bytes": total,
        "backup_location": str(root),
        "status": "PREVIEW ONLY — no files read, copied or changed",
        "game_prefix_mutated": False,
        "backup_created": False,
        "runtime_idle_verified": False,
        "ready_to_install": False,
    }


class DigestReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, n=-1):
        data = self.source.read(n)
        self.digest.update(data)
        self.bytes += len(data)
        return data


def create_backup(
    provider: str,
    game_id: str,
    prefix: Path,
    *,
    backup_root: Path,
    approved: bool,
    acknowledged_game_closed: bool,
) -> dict:
    """Archive an independent snapshot, preserving symlinks without following."""
    if not approved or not acknowledged_game_closed:
        raise BackupRefused("Explicit --approve-backup and --acknowledge-game-closed required")
    info = preview_backup(provider, game_id, prefix, backup_root)
    root = private_backup_root(backup_root)
    source = selected_prefix(prefix, root)
    items, total = inventory(source)
    filesystem = next((p for p in (root, *root.parents) if p.exists()), None)
    if filesystem is None:
        raise BackupRefused("No accessible backup filesystem")
    if shutil.disk_usage(filesystem).free < total + SPACE_RESERVE:
        raise BackupRefused("Insufficient independent backup disk space")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_backup_root(root)
    temp = Path(tempfile.mkdtemp(prefix=".incoming-", dir=root))
    target = root / (provider + "-" + game_id.replace(":", "_") + "-" +
                     uuid.uuid4().hex)
    try:
        # Open regular files O_NOFOLLOW and validate their identity before/after.
        # This only detects some concurrent changes; it is NOT an atomic
        # filesystem snapshot and cannot prove the game has stopped.
        manifest_files = []
        output_tar = temp / "prefix.tar"
        fd = os.open(output_tar, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as binary, tarfile.open(
            fileobj=binary, mode="w", format=tarfile.PAX_FORMAT
        ) as archive:
            for item in items:
                relative = item["path"]
                path = source.joinpath(*relative.split("/"))
                existing = path.lstat()
                if (existing.st_dev != item["device"] or
                        existing.st_ino != item["inode"] or
                        existing.st_mtime_ns != item["mtime_ns"] or
                        (item["kind"] == "file" and existing.st_size != item["size"])):
                    raise BackupRefused("Game prefix changed during snapshot")
                tarinfo = archive.gettarinfo(str(path), arcname="prefix/" + relative)
                tarinfo.uid = tarinfo.gid = 0
                tarinfo.uname = tarinfo.gname = ""
                if item["kind"] == "directory":
                    if not tarinfo.isdir():
                        raise BackupRefused("Directory changed during snapshot")
                    archive.addfile(tarinfo)
                elif item["kind"] == "symlink":
                    if not tarinfo.issym():
                        raise BackupRefused("Symlink changed during snapshot")
                    archive.addfile(tarinfo)
                else:
                    if not tarinfo.isfile():
                        raise BackupRefused("Game file changed during snapshot")
                    read_fd = os.open(path, os.O_RDONLY |
                                      getattr(os, "O_NOFOLLOW", 0))
                    with os.fdopen(read_fd, "rb") as stream:
                        before = os.fstat(stream.fileno())
                        if (before.st_dev != item["device"] or
                                before.st_ino != item["inode"] or
                                before.st_size != item["size"] or
                                before.st_mtime_ns != item["mtime_ns"]):
                            raise BackupRefused("File changed before backup read")
                        reader = DigestReader(stream)
                        archive.addfile(tarinfo, reader)
                        after = os.fstat(stream.fileno())
                        if (reader.bytes != item["size"] or
                                after.st_size != before.st_size or
                                after.st_mtime_ns != before.st_mtime_ns):
                            raise BackupRefused("File changed during backup read")
                    manifest_files.append({
                        "path": relative, "size": item["size"],
                        "sha256": reader.digest.hexdigest()
                    })
        # Re-inventory detects changed/deleted/added paths during the copy.
        final_items, _ = inventory(source)
        if final_items != items:
            raise BackupRefused("Game prefix inventory changed during backup")
        with tarfile.open(output_tar, "r") as archive:
            content = archive.getmembers()
            if len(content) != len(items):
                raise BackupRefused("Backup archive inventory mismatch")
        digest = hashlib.sha256()
        with output_tar.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
        manifest = {
            **info,
            "archive_sha256": digest.hexdigest(),
            "archive_bytes": output_tar.stat().st_size,
            "file_hashes": manifest_files,
            "status": "INDEPENDENT BACKUP SAVED — restore NOT implemented",
            "backup_created": True,
            "runtime_idle_verified": False,
            "ready_to_install": False,
            "game_prefix_mutated": False,
            "restoration_available": False,
            "game_closed_acknowledged_by_user": True,
            "note": "Backup may not be atomic; future install remains blocked."
        }
        # Save sensitive paths only inside the owner's private backup folder.
        with (temp / "manifest.json").open("x", encoding="utf-8") as destination:
            json.dump(manifest, destination, indent=2, sort_keys=True)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        if target.exists() or target.is_symlink():
            raise BackupRefused("Backup destination collision")
        os.rename(temp, target)
        return {
            "backup_path": str(target),
            "archive_sha256": manifest["archive_sha256"],
            "files": info["regular_files"],
            "total_file_bytes": total,
            "game_prefix_mutated": False,
            "runtime_idle_verified": False,
            "restoration_available": False,
            "ready_to_install": False,
            "status": manifest["status"],
        }
    finally:
        if temp.exists() and not temp.is_symlink():
            shutil.rmtree(temp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--prefix", required=True, type=Path)
    default_state = Path(os.environ.get("XDG_STATE_HOME") or
                         str(Path.home() / ".local/state"))
    parser.add_argument("--backup-root", type=Path,
                        default=default_state / "gameweld/prefix-backups")
    parser.add_argument("--approve-backup", action="store_true")
    parser.add_argument("--acknowledge-game-closed", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.approve_backup:
            result = create_backup(
                args.provider, args.game_id, args.prefix,
                backup_root=args.backup_root, approved=True,
                acknowledged_game_closed=args.acknowledge_game_closed,
            )
        else:
            result = preview_backup(args.provider, args.game_id,
                                    args.prefix, args.backup_root)
    except (BackupRefused, OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(2, f"GameWeld backup: BLOCKED — {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
