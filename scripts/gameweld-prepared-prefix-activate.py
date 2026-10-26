#!/usr/bin/env python3
"""Experimental transactional application of a prepared .NET prefix CANDIDATE.

Not used by the public GameWeld UI. Requires THREE explicit CLI approvals and
an environment opt-in to modify any real game prefix. Never overwrites or
deletes the original: same-filesystem renames preserve a complete backup, and
an explicit rollback retains the tested candidate as a separate directory.

This cannot prove Steam/game idle state absolutely, WeMod compatibility,
DLL injection, or trainer attachment. Test on synthetic fixtures first.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

ID = re.compile(r"[1-9][0-9]{0,9}\Z")
TX = re.compile(r"[0-9a-f]{32}\Z")
EXPERIMENT = "I_ACCEPT_PRIVATE_PREFIX_IMPORT_TEST"
RESERVE = 512 * 1024**2


class ActivationBlocked(ValueError):
    pass


def module(filename: str, name: str):
    script = Path(__file__).resolve().with_name(filename)
    if not script.is_file() or script.is_symlink():
        raise ActivationBlocked("Required local GameWeld safety module unavailable")
    spec = importlib.util.spec_from_file_location(name, script)
    if not spec or not spec.loader:
        raise ActivationBlocked("Could not load GameWeld safety module")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def validate_state(root: Path) -> Path:
    if (not root.is_absolute() or root.name != "prefix-imports" or
            root.parent.name != "gameweld" or root.is_symlink() or
            any(p.is_symlink() for p in root.parents) or
            not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077):
        raise ActivationBlocked("Existing private GameWeld import state root required")
    return root


def selected_candidate(root: Path, appid: str, candidate_dir: Path) -> tuple[Path, dict]:
    if (not candidate_dir.is_absolute() or
            candidate_dir.parent != root or candidate_dir.is_symlink() or
            not candidate_dir.is_dir() or
            not candidate_dir.name.startswith(appid + "-")):
        raise ActivationBlocked("Selected candidate is not in GameWeld private import state")
    record = candidate_dir / "candidate.json"
    if record.is_symlink() or not record.is_file() or record.stat().st_size > 16 * 1024:
        raise ActivationBlocked("Candidate import record missing or unsafe")
    try:
        manifest = json.loads(record.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ActivationBlocked("Candidate record is unreadable") from exc
    if (not isinstance(manifest, dict) or manifest.get("appid") != appid or
            manifest.get("mode") != "ISOLATED_CANDIDATE_PREPARED" or
            manifest.get("live_game_modified") is not False or
            not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("original_game_snapshot_sha256", "")))):
        raise ActivationBlocked("Candidate has no verified game-source fingerprint")
    candidate = candidate_dir / "compatdata"
    if candidate.is_symlink() or not candidate.is_dir():
        raise ActivationBlocked("Candidate has no ordinary compatdata directory")
    return candidate, manifest


def game_idle(appid: str, current: Path, *, proc_root: Path = Path("/proc")) -> dict:
    inspector = module("gameweld-prefix-runtime-preflight.py", "gw_prefix_idle")
    try:
        status = inspector.procfs_report(
            "steam", appid, current / "pfx", proc_root=proc_root)
    except (OSError, ValueError) as exc:
        raise ActivationBlocked("Could not safely inspect matching Wine/Proton processes") from exc
    if status["state"] != "IDLE_CANDIDATE" or status["unreadable_same_user_processes"]:
        raise ActivationBlocked("Wine/Proton may still be using the selected prefix")
    # Even IDLE_CANDIDATE is only a heuristic; explicit closed acknowledgement
    # is mandatory before a test activation can mutate a real prefix.
    return status


def journal_path(root: Path, txid: str) -> Path:
    if not TX.fullmatch(txid):
        raise ActivationBlocked("Invalid private import transaction ID")
    return root / "transactions" / (txid + ".json")


def write_new_journal(root: Path, txid: str, data: dict) -> None:
    path = journal_path(root, txid)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def update_journal(root: Path, txid: str, data: dict) -> None:
    path = journal_path(root, txid)
    temp = path.parent / (txid + ".updating")
    if temp.exists() or temp.is_symlink():
        raise ActivationBlocked("Incomplete journal update needs manual recovery")
    with temp.open("x", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def read_journal(root: Path, txid: str) -> dict:
    path = journal_path(root, txid)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024:
        raise ActivationBlocked("Import transaction record missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ActivationBlocked("Import transaction record is invalid") from exc
    if not isinstance(data, dict) or data.get("txid") != txid:
        raise ActivationBlocked("Import transaction identity mismatch")
    return data


def approval(approved: bool, closed: bool, accepted: bool) -> None:
    if not (approved and closed and accepted and
            os.environ.get("GAMEWELD_PREFIX_IMPORT_EXPERIMENT") == EXPERIMENT):
        raise ActivationBlocked(
            "Private experiment opt-in and explicit prefix-change/game-closed/risk approvals required")


def activate(
    appid: str, install_dir: Path, candidate_dir: Path, *,
    state_root: Path,
    approved: bool,
    game_closed: bool,
    accepted_risk: bool,
    proc_root: Path = Path("/proc"),
) -> dict:
    approval(approved, game_closed, accepted_risk)
    root = validate_state(state_root)
    importer = module("gameweld-prepared-prefix-import.py", "gw_prepared_import")
    current = importer.steam_game(appid, install_dir)
    candidate, info = selected_candidate(root, appid, candidate_dir)
    game_idle(appid, current, proc_root=proc_root)
    if importer.fingerprint(current) != info["original_game_snapshot_sha256"]:
        raise ActivationBlocked("Game prefix changed since the prepared test candidate was created")
    expected = importer.fingerprint(candidate)
    txid = uuid.uuid4().hex
    parent = current.parent
    backup = parent / f".gameweld-original-{appid}-{txid}"
    staging = parent / f".gameweld-import-{appid}-{txid}"
    if backup.exists() or backup.is_symlink() or staging.exists() or staging.is_symlink():
        raise ActivationBlocked("Reserved Steam compatdata transaction path already exists")
    _, size = importer.files_and_bytes(candidate)
    if shutil.disk_usage(parent).free < size + RESERVE:
        raise ActivationBlocked("Insufficient game-library disk space for safe candidate copy")
    # Never move live game files until a verified complete candidate exists
    # on the same filesystem as Steam's original compatdata directory.
    try:
        shutil.copytree(candidate, staging, symlinks=True)
        if importer.fingerprint(staging) != expected:
            raise ActivationBlocked("Staged game-library copy failed integrity verification")
        game_idle(appid, current, proc_root=proc_root)
        if importer.fingerprint(current) != info["original_game_snapshot_sha256"]:
            raise ActivationBlocked("Game prefix changed while preparing transaction")
        data = {
            "txid": txid, "appid": appid, "state": "PREPARED",
            "compat_path": str(current), "backup_path": str(backup),
            "staging_path": str(staging),
            "candidate_source": str(candidate_dir),
            "original_sha256": info["original_game_snapshot_sha256"],
            "candidate_sha256": expected,
            "original_backup_preserved": True,
            "trainer_verified": False,
        }
        write_new_journal(root, txid, data)
        os.rename(current, backup)
        try:
            os.rename(staging, current)
            data["state"] = "APPLIED"
            update_journal(root, txid, data)
        except Exception:
            # Even if publishing the APPLIED journal fails after the swap,
            # put the complete original back before returning an error.
            # Never delete the failed candidate or user data.
            recovered = parent / f".gameweld-failed-{appid}-{txid}"
            if current.exists() and not recovered.exists():
                os.rename(current, recovered)
            if backup.exists() and not current.exists():
                os.rename(backup, current)
            data["state"] = "ROLLED_BACK"
            update_journal(root, txid, data)
            raise
        return {
            "txid": txid, "state": "APPLIED",
            "backup_preserved": True,
            "backup_path": str(backup),
            "live_prefix_was_replaced_with_candidate": True,
            "steam_options_changed": False,
            "trainer_verified": False,
            "next": "Test Steam normal game launch and WeMod; rollback if unsuccessful",
        }
    finally:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)


def rollback(
    appid: str, install_dir: Path, txid: str, *,
    state_root: Path,
    approved: bool,
    game_closed: bool,
    accepted_risk: bool,
    proc_root: Path = Path("/proc"),
) -> dict:
    approval(approved, game_closed, accepted_risk)
    root = validate_state(state_root)
    importer = module("gameweld-prepared-prefix-import.py", "gw_prepared_import_rollback")
    current = importer.steam_game(appid, install_dir)
    record = read_journal(root, txid)
    if record.get("appid") != appid or record.get("state") != "APPLIED":
        raise ActivationBlocked("Only a verified applied import can be rolled back")
    backup = current.parent / f".gameweld-original-{appid}-{txid}"
    retired = current.parent / f".gameweld-postimport-{appid}-{txid}"
    if (record.get("compat_path") != str(current) or
            record.get("backup_path") != str(backup) or
            not backup.is_dir() or backup.is_symlink() or
            retired.exists() or retired.is_symlink()):
        raise ActivationBlocked("Import rollback path or original backup is invalid")
    game_idle(appid, current, proc_root=proc_root)
    if importer.fingerprint(backup) != record["original_sha256"]:
        raise ActivationBlocked("Saved original game prefix no longer matches its fingerprint")
    os.rename(current, retired)
    try:
        os.rename(backup, current)
    except OSError:
        os.rename(retired, current)
        raise
    record["state"] = "ROLLED_BACK"
    record["postimport_path"] = str(retired)
    update_journal(root, txid, record)
    return {
        "txid": txid, "state": "ROLLED_BACK",
        "original_game_restored": True,
        "postimport_files_preserved": True,
        "postimport_path": str(retired),
        "steam_options_changed": False,
    }



def recover_interrupted(
    appid: str, install_dir: Path, txid: str, *,
    state_root: Path, approved: bool, game_closed: bool,
    accepted_risk: bool, proc_root: Path = Path("/proc")
) -> dict:
    """Recover a PREPARED transaction if killed between two directory renames."""
    approval(approved, game_closed, accepted_risk)
    if not ID.fullmatch(appid):
        raise ActivationBlocked("Invalid Steam AppID")
    root = validate_state(state_root)
    record = read_journal(root, txid)
    if record.get("appid") != appid or record.get("state") != "PREPARED":
        raise ActivationBlocked("Only an interrupted PREPARED transaction can be recovered")
    if (not install_dir.is_absolute() or not install_dir.is_dir() or
            install_dir.parent.name != "common" or
            install_dir.parent.parent.name != "steamapps"):
        raise ActivationBlocked("Selected Steam game library is invalid")
    steamapps = install_dir.parent.parent
    if not (steamapps / f"appmanifest_{appid}.acf").is_file():
        raise ActivationBlocked("Steam game manifest missing")
    current = steamapps / "compatdata" / appid
    backup = current.parent / f".gameweld-original-{appid}-{txid}"
    staging = current.parent / f".gameweld-import-{appid}-{txid}"
    if (record.get("compat_path") != str(current) or
            record.get("backup_path") != str(backup) or
            record.get("staging_path") != str(staging)):
        raise ActivationBlocked("Journal paths differ from exact selected game")
    importer = module("gameweld-prepared-prefix-import.py", "gw_import_recovery")
    if backup.is_symlink() or current.is_symlink() or staging.is_symlink():
        raise ActivationBlocked("Symlinked prefix recovery path is forbidden")
    if backup.exists():
        if not backup.is_dir() or importer.fingerprint(backup) != record["original_sha256"]:
            raise ActivationBlocked("Preserved original prefix is missing or changed")
        if current.exists():
            if not current.is_dir():
                raise ActivationBlocked("Invalid current prefix during recovery")
            game_idle(appid, current, proc_root=proc_root)
            moved = current.parent / f".gameweld-recovered-test-{appid}-{txid}"
            if moved.exists() or moved.is_symlink():
                raise ActivationBlocked("Recovered test candidate already exists")
            os.rename(current, moved)
        os.rename(backup, current)
    elif not current.is_dir():
        raise ActivationBlocked("Neither current game prefix nor original backup exists")
    else:
        # Swap never began. Confirm process inactivity before finishing recovery.
        game_idle(appid, current, proc_root=proc_root)
        if importer.fingerprint(current) != record["original_sha256"]:
            raise ActivationBlocked("Game prefix changed during unfinished transaction")
    if staging.exists():
        # Private uncommitted candidate; preserve it for manual inspection.
        preserved = staging.with_name(staging.name + ".aborted")
        if preserved.exists() or preserved.is_symlink():
            raise ActivationBlocked("Aborted candidate path already exists")
        os.rename(staging, preserved)
    record["state"] = "ROLLED_BACK"
    update_journal(root, txid, record)
    return {
        "txid": txid, "state": "ROLLED_BACK",
        "original_game_restored": True,
        "failed_candidate_preserved": True,
        "steam_options_changed": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--install-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--rollback-id")
    parser.add_argument("--recover-id")
    parser.add_argument("--state-root", type=Path, default=Path(
        os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    ) / "gameweld/prefix-imports")
    parser.add_argument("--approve-real-prefix-change", action="store_true")
    parser.add_argument("--acknowledge-game-closed", action="store_true")
    parser.add_argument("--accept-experimental-risk", action="store_true")
    args = parser.parse_args(argv)
    kwargs = {
        "state_root": args.state_root,
        "approved": args.approve_real_prefix_change,
        "game_closed": args.acknowledge_game_closed,
        "accepted_risk": args.accept_experimental_risk
    }
    try:
        if args.rollback_id and args.recover_id:
            raise ActivationBlocked("Choose only one recovery operation")
        if args.recover_id:
            if args.candidate_dir is not None:
                raise ActivationBlocked("Cannot combine install candidate and recovery")
            output = recover_interrupted(args.appid, args.install_dir, args.recover_id, **kwargs)
        elif args.rollback_id:
            if args.candidate_dir is not None:
                raise ActivationBlocked("Cannot combine install candidate with rollback")
            output = rollback(args.appid, args.install_dir, args.rollback_id, **kwargs)
        else:
            if args.candidate_dir is None:
                raise ActivationBlocked("Explicit prepared candidate directory required")
            output = activate(args.appid, args.install_dir, args.candidate_dir, **kwargs)
    except (ActivationBlocked, OSError, ValueError) as exc:
        parser.exit(2, "GameWeld prefix import activation BLOCKED — " + str(exc) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
