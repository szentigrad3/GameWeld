#!/usr/bin/env python3
"""Non-mutating tests for source PC2's checked Steam handoff."""
import contextlib
import importlib.util
import io
import gc
import os
import time
import warnings
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

    def test_read_only_details_identify_appid_helper_without_exposing_environment(self):
        proc = self.root / "proc"
        proc.mkdir()
        process = proc / "12345"
        process.mkdir()
        (process / "environ").write_bytes(
            b"SECRET_TOKEN=do-not-display\0SteamAppId=3008130\0")
        (process / "comm").write_text("steamwebhelper\n")
        (process / "exe").symlink_to("/opt/steam/steamwebhelper")
        self.assertEqual(steam.associated_process_count("3008130", str(proc)), 1)
        details = steam.associated_process_details("3008130", str(proc))
        self.assertEqual(details, [
            (12345, "steamwebhelper", "steamwebhelper", "steam_helper")])
        self.assertNotIn("do-not-display", repr(details))
        self.assertEqual(steam.associated_process_details("3008131", str(proc)), [])

    def test_read_only_details_do_not_claim_game_identity(self):
        proc = self.root / "proc"
        proc.mkdir()
        process = proc / "456"
        process.mkdir()
        (process / "environ").write_bytes(b"SteamGameId=3008130\0")
        (process / "comm").write_text("DyingLight.exe\n")
        (process / "exe").symlink_to("/opt/Steam/DyingLight.exe")
        self.assertEqual(steam.associated_process_details("3008130", str(proc)),
                         [(456, "DyingLight.exe", "DyingLight.exe",
                           "windows_executable_candidate")])

    def test_read_only_details_redact_untrusted_process_names(self):
        proc = self.root / "proc"
        proc.mkdir()
        process = proc / "777"
        process.mkdir()
        (process / "environ").write_bytes(b"STEAM_COMPAT_APP_ID=3008130\0")
        (process / "comm").write_text("secret /home/user\n")
        details = steam.associated_process_details("3008130", str(proc))
        self.assertEqual(details[0][1], "redacted")
        self.assertEqual(details[0][2], "unavailable")

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

    def test_running_steam_handoff_is_reaped_without_forced_termination(self):
        # A command can remain alive after the observation window. This is
        # legitimate Steam IPC behaviour, not a reason to kill Steam.
        marker = self.root / "steam-completed"
        self.fake_steam('sleep 0.2\nprintf done > "' + str(marker) + '"\n')
        with patch.object(steam, "associated_process_count", return_value=0):
            with warnings.catch_warnings(record=True) as recorded:
                warnings.simplefilter("always", ResourceWarning)
                status, report = self.capture(
                    "2353250", steam=str(self.command), duration=0)
                gc.collect()
            self.assertEqual(status, 2, report)
            self.assertIn("STILL RUNNING", report)
            self.assertFalse(any(
                "subprocess" in str(w.message) and "still running" in str(w.message)
                for w in recorded), recorded)
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(marker.read_text(), "done")

    def test_steam_handoff_removes_only_gameweld_private_environment(self):
        marker = self.root / "env-probe"
        self.fake_steam('env > "' + str(marker) + '"\n')
        overrides = {
            "APPDIR": "/tmp/gameweld-private-dev-AppDir",
            "GAMEWELD_PC2_ENABLE_STEAM_WEMOD": "1",
            "DISPLAY": ":99",
        }
        with patch.dict(os.environ, overrides), patch.object(
                steam, "associated_process_count", return_value=0):
            status, report = self.capture(
                "3008130", steam=str(self.command), duration=0.1)
        self.assertEqual(status, 2, report)
        values = marker.read_text().splitlines()
        self.assertFalse(any(line.startswith("APPDIR=") for line in values))
        self.assertFalse(any(line.startswith("GAMEWELD_PC2_") for line in values))
        self.assertIn("DISPLAY=:99", values)

    def test_steam_uri_transport_uses_registered_handler_without_shell(self):
        marker = self.root / "uri-argv"
        self.fake_steam('printf "%s\n" "$@" > "' + str(marker) + '"\nexit 0\n')
        with patch.object(steam, "associated_process_count", return_value=0):
            status, report = self.capture(
                "3008130", steam=str(self.command), transport="steam-uri",
                duration=0.1, require_idle_before_launch=True)
        self.assertEqual(status, 2, report)  # A URI request is not startup proof
        self.assertEqual(marker.read_text().strip(), "steam://rungameid/3008130")
        self.assertIn("Steam launch transport: steam-uri", report)
        self.assertIn("UNCONFIRMED", report)

    def test_steam_uri_mode_does_not_bypass_existing_game_gate(self):
        marker = self.root / "should-not-launch"
        self.fake_steam('touch "' + str(marker) + '"\n')
        with patch.object(steam, "associated_process_count", return_value=1):
            status, report = self.capture(
                "3008130", steam=str(self.command), transport="steam-uri",
                duration=0, require_idle_before_launch=True)
        self.assertEqual(status, 3, report)
        self.assertFalse(marker.exists())

    def test_invalid_transport_fails_before_any_subprocess(self):
        with patch.object(steam.subprocess, "Popen") as spawn:
            status, report = self.capture(
                "3008130", steam=str(self.command), transport="shell", duration=0)
        self.assertEqual(status, 3)
        spawn.assert_not_called()
        self.assertIn("unsupported Steam transport", report)

    def test_steam_handoff_observes_new_exact_process_association(self):
        # Mock one newly observed process after issuing the command. An
        # already-running unrelated/old association must not prove a new start.
        appid = "4294967294"
        self.fake_steam("exit 0\n")
        with patch.object(steam, "associated_process_count", side_effect=[0, 1]):
            status, report = self.capture(appid, steam=str(self.command), duration=1)
        self.assertEqual(status, 0, report)
        self.assertIn("STEAM_ASSOCIATION_OBSERVED", report)
        self.assertIn("Game executable, visible window and trainer: NOT VERIFIED", report)

    def test_existing_process_does_not_prove_new_game_launch(self):
        self.fake_steam("exit 0\n")
        with patch.object(steam, "associated_process_count", return_value=4):
            status, report = self.capture("4294967294", steam=str(self.command), duration=0.01)
        self.assertEqual(status, 2, report)
        self.assertIn("UNCONFIRMED", report)

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

    def test_wrapper_only_gate_blocks_already_running_exact_appid(self):
        marker = self.root / "steam-was-executed"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        with patch.object(steam, "associated_process_count", return_value=1):
            status, report = self.capture(
                "2353250", steam=str(self.command), duration=0,
                require_idle_before_launch=True)
        self.assertEqual(status, 3, report)
        self.assertIn("already has a running associated process", report)
        self.assertFalse(marker.exists())

    def test_wrapper_only_gate_allows_idle_steam_request_not_trainer_claim(self):
        self.fake_steam("exit 0\n")
        with patch.object(steam, "associated_process_count", return_value=0):
            status, report = self.capture(
                "2353250", steam=str(self.command), duration=0.01,
                require_idle_before_launch=True)
        self.assertEqual(status, 2, report)
        self.assertIn("Launch result: UNCONFIRMED", report)
        self.assertNotIn("trainer attached", report.lower())

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
