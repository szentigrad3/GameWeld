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

    def test_no_matching_appmanifest_blocks_before_swap(self):
        (self.steamapps / "appmanifest_123.acf").unlink()
        with self.assertRaisesRegex(trial.QuickTryBlocked, "manifest"):
            self.call_prepare()
        self.assertEqual((self.current / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL REGISTRY")


if __name__ == "__main__":
    unittest.main()
