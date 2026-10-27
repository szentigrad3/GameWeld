#!/usr/bin/env python3
"""One-shot EXPERIMENTAL Steam test of retained DeckCheatz PfxVer10.1.

Prepare: extract over an independent COPY of the selected compatdata, then
atomically swap the copy into place and KEEP the untouched original beside it.
Restore: put the original compatdata back; retain the test copy separately.
This is not a publisher trust claim or a generic safe prefix installer.
No use by GameWeld public GUI. Requires explicit --accept-experimental-swap.
Run only with your OWN Steam installation and while the game is fully closed.
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

APPID_RE = re.compile(r"[1-9][0-9]{0,9}\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
CHUNK = 1024 * 1024
RESERVE = 512 * 1024 * 1024
MAX_EXPLICIT_UNKNOWN_PROCESSES = 8
SOURCE = "DeckCheatz/BuiltPrefixes-dev"
EXPECTED = ("PfxVer10.1", "GE-Proton10.1.zip")
EXPECTED_GROUPS = {
    frozenset((
        "pfx/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/installutil.exe",
        "pfx/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/InstallUtil.exe",
    )),
    frozenset((
        "pfx/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/CONFIG/machine.config",
        "pfx/drive_c/windows/Microsoft.NET/Framework64/v4.0.30319/Config/machine.config",
    )),
    frozenset((
        "pfx/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/InstallUtil.exe",
        "pfx/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/installutil.exe",
    )),
    frozenset((
        "pfx/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/CONFIG/machine.config",
        "pfx/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/Config/machine.config",
    )),
}


class QuickTryBlocked(ValueError):
    pass


def load(name: str, filename: str):
    path = Path(__file__).resolve().with_name(filename)
    if path.is_symlink() or not path.is_file():
        raise QuickTryBlocked("Required GameWeld safety module unavailable")
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise QuickTryBlocked("Cannot load required safety module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_steam(appid: str, steamapps: Path) -> tuple[Path, Path, Path]:
    if not APPID_RE.fullmatch(appid):
        raise QuickTryBlocked("Steam AppID must be numeric")
    root = steamapps
    if (not root.is_absolute() or root.name != "steamapps" or
            any(p.is_symlink() for p in (root, *root.parents)) or
            not root.is_dir()):
        raise QuickTryBlocked("Choose a real, non-symlinked Steam steamapps directory")
    if not (root / f"appmanifest_{appid}.acf").is_file():
        raise QuickTryBlocked("Matching Steam game manifest is missing")
    compat = root / "compatdata"
    current = compat / appid
    if (compat.is_symlink() or not compat.is_dir() or
            current.is_symlink() or not current.is_dir() or
            (current / "pfx").is_symlink() or not (current / "pfx").is_dir()):
        raise QuickTryBlocked("Selected game has no ordinary Proton compatdata/pfx")
    backup = compat / f".gameweld-original-{appid}"
    tested = compat / f".gameweld-tested-{appid}"
    return current, backup, tested


def process_report(appid: str, current: Path) -> dict:
    """Read-only scoped process report; process arguments are never disclosed."""
    inspector = load("gw_quick_try_active_guard", "gameweld-prefix-runtime-preflight.py")
    try:
        return inspector.procfs_report("steam", appid, current / "pfx")
    except (OSError, ValueError) as exc:
        raise QuickTryBlocked("Could not inspect running game/Proton processes") from exc


def process_verdict(report: dict) -> str:
    state = report.get("state")
    matching = report.get("matching_process_count", len(report.get("matching_processes", [])))
    unreadable = report.get("unreadable_same_user_processes", 0)
    if state == "ACTIVE" or matching:
        return (f"BLOCKED: {matching} process(es) still reference this game's "
                "Proton prefix. Close the game through Steam (Stop -> Play), "
                "then retry. Matching PIDs: " +
                ", ".join(str(pid) for pid in report.get("matching_processes", [])[:20]))
    if state != "IDLE_CANDIDATE" or unreadable:
        return (f"BLOCKED: {unreadable} same-user process(es) could not be "
                "inspected (state UNKNOWN); this does NOT prove the game is "
                "running. Do not kill unrelated Wine processes. For this "
                "private experiment ONLY, if Steam shows Play and the game is "
                "confirmed closed, --accept-unreadable-process-risk adds "
                "a separate, explicitly acknowledged UNKNOWN-only exception; "
                "a positively detected game process always blocks.")
    return "IDLE_CANDIDATE (process observation only; not proof that Steam closed the game)"


def status_report(appid: str, steamapps: Path) -> dict:
    """No extraction, archive reads or writes; report the precise blocker."""
    current, backup, tested = check_steam(appid, steamapps)
    report = process_report(appid, current)
    state = report.get("state")
    has_backup = backup.exists() or backup.is_symlink()
    has_tested = tested.exists() or tested.is_symlink()
    return {
        "appid": appid,
        "process_state": state,
        "matching_process_count": report.get("matching_process_count", 0),
        "matching_pids": report.get("matching_processes", [])[:20],
        "unreadable_same_user_processes":
            report.get("unreadable_same_user_processes", 0),
        "original_backup_present": has_backup,
        "tested_copy_present": has_tested,
        "can_attempt_prepare":
            state == "IDLE_CANDIDATE" and
            report.get("unreadable_same_user_processes", 0) == 0 and
            not has_backup and not has_tested,
        "experimental_unknown_override_available":
            may_override_unknown(report) and
            not has_backup and not has_tested,
        "verdict": process_verdict(report),
        "prefix_modified": False,
        "note": "Read-only process preflight. No ZIP extraction or prefix swap.",
    }


def may_override_unknown(report: dict) -> bool:
    """Narrow explicit-risk exception. Never overridable on positive matches."""
    return (
        report.get("state") == "UNKNOWN" and
        report.get("matching_process_count", 0) == 0 and
        not report.get("matching_processes") and
        type(report.get("unreadable_same_user_processes")) is int and
        0 < report["unreadable_same_user_processes"] <= MAX_EXPLICIT_UNKNOWN_PROCESSES
    )


def check_idle(appid: str, current: Path, *,
               allow_unreadable: bool = False) -> None:
    report = process_report(appid, current)
    if (report.get("state") == "IDLE_CANDIDATE" and
            report.get("unreadable_same_user_processes", 0) == 0 and
            report.get("matching_process_count", 0) == 0 and
            not report.get("matching_processes")):
        return
    if allow_unreadable and may_override_unknown(report):
        # User must also provide the regular closed-game acknowledgement
        # and experimental-swap approval. Check again before changing paths.
        return
    raise QuickTryBlocked(process_verdict(report))


def find_zip(cache_root: Path):
    if (not cache_root.is_absolute() or cache_root.name != "prepared-wemod" or
            cache_root.parent.name != "gameweld" or
            any(x.casefold() in {"steamapps", "compatdata", "pfx"}
                for x in cache_root.parts) or
            any(p.is_symlink() for p in (cache_root, *cache_root.parents))):
        raise QuickTryBlocked("Use only GameWeld's private prepared-wemod cache")
    rejected = cache_root / "rejected"
    if (not rejected.is_dir() or rejected.is_symlink() or
            stat.S_IMODE(rejected.stat().st_mode) & 0o077):
        raise QuickTryBlocked("No private rejected ZIP cache exists")
    files = list(rejected.glob("*.zip"))
    if len(files) != 1:
        raise QuickTryBlocked("Exactly one retained rejected ZIP is required")
    archive = files[0]
    sha = archive.stem
    if (archive.is_symlink() or not archive.is_file() or
            not DIGEST_RE.fullmatch(sha)):
        raise QuickTryBlocked("Retained ZIP filename is unsafe")
    receipt = rejected / (sha + ".rejected.json")
    if (receipt.is_symlink() or not receipt.is_file() or
            receipt.stat().st_size > 4096):
        raise QuickTryBlocked("Quarantine receipt missing or unsafe")
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise QuickTryBlocked("Unreadable ZIP quarantine receipt") from exc
    if (not isinstance(data, dict) or data.get("sha256") != sha or
            data.get("source") != SOURCE or
            (data.get("release_tag"), data.get("asset_name")) != EXPECTED or
            data.get("status") != "REJECTED_NOT_STAGEABLE" or
            type(data.get("bytes")) is not int or
            data["bytes"] != archive.stat().st_size):
        raise QuickTryBlocked("Retained ZIP identity does not match expected source")
    return archive


def verify_archive(archive: Path):
    audit = load("gw_quick_try_zip_audit", "gameweld-prepared-prefix-audit.py")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    if digest.hexdigest() != archive.stem:
        raise QuickTryBlocked("Retained ZIP local SHA-256 changed")
    try:
        with zipfile.ZipFile(archive) as z:
            n, uncompressed = audit.check_other_zip_safety_without_approving_collisions(z)
            categories, _ = audit.classify_zip_collisions(z)
            if categories != {"exact_duplicate": 0, "case_collision": 4,
                              "unicode_collision": 0, "file_directory_conflict": 0}:
                raise QuickTryBlocked("Unexpected archive collision inventory")
            from collections import defaultdict
            paths = defaultdict(set)
            for m in z.infolist():
                paths[m.filename.rstrip("/").casefold()].add(m.filename.rstrip("/"))
            actual = {frozenset(names) for names in paths.values() if len(names) > 1}
            if actual != EXPECTED_GROUPS:
                raise QuickTryBlocked("ZIP collision paths differ from the independently tested archive")
            if not any(m.filename == "pfx/.wemod_installer" for m in z.infolist()):
                raise QuickTryBlocked("Archive is not recognized as a DeckCheatz WeMod prefix")
            if z.testzip() is not None:
                raise QuickTryBlocked("ZIP CRC failure")
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError,
            audit.UnsafePreparedPrefix) as exc:
        raise QuickTryBlocked("ZIP failed last structural/CRC check") from exc
    return n, uncompressed


def extract_overlay(archive: Path, target: Path, max_bytes: int) -> int:
    """Only ever writes the separately cloned test candidate, never original."""
    expanded = 0
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            rel = member.filename.rstrip("/")
            destination = target.joinpath(*rel.split("/"))
            if not destination.is_relative_to(target):
                raise QuickTryBlocked("ZIP destination escaped private cloned candidate")
            for ancestor in (destination, *destination.parents):
                if ancestor == target:
                    break
                if ancestor.is_symlink():
                    raise QuickTryBlocked("ZIP overlay would follow an existing prefix symlink")
            if member.is_dir():
                if destination.exists() and not destination.is_dir():
                    raise QuickTryBlocked("ZIP directory collides with existing file")
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            if destination.exists() and not destination.is_file():
                raise QuickTryBlocked("ZIP entry collides with an existing directory")
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            flags = (os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                     getattr(os, "O_NOFOLLOW", 0))
            fd = os.open(destination, flags, 0o600)
            with os.fdopen(fd, "wb") as sink, z.open(member) as source:
                written = 0
                for piece in iter(lambda: source.read(CHUNK), b""):
                    written += len(piece)
                    expanded += len(piece)
                    if written > member.file_size or expanded > max_bytes:
                        raise QuickTryBlocked("ZIP expanded beyond its verified limits")
                    sink.write(piece)
            if written != member.file_size:
                raise QuickTryBlocked("Incomplete prefix member extraction")
    if expanded > max_bytes:
        raise QuickTryBlocked("ZIP overlay exceeded stated total size")
    return expanded


def validate_saved_test_copy(tested: Path) -> None:
    """Check the exact case-preserving DeckCheatz copy retained by --restore.

    This confirms local structure only, not code authenticity or compatibility.
    Refuse a symlink, missing .NET case variant or broken WeMod marker.
    """
    if tested.is_symlink() or not tested.is_dir():
        raise QuickTryBlocked("Saved experimental prefix is missing or symlinked")
    prefix = tested / "pfx"
    marker = prefix / ".wemod_installer"
    if (prefix.is_symlink() or not prefix.is_dir() or
            marker.is_symlink() or not marker.is_file()):
        raise QuickTryBlocked("Saved experimental prefix lacks its WeMod marker")
    for pair in EXPECTED_GROUPS:
        files = [tested.joinpath(*relative.split("/")) for relative in pair]
        if len(files) != 2:
            raise QuickTryBlocked("Saved experimental prefix has an unexpected collision group")
        for file in files:
            if (file.is_symlink() or not file.is_file() or
                    any(parent.is_symlink() for parent in
                        (file.parent, *file.parents[:6]))):
                raise QuickTryBlocked("Saved experimental prefix lost a required case variant")
        if files[0].stat().st_ino == files[1].stat().st_ino:
            raise QuickTryBlocked("Saved experimental prefix merged case variants")


def retest(appid: str, steamapps: Path, *,
           acknowledge_closed: bool, accept: bool,
           allow_unreadable: bool = False,
           idle_checker=check_idle) -> dict:
    """Reactivate previously saved test compatdata WITHOUT ZIP I/O or extraction.

    Complete, unchanged original compatdata is moved to the rollback name.
    Two same-filesystem renames make it reversible as in initial --prepare.
    """
    if not (acknowledge_closed and accept):
        raise QuickTryBlocked("Explicit closed-game and experimental-swap approvals required")
    current, backup, tested = check_steam(appid, steamapps)
    if backup.is_symlink() or backup.exists():
        raise QuickTryBlocked("An original backup is already present; cannot activate another test")
    validate_saved_test_copy(tested)
    if allow_unreadable:
        idle_checker(appid, current, allow_unreadable=True)
        idle_checker(appid, current, allow_unreadable=True)
    else:
        idle_checker(appid, current)
        idle_checker(appid, current)
    # No ZIP reads or extraction; source is only the previously retained local
    # directory. Never delete the original backup on a successful swap.
    os.rename(current, backup)
    try:
        os.rename(tested, current)
    except BaseException:
        os.rename(backup, current)
        raise
    return {
        "result": "SAVED_TEST_PREFIX_REACTIVATED",
        "appid": appid,
        "reused_existing_test_copy": True,
        "downloaded_bytes": 0,
        "extracted_bytes": 0,
        "backup": str(backup),
        "live": str(current),
        "launch": f"steam -applaunch {appid}",
        "restore": f"python3 scripts/gameweld-quick-try-prefix.py --restore "
                   f"--appid {appid} --steamapps '{steamapps}' "
                   "--acknowledge-game-closed --accept-experimental-swap" +
                   (" --accept-unreadable-process-risk" if allow_unreadable else ""),
        "warning": "Existing test copy may contain changes from an earlier game run. "
                   "Experimental case-ambiguous Wine prefix; no trainer claim.",
    }


def prepare(appid: str, steamapps: Path, cache_root: Path,
            *, acknowledge_closed: bool, accept: bool,
            allow_unreadable: bool = False,
            idle_checker=check_idle):
    if not (acknowledge_closed and accept):
        raise QuickTryBlocked("Explicit closed-game and experimental-swap approvals required")
    current, backup, tested = check_steam(appid, steamapps)
    if backup.exists() or backup.is_symlink():
        raise QuickTryBlocked("An original prefix backup already exists; restore/review first")
    if tested.exists() or tested.is_symlink():
        # --restore intentionally retains the last tested copy. Reuse it on
        # repeated --prepare rather than decompressing 2.55 GB again.
        return retest(appid, steamapps,
                      acknowledge_closed=acknowledge_closed, accept=accept,
                      allow_unreadable=allow_unreadable,
                      idle_checker=idle_checker)
    if allow_unreadable:
        idle_checker(appid, current, allow_unreadable=True)
    else:
        idle_checker(appid, current)
    archive = find_zip(cache_root)
    count, size = verify_archive(archive)
    importer = load("gw_quick_try_size", "gameweld-prepared-prefix-import.py")
    _, existing_bytes = importer.files_and_bytes(current)
    if shutil.disk_usage(current.parent).free < existing_bytes + size + RESERVE:
        raise QuickTryBlocked("Not enough disk space for separate prefix copy plus ZIP contents")
    work = Path(tempfile.mkdtemp(prefix=f".gameweld-preparing-{appid}-", dir=current.parent))
    candidate = work / "compatdata"
    try:
        shutil.copytree(current, candidate, symlinks=True)
        extracted = extract_overlay(archive, candidate, size)
        # Recheck right before swapping; a positively detected game ALWAYS blocks.
        if allow_unreadable:
            idle_checker(appid, current, allow_unreadable=True)
        else:
            idle_checker(appid, current)
        if backup.exists() or backup.is_symlink() or not current.is_dir():
            raise QuickTryBlocked("Game prefix changed or backup appeared during preparation")
        os.rename(current, backup)
        try:
            os.rename(candidate, current)
        except BaseException:
            os.rename(backup, current)
            raise
        return {
            "result": "TEST_PREFIX_ACTIVE",
            "appid": appid, "zip_entries": count, "overlay_bytes": extracted,
            "backup": str(backup), "live": str(current),
            "launch": f"steam -applaunch {appid}",
            "restore": f"python3 scripts/gameweld-quick-try-prefix.py --restore "
                       f"--appid {appid} --steamapps '{steamapps}' "
                       "--acknowledge-game-closed --accept-experimental-swap" +
                       (" --accept-unreadable-process-risk" if allow_unreadable else ""),
            "unknown_process_override_used": allow_unreadable,
            "warning": "Experimental Wine case-ambiguous prefix; game/trainer may fail",
        }
    finally:
        if work.exists() and not work.is_symlink():
            shutil.rmtree(work)


def restore(appid: str, steamapps: Path, *,
            acknowledge_closed: bool, accept: bool,
            allow_unreadable: bool = False,
            idle_checker=check_idle):
    if not (acknowledge_closed and accept):
        raise QuickTryBlocked("Explicit closed-game and experimental-swap approvals required")
    current, backup, tested = check_steam(appid, steamapps)
    if (backup.is_symlink() or not backup.is_dir() or
            tested.exists() or tested.is_symlink()):
        raise QuickTryBlocked("No unambiguous original backup available for restore")
    if allow_unreadable:
        idle_checker(appid, current, allow_unreadable=True)
    else:
        idle_checker(appid, current)
    os.rename(current, tested)
    try:
        os.rename(backup, current)
    except BaseException:
        os.rename(tested, current)
        raise
    return {
        "result": "ORIGINAL_PREFIX_RESTORED", "appid": appid,
        "original_restored": str(current),
        "test_copy_preserved": str(tested),
        "note": "Game may sync cloud state separately; review saves after restoring.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--prepare", action="store_true")
    choice.add_argument("--restore", action="store_true")
    choice.add_argument("--retest", action="store_true",
                        help="Reactivate the test prefix saved after --restore, no extraction")
    choice.add_argument("--status", action="store_true",
                        help="Read-only Steam/Proton process and backup diagnosis")
    parser.add_argument("--appid", required=True)
    parser.add_argument("--steamapps", type=Path, default=Path("/mnt/games/Steam/steamapps"))
    cache = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache"))
    parser.add_argument("--cache-root", type=Path, default=cache / "gameweld/prepared-wemod")
    parser.add_argument("--acknowledge-game-closed", action="store_true")
    parser.add_argument("--accept-experimental-swap", action="store_true")
    parser.add_argument("--accept-unreadable-process-risk", action="store_true",
                        help="Explicitly accept up to 8 inaccessible same-user "
                             "processes ONLY when no game process is identified; "
                             "never overrides ACTIVE")
    args = parser.parse_args()
    try:
        if args.status:
            if (args.acknowledge_game_closed or args.accept_experimental_swap or
                    args.accept_unreadable_process_risk):
                raise QuickTryBlocked("Read-only status cannot be combined with approval flags")
            out = status_report(args.appid, args.steamapps)
        elif args.prepare:
            out = prepare(args.appid, args.steamapps, args.cache_root,
                          acknowledge_closed=args.acknowledge_game_closed,
                          accept=args.accept_experimental_swap,
                          allow_unreadable=args.accept_unreadable_process_risk)
        elif args.retest:
            out = retest(args.appid, args.steamapps,
                         acknowledge_closed=args.acknowledge_game_closed,
                         accept=args.accept_experimental_swap,
                         allow_unreadable=args.accept_unreadable_process_risk)
        else:
            out = restore(args.appid, args.steamapps,
                          acknowledge_closed=args.acknowledge_game_closed,
                          accept=args.accept_experimental_swap,
                          allow_unreadable=args.accept_unreadable_process_risk)
    except (QuickTryBlocked, OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"GameWeld experimental quick try: BLOCKED — {exc}\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
