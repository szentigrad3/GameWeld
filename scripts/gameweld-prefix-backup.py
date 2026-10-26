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



def verify_backup(backup_dir: Path, *, backup_root: Path) -> dict:
    """Read-only TAR + manifest integrity verification; NEVER restore files."""
    root = private_backup_root(backup_root)
    saved = Path(backup_dir)
    if (not saved.is_absolute() or saved.parent != root or
            saved.is_symlink() or not saved.is_dir()):
        raise BackupRefused("Select one existing GameWeld-managed private backup directory")
    if stat.S_IMODE(saved.stat().st_mode) & 0o077:
        raise BackupRefused("Backup directory is not private")
    archive_path = saved / "prefix.tar"
    manifest_path = saved / "manifest.json"
    for path in (archive_path, manifest_path):
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise BackupRefused("Backup archive or manifest is missing or symlinked")
    if manifest_path.stat().st_size > 64 * 1024 * 1024:
        raise BackupRefused("Backup manifest exceeds safe size")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackupRefused("Backup manifest is invalid") from exc
    sha = hashlib.sha256()
    with archive_path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            sha.update(block)
    if (sha.hexdigest() != manifest.get("archive_sha256") or
            archive_path.stat().st_size != manifest.get("archive_bytes")):
        raise BackupRefused("Backup TAR does not match its saved checksum/size")
    hashes = manifest.get("file_hashes")
    if (not isinstance(hashes, list) or len(hashes) > MAX_FILES or
            not isinstance(manifest.get("entries"), int) or
            manifest["entries"] > MAX_FILES):
        raise BackupRefused("Backup manifest file list is invalid")
    expected = {}
    for value in hashes:
        if not isinstance(value, dict):
            raise BackupRefused("Invalid manifest file entry")
        relative, size, digest = value.get("path"), value.get("size"), value.get("sha256")
        if (not isinstance(relative, str) or not relative or relative.startswith("/") or
                any(part in ("", ".", "..") for part in relative.split("/")) or
                relative in expected or not isinstance(size, int) or size < 0 or
                not isinstance(digest, str) or
                not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise BackupRefused("Unsafe or conflicting backup file manifest entry")
        expected[relative] = (size, digest)
    seen = set()
    verified_bytes = 0
    symlinks = 0
    files = 0
    with tarfile.open(archive_path, "r") as snapshot:
        members = snapshot.getmembers()
        if len(members) != manifest["entries"]:
            raise BackupRefused("Backup TAR member count differs from the manifest")
        for member in members:
            name = member.name
            if not name.startswith("prefix/"):
                raise BackupRefused("Backup TAR contains a non-prefix member")
            relative = name[len("prefix/"):]
            parts = relative.split("/")
            if (not relative or relative.startswith("/") or
                    any(part in ("", ".", "..") for part in parts) or
                    relative in seen):
                raise BackupRefused("Backup TAR has invalid or duplicate member paths")
            seen.add(relative)
            if member.isfile():
                check = expected.get(relative)
                if check is None or member.size != check[0]:
                    raise BackupRefused("Backup file missing from manifest or wrong size")
                extracted = snapshot.extractfile(member)
                if extracted is None:
                    raise BackupRefused("Cannot read backed-up file")
                digest = hashlib.sha256()
                length = 0
                with extracted:
                    for block in iter(lambda: extracted.read(CHUNK), b""):
                        length += len(block)
                        if length > member.size:
                            raise BackupRefused("Backup member exceeds declared size")
                        digest.update(block)
                if length != check[0] or digest.hexdigest() != check[1]:
                    raise BackupRefused("Backed-up file failed its SHA-256 check")
                files += 1
                verified_bytes += length
            elif member.issym():
                symlinks += 1
            elif not member.isdir():
                raise BackupRefused("Backup TAR contains unsupported member type")
    if (files != len(expected) or files != manifest.get("regular_files") or
            symlinks != manifest.get("symlinks") or
            verified_bytes != manifest.get("total_file_bytes")):
        raise BackupRefused("Backup manifest inventory differs from TAR contents")
    return {
        "backup_path": str(saved),
        "status": "BACKUP READABLE AND CHECKSUMS VERIFIED — restoration unavailable",
        "verified_files": files,
        "verified_bytes": verified_bytes,
        "symlinks_not_followed": symlinks,
        "game_prefix_mutated": False,
        "runtime_idle_verified": False,
        "restoration_available": False,
        "ready_to_install": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--game-id")
    parser.add_argument("--prefix", type=Path)
    parser.add_argument("--verify-backup-dir", type=Path,
                        help="Read-only archive and SHA-256 verification; no restore")
    default_state = Path(os.environ.get("XDG_STATE_HOME") or
                         str(Path.home() / ".local/state"))
    parser.add_argument("--backup-root", type=Path,
                        default=default_state / "gameweld/prefix-backups")
    parser.add_argument("--approve-backup", action="store_true")
    parser.add_argument("--acknowledge-game-closed", action="store_true")
    args = parser.parse_args(argv)
    if not args.verify_backup_dir and (
            not args.provider or not args.game_id or args.prefix is None):
        parser.error("--provider, --game-id, and --prefix are required for preview/backup")
    try:
        if args.verify_backup_dir is not None:
            if args.approve_backup or args.acknowledge_game_closed:
                raise BackupRefused("Verification must not request backup creation")
            result = verify_backup(args.verify_backup_dir, backup_root=args.backup_root)
        elif args.approve_backup:
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
