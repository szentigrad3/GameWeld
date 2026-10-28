#!/usr/bin/env python3
"""Offline, read-only tests for GameWeld live/exit session comparison."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-steam-session-compare.py")
spec = importlib.util.spec_from_file_location("gw_session_compare_test", SOURCE)
assert spec and spec.loader
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class SteamSessionCompareTests(unittest.TestCase):
    def reports(self):
        base = {
            "steam_appid": "3008130", "mode": "read_only",
            "lifecycle": {
                "game_executable_candidates": 1,
                "total_appid_associated_processes": 27,
            },
            "recognized_launcher_processes": [
                {"pid": 1, "kind": "gameweld_one_shot_steam_shim"},
                {"pid": 2, "kind": "deckcheatz_or_wemod"},
            ],
            "saved_steam_launch_options": {
                "state": "gameweld_one_shot_shim_saved",
                "raw_option_text_included": False,
            },
            "pending_one_shot": {"state": "no_pending_token"},
            "deckcheatz_logs": [{
                "size_bytes": 34307, "modified_utc": "2026-10-28T11:58:31+00:00",
                "error_indicators": {"file not found": 4, "failed to": 12, "error:": 22},
            }],
        }
        import copy
        live, after = copy.deepcopy(base), copy.deepcopy(base)
        after["lifecycle"] = {
            "game_executable_candidates": 0,
            "total_appid_associated_processes": 0,
        }
        after["recognized_launcher_processes"] = [
            {"pid": 3, "kind": "proton"},  # not proven to be selected game
        ]
        after["deckcheatz_logs"] = [{
            "size_bytes": 37092, "modified_utc": "2026-10-28T11:59:01+00:00",
            "error_indicators": {"file not found": 4, "failed to": 15, "error:": 26},
        }]
        return live, after

    def test_realistic_appid_processes_clear_without_claiming_attachment(self):
        live, after = self.reports()
        outcome = compare.compare(live, after)
        self.assertEqual(outcome["result"],
                         "game_executable_observed_and_appid_associations_cleared")
        self.assertEqual(outcome["appid_associated_processes_live"], 27)
        self.assertEqual(outcome["appid_associated_processes_after_exit"], 0)
        self.assertFalse(outcome["game_window_verified"])
        self.assertFalse(outcome["wemod_trainer_attachment_verified"])
        self.assertFalse(outcome["all_wemod_processes_terminated_verified"])
        self.assertEqual(outcome["launcher_observation_scope"],
                         "same_user_only_not_appid_specific")
        self.assertEqual(outcome["launcher_processes_after_exit"]["proton"], 1)
        changes = outcome["deckcheatz_log_changes"]
        self.assertEqual(changes["bytes_added_between_snapshots"], 2785)
        self.assertEqual(changes["historical_keyword_count_changes"]["failed to"], 3)
        self.assertEqual(changes["historical_keyword_count_changes"]["error:"], 4)
        self.assertNotIn("/home", str(outcome))
        self.assertTrue(changes["raw_log_lines_included"] is False)

    def test_exact_appid_evidence_only_when_present_in_both_snapshots(self):
        live, after = self.reports()
        live["selected_appid_launcher_processes"] = [
            {"pid": 1, "kind": "gameweld_one_shot_steam_shim",
             "exact_appid_environment_observed": True},
            {"pid": 2, "kind": "deckcheatz_or_wemod",
             "exact_appid_environment_observed": True},
        ]
        after["selected_appid_launcher_processes"] = []
        outcome = compare.compare(live, after)
        self.assertEqual(outcome["launcher_observation_scope"],
                         "exact_same_user_appid_environment_matches")
        self.assertEqual(outcome["launcher_processes_live"]["deckcheatz_or_wemod"], 1)
        self.assertEqual(outcome["launcher_processes_after_exit"], {})
        self.assertFalse(outcome["wemod_trainer_attachment_verified"])

    def test_fails_closed_on_different_appid_or_invalid_lifecycle(self):
        live, after = self.reports()
        after["steam_appid"] = "999999"
        with self.assertRaisesRegex(compare.CompareBlocked, "same valid"):
            compare.compare(live, after)
        after["steam_appid"] = "3008130"
        after["lifecycle"]["total_appid_associated_processes"] = True
        with self.assertRaisesRegex(compare.CompareBlocked, "Incomplete"):
            compare.compare(live, after)

    def test_log_truncation_is_not_mislabeled_as_improvement(self):
        live, after = self.reports()
        after["deckcheatz_logs"][0]["size_bytes"] = 100
        outcome = compare.compare(live, after)
        self.assertEqual(outcome["deckcheatz_log_changes"]["state"],
                         "log_replaced_truncated_or_unverifiable")

    def test_bounded_interval_classifies_errors_without_leaking_raw_log(self):
        live, after = self.reports()
        prefix = b"historical private log content\n"
        interval = (b"FileNotFoundError: /home/secret/DO_NOT_SHARE missing DLL\n"
                    b"Failed to attach WeMod to the game process\n"
                    b"ConnectionError: HTTPS download failed TOKEN=PRIVATE\n"
                    b"Traceback (most recent call last):\n")
        live["deckcheatz_logs"][0]["size_bytes"] = len(prefix)
        after["deckcheatz_logs"][0]["size_bytes"] = len(prefix) + len(interval)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wemod.log"
            path.write_bytes(prefix + interval + b"later session not in scope\n")
            outcome = compare.analyze_deckcheatz_interval(live, after, path)
        self.assertEqual(outcome["bytes_examined"], len(interval))
        self.assertGreaterEqual(outcome["lines_with_failure_keywords"], 3)
        self.assertGreater(outcome["error_line_category_counts"]["wemod_or_trainer"], 0)
        self.assertGreater(outcome["error_line_category_counts"]["filesystem_or_permission"], 0)
        self.assertEqual(outcome["allowlisted_exception_type_counts"]["FileNotFoundError"], 1)
        self.assertFalse(outcome["source_bytes_were_unchanged_since_snapshots_verified"])
        self.assertFalse(outcome["raw_log_content_included"])
        self.assertNotIn("DO_NOT_SHARE", str(outcome))
        self.assertNotIn("TOKEN=PRIVATE", str(outcome))

    def test_upstream_stage_markers_and_failure_signatures_are_allowlisted(self):
        live, after = self.reports()
        content = (b"Communicating with the process\n"
                   b"Process finished\n"
                   b"Error while loading the wine server waiter: /PRIVATE_DATA\n"
                   b"Failed to unpack prefix: /SENSITIVE_PATH\n"
                   b"ERR:\n"
                   b"Exit command with 1\n")
        live["deckcheatz_logs"][0]["size_bytes"] = 0
        after["deckcheatz_logs"][0]["size_bytes"] = len(content)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wemod.log"
            path.write_bytes(content)
            outcome = compare.analyze_deckcheatz_interval(live, after, path)
        self.assertEqual(outcome["known_upstream_failure_signature_counts"]["wine_server_wait_error"], 1)
        self.assertEqual(outcome["known_upstream_failure_signature_counts"]["prefix_download_or_extraction_error"], 1)
        self.assertEqual(outcome["known_upstream_failure_signature_counts"]["unhandled_upstream_exception"], 1)
        self.assertEqual(outcome["observed_upstream_stage_markers_in_interval"]["game_process_wait_finished"], 1)
        self.assertEqual(outcome["observed_upstream_stage_markers_in_interval"]["upstream_troubleshooter_returned"], 1)
        self.assertFalse(outcome["absent_stage_markers_mean_stage_never_ran"])
        self.assertNotIn("PRIVATE_DATA", str(outcome))
        self.assertNotIn("SENSITIVE_PATH", str(outcome))

    def test_log_interval_refuses_symlinks_oversize_and_truncated_logs(self):
        live, after = self.reports()
        live["deckcheatz_logs"][0]["size_bytes"] = 0
        after["deckcheatz_logs"][0]["size_bytes"] = 10
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wemod.log"
            path.write_bytes(b"abc")
            with self.assertRaisesRegex(compare.CompareBlocked, "shorter"):
                compare.analyze_deckcheatz_interval(live, after, path)
            path.write_bytes(b"ten bytes!")
            alias = Path(tmp) / "alias"
            alias.symlink_to(path)
            with self.assertRaisesRegex(compare.CompareBlocked, "symlinked"):
                compare.analyze_deckcheatz_interval(live, after, alias)
            after["deckcheatz_logs"][0]["size_bytes"] = compare.MAX_LOG_SPAN_BYTES + 1
            with self.assertRaisesRegex(compare.CompareBlocked, "64 KiB"):
                compare.analyze_deckcheatz_interval(live, after, path)

    def test_snapshot_path_limit_symlink_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            saved = directory / "live.json"
            saved.write_text(json.dumps(self.reports()[0]))
            self.assertEqual(compare.read_snapshot(saved)["steam_appid"], "3008130")
            alias = directory / "alias"
            alias.symlink_to(saved)
            with self.assertRaisesRegex(compare.CompareBlocked, "symlinked"):
                compare.read_snapshot(alias)
            saved.write_bytes(b"{" + b"x" * (compare.MAX_JSON_BYTES + 1))
            with self.assertRaisesRegex(compare.CompareBlocked, "oversized"):
                compare.read_snapshot(saved)
            saved.write_bytes(b"{{")
            with self.assertRaisesRegex(compare.CompareBlocked, "invalid JSON"):
                compare.read_snapshot(saved)


if __name__ == "__main__":
    unittest.main()
