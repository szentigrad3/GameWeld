#!/usr/bin/env python3
"""Offline GameWeld synthetic transaction+rollback tests (no game mutations)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-transaction-rehearsal.py")
spec = importlib.util.spec_from_file_location("gameweld_transaction_rehearsal", SOURCE)
assert spec and spec.loader
txn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(txn)


class TransactionRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-transaction-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "gameweld/transaction-fixtures"
        self.root.mkdir(parents=True, mode=0o700)
        self.root.chmod(0o700)
        (self.root / ".gameweld-synthetic-fixture.json").write_text(
            json.dumps(txn.MARKER))
        (self.root / "prefix/drive_c").mkdir(parents=True)
        (self.root / "prefix/system.reg").write_bytes(b"KEEP ME")
        (self.root / "prefix/drive_c/account.dat").write_bytes(b"SAVED ACCOUNT")
        (self.root / "patch/drive_c").mkdir(parents=True)
        (self.root / "patch/drive_c/trainer-test.bin").write_bytes(b"TEST TRAINER")
        (self.root / "patch/system.reg").write_bytes(b"REPLACED SYNTHETIC REG")
        # Game simulations are separate directories outside the marked fixture.
        self.real_game_fixtures = [
            self.base / "steamapps/compatdata/361420/pfx",
            self.base / "Heroic/game-a/prefix",
            self.base / "Lutris/game-b/prefix",
        ]
        for game in self.real_game_fixtures:
            game.mkdir(parents=True)
            (game / "system.reg").write_bytes(b"DO NOT TOUCH")
        self.expected = self.snapshot()

    def snapshot(self):
        return [(str(p), (p / "system.reg").read_bytes())
                for p in self.real_game_fixtures]

    def run_tx(self, **kwargs):
        with patch.object(txn.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 2 * 1024 ** 3})()):
            return txn.apply_rehearsal(self.root, approved=kwargs.pop("approved", True),
                                       **kwargs)

    def test_apply_isolated_then_explicit_rollback_reverses_both_changes(self):
        outcome = self.run_tx()
        self.assertEqual(outcome["state"], "APPLIED")
        self.assertFalse(outcome["real_game_modified"])
        self.assertFalse(outcome["real_game_install_supported"])
        self.assertEqual((self.root / "prefix/system.reg").read_bytes(),
                         b"REPLACED SYNTHETIC REG")
        self.assertEqual((self.root / "prefix/drive_c/trainer-test.bin").read_bytes(),
                         b"TEST TRAINER")
        self.assertEqual((self.root / "prefix/drive_c/account.dat").read_bytes(),
                         b"SAVED ACCOUNT")
        data = txn.read_journal(self.root, outcome["id"])
        self.assertEqual(data["state"], "APPLIED")
        self.assertTrue((self.root / "transactions" / outcome["id"] / "original").exists())
        reverted = txn.rollback(self.root, outcome["id"])
        self.assertEqual(reverted["state"], "ROLLED_BACK")
        self.assertEqual((self.root / "prefix/system.reg").read_bytes(), b"KEEP ME")
        self.assertFalse((self.root / "prefix/drive_c/trainer-test.bin").exists())
        self.assertEqual((self.root / "prefix/drive_c/account.dat").read_bytes(),
                         b"SAVED ACCOUNT")
        self.assertEqual(self.snapshot(), self.expected)

    def test_all_injected_faults_restore_original_and_leave_recovery_journal(self):
        for phase in ("after_prepare", "after_original_move", "after_apply"):
            with self.subTest(phase=phase):
                with self.assertRaisesRegex(RuntimeError, phase):
                    self.run_tx(failure_at=phase)
                self.assertEqual((self.root / "prefix/system.reg").read_bytes(), b"KEEP ME")
                self.assertFalse((self.root / "prefix/drive_c/trainer-test.bin").exists())
                self.assertEqual((self.root / "prefix/drive_c/account.dat").read_bytes(),
                                 b"SAVED ACCOUNT")
                folders = list((self.root / "transactions").iterdir())
                self.assertTrue(all(
                    txn.read_journal(self.root, p.name)["state"] == "ROLLED_BACK"
                    for p in folders
                ))
                self.assertEqual(self.snapshot(), self.expected)

    def test_refuse_missing_consent_with_zero_writes(self):
        with self.assertRaisesRegex(txn.TransactionRefused, "Explicit"):
            self.run_tx(approved=False)
        self.assertFalse((self.root / "transactions").exists())
        self.assertEqual(self.snapshot(), self.expected)

    def test_invalid_marker_and_real_provider_path_blocked(self):
        marker = self.root / ".gameweld-synthetic-fixture.json"
        marker.write_text('{"kind":"real-prefix","schema":1}')
        with self.assertRaisesRegex(txn.TransactionRefused, "not a valid synthetic"):
            self.run_tx()
        marker.write_text(json.dumps(txn.MARKER))
        with self.assertRaisesRegex(txn.TransactionRefused, "existing GameWeld synthetic"):
            txn.apply_rehearsal(self.real_game_fixtures[0], approved=True)
        self.assertEqual(self.snapshot(), self.expected)

    def test_fixture_symlink_is_blocked(self):
        (self.root / "patch/drive_c/shortcut").symlink_to(self.real_game_fixtures[0],
                                                        target_is_directory=True)
        with self.assertRaisesRegex(txn.TransactionRefused, "links and special"):
            self.run_tx()
        self.assertFalse((self.root / "transactions").exists())
        self.assertEqual(self.snapshot(), self.expected)

    def test_unknown_transaction_and_path_escape_blocked(self):
        self.run_tx()
        with self.assertRaisesRegex(txn.TransactionRefused, "Invalid synthetic transaction"):
            txn.rollback(self.root, "../bad")
        with self.assertRaisesRegex(txn.TransactionRefused, "journal missing"):
            txn.rollback(self.root, "0" * 32)
        self.assertEqual(self.snapshot(), self.expected)

    def test_second_transaction_blocked_until_rollback(self):
        result = self.run_tx()
        with self.assertRaisesRegex(txn.TransactionRefused, "review or rollback"):
            self.run_tx()
        txn.rollback(self.root, result["id"])
        second = self.run_tx()
        self.assertEqual(second["state"], "APPLIED")
        self.assertNotEqual(second["id"], result["id"])
        self.assertEqual(self.snapshot(), self.expected)

    def test_not_enough_disk_prevents_transaction(self):
        with patch.object(txn.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5})()):
            with self.assertRaisesRegex(txn.TransactionRefused, "Insufficient"):
                txn.apply_rehearsal(self.root, approved=True)
        self.assertFalse((self.root / "transactions").exists())
        self.assertEqual(self.snapshot(), self.expected)

    def test_unexpected_symlinked_transaction_root_blocks(self):
        (self.root / "transactions").symlink_to(self.real_game_fixtures[0],
                                                target_is_directory=True)
        with self.assertRaisesRegex(txn.TransactionRefused, "journal root"):
            self.run_tx()
        self.assertEqual(self.snapshot(), self.expected)

    def test_hardlinked_fixture_file_blocks(self):
        os.link(self.root / "prefix/system.reg", self.root / "prefix/system-alias.reg")
        with self.assertRaisesRegex(txn.TransactionRefused, "hard-linked"):
            self.run_tx()
        self.assertEqual(self.snapshot(), self.expected)

    def test_detects_patch_changed_during_prepare_and_restores(self):
        previous = txn.shutil.copytree
        def swap_patch(source, target, *args, **kwargs):
            out = previous(source, target, *args, **kwargs)
            (self.root / "patch/drive_c/trainer-test.bin").write_bytes(b"TAMPERED")
            return out
        with patch.object(txn.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 2 * 1024 ** 3})()):
            with patch.object(txn.shutil, "copytree", side_effect=swap_patch):
                with self.assertRaisesRegex(txn.TransactionRefused, "changed"):
                    txn.apply_rehearsal(self.root, approved=True)
        self.assertEqual((self.root / "prefix/system.reg").read_bytes(), b"KEEP ME")
        self.assertEqual(self.snapshot(), self.expected)


if __name__ == "__main__":
    unittest.main()
