#!/usr/bin/env python3
"""Offline safety tests for full-byte read-only quarantined ZIP integrity checks."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("gameweld-rejected-zip-integrity.py")
spec = importlib.util.spec_from_file_location("gw_rejected_integrity", SCRIPT)
assert spec and spec.loader
integrity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrity)


class RejectedZipIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gw-rejected-verify-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "private/gameweld/prepared-wemod"
        self.rejected = self.cache / "rejected"
        self.rejected.mkdir(parents=True, mode=0o700)
        self.cache.chmod(0o700)
        self.rejected.chmod(0o700)
        self.game = self.root / "steamapps/compatdata/111/pfx"
        self.game.mkdir(parents=True)
        (self.game / "user.reg").write_bytes(b"DO-NOT-CHANGE")

    def make_zip(self, *, traversal=False):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("pfx/Framework/InstallUtil.exe", b"UNIQUE-PAYLOAD-LOWER")
            z.writestr("pfx/Framework/installutil.exe", b"distinct-payload-upper")
            if traversal:
                z.writestr("../escape-file", b"INVALID")
        return buffer.getvalue()

    def store(self, content):
        sha = hashlib.sha256(content).hexdigest()
        path = self.rejected / (sha + ".zip")
        path.write_bytes(content)
        (self.rejected / (sha + ".rejected.json")).write_text(json.dumps({
            "sha256": sha, "bytes": len(content),
            "source": "DeckCheatz/BuiltPrefixes-dev",
            "status": "REJECTED_NOT_STAGEABLE",
            "asset_name": "GE-Proton10.1.zip", "release_tag": "PfxVer10.1",
        }))
        return path

    def assert_preserved(self):
        self.assertEqual((self.game / "user.reg").read_bytes(), b"DO-NOT-CHANGE")
        self.assertFalse((self.cache / "downloads").exists())
        self.assertFalse((self.cache / "staging").exists())
        self.assertFalse((self.root / "escape-file").exists())

    def test_matching_sha_and_crc_pass_without_promoting_or_extraction(self):
        data = self.make_zip()
        path = self.store(data)
        before = path.read_bytes()
        report = integrity.integrity_report(self.cache)
        self.assertIn("Local ZIP SHA-256: MATCHES", report)
        self.assertIn("ZIP CRC-32: PASS (2 members;", report)
        self.assertIn("Case-colliding member names: 1 — STILL BLOCKED", report)
        self.assertIn("staging, extraction to disk and installation: NOT AUTHORIZED", report)
        self.assertEqual(before, path.read_bytes())
        self.assert_preserved()

    def test_altered_bytes_are_rejected_by_sha256(self):
        path = self.store(self.make_zip())
        with path.open("ab") as f:
            f.write(b"changed")
        with self.assertRaisesRegex(integrity.IntegrityRefused, "size or type"):
            integrity.integrity_report(self.cache)
        self.assert_preserved()

    def test_crc_error_rejects_even_with_matching_local_digest_and_receipt(self):
        source = self.make_zip()
        self.assertEqual(source.count(b"UNIQUE-PAYLOAD-LOWER"), 1)
        corrupted = source.replace(b"UNIQUE-PAYLOAD-LOWER", b"BROKEN-PAYLOAD-LOWER", 1)
        self.assertEqual(len(corrupted), len(source))
        self.store(corrupted)  # filename SHA matches corrupt bytes but member CRC does not
        with self.assertRaisesRegex(integrity.IntegrityRefused, "CRC verification FAILED"):
            integrity.integrity_report(self.cache)
        self.assert_preserved()

    def test_noncollision_traversal_fails_despite_known_case_variants(self):
        self.store(self.make_zip(traversal=True))
        with self.assertRaisesRegex(integrity.IntegrityRefused, "CRC verification FAILED"):
            integrity.integrity_report(self.cache)
        self.assert_preserved()

    def test_multiple_rejected_zips_cannot_be_selected_automatically(self):
        self.store(self.make_zip())
        self.store(self.make_zip(traversal=True))
        with self.assertRaisesRegex(integrity.IntegrityRefused, "exactly one"):
            integrity.integrity_report(self.cache)
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
