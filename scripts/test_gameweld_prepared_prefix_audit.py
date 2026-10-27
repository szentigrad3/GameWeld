#!/usr/bin/env python3
"""Offline safety regression tests for a provider-independent WeMod prefix ZIP."""
from __future__ import annotations

import importlib.util
import pathlib
import stat
import tempfile
import unittest
import zipfile

SOURCE = pathlib.Path(__file__).with_name("gameweld-prepared-prefix-audit.py")
spec = importlib.util.spec_from_file_location("gameweld_prepared_archive", SOURCE)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PreparedPrefixArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-prefix-audit-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.archive = self.root / "prepared.zip"

    def build(self, members, compression=zipfile.ZIP_DEFLATED):
        with zipfile.ZipFile(self.archive, "w", compression=compression) as file:
            for key, data in members:
                file.writestr(key, data)
        return self.archive

    def test_valid_archive_is_report_only_and_never_extracted(self):
        self.build([
            ("pfx/drive_c/windows/system32/test.dll", b"mock-dll-contents"),
            ("pfx/user.reg", b"WINE REGISTRY Version 2"),
        ])
        before = self.archive.read_bytes()
        out = audit.archive_report(self.archive)
        self.assertIn("Archive structural checks: PASS", out)
        self.assertIn("reusable prefix template cache for Steam, Heroic and Lutris", out)
        self.assertIn("Publisher integrity verification: NOT AVAILABLE", out)
        self.assertIn("Installation status: NOT AUTHORIZED", out)
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["prepared.zip"])

    def test_archive_with_traversal_windows_backslash_or_absolute_path_is_blocked(self):
        for i, entry in enumerate([
            "../outside.reg", "pfx/../outside.reg", "/etc/passwd",
            "C:/Windows/system.reg", r"pfx\..\user.reg", "pfx/AUX",
            "pfx/desktop.ini:stream", "pfx/foo. ", "pfx//double",
        ]):
            with self.subTest(entry=entry):
                self.build([(entry, b"x")])
                with self.assertRaises(audit.UnsafePreparedPrefix):
                    audit.archive_report(self.archive)

    def test_symlink_and_case_colliding_entries_blocked(self):
        link = zipfile.ZipInfo("pfx/drive_c/Users/owner")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.build([(link, b"../../other-place")])
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "Links"):
            audit.archive_report(self.archive)
        self.build([("pfx/drive_c/FILE", b"A"), ("pfx/drive_c/file", b"B")])
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "colliding"):
            audit.archive_report(self.archive)

    def test_compression_bomb_and_encryption_are_rejected(self):
        self.build([("pfx/data.bin", b"A" * (1024 * 1024))])
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "ratio"):
            audit.archive_report(self.archive)
        self.build([("pfx/ok.reg", b"not compressed" * 10)])
        with zipfile.ZipFile(self.archive) as file:
            item = file.infolist()[0]
            item.flag_bits |= 1
            with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "Encrypted"):
                audit.inspect_zip_members(file)

    def test_symlinked_input_and_invalid_zip_are_rejected(self):
        other = self.root / "other.zip"
        self.build([("pfx/user.reg", b"ok")])
        other.symlink_to(self.archive)
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "non-symlinked"):
            audit.archive_report(other)
        self.archive.write_bytes(b"not a zip")
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "invalid"):
            audit.archive_report(self.archive)

    def test_case_collision_comparison_distinguishes_identical_and_different_bytes(self):
        self.build([
            ("pfx/Framework/InstallUtil.exe", b"same-binary"),
            ("pfx/Framework/installutil.exe", b"same-binary"),
            ("pfx/Framework/CONFIG/machine.config", b"one"),
            ("pfx/Framework/Config/machine.config", b"two"),
        ], compression=zipfile.ZIP_STORED)
        original = self.archive.read_bytes()
        with zipfile.ZipFile(self.archive) as z:
            result = audit.compare_case_collision_bytes(z)
        self.assertEqual(result["identical_payload"], 1)
        self.assertEqual(result["different_payload"], 1)
        self.assertEqual(result["size_mismatch"], 0)
        self.assertEqual(result["comparison_skipped"], 0)
        self.assertEqual(self.archive.read_bytes(), original)

    def test_case_collision_comparison_skips_oversized_members_without_extraction(self):
        self.build([
            ("pfx/A", b"a" * 128),
            ("pfx/a", b"b" * 129),
        ], compression=zipfile.ZIP_STORED)
        with zipfile.ZipFile(self.archive) as z:
            result = audit.compare_case_collision_bytes(z)
        self.assertEqual(result["size_mismatch"], 1)
        self.assertFalse((self.root / "pfx").exists())

    def test_rejected_diagnostic_does_not_authorize_case_collision_staging(self):
        self.build([
            ("pfx/windows/InstallUtil.exe", b"actual"),
            ("pfx/windows/installutil.exe", b"different"),
        ], compression=zipfile.ZIP_STORED)
        before = self.archive.read_bytes()
        with zipfile.ZipFile(self.archive) as z:
            with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "colliding"):
                audit.inspect_zip_members(z)
            count, unpacked = audit.check_other_zip_safety_without_approving_collisions(z)
        self.assertEqual(count, 2)
        self.assertEqual(unpacked, len(b"actual") + len(b"different"))
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertFalse((self.root / "pfx").exists())

    def test_diagnostic_still_rejects_traversal_and_links_alongside_collisions(self):
        link = zipfile.ZipInfo("pfx/symlink")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for third, reason in ((("../escape", b"escape"), "Path traversal"),
                              ((link, b"other"), "Links")):
            with self.subTest(reason=reason):
                self.build([
                    ("pfx/InstallUtil.exe", b"real"),
                    ("pfx/installutil.exe", b"variant"),
                    third,
                ], compression=zipfile.ZIP_STORED)
                with zipfile.ZipFile(self.archive) as z:
                    with self.assertRaisesRegex(audit.UnsafePreparedPrefix, reason):
                        audit.check_other_zip_safety_without_approving_collisions(z)

    def test_supplied_digest_does_not_prove_publisher_authenticity(self):
        self.build([("pfx/user.reg", b"test-data")])
        import hashlib
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        matched = audit.archive_report(self.archive, expected_sha256=digest)
        self.assertIn("MATCHES supplied digest", matched)
        self.assertIn("publisher identity NOT verified", matched)
        mismatch = audit.archive_report(self.archive, expected_sha256="0" * 64)
        self.assertIn("MISMATCH — DO NOT INSTALL", mismatch)
        with self.assertRaisesRegex(audit.UnsafePreparedPrefix, "64 hex"):
            audit.archive_report(self.archive, expected_sha256="bad")

if __name__ == "__main__":
    unittest.main()
