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
import subprocess
import sys
import tempfile

SOURCE_URL = "https://github.com/DeckCheatz/wemod-launcher.git"
SOURCE_BRANCH = "main"
SUBDIR = "gameweld/deckcheatz"
MAX_REPORT = 3000


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


def status() -> dict:
    detected = provider().inspect_available()
    target = install_directory()
    return {
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
    env = os.environ.copy()
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_LFS_SKIP_SMUDGE": "1",
    })
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
    parser.add_argument("--confirm", action="store_true", help="explicit GUI/user permission to download")
    args = parser.parse_args()
    if args.confirm and not args.install:
        parser.error("--confirm is only valid with --install")
    if args.install and not args.confirm:
        parser.error("External download requires explicit --install --confirm")
    try:
        report = install() if args.install else status()
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
