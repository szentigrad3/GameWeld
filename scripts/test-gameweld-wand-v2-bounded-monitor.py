#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real child-process tests; never launches a game, Proton, Wine, or trainer."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = Path(__file__).with_name("gameweld-wand-v2-bounded-monitor.py")
spec = importlib.util.spec_from_file_location("gameweld_v2_bounded_monitor", SOURCE)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BoundedMonitorTests(unittest.TestCase):
    def invoke(self, script: str, *, limit=262144, timeout=5, extra_args=None):
        cmd = [sys.executable, "-c", script]
        if extra_args:
            cmd.extend(extra_args)
        return runner.run_monitor(cmd, dict(os.environ),
                                  timeout_seconds=timeout,
                                  max_stdout_bytes=limit)

    def test_successful_protocol_json(self):
        outcome = self.invoke("print('{\\\"state\\\":\\\"monitor_session_finished\\\"}')")
        self.assertEqual(outcome.returncode, 0)
        self.assertIn("monitor_session_finished", outcome.stdout)

    def test_nonzero_process_returncode_preserved(self):
        outcome = self.invoke("import sys; print('blocked'); sys.exit(7)")
        self.assertEqual(outcome.returncode, 7)
        self.assertEqual(outcome.stdout.strip(), "blocked")

    def test_empty_output_allowed_for_bridge_to_reject(self):
        outcome = self.invoke("pass")
        self.assertEqual(outcome.stdout, "")

    def test_output_limit_exceeded_fails_closed(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_output_limit_exceeded"):
            self.invoke("print('x' * 5000)", limit=1024)

    def test_large_stderr_not_captured(self):
        outcome = self.invoke(
            "import sys; sys.stderr.write('z'*100000); print('ok')", limit=1024)
        self.assertEqual(outcome.stdout.strip(), "ok")

    def test_timeout_terminates_owned_direct_child(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_timeout"):
            self.invoke("import time; time.sleep(10)", timeout=.1)

    def test_stdin_is_not_forwarded_from_gameweld(self):
        outcome = self.invoke("import sys; print(repr(sys.stdin.read()))")
        self.assertEqual(outcome.stdout.strip(), "''")

    def test_arguments_are_not_interpreted_by_shell(self):
        outcome = self.invoke("import sys; print(sys.argv[1])",
                              extra_args=["hello; echo unsafe"])
        self.assertEqual(outcome.stdout.strip(), "hello; echo unsafe")

    def test_invalid_executable_blocks(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_spawn_failed"):
            runner.run_monitor(["/does/not/exist/gameweld-monitor-executable"],
                               dict(os.environ), timeout_seconds=1)

    def test_bad_timeout_rejected(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_invalid_limits"):
            self.invoke("print('ok')", timeout=0)

    def test_negative_output_limit_rejected(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_invalid_limits"):
            self.invoke("print('ok')", limit=-1)

    def test_non_utf8_output_rejected(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_output_not_utf8"):
            self.invoke("import sys; sys.stdout.buffer.write(bytes([255]))")

    def test_output_exactly_limit_allowed(self):
        outcome = self.invoke("import sys; sys.stdout.write('x'*1024)", limit=1024)
        self.assertEqual(len(outcome.stdout), 1024)

    def test_output_stream_is_drained_beyond_limit(self):
        with self.assertRaisesRegex(runner.MonitorRunFailure,
                                    "upstream_monitor_output_limit_exceeded"):
            self.invoke("import sys; sys.stdout.write('z'*1000000)", limit=1024)

    def test_external_environment_passed_to_child(self):
        environment = dict(os.environ)
        environment["GAMEWELD_TEST_ONLY_VARIABLE"] = "safe"
        outcome = runner.run_monitor([sys.executable, "-c",
                                      "import os; print(os.getenv('GAMEWELD_TEST_ONLY_VARIABLE'))"],
                                     environment, timeout_seconds=5)
        self.assertEqual(outcome.stdout.strip(), "safe")


if __name__ == "__main__":
    unittest.main()
