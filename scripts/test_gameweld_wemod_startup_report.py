#!/usr/bin/env python3
"""Offline privacy and failure-category tests for no-options WeMod startup."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-wemod-startup-report.py")
spec = importlib.util.spec_from_file_location("gw_wemod_startup_report", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WeModStartupReportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "gameweld/wemod-live"
        self.root.mkdir(parents=True)
        self.appid = "3008130"

    def log(self, stamp, content):
        path = self.root / f"{self.appid}-{stamp}.log"
        path.write_bytes(content)
        return path

    def test_latest_selected_game_and_private_categories(self):
        older = self.log("1793192433761672761", b"old log\n")
        newest = self.log("1793192433761672762",
                          b"Proton: runinprefix failed to initialize: /PRIVATE\n"
                          b"FileNotFoundError: secret TOKEN_DO_NOT_SHARE\n"
                          b"Electron GPU process error_code=43\n"
                          b"WeMod.exe\n")
        os.utime(older, ns=(1, 1))
        os.utime(newest, ns=(2, 2))
        selected = mod.choose_log(self.appid, self.root)
        self.assertEqual(selected, newest)
        outcome = mod.summarize(self.appid, selected)
        self.assertEqual(outcome["steam_appid"], self.appid)
        self.assertTrue(outcome["failure_category_counts"]["missing_file_or_dll"])
        self.assertTrue(outcome["failure_category_counts"]["electron_gpu_or_vulkan_problem"])
        self.assertFalse(outcome["raw_log_content_included"])
        self.assertFalse(outcome["wemod_window_verified"])
        self.assertFalse(outcome["trainer_attachment_verified"])
        self.assertNotIn("PRIVATE", str(outcome))
        self.assertNotIn("TOKEN_DO_NOT_SHARE", str(outcome))
        self.assertNotIn(str(self.root), json.dumps(outcome))

    def test_game_specific_selection_and_symlink_not_trusted(self):
        other = self.root / "9999999-1793192433761672762.log"
        other.write_text("error")
        with self.assertRaisesRegex(mod.Blocked, "No GameWeld"):
            mod.choose_log(self.appid, self.root)
        target = self.root / "not-own-log"
        target.write_text("private")
        link = self.root / f"{self.appid}-1793192433761672762.log"
        link.symlink_to(target)
        with self.assertRaisesRegex(mod.Blocked, "No GameWeld"):
            mod.choose_log(self.appid, self.root)
        with self.assertRaisesRegex(mod.Blocked, "symlinked"):
            mod.summarize(self.appid, link)

    def test_no_crash_for_empty_and_unrecognized_log(self):
        log = self.log("1793192433761672762", b"ordinary startup text\n")
        out = mod.summarize(self.appid, log)
        self.assertEqual(out["failure_category_counts"], {})
        self.assertFalse(out["wemod_window_verified"])

    def test_v2_log_root_is_separate_from_old_live_handoff(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"XDG_STATE_HOME": home}):
                self.assertEqual(mod.default_log_root(v2=True),
                                 Path(home) / "wand/sessions")
                self.assertEqual(mod.default_log_root(),
                                 Path(home) / "gameweld/wemod-live")
                session_dir = mod.default_log_root(v2=True)
                session_dir.mkdir(parents=True)
                artifact = session_dir / "3008130-1793192433761672762.log"
                artifact.write_bytes(b"Proton: runinprefix error\\n")
                result = mod.summarize("3008130", mod.choose_log("3008130", session_dir))
                self.assertTrue(result["failure_category_counts"]["other_failure_keyword"])
                self.assertFalse(result["raw_log_content_included"])

    def test_repeated_gpu_errors_reported_only_as_fixed_categories(self):
        log = self.log("1793192433761672762",
                       (b"[ERROR:gpu_process_host.cc] GPU process launch failed: error_code=99 SECRET=one\n"
                        b"[ERROR:gpu_process_host.cc] GPU process launch failed: error_code=99 SECRET=two\n"
                        b"[FATAL:gpu_data_manager_impl_private.cc] GPU process isn't usable. Goodbye.\n"))
        out = mod.summarize("3008130", log)
        self.assertEqual(out["gpu_failure_signature_counts"]["gpu_process_launch_failed"], 2)
        self.assertEqual(out["gpu_failure_signature_counts"]["gpu_process_not_usable"], 1)
        self.assertTrue(out["category_counts_may_overlap_or_repeat"])
        self.assertFalse(out["raw_log_content_included"])
        self.assertNotIn("SECRET", str(out))
        self.assertNotIn("error_code=99", str(out))

    def test_invalid_appid_and_size_fail_closed(self):
        good = self.log("1793192433761672762", b"error\n")
        with self.assertRaisesRegex(mod.Blocked, "Invalid Steam AppID"):
            mod.summarize("not_a_number", good)
        with self.assertRaisesRegex(mod.Blocked, "Invalid Steam AppID"):
            mod.summarize("4294967296", good)
        with good.open("wb") as stream:
            stream.truncate(mod.MAX_LOG_BYTES + 1)
        with self.assertRaisesRegex(mod.Blocked, "size"):
            mod.summarize(self.appid, good)


if __name__ == "__main__":
    unittest.main()
