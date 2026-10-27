#!/usr/bin/env python3
"""Synthetic Steam compatdata fixtures for the opt-in rejected ZIP quick try."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SRC = Path(__file__).with_name("gameweld-quick-try-prefix.py")
spec = importlib.util.spec_from_file_location("gw_prefix_quick_try", SRC)
assert spec and spec.loader
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)

NO_GAME = lambda appid, current: None


class QuickTryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-quick-try-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.steamapps = self.root / "Steam/steamapps"
        self.current = self.steamapps / "compatdata/123"
        (self.current / "pfx/drive_c").mkdir(parents=True)
        (self.current / "pfx/user.reg").write_bytes(b"ORIGINAL REGISTRY")
        (self.current / "version").write_text("GE-Proton10.1")
        (self.steamapps / "appmanifest_123.acf").write_text('"appid" "123"')
        self.cache = self.root / "cache/gameweld/prepared-wemod"
        self.rejected = self.cache / "rejected"
        self.rejected.mkdir(parents=True, mode=0o700)
        self.cache.chmod(0o700)
        self.rejected.chmod(0o700)
        self.zip = self.create_zip()

    def create_zip(self, *, extra=None):
        pair_entries = [(name, (b"A" * (5 + i))) for i, group in enumerate(
            sorted(trial.EXPECTED_GROUPS, key=lambda x: sorted(x)[0]))
            for name in sorted(group)]
        payloads = pair_entries + [
            ("pfx/user.reg", b"REPLACED IN TEST ONLY"),
            ("pfx/.wemod_installer", b"TEST"),
        ]
        if extra:
            payloads.extend(extra)
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_STORED) as archive:
            for filename, data in payloads:
                archive.writestr(filename, data)
        content = mem.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        src = self.rejected / (digest + ".zip")
        src.write_bytes(content)
        (self.rejected / (digest + ".rejected.json")).write_text(json.dumps({
            "sha256": digest, "bytes": len(content),
            "source": "DeckCheatz/BuiltPrefixes-dev",
            "release_tag": "PfxVer10.1", "asset_name": "GE-Proton10.1.zip",
            "status": "REJECTED_NOT_STAGEABLE",
        }))
        return src

    def call_prepare(self, **kwargs):
        return trial.prepare("123", self.steamapps, self.cache,
                             acknowledge_closed=True, accept=True,
                             idle_checker=NO_GAME, **kwargs)

    def call_restore(self):
        return trial.restore("123", self.steamapps,
                             acknowledge_closed=True, accept=True,
                             idle_checker=NO_GAME)

    def test_complete_prepare_and_restore_preserve_original_contents(self):
        first = self.call_prepare()
        backup = self.current.parent / ".gameweld-original-123"
        tested = self.current.parent / ".gameweld-tested-123"
        self.assertEqual(first["result"], "TEST_PREFIX_ACTIVE")
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"REPLACED IN TEST ONLY")
        self.assertEqual((backup / "pfx/user.reg").read_bytes(), b"ORIGINAL REGISTRY")
        self.assertEqual((self.current / "version").read_text(), "GE-Proton10.1")
        for group in trial.EXPECTED_GROUPS:
            for name in group:
                self.assertTrue((self.current / name).exists())
        with self.assertRaisesRegex(trial.QuickTryBlocked, "quick try exists"):
            self.call_prepare()
        restored = self.call_restore()
        self.assertEqual(restored["result"], "ORIGINAL_PREFIX_RESTORED")
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(), b"ORIGINAL REGISTRY")
        self.assertEqual((tested / "pfx/user.reg").read_bytes(),
                         b"REPLACED IN TEST ONLY")
        self.assertEqual(self.zip.stat().st_size, len(self.zip.read_bytes()))
        self.assertFalse(backup.exists())

    def test_requires_explicit_user_approvals(self):
        with self.assertRaisesRegex(trial.QuickTryBlocked, "approvals"):
            trial.prepare("123", self.steamapps, self.cache,
                          acknowledge_closed=True, accept=False,
                          idle_checker=NO_GAME)
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")

    def test_rejects_unknown_filename_conflicts(self):
        self.zip.unlink()
        old_receipts = list(self.rejected.glob("*.rejected.json"))
        for f in old_receipts: f.unlink()
        self.zip = self.create_zip(extra=[
            ("pfx/FOO", b"A"),
            ("pfx/foo", b"B"),
        ])
        with self.assertRaisesRegex(trial.QuickTryBlocked, "collision inventory"):
            self.call_prepare()
        self.assertFalse((self.current.parent / ".gameweld-original-123").exists())
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")

    def test_rejects_malicious_zip_traversal_without_any_swap(self):
        self.zip.unlink()
        for f in self.rejected.glob("*.rejected.json"): f.unlink()
        self.zip = self.create_zip(extra=[("../ESCAPE", b"BAD")])
        with self.assertRaisesRegex(trial.QuickTryBlocked, "ZIP failed"):
            self.call_prepare()
        self.assertFalse((self.root / "ESCAPE").exists())
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")

    def test_refuses_unexpected_overlay_symlink_without_modifying_original(self):
        (self.current / "pfx/drive_c/windows").symlink_to(self.root)
        with self.assertRaisesRegex(trial.QuickTryBlocked, "symlink"):
            self.call_prepare()
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")
        self.assertFalse((self.current.parent / ".gameweld-original-123").exists())

    def test_status_distinguishes_active_game_from_unknown_processes(self):
        active = {
            "state": "ACTIVE", "matching_process_count": 2,
            "matching_processes": [101, 102],
            "unreadable_same_user_processes": 0,
        }
        with patch.object(trial, "process_report", return_value=active):
            status = trial.status_report("123", self.steamapps)
            self.assertEqual(status["matching_pids"], [101, 102])
            self.assertFalse(status["can_attempt_prepare"])
            self.assertIn("2 process(es) still reference", status["verdict"])
            self.assertIn("101", status["verdict"])
            with self.assertRaisesRegex(trial.QuickTryBlocked, "Matching PIDs: 101, 102"):
                trial.check_idle("123", self.current)
        unknown = {
            "state": "UNKNOWN", "matching_process_count": 0,
            "matching_processes": [], "unreadable_same_user_processes": 3,
        }
        with patch.object(trial, "process_report", return_value=unknown):
            status = trial.status_report("123", self.steamapps)
            self.assertFalse(status["can_attempt_prepare"])
            self.assertIn("3 same-user process(es) could not be", status["verdict"])
            self.assertIn("does NOT prove", status["verdict"])
            with self.assertRaisesRegex(trial.QuickTryBlocked, "state UNKNOWN"):
                trial.check_idle("123", self.current)
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")
        self.assertFalse((self.current.parent / ".gameweld-original-123").exists())

    def test_status_reports_candidate_only_when_processes_readable_and_no_backup(self):
        idle = {"state": "IDLE_CANDIDATE", "matching_process_count": 0,
                "matching_processes": [], "unreadable_same_user_processes": 0}
        with patch.object(trial, "process_report", return_value=idle):
            status = trial.status_report("123", self.steamapps)
            self.assertTrue(status["can_attempt_prepare"])
            self.assertFalse(status["prefix_modified"])
            trial.check_idle("123", self.current)
            (self.current.parent / ".gameweld-original-123").mkdir()
            status = trial.status_report("123", self.steamapps)
            self.assertFalse(status["can_attempt_prepare"])
            self.assertTrue(status["original_backup_present"])
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")

    def test_explicit_unknown_override_is_narrow_and_active_cannot_override(self):
        unknown = {
            "state": "UNKNOWN", "matching_process_count": 0,
            "matching_processes": [], "unreadable_same_user_processes": 4,
        }
        with patch.object(trial, "process_report", return_value=unknown):
            status = trial.status_report("123", self.steamapps)
            self.assertTrue(status["experimental_unknown_override_available"])
            self.assertFalse(status["can_attempt_prepare"])
            with self.assertRaisesRegex(trial.QuickTryBlocked, "state UNKNOWN"):
                trial.check_idle("123", self.current)
            trial.check_idle("123", self.current, allow_unreadable=True)
        for refusal in (
            {"state": "ACTIVE", "matching_process_count": 1,
             "matching_processes": [4141], "unreadable_same_user_processes": 4},
            {"state": "UNKNOWN", "matching_process_count": 0,
             "matching_processes": [], "unreadable_same_user_processes": 9},
            {"state": "UNKNOWN", "matching_process_count": 0,
             "matching_processes": [], "unreadable_same_user_processes": 0},
            {"state": "IDLE_CANDIDATE", "matching_process_count": 1,
             "matching_processes": [202], "unreadable_same_user_processes": 0},
        ):
            with self.subTest(refusal=refusal), \
                 patch.object(trial, "process_report", return_value=refusal):
                self.assertFalse(trial.may_override_unknown(refusal))
                with self.assertRaises(trial.QuickTryBlocked):
                    trial.check_idle("123", self.current, allow_unreadable=True)
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(), b"ORIGINAL REGISTRY")

    def test_unknown_override_still_backups_and_restores(self):
        unknown = {
            "state": "UNKNOWN", "matching_process_count": 0,
            "matching_processes": [], "unreadable_same_user_processes": 4,
        }
        with patch.object(trial, "process_report", return_value=unknown):
            with self.assertRaisesRegex(trial.QuickTryBlocked, "state UNKNOWN"):
                trial.prepare("123", self.steamapps, self.cache,
                              acknowledge_closed=True, accept=True)
            first = trial.prepare(
                "123", self.steamapps, self.cache,
                acknowledge_closed=True, accept=True,
                allow_unreadable=True)
            self.assertTrue(first["unknown_process_override_used"])
            self.assertIn("--accept-unreadable-process-risk", first["restore"])
            backup = self.current.parent / ".gameweld-original-123"
            self.assertEqual((backup / "pfx/user.reg").read_bytes(), b"ORIGINAL REGISTRY")
            self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                             b"REPLACED IN TEST ONLY")
            with self.assertRaisesRegex(trial.QuickTryBlocked, "state UNKNOWN"):
                trial.restore("123", self.steamapps,
                              acknowledge_closed=True, accept=True)
            restored = trial.restore(
                "123", self.steamapps,
                acknowledge_closed=True, accept=True,
                allow_unreadable=True)
            self.assertEqual(restored["result"], "ORIGINAL_PREFIX_RESTORED")
            self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                             b"ORIGINAL REGISTRY")
            self.assertEqual(
                (self.current.parent / ".gameweld-tested-123/pfx/user.reg").read_bytes(),
                b"REPLACED IN TEST ONLY")
        self.assertFalse((self.current.parent / ".gameweld-original-123").exists())

    def test_positive_active_during_second_check_never_swaps(self):
        reports = [
            {"state": "UNKNOWN", "matching_process_count": 0,
             "matching_processes": [], "unreadable_same_user_processes": 4},
            {"state": "ACTIVE", "matching_process_count": 1,
             "matching_processes": [4141], "unreadable_same_user_processes": 0},
        ]
        with patch.object(trial, "process_report", side_effect=reports):
            with self.assertRaisesRegex(trial.QuickTryBlocked, "Matching PIDs: 4141"):
                trial.prepare("123", self.steamapps, self.cache,
                              acknowledge_closed=True, accept=True,
                              allow_unreadable=True)
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")
        self.assertFalse((self.current.parent / ".gameweld-original-123").exists())
        self.assertEqual(list(self.current.parent.glob(".gameweld-preparing-*")), [])

    def test_no_matching_appmanifest_blocks_before_swap(self):
        (self.steamapps / "appmanifest_123.acf").unlink()
        with self.assertRaisesRegex(trial.QuickTryBlocked, "manifest"):
            self.call_prepare()
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")


if __name__ == "__main__":
    unittest.main()
