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
        class Setup:
            saved = "PROTON_LOG=1 /home/example/steam-session.py run --appid 3008130 -- %command%"
            @staticmethod
            def read_config_bytes(_cfg):
                return b"sample"
            @classmethod
            def saved_option_value(cls, _raw, _appid, _options):
                return cls.saved
        def peer(name, label):
            return Options if name.endswith("preserve.py") else Setup
        with patch.object(report, "peer", side_effect=peer):
            result = report.saved_steam_option_state("3008130")
            self.assertEqual(result["state"], "gameweld_one_shot_shim_saved")
            self.assertEqual(result["placeholder_count"], 1)
            self.assertFalse(result["raw_option_text_included"])
            self.assertNotIn("PROTON_LOG", str(result))
            Setup.saved = None
            absent = report.saved_steam_option_state("3008130")
        self.assertEqual(absent["state"], "missing_saved_launch_options_field")
        self.assertIn("managed setup", absent["next_step"])
        self.assertFalse(absent["live_steam_cache_verified"])
        self.assertNotIn("/home/example", str(absent))

    def test_stuck_report_passes_the_requested_steam_root_to_compat_lookup(self):
        from unittest.mock import patch
        class Readiness:
            @staticmethod
            def saved_compatibility_bridge_state(appid, *, steam_root=None):
                self.assertEqual(appid, "3008130")
                self.assertEqual(steam_root, Path("/mnt/games/Steam"))
                return {"state": "no_exact_per_game_mapping",
                        "live_client_selection_verified": False}
        with patch.object(report, "peer", return_value=Readiness):
            state = report.saved_compatibility_tool_state(
                "3008130", Path("/mnt/games/Steam"))
        self.assertEqual(state["state"], "no_exact_per_game_mapping")

    def test_existing_prefix_runtime_is_labeled_historical_not_live(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "steamapps/compatdata/3008130"
            folder.mkdir(parents=True)
            (folder / "config_info").write_text("sample")
            tool = root / "steamapps/common/Proton - Experimental"
            tool.mkdir(parents=True)
            (tool / "proton").write_text("#!/bin/sh")
            class Resolver:
                @staticmethod
                def _compatdata_runtime_hint(_folder):
                    return "Proton - Experimental", str(tool)
            with patch.object(report, "peer", return_value=Resolver):
                result = report.last_prefix_runtime_hint("3008130", root)
            self.assertEqual(result["state"], "prefix_runtime_resolved")
            self.assertTrue(result["launcher_file_present"])
            self.assertFalse(result["current_steam_selection_verified"])
            self.assertNotIn(directory, str(result))

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
