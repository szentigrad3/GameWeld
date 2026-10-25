#!/usr/bin/env python3
"""Tests for the read-only WeMod live log audit."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parent / "gameweld-wemod-log-audit.py"
spec = importlib.util.spec_from_file_location("wemod_log_audit", FILE)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class WeModLogAuditTests(unittest.TestCase):
    def test_binary_safe_native_dll_and_gpu_summary(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "wand-live-2353250-123.log"
            path.write_bytes(
                b"GameWeld live\n"
                b"067c:trace:loaddll:build_module Loaded L\"Z:\\Wemod\\version.dll\" at 1234: native\n"
                b"\0\0\0"
                b"[724:1025/111033:ERROR:gpu_process_host.cc(975)] GPU process launch failed: error_code=43\n"
                b"[724:1025/111033:WARNING:gpu_process_host.cc(1418)] The GPU process has crashed 22782 time(s)\n"
            )
            report = audit.audit(path)
            self.assertIn("Embedded NUL bytes: 3", report)
            self.assertIn("GPU launch failure lines scanned: 1", report)
            self.assertIn("Last reported Chromium crash counter: 22782", report)
            self.assertIn("version.dll native loads: 1", report)
            self.assertIn("version.dll builtin loads: 0", report)
            self.assertIn("history may be incomplete", report)

    def test_newest_log_selects_per_launch_filename(self):
        with tempfile.TemporaryDirectory() as root:
            state = Path(root)
            (state / "wand-live-2353250.log").write_bytes(b"old")
            latest = state / "wand-live-2353250-99-123456.log"
            latest.write_bytes(b"new")
            # Explicit metadata ensures no scheduling race in the fixture.
            import os
            os.utime(state / "wand-live-2353250.log", ns=(1000, 1000))
            os.utime(latest, ns=(2000, 2000))
            self.assertEqual(audit.newest_log("2353250", state), latest)

    def test_rejects_missing_log(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                audit.newest_log("2353250", Path(root))


if __name__ == "__main__":
    unittest.main()
