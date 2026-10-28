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
            self.assertIn("modified_utc", sample)
            self.assertGreaterEqual(sample["age_seconds_at_scan"], 0)
            self.assertIn("Historical log", sample["note"])
            self.assertEqual(sample["error_indicators"]["traceback"], 1)
            self.assertEqual(sample["error_indicators"]["tkinter"], 1)
            self.assertNotIn("SECRET123", str(sample))
            bad = Path(directory) / "alias"
            bad.symlink_to(path)
            self.assertFalse(report.log_indicators(bad)["found"])

    def test_saved_steam_option_state_redacts_custom_commands(self):
        from unittest.mock import patch
        class Options:
            @staticmethod
            def find_config(*_):
                return Path("/tmp/example_config"), "123"
            @staticmethod
            def launch_option(*_):
                return "PROTON_LOG=1 /home/example/steam-session.py run --appid 3008130 -- %command%"
        with patch.object(report, "peer", return_value=Options):
            result = report.saved_steam_option_state("3008130")
        self.assertEqual(result["state"], "gameweld_one_shot_shim_saved")
        self.assertEqual(result["placeholder_count"], 1)
        self.assertFalse(result["raw_option_text_included"])
        self.assertNotIn("PROTON_LOG", str(result))

    def test_pending_one_shot_status_reads_without_changing_token(self):
        import json
        import os
        import time
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gameweld/steam-session-tokens"
            root.mkdir(parents=True)
            target = root / "3008130.json"
            record = {"schema": 1, "appid": "3008130", "expiry": time.time() + 280,
                      "launcher": "/private/secret/wemod"}
            target.write_text(json.dumps(record))
            target.chmod(0o600)
            before = target.read_bytes()
            with patch.dict(os.environ, {"XDG_STATE_HOME": directory}):
                state = report.pending_one_shot_state("3008130")
            self.assertEqual(state["state"], "armed")
            self.assertNotIn("secret", str(state))
            self.assertEqual(target.read_bytes(), before)

    def test_invalid_appids_are_rejected_without_proc_scans(self):
        for appid in ("", "3008130;shutdown", "-42", "4294967296"):
            with self.subTest(appid=appid):
                with self.assertRaisesRegex(ValueError, "Invalid Steam AppID"):
                    report.diagnose(appid, Path("/missing"))

if __name__ == "__main__":
    unittest.main()
