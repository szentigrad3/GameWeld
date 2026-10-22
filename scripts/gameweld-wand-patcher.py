#!/usr/bin/env python3
"""GameWeld 0.6.0 Test 5: safe local Wand/WeMod patcher integration.

Discovers the selected installation, makes a separate GameWeld-owned backup,
restores from that backup, and can launch a user-built upstream WandEnhancer.exe
in an explicit, pre-existing Wine prefix. It does not contain, fetch, or apply
subscription/license bypasses or mutate Electron/ASAR integrity flags.

Upstream Windows WPF/.NET Framework patching is experimental under Wine;
launch success does not imply it worked. No Wine prefix or runner is invented.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import fcntl
import contextlib
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gameweld_wand_compat_audit", HERE / "gameweld-wand-compat-audit.py")
audit = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(audit)


class PatcherError(Exception):
    pass


def normal_prefix(prefix: Path) -> Path:
    try:
        return audit._prefix_root(prefix.expanduser().resolve(strict=True))
    except (ValueError, OSError) as e:
        raise PatcherError(f"Existing Wine prefix required: {e}") from e


def scope(prefix: Path, install: Path | None) -> tuple[Path, Path]:
    pfx = normal_prefix(prefix)
    drive = (pfx / "drive_c").resolve()
    if install is not None:
        roots = audit.candidates(None, install.expanduser().resolve(strict=True))
        if len(roots) != 1 or not audit._under(roots[0], drive):
            raise PatcherError("Selected Wand installation must be inside the specified Wine prefix")
    else:
        roots = audit.candidates(pfx, None)
    if not roots:
        raise PatcherError("No Wand/WeMod resources/app.asar found inside that Wine prefix")
    if len(roots) > 1:
        raise PatcherError(f"Found {len(roots)} Wand/WeMod versions; specify the exact version with --install")
    root = roots[0].resolve(strict=True)
    if root.is_symlink() or not audit._under(root, drive):
        raise PatcherError("Refusing symlink/escaped install root")
    asar = root / "resources" / "app.asar"
    if not asar.is_file() or asar.is_symlink():
        raise PatcherError("No ordinary resources/app.asar file at selected installation")
    return pfx, root


def snapshot_location(root: Path) -> Path:
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    digest = hashlib.sha256(str(root).encode()).hexdigest()[:24]
    return state / "gameweld" / "wand-patcher" / digest


def _sha(path: Path) -> str:
    return audit.sha256_file(path)


def _write_json(path: Path, info: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


MAX_SNAPSHOT_FILES = 25000


def _tree_inventory(directory: Path) -> dict[str, dict]:
    """Hash regular files only; refuse links and unsupported file types in backups."""
    if not directory.is_dir() or directory.is_symlink():
        raise PatcherError("The unpacked snapshot is missing or uses a symbolic link")
    inventory: dict[str, dict] = {}
    for base, dirs, files in os.walk(directory, followlinks=False):
        relbase = Path(base).relative_to(directory)
        for name in dirs:
            child = Path(base) / name
            if child.is_symlink():
                raise PatcherError("Symbolic links are not permitted inside Wand backups")
        for name in files:
            child = Path(base) / name
            if child.is_symlink() or not child.is_file():
                raise PatcherError("Wand backup contains a symlink or unsupported file")
            key = (relbase / name).as_posix()
            inventory[key] = {"bytes": child.stat().st_size, "sha256": _sha(child)}
            if len(inventory) > MAX_SNAPSHOT_FILES:
                raise PatcherError("Wand unpacked tree exceeds the backup safety limit")
    return inventory


def _active_wand_pids(prefix: Path, root: Path, proc: Path = Path("/proc")) -> list[int]:
    """Fail closed for identifiable Wand processes whose prefix cannot be proven unrelated."""
    active: list[int] = []
    if not proc.is_dir():
        raise PatcherError("Cannot inspect Linux processes; Wand must be closed before modifying files")
    for item in proc.iterdir():
        if not item.name.isdecimal():
            continue
        try:
            command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except (OSError, PermissionError):
            continue
        if not re.search(r"(?i)(?:^|[/\\\s])(?:wand|wemod|wandenhancer)\.exe(?:\s|$)", command):
            continue
        try:
            environment = (item / "environ").read_bytes().split(b"\0")
        except (OSError, PermissionError):
            active.append(int(item.name))
            continue
        match = False
        for value in environment:
            if b"=" not in value:
                continue
            key, val = value.split(b"=", 1)
            if key in (b"WINEPREFIX", b"STEAM_COMPAT_DATA_PATH", b"PROTON_COMPAT_DATA_PATH"):
                try:
                    observed = Path(os.fsdecode(val)).resolve()
                    if observed in (prefix, prefix.parent) or str(root).startswith(str(observed) + "/"):
                        match = True
                except (OSError, ValueError):
                    match = True
        if match or str(root) in command or str(prefix) in command or not environment:
            active.append(int(item.name))
        else:
            # A Wand.exe with no trustworthy prefix identification is ambiguous.
            if not any(v.startswith((b"WINEPREFIX=", b"STEAM_COMPAT_DATA_PATH=", b"PROTON_COMPAT_DATA_PATH=")) for v in environment):
                active.append(int(item.name))
    return sorted(active)


def _ensure_closed(prefix: Path, root: Path) -> None:
    running = _active_wand_pids(prefix, root)
    if running:
        raise PatcherError(f"Close Wand/WeMod in this prefix before changing files (process IDs: {', '.join(map(str, running[:10]))})")


@contextlib.contextmanager
def _exclusive_install(root: Path):
    folder = snapshot_location(root).parent
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    lockfile = folder / (snapshot_location(root).name + ".lock")
    with lockfile.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PatcherError("Another GameWeld backup/restore operation is active for this Wand installation") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _verify_snapshot(snap: Path, root: Path) -> dict:
    manifest = snap / "manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise PatcherError("No complete GameWeld snapshot exists; use Backup before patching")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PatcherError("Snapshot manifest is unreadable") from e
    if data.get("schema") not in (1, 2) or data.get("install_path") != str(root):
        raise PatcherError("Backup does not belong to the selected installation")
    saved = snap / "app.asar.original"
    if not saved.is_file() or saved.is_symlink() or _sha(saved) != data.get("asar_sha256"):
        raise PatcherError("Backup hash mismatch; refusing to use corrupted backup")
    if data.get("unpacked_present"):
        tree = _tree_inventory(snap / "app.asar.unpacked.original")
        if data["schema"] == 2 and tree != data.get("unpacked_files"):
            raise PatcherError("Unpacked backup contents changed or were corrupted; refusing restore")
    elif (snap / "app.asar.unpacked.original").exists():
        raise PatcherError("Unexpected unpacked backup tree present")
    return data


def backup(root: Path) -> dict:
    dest = snapshot_location(root)
    if dest.exists():
        data = _verify_snapshot(dest, root)
        return {"status": "existing_backup_preserved", "backup_sha256": data["asar_sha256"]}
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest.parent.chmod(0o700)
    stage = Path(tempfile.mkdtemp(prefix=".wand-backup-", dir=dest.parent))
    try:
        res = root / "resources"
        saved = stage / "app.asar.original"
        shutil.copy2(res / "app.asar", saved, follow_symlinks=False)
        if _sha(saved) != _sha(res / "app.asar"):
            raise PatcherError("File changed during backup; close Wand and retry")
        unpacked = res / "app.asar.unpacked"
        if unpacked.is_symlink():
            raise PatcherError("Refusing an unpacked tree which is a symbolic link")
        exists = unpacked.is_dir()
        tree_files = {}
        if exists:
            _tree_inventory(unpacked)  # reject untrusted symlinks before copying
            shutil.copytree(unpacked, stage / "app.asar.unpacked.original", symlinks=False)
            tree_files = _tree_inventory(stage / "app.asar.unpacked.original")
            if tree_files != _tree_inventory(unpacked):
                raise PatcherError("Unpacked resources changed during backup; retry with Wand closed")
        digest = _sha(saved)
        _write_json(stage / "manifest.json", {
            "schema": 2, "install_path": str(root), "asar_sha256": digest,
            "asar_bytes": saved.stat().st_size, "unpacked_present": exists,
            "unpacked_files": tree_files,
            "timestamp": int(time.time()), "upstream": "Wand-Enhancer (third-party, not bundled)"})
        stage.rename(dest)
        return {"status": "backup_created", "backup_sha256": digest}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def restore(root: Path) -> dict:
    snap = snapshot_location(root)
    data = _verify_snapshot(snap, root)
    res = root / "resources"
    target = res / "app.asar"
    unpacked = res / "app.asar.unpacked"
    if target.is_symlink() or unpacked.is_symlink():
        raise PatcherError("Refusing symlink target during restore")
    if not os.access(res, os.W_OK):
        raise PatcherError("Wand resources directory is not writable")
    stage = Path(tempfile.mkdtemp(prefix=".gameweld-restore-", dir=res))
    previous_asar = stage / "previous.asar"
    replacement = stage / "new.asar"
    prior_tree = stage / "previous-unpacked"
    try:
        shutil.copy2(target, previous_asar)
        shutil.copy2(snap / "app.asar.original", replacement)
        if _sha(replacement) != data["asar_sha256"]:
            raise PatcherError("Backup failed verification while staging restore")
        if data["unpacked_present"]:
            shutil.copytree(snap / "app.asar.unpacked.original", stage / "new-unpacked", symlinks=False)
            if data["schema"] == 2 and _tree_inventory(stage / "new-unpacked") != data["unpacked_files"]:
                raise PatcherError("Staged unpacked restore did not pass integrity checks")
        moved_tree = False
        replaced_asar = False
        try:
            if unpacked.exists():
                unpacked.rename(prior_tree)
                moved_tree = True
            if data["unpacked_present"]:
                (stage / "new-unpacked").rename(unpacked)
            replacement.replace(target)
            replaced_asar = True
            if _sha(target) != data["asar_sha256"]:
                raise PatcherError("Restored file checksum did not match the snapshot")
        except Exception:
            if replaced_asar:
                previous_asar.replace(target)
            if unpacked.exists():
                if unpacked.is_dir():
                    shutil.rmtree(unpacked)
                else:
                    unpacked.unlink()
            if moved_tree and prior_tree.exists():
                prior_tree.rename(unpacked)
            raise
        return {"status": "original_files_restored", "restored_sha256": data["asar_sha256"],
                "legacy_tree_unverified": data["schema"] == 1 and data["unpacked_present"]}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def launch(root: Path, pfx: Path, patcher: Path, wine: str) -> dict:
    _verify_snapshot(snapshot_location(root), root)
    patcher = patcher.expanduser().resolve(strict=True)
    if not patcher.is_file() or patcher.suffix.casefold() != ".exe":
        raise PatcherError("Choose a real Windows WandEnhancer.exe built from upstream source")
    with patcher.open("rb") as stream:
        magic = stream.read(2)
    if magic != b"MZ":
        raise PatcherError("Selected file is not a Windows executable")
    if patcher.name.casefold() != "wandenhancer.exe":
        raise PatcherError("Only the explicitly selected WandEnhancer.exe is supported")
    if not wine or not Path(wine).is_absolute():
        raise PatcherError("A validated absolute classic Wine executable is required. Steam Proton cannot use generic system wine.")
    wine_bin = wine
    if not wine_bin or not Path(wine_bin).is_file():
        raise PatcherError("The explicitly chosen Wine executable is unavailable; no fallback runner will be used")
    env = os.environ.copy()
    env["WINEPREFIX"] = str(pfx)
    proc = subprocess.Popen([wine_bin, str(patcher)], cwd=str(patcher.parent), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    return {"status": "external_patcher_spawned_unverified", "pid": proc.pid,
            "warning": "Windows WPF/.NET Framework 4.8 under Wine is not guaranteed. Check the patcher window and its logs before assuming success."}


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "backup", "restore", "prepare", "launch"))
    parser.add_argument("--prefix", required=True, type=Path, help="Existing Wine prefix; never auto-created")
    parser.add_argument("--install", type=Path, help="Optional exact Wand version directory")
    parser.add_argument("--patcher", type=Path, help="Locally built WandEnhancer.exe")
    parser.add_argument("--wine", help="Explicit validated classic Wine executable (no Steam Proton fallback)")
    parser.add_argument("--confirm", action="store_true", help="Explicit confirmation of file-changing actions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        pfx, root = scope(args.prefix, args.install)
        if args.action == "audit":
            data = audit.assess(root, include_paths=False, hash_files=True)
            snap = snapshot_location(root)
            try:
                snapshot = _verify_snapshot(snap, root)
                data["gameweld_backup"] = "valid"
                data["gameweld_original_sha256"] = snapshot["asar_sha256"]
            except PatcherError:
                data["gameweld_backup"] = "not_available"
            result = {"status": "inspection_complete", **data}
        elif args.action in ("backup", "restore", "prepare") and not args.confirm:
            raise PatcherError("--confirm is required for snapshot/restore/prepare")
        elif args.action in ("backup", "restore", "prepare"):
            with _exclusive_install(root):
                _ensure_closed(pfx, root)
                if args.action == "backup":
                    result = backup(root)
                elif args.action == "restore":
                    result = restore(root)
                else:
                    data = audit.assess(root, include_paths=False, hash_files=True)
                    saved = backup(root)
                    checked = _verify_snapshot(snapshot_location(root), root)
                    result = {"status": "ready_backup_verified_external_patch_unavailable",
                              "product": data.get("product", "Wand/WeMod"), "backup_status": saved["status"],
                              "backup_schema": checked["schema"],
                              "message": "Backup verified. GameWeld does not bundle a native patch executor or automatically change subscriptions."}
        else:
            if args.patcher is None:
                raise PatcherError("--patcher is required for launch")
            result = launch(root, pfx, args.patcher, args.wine)
        payload = {"ok": True, **result}
        print(json.dumps(payload, sort_keys=True) if args.json else f"{result['status']}: {json.dumps(result, sort_keys=True)}")
        return 0
    except (PatcherError, FileNotFoundError, PermissionError, OSError, ValueError, shutil.Error) as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload) if args.json else f"Wand patcher: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
