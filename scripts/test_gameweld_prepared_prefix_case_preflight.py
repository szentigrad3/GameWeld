#!/usr/bin/env python3
"""Offline tests for case-preserving quarantine compatibility preflight."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SOURCE = Path(__file__).with_name("gameweld-prepared-prefix-case-preflight.py")
spec = importlib.util.spec_from_file_location("gameweld_case_preflight", SOURCE)
assert spec and spec.loader
case = importlib.util.module_from_spec(spec)
spec.loader.exec_module(case)


class CaseCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-case-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "user/gameweld/prepared-wemod"
        self.rejected = self.root / "rejected"
        self.rejected.mkdir(parents=True, mode=0o700)
        self.root.chmod(0o700)
        self.rejected.chmod(0o700)
        self.game = self.home / "steamapps/compatdata/361420/pfx"
        self.game.mkdir(parents=True)
        (self.game / "system.reg").write_bytes(b"PRESERVE-GAME-REG")
        self.fixture = [
            ("pfx/drive_c/windows/InstallUtil.exe", b"binary-version-A"),
            ("pfx/drive_c/windows/installutil.exe", b"binary-other-version"),
            ("pfx/drive_c/windows/CONFIG/machine.config", b"one"),
            ("pfx/drive_c/windows/Config/machine.config", b"other"),
        ]

    def store(self, entries=None):
        entries = self.fixture if entries is None else entries
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as z:
            for name, payload in entries:
                z.writestr(name, payload)
        raw = output.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        archive = self.rejected / (sha + ".zip")
        archive.write_bytes(raw)
        (self.rejected / (sha + ".rejected.json")).write_text(json.dumps({
            "sha256": sha, "bytes": len(raw),
            "source": "DeckCheatz/BuiltPrefixes-dev",
            "status": "REJECTED_NOT_STAGEABLE",
            "asset_name": "GE-Proton10.1.zip",
            "release_tag": "PfxVer10.1",
        }))
        return archive

    def assert_no_game_changes(self):
        self.assertEqual((self.game / "system.reg").read_bytes(),
                         b"PRESERVE-GAME-REG")
        self.assertFalse((self.root / "staging").exists())
        self.assertFalse((self.root / "downloads").exists())

    def test_read_only_inventory_classifies_two_case_variants(self):
        archive = self.store()
        content = archive.read_bytes()
        out = case.report(self.root)
        self.assertIn("Distinct case-ambiguous path groups: 2", out)
        self.assertIn("Groups with different sizes: 2", out)
        self.assertIn("Host filesystem not tested", out)
        self.assertIn("STILL REJECTED", out)
        self.assertEqual(archive.read_bytes(), content)
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.assert_no_game_changes()

    def test_host_filesystem_synthetic_probe_preserves_exact_case(self):
        self.store()
        out = case.report(self.root, test_host=True)
        # CI runners normally have case-sensitive Linux temporary filesystems.
        self.assertIn("Host file case-preservation: PASS", out)
        self.assertIn("Host directory case-preservation: PASS", out)
        self.assertIn("Wine/Proton lookup behavior is still UNVERIFIED", out)
        self.assertEqual(list(self.root.glob(".case-probe-*")), [])
        self.assert_no_game_changes()

    def test_no_receipt_means_no_archive_inspection(self):
        archive = self.store()
        archive.with_suffix(".rejected.json").unlink()
        with self.assertRaisesRegex(case.CasePreflightRefused, "receipt"):
            case.report(self.root)
        self.assert_no_game_changes()

    def test_multiple_rejects_refuse_arbitrary_selection(self):
        self.store()
        self.store([("pfx/x", b"new")])
        with self.assertRaisesRegex(case.CasePreflightRefused, "Exactly one"):
            case.report(self.root)
        self.assert_no_game_changes()

    def test_root_inside_game_prefix_is_refused(self):
        self.store()
        unsafe = self.game / "gameweld/prepared-wemod"
        unsafe.mkdir(parents=True)
        with self.assertRaisesRegex(case.CasePreflightRefused, "unavailable or unsafe"):
            case.cache_root_ok(unsafe)
        self.assert_no_game_changes()


if __name__ == "__main__":
    unittest.main()
