#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic evidence-contract tests. Never starts Wine or a Windows process."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).with_name("gameweld-wand-v2-win32-evidence.py")
spec = importlib.util.spec_from_file_location("gameweld_win32_evidence", SOURCE)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class Win32EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix_parent = self.root / "compatdata/3008130"
        self.prefix = self.prefix_parent / "pfx"
        (self.prefix / "dosdevices").mkdir(parents=True)
        self.steam = self.root / "steam_library"
        self.executable = self.steam / "steamapps/common/Example/Game.exe"
        self.executable.parent.mkdir(parents=True)
        self.executable.write_bytes(b"MZ")
        (self.prefix / "dosdevices/z:").symlink_to(self.steam, target_is_directory=True)
        self.anchor = {
            "appid": 3008130,
            "state": "linux_runtime_anchor_stable",
            "anchored_linux_pid": 185951,
            "anchored_process_start_ticks": 12945298,
            "linux_process_identity_stable": True,
            "same_prefix_wineserver_observed": True,
            "samples_completed": 3,
        }
        self.observer = {
            "appid": 3008130,
            "game_started_by_monitor": False,
            "candidate_count": 1,
            "linux_game_pid": 185951,
            "linux_game_start_ticks": 12945298,
            "win32_game_pid": 524,
            "win32_game_executable": r"Z:\steamapps\common\Example\Game.exe",
        }

    def inspect(self, **changes):
        return audit.compare_observer_claim(
            3008130, self.prefix_parent, self.executable,
            dict(self.anchor), dict(self.observer, **changes))

    def test_valid_file_and_anchor_correlate_only_candidate(self):
        r = self.inspect()
        self.assertEqual(r["state"], "observer_candidate_evidence_correlated")
        self.assertTrue(r["linux_game_identity_correlated"])
        self.assertTrue(r["observer_path_correlated"])
        self.assertTrue(r["observer_win32_pid_reported"])
        self.assertFalse(r["win32_pid_verified"])
        self.assertFalse(r["trainer_attachment_verified"])
        self.assertFalse(r["monitor_authenticated"])
        self.assertFalse(r["trainer_cleanup_verified"])

    def test_wrong_observer_appid_rejected(self):
        self.assertEqual(self.inspect(appid=7)["reason"],
                         "observer_game_or_candidate_mismatch")

    def test_multiple_win32_candidates_rejected(self):
        self.assertEqual(self.inspect(candidate_count=2)["reason"],
                         "observer_game_or_candidate_mismatch")

    def test_direct_game_launch_claim_rejected(self):
        self.assertEqual(self.inspect(game_started_by_monitor=True)["reason"],
                         "observer_game_or_candidate_mismatch")

    def test_missing_direct_game_launch_field_rejected(self):
        observer = dict(self.observer)
        del observer["game_started_by_monitor"]
        self.assertEqual(audit.compare_observer_claim(
            3008130, self.prefix_parent, self.executable,
            self.anchor, observer)["reason"], "observer_game_or_candidate_mismatch")

    def test_mismatched_linux_pid_rejected(self):
        self.assertEqual(self.inspect(linux_game_pid=1)["reason"],
                         "observer_linux_session_mismatch")

    def test_mismatched_linux_start_ticks_rejected(self):
        self.assertEqual(self.inspect(linux_game_start_ticks=100)["reason"],
                         "observer_linux_session_mismatch")

    def test_zero_win32_pid_rejected(self):
        self.assertEqual(self.inspect(win32_game_pid=0)["reason"],
                         "win32_process_id_not_reported")

    def test_boolean_win32_pid_rejected(self):
        self.assertEqual(self.inspect(win32_game_pid=True)["reason"],
                         "win32_process_id_not_reported")

    def test_different_existing_game_file_rejected(self):
        other = self.steam / "steamapps/common/Example/Other.exe"
        other.write_bytes(b"MZ")
        self.assertEqual(self.inspect(
            win32_game_executable=r"Z:\steamapps\common\Example\Other.exe"
        )["reason"], "observer_game_executable_mismatch")

    def test_parent_traversal_rejected(self):
        self.assertIsNone(audit.drive_path_to_existing_file(
            self.prefix, r"Z:\steamapps\common\..\Example\Game.exe"))

    def test_unc_path_rejected(self):
        self.assertIsNone(audit.drive_path_to_existing_file(
            self.prefix, r"\\server\share\Game.exe"))

    def test_relative_windows_path_rejected(self):
        self.assertIsNone(audit.drive_path_to_existing_file(
            self.prefix, r"steamapps\common\Example\Game.exe"))

    def test_missing_drive_mapping_rejected(self):
        self.assertIsNone(audit.drive_path_to_existing_file(
            self.prefix, r"Y:\steamapps\common\Example\Game.exe"))

    def test_symlink_escape_rejected(self):
        outside = self.root / "secret.exe"
        outside.write_bytes(b"MZ")
        link = self.steam / "steamapps/common/Example/escaped.exe"
        link.symlink_to(outside)
        self.assertIsNone(audit.drive_path_to_existing_file(
            self.prefix, r"Z:\steamapps\common\Example\escaped.exe"))

    def test_stale_linux_anchor_rejected(self):
        self.anchor["state"] = "steam_session_context_candidate"
        self.assertEqual(self.inspect()["reason"],
                         "linux_anchor_not_fully_revalidated")

    def test_missing_wineserver_evidence_rejected(self):
        self.anchor["same_prefix_wineserver_observed"] = False
        self.assertEqual(self.inspect()["reason"],
                         "linux_anchor_not_fully_revalidated")

    def test_missing_three_samples_rejected(self):
        self.anchor["samples_completed"] = 2
        self.assertEqual(self.inspect()["reason"],
                         "linux_anchor_not_fully_revalidated")

    def test_invalid_compatdata_rejected(self):
        wrong = self.root / "compatdata/3008131"
        wrong.mkdir(parents=True)
        r = audit.compare_observer_claim(
            3008130, wrong, self.executable, self.anchor, self.observer)
        self.assertEqual(r["reason"], "inconsistent_selected_paths")

    def test_no_provenance_is_not_attachment_authorization(self):
        r = self.inspect()
        for forbidden in ("win32_pid_verified", "exact_runtime_verified",
                          "monitor_authenticated", "monitor_attached",
                          "trainer_launched", "trainer_attachment_verified",
                          "trainer_cleanup_verified", "steam_configuration_written"):
            self.assertIs(r[forbidden], False)
        self.assertEqual(r["processes_signalled"], 0)

    def test_wrong_observer_payload_type_rejected(self):
        r = audit.compare_observer_claim(
            3008130, self.prefix_parent, self.executable, self.anchor, ["wrong"])
        self.assertEqual(r["state"], "observer_evidence_rejected")


if __name__ == "__main__":
    unittest.main()
