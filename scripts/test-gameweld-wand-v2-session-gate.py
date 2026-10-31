#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic tests of the GameWeld v2 Linux-game pre-handoff safety gate."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-wand-v2-session.py")
spec = importlib.util.spec_from_file_location("gameweld_wand_v2_session", SOURCE)
assert spec and spec.loader
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

TOKEN = "a" * 40


class BridgeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.compatdata = self.root / "compatdata/3008130"
        (self.compatdata / "pfx/drive_c").mkdir(parents=True)
        self.client = self.root / "WeMod.exe"
        self.client.write_bytes(b"test")
        self.game = self.root / "DyingLightGame_TheBeast_x64_rwdi.exe"
        self.game.write_bytes(b"MZfake")
        self.rewrite = self.root / "deckcheatz-v2"
        src = self.rewrite / "src/wand_launcher"
        src.mkdir(parents=True)
        (src / "entrypoint.py").write_text("# test\n")
        self.args = ["--appid", "3008130", "--compatdata", str(self.compatdata),
                     "--client", str(self.client), "--game-exe", str(self.game),
                     "--monitor-endpoint", "127.0.0.1:14444",
                     "--rewrite-root", str(self.rewrite)]

    def execute(self, gate=(False, "linux_game_anchor_not_stable"),
                token=TOKEN, endpoint=None, subprocess_result=None):
        args = list(self.args)
        if endpoint is not None:
            pos = args.index("--monitor-endpoint")
            args[pos + 1] = endpoint
        if subprocess_result is None:
            subprocess_result = SimpleNamespace(returncode=0, stdout=json.dumps({
                "state": "monitor_session_finished", "game_started": True,
                "trainer_process_started": True, "game_exit_code": 0,
                "trainer_cleanup_verified": True
            }))
        with patch.dict(os.environ, {"WAND_MONITOR_SESSION_TOKEN": token}), \
             patch.object(bridge, "verify_running_linux_game", return_value=gate) as verify, \
             patch.object(bridge, "execute_bounded_monitor", return_value=subprocess_result) as runner, \
             redirect_stdout(io.StringIO()) as capture:
            code = bridge.run(args)
        return code, json.loads(capture.getvalue()), verify, runner

    def test_linux_game_missing_refuses_upstream(self):
        code, obj, verify, runner = self.execute()
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "linux_game_anchor_not_stable")
        verify.assert_called_once()
        runner.assert_not_called()

    def test_linux_game_unreadable_refuses_upstream(self):
        _, obj, _, runner = self.execute(gate=(False, "linux_game_anchor_inspection_failed"))
        self.assertEqual(obj["reason"], "linux_game_anchor_inspection_failed")
        runner.assert_not_called()

    def test_stable_linux_gate_allows_existing_handoff(self):
        code, obj, _, runner = self.execute(gate=(True, "linux_game_anchor_stable"))
        self.assertEqual(code, 0)
        self.assertEqual(obj["state"], "gameweld_wand_v2_session_finished")
        self.assertFalse(obj["trainer_attachment_verified"])
        self.assertFalse(obj["trainer_cleanup_verified"])
        self.assertTrue(obj["upstream_trainer_cleanup_reported"])
        self.assertFalse(obj["steam_launch_options_changed"])
        runner.assert_called_once()
        self.assertIn("--observe-existing-game", runner.call_args.args[0])

    def test_session_does_not_inherit_monitor_without_token(self):
        code, obj, verify, runner = self.execute(
            gate=(True, "linux_game_anchor_stable"), token="")
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "monitor_token_missing")
        verify.assert_not_called()
        runner.assert_not_called()

    def test_bad_endpoint_refused_before_gate(self):
        code, obj, verify, runner = self.execute(
            gate=(True, "linux_game_anchor_stable"), endpoint="192.168.1.1:8899")
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "monitor_not_localhost")
        verify.assert_not_called()
        runner.assert_not_called()

    def test_missing_rewrite_source_refused(self):
        (self.rewrite / "src/wand_launcher/entrypoint.py").unlink()
        code, obj, verify, runner = self.execute(gate=(True, "linux_game_anchor_stable"))
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "deckcheatz_v2_source_missing")
        verify.assert_not_called()
        runner.assert_not_called()

    def test_upstream_failure_still_blocks(self):
        code, obj, _, runner = self.execute(
            gate=(True, "linux_game_anchor_stable"),
            subprocess_result=SimpleNamespace(returncode=2, stdout="{}"))
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "upstream_monitor_rejected")
        runner.assert_called_once()

    def test_unverified_cleanup_report_refused(self):
        code, obj, _, runner = self.execute(
            gate=(True, "linux_game_anchor_stable"),
            subprocess_result=SimpleNamespace(returncode=0, stdout=json.dumps({
                "state": "monitor_session_finished", "game_started": True,
                "trainer_process_started": True, "game_exit_code": 0,
                "trainer_cleanup_verified": False
            })))
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "upstream_trainer_cleanup_unverified")

    def test_upstream_report_malformed_refused(self):
        code, obj, _, _ = self.execute(
            gate=(True, "linux_game_anchor_stable"),
            subprocess_result=SimpleNamespace(returncode=0, stdout="not json"))
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "upstream_session_report_invalid")

    def test_upstream_cross_appid_claim_rejected(self):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({
            "state": "monitor_session_finished", "appid": 1234,
            "game_started": True, "trainer_process_started": True,
            "trainer_cleanup_verified": True, "game_exit_code": 0,
        }))
        code, report, _, runner = self.execute(
            gate=(True, "linux_game_anchor_stable"), subprocess_result=result)
        self.assertEqual(code, 2)
        self.assertEqual(report["reason"], "upstream_appid_mismatch")
        runner.assert_called_once()

    def test_upstream_direct_game_spawn_claim_rejected(self):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({
            "state": "monitor_session_finished", "appid": 3008130,
            "game_started": True, "trainer_process_started": True,
            "trainer_cleanup_verified": True, "game_exit_code": 0,
            "game_started_by_monitor": True,
        }))
        code, report, _, _ = self.execute(
            gate=(True, "linux_game_anchor_stable"), subprocess_result=result)
        self.assertEqual(code, 2)
        self.assertEqual(report["reason"], "upstream_unexpected_game_launch")

    def test_upstream_wrong_shape_rejected(self):
        code, report, _, _ = self.execute(
            gate=(True, "linux_game_anchor_stable"),
            subprocess_result=SimpleNamespace(returncode=0, stdout="[]"))
        self.assertEqual(code, 2)
        self.assertEqual(report["reason"], "upstream_session_report_invalid")

    def test_bounded_output_failure_refused(self):
        with patch.dict(os.environ, {"WAND_MONITOR_SESSION_TOKEN": TOKEN}), \
             patch.object(bridge, "verify_running_linux_game",
                          return_value=(True, "linux_game_anchor_stable")), \
             patch.object(bridge, "execute_bounded_monitor",
                          side_effect=RuntimeError("upstream_monitor_output_limit_exceeded")), \
             redirect_stdout(io.StringIO()) as capture:
            code = bridge.run(self.args)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(capture.getvalue())["reason"],
                         "upstream_monitor_output_limit_exceeded")

    def test_monitor_timeout_failure_refused(self):
        with patch.dict(os.environ, {"WAND_MONITOR_SESSION_TOKEN": TOKEN}), \
             patch.object(bridge, "verify_running_linux_game",
                          return_value=(True, "linux_game_anchor_stable")), \
             patch.object(bridge, "execute_bounded_monitor",
                          side_effect=RuntimeError("upstream_monitor_timeout")), \
             redirect_stdout(io.StringIO()) as capture:
            code = bridge.run(self.args)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(capture.getvalue())["reason"],
                         "upstream_monitor_timeout")

    def test_missing_compatdata_refused_without_launch(self):
        (self.compatdata / "pfx/drive_c").rmdir()
        code, obj, verify, runner = self.execute(gate=(True, "linux_game_anchor_stable"))
        self.assertEqual(code, 2)
        self.assertEqual(obj["reason"], "game_prefix_or_appid_mismatch")
        verify.assert_not_called()
        runner.assert_not_called()

    def test_live_gate_requires_three_samples_and_identity(self):
        good = dict(state="linux_runtime_anchor_stable", samples_completed=3,
                    linux_process_identity_stable=True, same_prefix_wineserver_observed=True,
                    anchored_linux_pid=58638, anchored_process_start_ticks=3641164)
        fresh = dict(state="linux_anchor_acquired", anchored_linux_pid=58638,
                     anchored_process_start_ticks=3641164)
        fake_module = SimpleNamespace(acquire_fresh_anchor=lambda *_: fresh,
                                      verify_anchor=lambda *_, **__: good)
        with patch.object(bridge, "_load_live_anchor", return_value=fake_module):
            self.assertEqual(bridge.verify_running_linux_game(3008130, self.compatdata, self.game),
                             (True, "linux_game_anchor_stable"))

    def test_live_gate_rejects_changed_anchor_after_samples(self):
        fresh = dict(state="linux_anchor_acquired", anchored_linux_pid=58638,
                     anchored_process_start_ticks=3641164)
        changed = dict(state="linux_runtime_anchor_stable", samples_completed=3,
                       linux_process_identity_stable=True, same_prefix_wineserver_observed=True,
                       anchored_linux_pid=58638, anchored_process_start_ticks=99999)
        fake_module = SimpleNamespace(acquire_fresh_anchor=lambda *_: fresh,
                                      verify_anchor=lambda *_, **__: changed)
        with patch.object(bridge, "_load_live_anchor", return_value=fake_module):
            self.assertEqual(bridge.verify_running_linux_game(3008130, self.compatdata, self.game),
                             (False, "linux_game_anchor_not_stable"))

    def test_live_gate_rejects_missing_wineserver(self):
        fresh = dict(state="linux_anchor_acquired", anchored_linux_pid=58638,
                     anchored_process_start_ticks=3641164)
        missing = dict(state="linux_runtime_anchor_stable", samples_completed=3,
                       linux_process_identity_stable=True, same_prefix_wineserver_observed=False,
                       anchored_linux_pid=58638, anchored_process_start_ticks=3641164)
        fake_module = SimpleNamespace(acquire_fresh_anchor=lambda *_: fresh,
                                      verify_anchor=lambda *_, **__: missing)
        with patch.object(bridge, "_load_live_anchor", return_value=fake_module):
            self.assertEqual(bridge.verify_running_linux_game(3008130, self.compatdata, self.game),
                             (False, "linux_game_anchor_not_stable"))

    def test_live_gate_rejects_load_error(self):
        with patch.object(bridge, "_load_live_anchor", side_effect=OSError("test")):
            self.assertEqual(bridge.verify_running_linux_game(3008130, self.compatdata, self.game),
                             (False, "linux_game_anchor_inspection_failed"))


if __name__ == "__main__":
    unittest.main()
