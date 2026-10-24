#!/usr/bin/env python3
"""Disposable read-only fixtures for 0.1.41 old crypt32 recovery audit."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
import zipfile
import sys

SRC = Path(__file__).with_name("pc2-wand-crypt32-recovery-audit.py")
spec = importlib.util.spec_from_file_location("pc2_wand_crypt32_audit", SRC)
auditmod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = auditmod
spec.loader.exec_module(auditmod)


class ReadOnlyRecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-crypt32-audit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data64 = b"MZ" + b"validated test x64" * 200
        self.data32 = b"MZ" + b"validated test i386" * 200
        self.expected = {
            "x86_64-windows": hashlib.sha256(self.data64).hexdigest(),
            "i386-windows": hashlib.sha256(self.data32).hexdigest(),
        }
        self.patch_expected = patch.object(auditmod, "EXPECTED", self.expected)
        self.patch_expected.start()
        self.addCleanup(self.patch_expected.stop)

    def test_source_rc_archive_is_patch_only(self):
        src = self.root / "wand-native-0.1.41-rc3-source.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("wand-native-0.1.41/patches/wine-crypt32-cert-sha256-prop.patch",
                       "+case CERT_SHA256_HASH_PROP_ID:")
        report = auditmod.audit([self.root])
        self.assertIn("SOURCE PATCH ONLY", report)
        self.assertIn("NO COMPLETE PROVEN COMPILED DLL PAIR FOUND", report)
        self.assertTrue(src.is_file(), "Audit should not modify source archive")

    def test_installed_mismatched_dlls_are_reported_not_changed(self):
        tool = self.root / "GE-Proton-Wand-SHA256"
        dll64 = tool / "files/lib/wine/x86_64-windows/crypt32.dll"
        dll64.parent.mkdir(parents=True)
        dll64.write_bytes(b"MZ" + b"not patched")
        report = auditmod.audit([self.root])
        self.assertIn("DIFFERENT DLL:", report)
        self.assertIn(hashlib.sha256(dll64.read_bytes()).hexdigest(), report)
        self.assertIn("Verified x86_64-windows candidates: 0", report)
        self.assertEqual(dll64.read_bytes(), b"MZ" + b"not patched")

    def test_one_archive_with_both_proven_payloads_is_found_readonly(self):
        archive = self.root / "wand-native-0.1.41-linux_x86_64.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("wand-native-0.1.41/payload/crypt32/x86_64-windows/crypt32.dll",
                       self.data64)
            z.writestr("wand-native-0.1.41/payload/crypt32/i386-windows/crypt32.dll",
                       self.data32)
        report = auditmod.audit([self.root])
        self.assertIn("RESULT: BOTH HISTORICALLY PROVEN DLLS LOCATED", report)
        self.assertIn(str(archive), report)
        self.assertIn("Verified i386-windows candidates: 1", report)
        self.assertFalse((self.root / "wand-native-0.1.41").exists(),
                         "Inspection must not extract into the directory")

    def test_direct_verified_dlls_are_reported(self):
        payload = self.root / "payload/crypt32"
        for arch, content in (("x86_64-windows", self.data64),
                              ("i386-windows", self.data32)):
            path = payload / arch / "crypt32.dll"
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
        report = auditmod.audit([self.root])
        self.assertIn("RESULT: BOTH HISTORICALLY PROVEN DLLS LOCATED", report)
        self.assertIn("PROVEN DLL:", report)

    def test_unrelated_archive_not_unpacked_or_opened(self):
        archive = self.root / "random-game-pack.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("x86_64-windows/crypt32.dll", self.data64)
        report = auditmod.audit([self.root])
        self.assertIn("Candidate files/archives examined: 0", report)
        self.assertIn("NO COMPLETE PROVEN COMPILED DLL PAIR", report)

if __name__ == "__main__":
    unittest.main()
