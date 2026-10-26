#!/usr/bin/env python3
"""Synthetic transaction/rollback rehearsal for GameWeld (NOT a game installer).

Operates ONLY in an explicitly marked private test fixture directory:
  .../gameweld/transaction-fixtures/
Never accepts a real Steam/Heroic/Lutris prefix, prepared WeMod ZIP, or runner.
A durable journal and independent rename-preserved original allow fault tests.
Passing this rehearsal cannot enable a real game's Install or Play action.
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
import uuid

MARKER = {"kind": "gameweld-synthetic-transaction-fixture", "schema": 1}
MAX_FILES = 5000
MAX_BYTES = 256 * 1024 * 1024
CHUNK = 1024 * 1024
TXID = re.compile(r"[0-9a-f]{32}\Z")
FORBIDDEN = {"steamapps", "compatdata", "pfx", "heroic", "lutris"}


class TransactionRefused(ValueError):
    pass


def fixture_root(root: Path) -> Path:
    """Require a deliberately marked and private test-only namespace."""
    if (not root.is_absolute() or root.name != "transaction-fixtures" or
            root.parent.name != "gameweld" or not root.is_dir()):
        raise TransactionRefused("Use an existing GameWeld synthetic transaction fixture")
    if any(part.casefold() in FORBIDDEN for part in root.parts):
        raise TransactionRefused("A real game/library path cannot be a fixture")
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise TransactionRefused("Symlinked fixture ancestry is forbidden")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise TransactionRefused("Fixture root must be private (0700)")
    marker = root / ".gameweld-synthetic-fixture.json"
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 256:
        raise TransactionRefused("Synthetic fixture marker missing or unsafe")
    try:
        if json.loads(marker.read_text(encoding="utf-8")) != MARKER:
            raise TransactionRefused("This is not a valid synthetic fixture")
    except (ValueError, UnicodeError) as exc:
        raise TransactionRefused("Synthetic marker is invalid") from exc
    return root


def collect(directory: Path) -> dict[str, tuple[int, str]]:
    """Inventory regular files without following links; reject special files."""
    if directory.is_symlink() or not directory.is_dir():
        raise TransactionRefused("Missing or symlinked synthetic directory")
    entries: dict[str, tuple[int, str]] = {}
    total = 0

    def onerror(exc):
        raise TransactionRefused("Cannot traverse fixture") from exc

    for base, dirs, files in os.walk(directory, followlinks=False, onerror=onerror):
        for name in dirs + files:
            item = Path(base) / name
            meta = item.lstat()
            if stat.S_ISLNK(meta.st_mode) or not (
                stat.S_ISREG(meta.st_mode) or stat.S_ISDIR(meta.st_mode)
            ):
                raise TransactionRefused("Fixture links and special files are not supported")
            if stat.S_ISREG(meta.st_mode):
                if meta.st_nlink != 1:
                    raise TransactionRefused("Shared hard-linked fixture files are forbidden")
                rel = item.relative_to(directory).as_posix()
                digest = hashlib.sha256()
                with item.open("rb") as source:
                    for chunk in iter(lambda: source.read(CHUNK), b""):
                        digest.update(chunk)
                entries[rel] = (meta.st_size, digest.hexdigest())
                total += meta.st_size
                if len(entries) > MAX_FILES or total > MAX_BYTES:
                    raise TransactionRefused("Synthetic fixture exceeds safety quota")
    return entries


def journal_file(root: Path, txid: str) -> Path:
    if not TXID.fullmatch(txid):
        raise TransactionRefused("Invalid synthetic transaction ID")
    return root / "transactions" / txid / "journal.json"


def read_journal(root: Path, txid: str) -> dict:
    path = journal_file(root, txid)
    if path.is_symlink() or not path.is_file():
        raise TransactionRefused("Transaction journal missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise TransactionRefused("Transaction journal is invalid") from exc
    if not isinstance(data, dict) or data.get("id") != txid or data.get("synthetic") is not True:
        raise TransactionRefused("Invalid synthetic transaction journal")
    return data


def write_journal(root: Path, txid: str, info: dict) -> None:
    path = journal_file(root, txid)
    temp = path.with_name("journal.new")
    if temp.exists() or temp.is_symlink():
        raise TransactionRefused("Pending journal update exists; manual review required")
    data = json.dumps(info, sort_keys=True, indent=2) + "\n"
    with temp.open("x", encoding="utf-8") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def rollback(root: Path, txid: str) -> dict:
    """Restore the preserved synthetic original; never touch a real prefix."""
    root = fixture_root(root)
    info = read_journal(root, txid)
    if info.get("state") == "ROLLED_BACK":
        return {"id": txid, "state": "ROLLED_BACK", "real_game_modified": False}
    if info.get("state") not in ("PREPARED", "SWITCHING", "APPLIED", "ROLLBACK_PENDING"):
        raise TransactionRefused("Unrecognized journal state; refusing recovery")
    folder = journal_file(root, txid).parent
    original = folder / "original"
    candidate = folder / "candidate"
    prefix = root / "prefix"
    displaced = folder / "displaced"
    if (original.is_symlink() or prefix.is_symlink() or
            candidate.is_symlink() or displaced.is_symlink()):
        raise TransactionRefused("Recovery path became a symlink")
    if info["state"] == "PREPARED":
        if not prefix.is_dir() or original.exists():
            raise TransactionRefused("Prepared state differs from fixture layout")
    else:
        if not original.is_dir() or displaced.exists():
            raise TransactionRefused("Preserved original missing or recovery already interrupted")
        if prefix.exists():
            if not prefix.is_dir():
                raise TransactionRefused("Synthetic prefix path is not a directory")
            os.rename(prefix, displaced)
        os.rename(original, prefix)
        if displaced.exists():
            shutil.rmtree(displaced)
    if candidate.exists():
        shutil.rmtree(candidate)
    info["state"] = "ROLLED_BACK"
    write_journal(root, txid, info)
    return {"id": txid, "state": "ROLLED_BACK", "real_game_modified": False}


def apply_rehearsal(
    root: Path, *, approved: bool, failure_at: str | None = None
) -> dict:
    if not approved:
        raise TransactionRefused("Explicit --approve-rehearsal required")
    root = fixture_root(root)
    if failure_at not in (None, "after_prepare", "after_original_move", "after_apply"):
        raise TransactionRefused("Unknown synthetic fault injection stage")
    source, patch = root / "prefix", root / "patch"
    source_before, updates = collect(source), collect(patch)
    if not updates:
        raise TransactionRefused("No synthetic changes to test")
    # The fixture is intentionally a synthetic provider-independent sample.
    txroot = root / "transactions"
    if txroot.is_symlink() or (txroot.exists() and not txroot.is_dir()):
        raise TransactionRefused("Invalid synthetic transaction journal root")
    # Fail closed: a pending transaction must be explicitly recovered first.
    if txroot.exists():
        for other in txroot.iterdir():
            if other.is_symlink() or not other.is_dir():
                raise TransactionRefused("Unexpected transaction folder")
            saved = read_journal(root, other.name)
            if saved.get("state") not in ("ROLLED_BACK",):
                raise TransactionRefused("Previous synthetic transaction needs review or rollback")
    free = shutil.disk_usage(root).free
    required = sum(s for s, _ in source_before.values()) * 2 + \
               sum(s for s, _ in updates.values()) + 128 * 1024 * 1024
    if free < required:
        raise TransactionRefused("Insufficient space for independent synthetic backups")
    txroot.mkdir(mode=0o700, exist_ok=True)
    txid = uuid.uuid4().hex
    folder = txroot / txid
    folder.mkdir(mode=0o700)
    original = folder / "original"
    candidate = folder / "candidate"
    info = {
        "id": txid, "state": "PREPARED", "synthetic": True,
        "before": source_before, "patch": updates,
        "real_game_modified": False, "real_game_install_supported": False
    }
    try:
        # Never follow a symlink added during preparation; collect() then rejects it.
        shutil.copytree(source, candidate, symlinks=True)
        # After copying, re-inventory input to catch simple races.
        if collect(source) != source_before or collect(patch) != updates:
            raise TransactionRefused("Fixture changed during transaction preparation")
        for rel in updates:
            target = candidate.joinpath(*rel.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                raise TransactionRefused("Cannot replace a directory with a test file")
            shutil.copyfile(patch / rel, target, follow_symlinks=False)
        if collect(candidate) != {**source_before, **updates}:
            raise TransactionRefused("Synthetic transaction candidate verification failed")
        write_journal(root, txid, info)
        if failure_at == "after_prepare":
            raise RuntimeError("synthetic injected fault: after_prepare")
        info["state"] = "SWITCHING"
        write_journal(root, txid, info)
        os.rename(source, original)
        if failure_at == "after_original_move":
            raise RuntimeError("synthetic injected fault: after_original_move")
        os.rename(candidate, source)
        if failure_at == "after_apply":
            raise RuntimeError("synthetic injected fault: after_apply")
        if collect(source) != {**source_before, **updates}:
            raise TransactionRefused("Applied synthetic transaction verification failed")
        info["state"] = "APPLIED"
        write_journal(root, txid, info)
        return {
            "id": txid, "state": "APPLIED", "changed_files": len(updates),
            "synthetic_rollback_available": True,
            "real_game_modified": False, "real_game_install_supported": False
        }
    except Exception:
        # A crash can interrupt this branch; the journal plus preserved
        # original are retained for explicit recovery if cleanup fails.
        if (folder / "journal.json").exists():
            rollback(root, txid)
        elif folder.exists():
            shutil.rmtree(folder)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--approve-rehearsal", action="store_true")
    parser.add_argument("--rollback-id", help="Restore only the marked synthetic fixture")
    args = parser.parse_args(argv)
    try:
        if args.rollback_id:
            result = rollback(args.fixture_root, args.rollback_id)
        else:
            result = apply_rehearsal(args.fixture_root, approved=args.approve_rehearsal)
    except (TransactionRefused, OSError, ValueError) as exc:
        parser.exit(2, f"GameWeld synthetic transaction BLOCKED — {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
