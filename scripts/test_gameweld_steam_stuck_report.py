#!/usr/bin/env python3
"""Read-only tests for stalled Steam wrapper diagnostics."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-steam-stuck-report.py")
spec = importlib.util.spec_from_file_location("gw_stall_report_tests", SOURCE)
assert spec and spec.loader
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class StalledSteamReportTests(unittest.TestCase):
    def test_only_recognizes_expected_launcher_and_not_arbitrary_process(self):
        self.assertEqual(report.kind_from_cmdline(
            [b"/usr/bin/python3", b"/home/test/steam-session.py",
             b"run", b"--appid", b"3008130"]), "gameweld_one_shot_steam_shim")
        self.assertEqual(report.kind_from_cmdline(
            [b"/home/test/wemod"]), "deckcheatz_or_wemod")
        self.assertEqual(report.kind_from_cmdline(
            [b"/some/proton", b"waitforexitandrun"]), "proton")
        self.assertIsNone(report.kind_from_cmdline(
            [b"/usr/bin/bash", b"sleep", b"100"]))

    def test_log_counts_errors_but_does_not_export_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wemod.log"
            path.write_text("SECRET123 TOKEN abc\nTraceback\nTkinter failed to start\n")
            sample = report.log_indicators(path)
            self.assertTrue(sample["found"])
            self.assertEqual(sample["error_indicators"]["traceback"], 1)
            self.assertEqual(sample["error_indicators"]["tkinter"], 1)
            self.assertNotIn("SECRET123", str(sample))
            bad = Path(directory) / "alias"
            bad.symlink_to(path)
            self.assertFalse(report.log_indicators(bad)["found"])

    def test_invalid_appids_are_rejected_without_proc_scans(self):
        for appid in ("", "3008130;shutdown", "-42", "4294967296"):
            with self.subTest(appid=appid):
                with self.assertRaisesRegex(ValueError, "Invalid Steam AppID"):
                    report.diagnose(appid, Path("/missing"))

if __name__ == "__main__":
    unittest.main()
