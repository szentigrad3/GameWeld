#!/usr/bin/env python3
"""Non-mutating tests for source PC2's checked Steam handoff."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-steam-handoff.py")
spec = importlib.util.spec_from_file_location("gameweld_steam_handoff", SCRIPT)
assert spec and spec.loader
steam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(steam)


class SteamHandoffTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="gameweld-steam-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.command = self.bin / "steam"

    def fake_steam(self, body: str) -> None:
        self.command.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        self.command.chmod(0o755)

    def capture(self, *args, **kwargs):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = steam.run_launch(*args, **kwargs)
        return result, buffer.getvalue()

    def test_app_id_validation(self):
        for value in ("", "0", "01", " 1", "1;touch /tmp/x", "4294967296", "-1", "abc"):
            self.assertFalse(steam.valid_appid(value), value)
        self.assertTrue(steam.valid_appid("2353250"))
        self.assertTrue(steam.valid_appid("4294967295"))

    def test_launcher_missing_reports_failure(self):
        with patch("shutil.which", return_value=None):
            status, report = self.capture("2353250", duration=0)
        self.assertEqual(status, 3)
        self.assertIn("NOT FOUND", report)
        self.assertIn("Launch result: FAILED", report)

    def test_steam_nonzero_exit_reported(self):
        self.fake_steam("exit 27\n")
        status, report = self.capture("2353250", steam=str(self.command), duration=1.2)
        self.assertEqual(status, 3, report)
        self.assertIn("Steam command exit status: 27", report)
        self.assertIn("Launch result: FAILED", report)

    def test_zero_exit_does_not_claim_game_launched(self):
        self.fake_steam("exit 0\n")
        status, report = self.capture("2353250", steam=str(self.command), duration=0.6)
        self.assertEqual(status, 2, report)
        self.assertIn("Launch result: UNCONFIRMED", report)
        self.assertNotIn("STEAM_ASSOCIATION_OBSERVED", report)

    def test_steam_handoff_observes_exact_process_association(self):
        # This is a fake Steam child and a fake Linux process. No real game is
        # launched, and the presence of its env var is not proof of game identity.
        appid = "4294967294"
        self.fake_steam("exit 0\n")
        env = dict(os.environ, SteamAppId=appid)
        proc = subprocess.Popen(["sleep", "4"], env=env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            status, report = self.capture(appid, steam=str(self.command), duration=1)
            self.assertEqual(status, 0, report)
            self.assertIn("STEAM_ASSOCIATION_OBSERVED", report)
            self.assertIn("Game executable, visible window and trainer: NOT VERIFIED", report)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_cli_needs_confirm_and_invalid_appid_never_runs_steam(self):
        marker = self.root / "executed"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH","/usr/bin"))
        for arguments in (("launch", "--appid", "2353250"),
                          ("launch", "--appid", "2353250;sh", "--confirm")):
            result = subprocess.run([sys.executable, str(SCRIPT), *arguments],
                                    env=env, capture_output=True, text=True,
                                    timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_read_only_status_never_runs_steam(self):
        marker = self.root / "executed"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", "/usr/bin"))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "status", "--appid", "2353250"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Steam executable: FOUND", result.stdout)
        self.assertIn("No Steam command or trainer was launched.", result.stdout)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
