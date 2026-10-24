#!/usr/bin/env python3
"""Fixture-only tests of GameWeld's integrated managed Proton architecture."""
from __future__ import annotations
from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-managed-wand.py")
spec = importlib.util.spec_from_file_location("gameweld_managed_wand_test", SOURCE)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class IntegratedManagedSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-managed-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.steamroot = self.home / ".local/share/Steam"
        self.steamroot.mkdir(parents=True)
        self.library = self.root / "Library"
        self.apps = self.library / "steamapps"
        self.game = self.apps / "common" / "Astrometica"
        self.game.mkdir(parents=True)
        self.exe = self.game / "Astrometica.exe"
        self.exe.write_bytes(b"MZ-GAME")
        (self.apps / "appmanifest_2353250.acf").write_text(
            '"AppState"\n{\n    "appid"    "2353250"\n    "installdir" "Astrometica"\n}\n'
        )
        self.compat = self.apps / "compatdata" / "2353250"
        self.prefix = self.compat / "pfx"
        user = self.prefix / "drive_c/users/steamuser"
        user.mkdir(parents=True)
        dos = self.prefix / "dosdevices"
        dos.mkdir()
        (dos / "c:").symlink_to(self.prefix / "drive_c", target_is_directory=True)
        self.wand = self.root / "Wand" / "app-12.55.0" / "WeMod.exe"
        self.wand.parent.mkdir(parents=True)
        self.wand.write_bytes(b"MZ-WAND")
        self.dwrite = self.wand.parent / "DWriteCore.dll"
        self.dwrite.write_bytes(b"MZ" + b"D" * (1024 * 1024 + 10))
        self.protonroot = self.library / "compatibilitytools.d" / mod.TOOL
        self.protonroot.mkdir(parents=True)
        self.proton = self.protonroot / "proton"
        self.proton.write_text("#!/bin/sh\nexit 0\n")
        self.proton.chmod(0o755)
        (self.protonroot / "compatibilitytool.vdf").write_text(
            '"compatibilitytools" { "compat_tools" { "GE-Proton-Wand-SHA256" { "display_name" "GE Proton Wand SHA256" } } }'
        )
        (self.protonroot / "WAND-HYBRID.json").write_text(json.dumps({
            "tool_id": mod.TOOL,
            "patched_x86_64_crypt32_sha256": mod.EXPECTED["x86_64-windows"],
            "patched_i386_crypt32_sha256": mod.EXPECTED["i386-windows"],
        }))
        for arch in mod.EXPECTED:
            dll = self.protonroot / "files" / "lib" / "wine" / arch / "crypt32.dll"
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b"MZ-FAKE-PAYLOAD-" + arch.encode())
        self.env = patch.dict(os.environ, {"HOME": str(self.home),
                                          "XDG_STATE_HOME": str(self.root / "state")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def fake_sha(self, path):
        arch = path.parent.name
        return mod.EXPECTED[arch]

    @contextmanager
    def healthy(self):
        with patch.object(mod, "verified_client", return_value=self.wand), \
             patch.object(mod, "sha256", side_effect=self.fake_sha), \
             patch.object(mod, "existing_game_process", return_value=False):
            yield

    def test_integrated_check_does_not_need_wandctl_and_changes_no_game(self):
        with self.healthy():
            p = mod.plan("2353250", str(self.game), None)
            self.assertEqual(p.proton, self.proton.resolve())
            self.assertEqual(p.game_exe, self.exe.resolve())
            self.assertEqual(p.windows_user, "steamuser")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(mod.main(["check", "--appid", "2353250",
                                          "--game-dir", str(self.game)]), 0)
        self.assertIn("READINESS PASS", stdout.getvalue())
        self.assertIn("no real game", stdout.getvalue())
        self.assertEqual(self.exe.read_bytes(), b"MZ-GAME")
        self.assertEqual(self.wand.read_bytes(), b"MZ-WAND")
        self.assertFalse((self.root / "state").exists())

    def test_real_fingerprint_mismatch_blocks_before_launch(self):
        # Synthetic crypt32 DLLs don't match the tested release fingerprints.
        with patch.object(mod, "verified_client", return_value=self.wand), \
             patch.object(mod, "existing_game_process", return_value=False):
            with self.assertRaisesRegex(mod.Blocked, "crypt32.*does not match"):
                mod.plan("2353250", str(self.game), None)
        self.assertFalse((self.root / "state").exists())

    def test_one_proton_batch_contains_wand_first_game_second_and_restores_profile(self):
        with self.healthy():
            p = mod.plan("2353250", str(self.game), None)
            text = mod.build_batch(p, p.state_dir / "launch.bat", p.state_dir / "stage.txt")
        self.assertIn("SteamAppId=2353250", text)
        self.assertIn("USERPROFILE=C:\\users\\steamuser", text)
        self.assertIn("set \"USERPROFILE=%WAND_SAVED_USERPROFILE%\"", text)
        self.assertLess(text.index("echo starting-wand"), text.index("echo starting-game"))
        self.assertIn("start \"\" /D", text)
        self.assertNotIn("--disable-gpu", text)
        self.assertTrue("\r\n" in text)

    def test_confirmation_required_and_mock_proton_launch_uses_waitforexitandrun(self):
        args = ["play", "--appid", "2353250", "--game-dir", str(self.game)]
        with patch.object(mod, "plan") as check:
            with self.assertRaisesRegex(mod.Blocked, "explicit --confirm"):
                mod.main(args)
            check.assert_not_called()
        child = Mock(pid=321)
        with self.healthy(), patch.object(mod.subprocess, "Popen", return_value=child) as launch:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(mod.main(args + ["--confirm"]), 0)
        cmd = launch.call_args.args[0]
        self.assertEqual(cmd[0], str(self.proton.resolve()))
        self.assertEqual(cmd[1], "waitforexitandrun")
        self.assertTrue(cmd[2].endswith("appid-2353250-launch.bat"))
        self.assertIn("REQUEST SENT", output.getvalue())
        self.assertIn("NOT VERIFIED", output.getvalue())
        self.assertTrue((self.root / "state/gameweld/managed-wand/appid-2353250-launch.bat").is_file())

    def test_running_game_blocks_managed_session(self):
        with patch.object(mod, "existing_game_process", return_value=True):
            with self.assertRaisesRegex(mod.Blocked, "already running"):
                mod.plan("2353250", str(self.game), None)

    def test_missing_proton_tool_and_wrong_game_id_are_blocked(self):
        (self.protonroot / "proton").unlink()
        with patch.object(mod, "existing_game_process", return_value=False):
            with self.assertRaisesRegex(mod.Blocked, "No unique verified"):
                mod.plan("2353250", str(self.game), None)
        with self.assertRaisesRegex(mod.Blocked, "manifest"):
            mod.steam_install(self.game, "251570")
        with self.assertRaisesRegex(mod.Blocked, "Invalid"):
            mod.valid_appid("2353250;rm -rf /")

    def test_ambiguous_executable_fails_closed(self):
        (self.game / "Extras").mkdir()
        (self.game / "Extras/Astrometica.exe").write_bytes(b"MZ-AMBIGUOUS")
        with self.assertRaisesRegex(mod.Blocked, "one exact Windows game executable"):
            mod.choose_game_exe(self.game, None)

    def test_dwrite_must_be_present_no_auto_network_install(self):
        self.dwrite.unlink()
        with self.healthy():
            with self.assertRaisesRegex(mod.Blocked, "DWriteCore"):
                mod.plan("2353250", str(self.game), None)

if __name__ == "__main__":
    unittest.main()
