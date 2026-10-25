#!/usr/bin/env python3
"""Offline tests of the conservative GameWeld ELF dependency report."""
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("pc2-audit-runtime-closure.py")
spec = importlib.util.spec_from_file_location("pc2_runtime_closure", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class RuntimeClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "usr/bin"
        self.bin.mkdir(parents=True)
        for name in ("gameweld", "wand-native-backend"):
            (self.bin / name).write_bytes(b"test fixture")
    def test_missing_dynamic_library_remains_unbundled(self):
        with patch.object(audit, "dependencies", return_value=["libgtk-3.so.0", "libc.so.6"]):
            report = audit.inspect(self.root)
        self.assertFalse(report["direct_elf_closure_satisfied"])
        self.assertEqual(report["unbundled_dependencies"], ["libgtk-3.so.0"])
        self.assertFalse(report["portable"])
    def test_host_only_dependencies_do_not_count_as_gaps(self):
        with patch.object(audit, "dependencies", return_value=["libc.so.6", "libm.so.6"]):
            report = audit.inspect(self.root)
        self.assertTrue(report["direct_elf_closure_satisfied"])
        self.assertFalse(report["portable"])
    def test_bundled_soname_satisfies_direct_dependency(self):
        libdir = self.root / "usr/lib"
        libdir.mkdir()
        (libdir / "libexample.so.1").write_bytes(b"test fixture")
        with patch.object(audit, "dependencies", side_effect=lambda p: ["libexample.so.1"] if p.parent == self.bin else []):
            report = audit.inspect(self.root)
        self.assertTrue(report["direct_elf_closure_satisfied"])
    def test_missing_executable_blocks_closure(self):
        (self.bin / "wand-native-backend").unlink()
        with patch.object(audit, "dependencies", return_value=[]):
            report = audit.inspect(self.root)
        self.assertFalse(report["direct_elf_closure_satisfied"])
        self.assertEqual(len(report["missing_executables"]), 1)

if __name__ == "__main__":
    unittest.main()
