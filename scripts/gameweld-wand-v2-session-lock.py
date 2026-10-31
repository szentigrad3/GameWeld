#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Non-destructive, per-AppID session ownership lock for GameWeld v2.

The lock file lives in a private per-user runtime directory.  It does not
change Steam Launch Options, a game's compatdata, or any game/WeMod process.
Locks are advisory: GameWeld callers must use this module to participate.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import stat
import tempfile


class SessionLockError(RuntimeError):
    pass


def private_runtime_dir(runtime_dir: Path | None = None) -> Path:
    uid = os.geteuid()
    if runtime_dir is None:
        supplied = os.environ.get("XDG_RUNTIME_DIR")
        if supplied:
            runtime_dir = Path(supplied)
        else:
            # Private, fixed per-UID fallback, never a process-unique temp dir.
            runtime_dir = Path(tempfile.gettempdir()) / f"gameweld-v2-{uid}"
    runtime_dir = Path(runtime_dir)
    try:
        if not runtime_dir.exists():
            runtime_dir.mkdir(mode=0o700)
        info = runtime_dir.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid:
            raise SessionLockError("unsafe_session_runtime_directory")
        # A public or shared directory must not host our locks. The user
        # owns the dir; no process should be able to substitute its locks.
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise SessionLockError("session_runtime_directory_not_private")
        return runtime_dir
    except (OSError, ValueError) as exc:
        raise SessionLockError("session_runtime_directory_unavailable") from exc


def acquire_session_lock(appid: int, runtime_dir: Path | None = None) -> int:
    """Return an owned fd with LOCK_EX; caller closes it in all code paths.

    Intentionally never unlinks the lock file: unlinking can cause two
    unrelated processes to lock different inodes under the same path.
    """
    if type(appid) is not int or not 1 <= appid <= 9999999999:
        raise SessionLockError("invalid_session_appid")
    base = private_runtime_dir(runtime_dir)
    lock_file = base / f"gameweld-wand-v2-{appid}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_file, flags, 0o600)
    except OSError as exc:
        raise SessionLockError("session_lock_unavailable") from exc
    try:
        meta = os.fstat(fd)
        link = lock_file.lstat()
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or stat.S_IMODE(meta.st_mode) != 0o600
                or link.st_dev != meta.st_dev or link.st_ino != meta.st_ino
                or not stat.S_ISREG(link.st_mode)):
            raise SessionLockError("unsafe_session_lock_file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SessionLockError("duplicate_gameweld_session") from exc
        # Ensure original pathname still references the inode locked.
        check = lock_file.lstat()
        if check.st_ino != meta.st_ino or check.st_dev != meta.st_dev:
            raise SessionLockError("session_lock_path_changed")
        return fd
    except (OSError, SessionLockError):
        os.close(fd)
        raise


def release_session_lock(fd: int) -> None:
    """Release only GameWeld's owned descriptor. No signalling or unlinking."""
    if type(fd) is not int or fd < 0:
        raise SessionLockError("invalid_session_lock_descriptor")
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
