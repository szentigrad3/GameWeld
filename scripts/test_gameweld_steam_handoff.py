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

    def make_wemod_process_fixture(self):
        proc = self.root / "proc"
        proc.mkdir(exist_ok=True)
        directory = proc / "525322"
        directory.mkdir(exist_ok=True)
        (directory / "environ").write_bytes(
            b"SteamAppId=3008130\0SENSITIVE=not-for-output\0")
        (directory / "comm").write_text("wine64\n")
        (directory / "exe").symlink_to("/fake/proton/bin/wine64-preloader")
        (directory / "cmdline").write_bytes(
            b"/fake/proton/bin/wine64-preloader\0"
            b"C:\\Program Files\\WeMod\\WeMod.exe\0")
        return proc, directory

    def test_wemod_only_loader_does_not_block_steam_game_only_request(self):
        proc, directory = self.make_wemod_process_fixture()
        blocked, clients = steam.associated_non_client_processes(
            "3008130", str(proc))
        self.assertEqual(blocked, [])
        self.assertEqual(clients, 1)
        self.assertTrue(steam.recognizable_wemod_client_only(directory))
        self.assertFalse(steam.recognizable_wemod_client_only(proc))

    def test_same_loader_with_game_or_hidden_executable_remains_blocked(self):
        proc, directory = self.make_wemod_process_fixture()
        variants = (
            b"wine64\0C:\\WeMod\\WeMod.exe\0C:\\Games\\DyingLight.exe\0",
            b"wine64\0C:\\Games\\DyingLight.exe\0",
            b"wine64\0C:\\WeMod\\WeMod.exe",  # truncated cmdline
            b"x" * 8193,  # oversized command line
            b"wine64\0C:\\WeMod\\WeMod.exe\0--bad=name.exe\0",
        )
        for argv in variants:
            (directory / "cmdline").write_bytes(argv)
            blocked, clients = steam.associated_non_client_processes(
                "3008130", str(proc))
            self.assertEqual(len(blocked), 1, argv[:80])
            self.assertEqual(clients, 0)

    def test_wemod_only_is_not_claimed_for_other_appid_or_non_wine_process(self):
        proc, directory = self.make_wemod_process_fixture()
        blockers, clients = steam.associated_non_client_processes(
            "3008131", str(proc))
        self.assertEqual(blockers, [])
        self.assertEqual(clients, 0)
        (directory / "exe").unlink()
        (directory / "exe").symlink_to("/usr/bin/other")
        self.assertEqual(steam.associated_non_client_processes(
            "3008130", str(proc))[1], 0)

    def test_steam_launch_can_proceed_with_known_wemod_client_only(self):
        marker = self.root / "steam-invoked"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        with patch.object(steam, "associated_process_count",
                          side_effect=[1] + [2] * 60), \
             patch.object(steam, "associated_non_client_processes",
                          return_value=([], 1)):
            status, report = self.capture(
                "3008130", steam=str(self.command),
                require_idle_before_launch=True, duration=0.2)
        self.assertEqual(status, 2, report)
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())
        self.assertIn("Recognized existing WeMod-only Wine client(s): 1", report)
        self.assertIn("STEAM_ASSOCIATION_ONLY", report)
        self.assertIn("game EXE not verified", report)

    def test_steam_launch_aborts_if_wemod_only_evidence_changes(self):
        marker = self.root / "steam-not-invoked"
        self.fake_steam('touch "' + str(marker) + '"\n')
        with patch.object(steam, "associated_process_count", return_value=1), \
             patch.object(steam, "associated_non_client_processes",
                          side_effect=[([], 1), ([Path("/proc/999")], 1)]):
            status, report = self.capture(
                "3008130", steam=str(self.command),
                require_idle_before_launch=True, duration=0)
        self.assertEqual(status, 3)
        self.assertFalse(marker.exists())
        self.assertIn("process evidence changed during preflight", report)

    def test_steam_log_probe_reports_only_new_exact_appid_events(self):
        steam_root = self.root / "Steam"
        log = steam_root / "logs" / "gameprocess_log.txt"
        log.parent.mkdir(parents=True)
        log.write_text(
            "[2026] Game process removed: AppID 3008130 old secret /home/private\n")
        probe = steam.SteamLogProbe(steam_root)
        with log.open("a") as stream:
            stream.write("[2026] Game process added: AppID 30081300 unrelated\n")
            stream.write("[2026] GameAction [AppID 3008130, ActionID 4] launch\n")
            stream.write("[2026] Game process added : AppID 3008130 /home/private/tokens\n")
            stream.write("[2026] Game process removed: AppID 3008130 /home/private\n")
        notes = "\n".join(probe.summary("3008130"))
        self.assertIn("launch_action=1", notes)
        self.assertIn("process_added=1", notes)
        self.assertIn("process_removed=1", notes)
        self.assertNotIn("30081300", notes)
        self.assertNotIn("/home/private", notes)
        self.assertNotIn("old secret", notes)

    def test_steam_log_probe_handles_rotation_truncation_and_symlink(self):
        root = self.root / "Steam"
        log = root / "logs" / "gameprocess_log.txt"
        log.parent.mkdir(parents=True)
        log.write_text("a" * 500)
        probe = steam.SteamLogProbe(root)
        log.unlink()
        log.write_text("[2026] Game process added: AppID 3008130\n")
        notes = "\n".join(probe.summary("3008130"))
        self.assertIn("changed/rotated", notes)
        log.unlink()
        log.symlink_to(self.root / "secret")
        (self.root / "secret").write_text("AppID 3008130 secret\n")
        self.assertEqual(steam._log_identity(log), None)
        notes = "\n".join(steam.SteamLogProbe(root).summary(
            "3008130", historical=True))
        self.assertNotIn("secret", notes)

    def test_unconfirmed_steam_launch_reports_sanitized_client_events(self):
        steam_root = self.root / "Steam"
        log = steam_root / "logs" / "gameprocess_log.txt"
        log.parent.mkdir(parents=True)
        log.write_text("old lines\n")
        self.fake_steam(
            'printf "[2026] Game process added : AppID 3008130 private-info\\n" '
            '>> "' + str(log) + '"\nexit 0\n'
        )
        with patch.object(steam, "associated_process_count", return_value=0):
            status, report = self.capture(
                "3008130", steam=str(self.command), steam_root=steam_root,
                duration=0.15)
        self.assertEqual(status, 2, report)
        self.assertIn("Launch result: UNCONFIRMED", report)
        self.assertIn("Steam log gameprocess_log.txt AppID events: process_added=1", report)
        self.assertNotIn("private-info", report)

    def make_steam_game_process_fixture(self):
        root = self.root / "Steam"
        game = root / "steamapps/common/Dying Light Beast"
        game.mkdir(parents=True)
        (root / "steamapps/appmanifest_3008130.acf").write_text(
            '"AppState" { "appid" "3008130" }')
        exe = game / "DyingLightGame.exe"
        exe.write_bytes(b"MZ")
        proc = self.root / "proc"
        proc.mkdir(exist_ok=True)
        p = proc / "1234"
        p.mkdir()
        (p / "cmdline").write_bytes(
            b"/usr/bin/wine64-preloader\0" +
            ("Z:" + str(exe).replace("/", "\\")).encode() + b"\0")
        (p / "environ").write_bytes(b"SteamAppId=3008130\0")
        (p / "comm").write_text("wine64\n")
        (p / "exe").symlink_to("/usr/bin/wine64-preloader")
        return game, proc, p

    def test_game_executable_detected_independently_of_wemod_appid_count(self):
        game, proc, item = self.make_steam_game_process_fixture()
        self.assertEqual(
            steam.observed_game_executable_pids("3008130", game, str(proc)),
            {1234})
        self.assertEqual(
            steam.observed_game_executable_pids("3008131", game, str(proc)),
            set())
        item.joinpath("cmdline").write_bytes(
            b"/usr/bin/wine64-preloader\0C:\\WeMod\\WeMod.exe\0")
        self.assertEqual(
            steam.observed_game_executable_pids("3008130", game, str(proc)),
            set())

    def test_rejects_missing_manifest_or_game_exe_outside_selected_directory(self):
        game, proc, item = self.make_steam_game_process_fixture()
        self.assertEqual(len(steam.observed_game_executable_pids(
            "3008130", game, str(proc))), 1)
        (game.parent.parent / "appmanifest_3008130.acf").unlink()
        self.assertEqual(steam.observed_game_executable_pids(
            "3008130", game, str(proc)), set())
        outside = self.root / "Outside.exe"
        outside.write_bytes(b"MZ")
        (game.parent.parent / "appmanifest_3008130.acf").write_text("manifest")
        item.joinpath("cmdline").write_bytes(
            b"wine64\0" + str(outside).encode() + b"\0")
        self.assertEqual(steam.observed_game_executable_pids(
            "3008130", game, str(proc)), set())

    def test_lifecycle_distinguishes_wemod_remnant_without_terminating_it(self):
        game, proc, game_process = self.make_steam_game_process_fixture()
        wemod = proc / "525322"
        wemod.mkdir()
        (wemod / "environ").write_bytes(b"SteamAppId=3008130\0")
        (wemod / "comm").write_text("wine64\n")
        (wemod / "exe").symlink_to("/usr/bin/wine64-preloader")
        (wemod / "cmdline").write_bytes(
            b"wine64-preloader\0C:\\Program Files\\WeMod\\WeMod.exe\0")
        before = steam.game_session_lifecycle("3008130", game, root=str(proc))
        self.assertEqual(before["game_executable_candidates"], 1)
        self.assertEqual(before["wemod_only_wine_clients"], 1)
        self.assertFalse(before["game_closed_verified"])
        game_process.joinpath("cmdline").write_bytes(b"wine64-preloader\0")
        after = steam.game_session_lifecycle("3008130", game, root=str(proc))
        self.assertEqual(after["game_executable_candidates"], 0)
        self.assertEqual(after["wemod_only_wine_clients"], 1)
        self.assertEqual(after["other_appid_associated_processes"], 1)
        self.assertTrue(wemod.exists())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            steam.print_game_lifecycle(after)
        self.assertIn("WeMod is present but game EXE was not verified", output.getvalue())
        self.assertIn("No process was terminated", output.getvalue())

    def test_launch_confirms_new_game_exe_without_new_appid_process(self):
        marker = self.root / "steam-invoked"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        game, proc, item = self.make_steam_game_process_fixture()
        with patch.object(steam, "associated_process_count", return_value=1), \
             patch.object(steam, "observed_game_executable_pids",
                          side_effect=[set(), {1234}]), \
             patch.object(steam, "associated_non_client_processes",
                          return_value=([], 1)):
            status, report = self.capture(
                "3008130", steam=str(self.command), install_dir=game,
                require_idle_before_launch=True, duration=0.3)
        self.assertEqual(status, 0, report)
        self.assertIn("Launch result: GAME_EXECUTABLE_OBSERVED", report)
        self.assertNotIn("Trainer attachment: VERIFIED", report)

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

    def test_wine_loader_is_ambiguous_and_windows_hint_is_redacted(self):
        proc = self.root / "proc"
        proc.mkdir()
        item = proc / "525322"
        item.mkdir()
        (item / "environ").write_bytes(
            b"SECRET_TOKEN=must-not-leak\0SteamAppId=3008130\0")
        (item / "comm").write_text("wine64\n")
        (item / "exe").symlink_to("/home/private/Proton/bin/wine64-preloader")
        (item / "status").write_text(
            "Name:\twine64\nState:\tS (sleeping)\nPPid:\t123\n")
        (item / "cmdline").write_bytes(
            b"/home/private/Proton/bin/wine64-preloader\0"
            b"C:\\Program Files\\Some Game\\DyingLightGame.exe\0"
            b"--private-token=must-not-leak\0")
        details = steam.associated_process_details("3008130", str(proc))
        self.assertEqual(details, [
            (525322, "wine64", "wine64-preloader", "wine_loader_ambiguous")])
        self.assertEqual(
            steam.associated_process_context("3008130", 525322, str(proc)),
            ("123", "S", "DyingLightGame.exe"))
        self.assertEqual(
            steam.associated_process_context("3008131", 525322, str(proc)),
            ("unavailable", "?", "unavailable"))
        self.assertNotIn("must-not-leak", repr(details))
        self.assertNotIn("private", repr(details))

    def test_wine_loader_without_safe_target_remains_unknown(self):
        proc = self.root / "proc"
        proc.mkdir()
        item = proc / "300"
        item.mkdir()
        (item / "environ").write_bytes(b"SteamGameId=3008130\0")
        (item / "comm").write_text("wine64\n")
        (item / "exe").symlink_to("/tmp/Proton/bin/wine64-preloader")
        (item / "status").write_text("PPid:\tnot-a-pid\nState:\tS (sleeping)\n")
        (item / "cmdline").write_bytes(
            b"wine64-preloader\0C:\\windows\\system32\\services.exe\0")
        self.assertEqual(
            steam.associated_process_context("3008130", 300, str(proc)),
            ("unavailable", "S", "unavailable"))

    def test_oversized_or_path_like_command_line_cannot_leak(self):
        proc = self.root / "proc"
        proc.mkdir()
        item = proc / "301"
        item.mkdir()
        (item / "environ").write_bytes(b"SteamAppId=3008130\0")
        (item / "comm").write_text("wine64\n")
        (item / "cmdline").write_bytes(b"x" * 8193)
        self.assertEqual(
            steam.associated_process_context("3008130", 301, str(proc))[2],
            "unavailable")
        (item / "cmdline").write_bytes(
            b"C:\\Users\\private\\token name.exe\0")
        self.assertEqual(
            steam.associated_process_context("3008130", 301, str(proc))[2],
            "unavailable")

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
        with patch.object(steam, "associated_process_count", side_effect=[0] + [1] * 60):
            status, report = self.capture(appid, steam=str(self.command), duration=0.2)
        self.assertEqual(status, 2, report)
        self.assertIn("STEAM_ASSOCIATION_ONLY", report)
        self.assertIn("No game window or WeMod/trainer startup was verified.", report)

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

    def test_bounded_observe_seconds_preserves_steam_cli_consent(self):
        marker = self.root / "executed"
        self.fake_steam('touch "' + str(marker) + '"\\nexit 0\\n')
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH","/usr/bin"))
        for seconds in ("-1", "91", "999999"):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "launch", "--appid", "2353250",
                 "--confirm", "--observe-seconds", seconds],
                env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
        with patch.object(steam, "run_launch", return_value=2) as runner:
            with patch.object(sys, "argv", [str(SCRIPT), "launch", "--appid",
                                            "2353250", "--confirm",
                                            "--observe-seconds", "75"]):
                status = steam.main()
        self.assertEqual(status, 2)
        self.assertEqual(runner.call_args.kwargs["duration"], 75)
        self.assertTrue(runner.call_args.kwargs["require_idle_before_launch"] is False)

    def test_wrapper_only_gate_blocks_already_running_exact_appid(self):
        marker = self.root / "steam-was-executed"
        self.fake_steam('touch "' + str(marker) + '"\nexit 0\n')
        with patch.object(steam, "associated_process_count", return_value=1), \
             patch.object(steam, "associated_non_client_processes",
                          return_value=([Path("/proc/999")], 0)), \
             patch.object(steam, "associated_process_details",
                          return_value=[(999, "Game.exe", "wine64-preloader",
                                         "windows_executable_candidate")]), \
             patch.object(steam, "associated_process_context",
                          return_value=("1", "S", "Game.exe")):
            status, report = self.capture(
                "2353250", steam=str(self.command), duration=0,
                require_idle_before_launch=True)
        self.assertEqual(status, 3, report)
        self.assertIn("unverified non-WeMod process", report)
        self.assertIn("Game.exe", report)
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
