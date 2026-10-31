#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Linux-only tests of non-destructive GameWeld AppID session ownership."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).with_name("gameweld-wand-v2-session-lock.py")
spec = importlib.util.spec_from_file_location("gameweld_v2_lock", source)
assert spec and spec.loader
locks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locks)


class SessionLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name) / "only-owner"
        self.private.mkdir(mode=0o700)

    def get(self, appid=3008130):
        return locks.acquire_session_lock(appid, self.private)

    def test_first_session_acquires(self):
        fd = self.get()
        self.assertGreaterEqual(fd, 0)
        locks.release_session_lock(fd)

    def test_same_appid_second_session_blocked(self):
        fd = self.get()
        try:
            with self.assertRaisesRegex(locks.SessionLockError, "duplicate_gameweld_session"):
                self.get()
        finally:
            locks.release_session_lock(fd)

    def test_different_appid_sessions_independent(self):
        one = self.get(3008130)
        two = self.get(3008131)
        locks.release_session_lock(two)
        locks.release_session_lock(one)

    def test_released_lock_can_be_reacquired(self):
        first = self.get()
        locks.release_session_lock(first)
        second = self.get()
        locks.release_session_lock(second)

    def test_lock_file_is_never_removed_on_release(self):
        fd = self.get()
        path = self.private / "gameweld-wand-v2-3008130.lock"
        self.assertTrue(path.is_file())
        locks.release_session_lock(fd)
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_size, 0)

    def test_file_permissions_private(self):
        fd = self.get()
        path = self.private / "gameweld-wand-v2-3008130.lock"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        locks.release_session_lock(fd)

    def test_world_readable_lock_rejected(self):
        file = self.private / "gameweld-wand-v2-3008130.lock"
        file.write_text("")
        file.chmod(0o644)
        with self.assertRaisesRegex(locks.SessionLockError, "unsafe_session_lock_file"):
            self.get()

    def test_symlink_to_another_file_rejected(self):
        target = self.private / "unrelated"
        target.write_text("not a lock")
        path = self.private / "gameweld-wand-v2-3008130.lock"
        path.symlink_to(target)
        with self.assertRaisesRegex(locks.SessionLockError, "session_lock_unavailable"):
            self.get()
        self.assertEqual(target.read_text(), "not a lock")

    def test_world_readable_runtime_dir_rejected(self):
        self.private.chmod(0o755)
        with self.assertRaisesRegex(locks.SessionLockError, "session_runtime_directory_not_private"):
            self.get()

    def test_runtime_symlink_rejected(self):
        other = self.private / "other"
        other.mkdir(mode=0o700)
        linked = self.private / "link"
        linked.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(locks.SessionLockError, "unsafe_session_runtime_directory"):
            locks.acquire_session_lock(3008130, linked)

    def test_invalid_appid_zero(self):
        with self.assertRaisesRegex(locks.SessionLockError, "invalid_session_appid"):
            self.get(0)

    def test_invalid_appid_boolean(self):
        with self.assertRaisesRegex(locks.SessionLockError, "invalid_session_appid"):
            self.get(True)

    def test_invalid_appid_negative(self):
        with self.assertRaisesRegex(locks.SessionLockError, "invalid_session_appid"):
            self.get(-1)

    def test_invalid_fd_rejected(self):
        with self.assertRaisesRegex(locks.SessionLockError, "invalid_session_lock_descriptor"):
            locks.release_session_lock(-1)

    def test_nonempty_stale_file_does_not_invalidate_lock(self):
        # A stale file alone is not a held advisory lock; never parse a
        # stored PID from it or kill a process because of its contents.
        path = self.private / "gameweld-wand-v2-3008130.lock"
        path.write_text("999999\n")
        path.chmod(0o600)
        fd = self.get()
        locks.release_session_lock(fd)
        self.assertEqual(path.read_text(), "999999\n")

    def test_runtime_fallback_private(self):
        with patch.object(locks.tempfile, "gettempdir", return_value=str(self.private)):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("XDG_RUNTIME_DIR", None)
                d = locks.private_runtime_dir()
                self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
                self.assertEqual(d.stat().st_uid, os.geteuid())

    def test_existing_private_runtime_accepted(self):
        self.assertEqual(locks.private_runtime_dir(self.private), self.private)


if __name__ == "__main__":
    unittest.main()
