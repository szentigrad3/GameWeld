#!/usr/bin/env python3
"""GameWeld PC2: manage an external DeckCheatz 1.x checkout for a local user.

Read-only --status; opt-in --install --confirm. We do NOT copy AGPL source into
GameWeld, use sudo, change Steam launch options, patch Wine/WeMod, or run upstream
code at install time. Installation is an atomic, non-destructive git clone of
the official 1.x main branch, which upstream describes as bugfix-only.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time
import re
import subprocess
import sys
import tempfile

SOURCE_URL = "https://github.com/DeckCheatz/wemod-launcher.git"
SOURCE_BRANCH = "main"
SUBDIR = "gameweld/deckcheatz"
MAX_REPORT = 3000
MANAGED_MARKER = ".gameweld-managed.json"
REV_RE = re.compile(r"[0-9a-f]{40}\Z")


class InstallError(RuntimeError):
    pass


def provider():
    helper = Path(__file__).with_name("gameweld-deckcheatz-direct.py")
    spec = importlib.util.spec_from_file_location("_gameweld_deckcheatz_direct", helper)
    if spec is None or spec.loader is None:
        raise InstallError("The GameWeld DeckCheatz provider helper is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def data_root() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg and os.path.isabs(xdg):
        return Path(xdg)
    return Path.home() / ".local/share"


def install_directory() -> Path:
    return data_root() / SUBDIR


def dependencies() -> dict:
    result = {"git": bool(shutil.which("git")), "python3": True}
    try:
        import tkinter  # noqa: F401 -- upstream graphical installer requires Tk
        result["tkinter"] = True
    except ImportError:
        result["tkinter"] = False
    try:
        import venv  # noqa: F401
        result["venv"] = True
    except ImportError:
        result["venv"] = False
    return result



def managed_metadata(path: Path) -> dict | None:
    """Read-only: recognize installs GameWeld explicitly created."""
    try:
        if path.is_symlink():
            return None
        meta = json.loads((path / MANAGED_MARKER).read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return None
        if (meta.get("schema") != 1 or meta.get("origin") != SOURCE_URL
                or meta.get("branch") != SOURCE_BRANCH
                or not isinstance(meta.get("revision"), str)
                or not REV_RE.fullmatch(meta["revision"])):
            return None
        provider().inspect_launcher(path / "wemod")
        return meta
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def write_managed_metadata(path: Path, revision: str) -> None:
    if not REV_RE.fullmatch(revision):
        raise InstallError("Cannot mark a checkout with an invalid Git revision")
    marker = path / MANAGED_MARKER
    if marker.exists() or marker.is_symlink():
        raise InstallError("Upstream checkout contains GameWeld's private metadata name")
    payload = {"schema": 1, "origin": SOURCE_URL,
               "branch": SOURCE_BRANCH, "revision": revision}
    with marker.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")


def git_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_LFS_SKIP_SMUDGE": "1",
    })
    return env


def git_readonly(args: list[str], timeout: float = 20) -> str:
    binary = shutil.which("git")
    if not binary:
        raise InstallError("Git is missing; install the git package before updating.")
    try:
        result = subprocess.run([binary, *args], capture_output=True,
                                text=True, check=False, timeout=timeout,
                                env=git_environment(), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("Read-only Git check failed: " + type(exc).__name__) from exc
    if result.returncode:
        raise InstallError("Read-only Git check failed: " +
                           (result.stderr or result.stdout or "Unknown Git error").strip()[-MAX_REPORT:])
    return result.stdout.strip()


def remote_revision() -> str:
    output = git_readonly(["ls-remote", "--heads", SOURCE_URL, SOURCE_BRANCH], timeout=30)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "refs/heads/" + SOURCE_BRANCH and REV_RE.fullmatch(parts[0]):
            return parts[0]
    raise InstallError("Official DeckCheatz main branch returned no verifiable Git revision")


def inspect_managed_checkout(path: Path) -> str:
    meta = managed_metadata(path)
    if meta is None:
        raise InstallError("This DeckCheatz checkout was not installed by GameWeld; updates will not overwrite it.")
    local = git_readonly(["-C", str(path), "rev-parse", "HEAD"])
    if local != meta["revision"]:
        raise InstallError("Managed DeckCheatz revision differs from its install record; update blocked.")
    origin = git_readonly(["-C", str(path), "remote", "get-url", "origin"])
    if origin != SOURCE_URL:
        raise InstallError("Managed DeckCheatz Git origin changed; update blocked.")
    changes = git_readonly(["-C", str(path), "status", "--porcelain", "--untracked-files=normal"])
    for line in changes.splitlines():
        # The intentionally untracked metadata file does not count as source edits.
        if line[3:] != MANAGED_MARKER:
            raise InstallError("Managed DeckCheatz source contains local changes; update blocked to protect user data.")
    return local


def running_launcher(path: Path) -> bool:
    """Best-effort refusal to update while the managed upstream launcher runs."""
    wanted = ((str(path / "wemod")).encode(), (str(path / "src/wemod.py")).encode())
    try:
        with os.scandir("/proc") as items:
            for item in items:
                if not item.name.isdecimal() or int(item.name) == os.getpid():
                    continue
                try:
                    if item.stat().st_uid != os.getuid():
                        continue
                    argv = (Path(item.path) / "cmdline").read_bytes()[:65536].split(b"\0")
                    if any(token in wanted for token in argv):
                        return True
                except (OSError, PermissionError):
                    continue
    except OSError:
        return False
    return False


def check_update() -> dict:
    current = status()
    target = install_directory()
    meta = managed_metadata(target)
    if meta is None:
        return {"result": "not_managed" if current["installed"] else "not_installed",
                "message": "Only check updates for managed DeckCheatz installs.",
                **current}
    old = inspect_managed_checkout(target)
    latest = remote_revision()
    return {
        "result": "update_available" if latest != old else "up_to_date",
        "installed_revision": old, "upstream_revision": latest,
        "update_available": latest != old,
        **current,
    }


def update() -> dict:
    parent = install_directory().parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = parent / ".deckcheatz-install.lock"
    with lock_path.open("a+") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = install_directory()
        old = inspect_managed_checkout(target)
        if running_launcher(target):
            raise InstallError("DeckCheatz is running; close WeMod and its launcher before updating.")
        latest = remote_revision()
        if old == latest:
            return {"result": "up_to_date", "installed_revision": old, **status()}
        staging_parent = Path(tempfile.mkdtemp(prefix=".deckcheatz-staging-", dir=parent))
        backup = parent / (".deckcheatz-backup-" + old[:12] + "-" + str(time.time_ns()))
        try:
            checkout = staging_parent / "checkout"
            new = _clone_to(checkout)
            if new == old:
                return {"result": "up_to_date", "installed_revision": old, **status()}
            write_managed_metadata(checkout, new)
            # Verify that no outside actor changed the old checkout while
            # staging the replacement.
            if inspect_managed_checkout(target) != old or running_launcher(target):
                raise InstallError("Managed checkout changed or was launched during update; refusing replacement.")
            target.rename(backup)
            try:
                checkout.rename(target)
                if inspect_managed_checkout(target) != new:
                    raise InstallError("Replacement checkout could not be verified after activation")
            except Exception:
                # Preserve the failed replacement for inspection if possible,
                # but always prefer bringing the previously working copy back.
                if target.exists():
                    failed = staging_parent / "failed-checkout"
                    target.rename(failed)
                backup.rename(target)
                raise
            return {"result": "updated", "previous_revision": old,
                    "upstream_revision": new, "rollback_path": str(backup), **status()}
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)


def status() -> dict:
    detected = provider().inspect_available()
    target = install_directory()
    meta = managed_metadata(target)
    return {
        "managed_install": meta is not None,
        "installed_revision": meta.get("revision", "") if meta else "",
        "update_policy": "manual_opt_in_with_rollback",
        "provider": "DeckCheatz/wemod-launcher",
        "manager": "GameWeld managed optional external checkout",
        "mode": "read_only",
        "installed": detected["available_count"] > 0,
        "available_count": detected["available_count"],
        "checkouts": detected["checkouts"],
        "managed_path": str(target),
        "managed_path_occupied": target.exists() or target.is_symlink(),
        "source_repository": SOURCE_URL,
        "source_branch": SOURCE_BRANCH,
        "dependencies": dependencies(),
        "modifies_steam_launch_options": False,
        "game_or_trainer_launched": False,
    }


def _clone_to(staging: Path) -> str:
    git = shutil.which("git")
    if not git:
        raise InstallError("Git is missing. Install the git package and retry in GameWeld.")
    # Isolate Git configuration to avoid locally configured smudge filters,
    # templates/hooks and interactive credential helpers during checkout.
    env = git_environment()
    args = [git, "-c", "init.templateDir=/dev/null",
            "-c", "core.hooksPath=/dev/null",
            "clone", "--depth", "1", "--single-branch", "--branch",
            SOURCE_BRANCH, "--", SOURCE_URL, str(staging)]
    try:
        result = subprocess.run(
            args, text=True, capture_output=True, check=False,
            timeout=150, env=env, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallError("Official DeckCheatz checkout timed out; retry with a working network.") from exc
    except OSError as exc:
        raise InstallError("Cannot execute Git: " + str(exc)) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()[-MAX_REPORT:]
        raise InstallError("Official DeckCheatz clone failed: " + detail)
    # Branch name is pinned to 'main', NOT 'rewrite/v2'; the actual upstream
    # commit is recorded so users know which external version was installed.
    try:
        rev = subprocess.run(
            [git, "-C", str(staging), "rev-parse", "--verify", "HEAD"],
            text=True, capture_output=True, timeout=15, check=True, env=env,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InstallError("Git checkout has no verifiable commit ID") from exc
    if len(rev) != 40 or not all(c in "0123456789abcdef" for c in rev.lower()):
        raise InstallError("Git returned an invalid checkout revision")
    try:
        provider().inspect_launcher(staging / "wemod")
    except (ValueError, OSError) as exc:
        raise InstallError("Downloaded checkout failed DeckCheatz 1.x layout checks: " + str(exc)) from exc
    return rev


def install() -> dict:
    parent = install_directory().parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = parent / ".deckcheatz-install.lock"
    with lock_path.open("a+") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        # A pre-existing supported checkout takes priority, including an
        # existing user-selected installation elsewhere. Do not overwrite it.
        before = status()
        if before["installed"]:
            return {"result": "already_installed", **before}
        target = install_directory()
        if target.exists() or target.is_symlink():
            raise InstallError(
                "The managed DeckCheatz folder already exists but is not a valid "
                "1.x checkout. GameWeld will not delete or overwrite user data: "
                + str(target))
        staging_parent = Path(tempfile.mkdtemp(prefix=".deckcheatz-staging-", dir=parent))
        try:
            checkout = staging_parent / "checkout"
            revision = _clone_to(checkout)
            write_managed_metadata(checkout, revision)
            # The destination has been held absent for the entire locked
            # transaction; os.rename is atomic within this data directory.
            if target.exists() or target.is_symlink():
                raise InstallError("Another install created the managed DeckCheatz folder")
            checkout.rename(target)
        finally:
            shutil.rmtree(staging_parent, ignore_errors=True)
        result = status()
        if not result["installed"]:
            raise InstallError("Checkout installation finished but provider validation failed")
        return {"result": "installed", "upstream_revision": revision, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="read-only installed checkout inspection")
    mode.add_argument("--install", action="store_true", help="clone the official external 1.x checkout")
    mode.add_argument("--check-update", action="store_true", help="query latest upstream commit without modifying install")
    mode.add_argument("--update", action="store_true", help="opt-in managed checkout update with backup rollback")
    parser.add_argument("--confirm", action="store_true", help="explicit GUI/user permission to install or update")
    args = parser.parse_args()
    if args.confirm and not (args.install or args.update):
        parser.error("--confirm is only valid with --install or --update")
    if (args.install or args.update) and not args.confirm:
        parser.error("External download/update requires explicit --confirm")
    try:
        report = (install() if args.install else
                  update() if args.update else
                  check_update() if args.check_update else status())
        print(json.dumps(report, indent=2))
        return 0
    except (InstallError, OSError) as exc:
        print(json.dumps({
            "result": "failed", "error": str(exc),
            "modifies_steam_launch_options": False,
            "game_or_trainer_launched": False,
        }, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
