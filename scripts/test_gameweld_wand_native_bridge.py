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
        # ALL fixture tests must inspect only the disposable Proton root.
        # Without this guard, discovery also scans real /mnt/games/Steam;
        # mocked crypt32 hashes then falsely mark the user's *real* DLLs
        # as valid and can mask invalid fixture metadata. Never hash or
        # inspect a host Steam compatibility tool from a unit test.
        self.original_proton_candidates = mod._proton_candidates
        self.fixture_discovery = patch.object(
            mod, "_proton_candidates", return_value=[self.protonroot])
        self.fixture_discovery.start()
        self.addCleanup(self.fixture_discovery.stop)

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

    def test_missing_historical_metadata_accepts_exact_verified_dll_hashes_readonly(self):
        metadata = self.protonroot / "WAND-HYBRID.json"
        metadata.unlink()
        with self.healthy():
            output = io.StringIO()
            with redirect_stdout(output):
                p = mod.plan("2353250", str(self.game), None)
                self.assertEqual(
                    mod.main(["check", "--appid", "2353250",
                              "--game-dir", str(self.game)]), 0)
        self.assertEqual(p.proton, self.proton.resolve())
        self.assertIn("WAND-HYBRID.json ABSENT", output.getvalue())
        self.assertIn("BOTH exact proven crypt32 DLL hashes VERIFIED", output.getvalue())
        self.assertIn("READINESS PASS", output.getvalue())
        self.assertFalse(metadata.exists(), "Read-only check must not repair metadata")
        self.assertEqual(self.exe.read_bytes(), b"MZ-GAME")
        self.assertFalse((self.root / "state").exists())

    def test_missing_metadata_does_not_bypass_real_hash_mismatch(self):
        metadata = self.protonroot / "WAND-HYBRID.json"
        metadata.unlink()
        with patch.object(mod, "verified_client", return_value=self.wand), \
             patch.object(mod, "existing_game_process", return_value=False):
            with self.assertRaisesRegex(mod.Blocked, "x86_64-windows crypt32 SHA-256 mismatch"):
                mod.plan("2353250", str(self.game), None)
        self.assertFalse(metadata.exists())
        self.assertFalse((self.root / "state").exists())

    def test_existing_bad_metadata_rejected_even_when_dll_hashes_match(self):
        metadata = self.protonroot / "WAND-HYBRID.json"
        data = json.loads(metadata.read_text(encoding="utf-8"))
        data["patched_i386_crypt32_sha256"] = "0" * 64
        metadata.write_text(json.dumps(data))
        with self.healthy():
            with self.assertRaisesRegex(mod.Blocked, "WAND-HYBRID.json payload hash"):
                mod.plan("2353250", str(self.game), None)
        self.assertFalse((self.root / "state").exists())

    def test_symlinked_metadata_rejected_even_with_known_dll_hashes(self):
        metadata = self.protonroot / "WAND-HYBRID.json"
        other = self.root / "untrusted.json"
        other.write_bytes(metadata.read_bytes())
        metadata.unlink()
        metadata.symlink_to(other)
        with self.healthy():
            with self.assertRaisesRegex(mod.Blocked, "WAND-HYBRID.json is symlinked"):
                mod.plan("2353250", str(self.game), None)
        self.assertFalse((self.root / "state").exists())

    def test_real_fingerprint_mismatch_blocks_before_launch(self):
        # Synthetic crypt32 DLLs don't match the tested release fingerprints.
        with patch.object(mod, "verified_client", return_value=self.wand), \
             patch.object(mod, "existing_game_process", return_value=False):
            with self.assertRaisesRegex(mod.Blocked, "crypt32 SHA-256 mismatch"):
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
            with self.assertRaisesRegex(mod.Blocked, "Expected one verified"):
                mod.plan("2353250", str(self.game), None)
        with self.assertRaisesRegex(mod.Blocked, "manifest"):
            mod.steam_install(self.game, "251570")
        with self.assertRaisesRegex(mod.Blocked, "Invalid"):
            mod.valid_appid("2353250;rm -rf /")

    def test_missing_tool_error_shows_prior_release_archive_without_installing(self):
        home_archive = self.home / "src/wand-ge-proton/build/GE-Proton-Wand-SHA256.tar.gz"
        home_archive.parent.mkdir(parents=True)
        home_archive.write_bytes(b"ARCHIVED-TEST-FIXTURE-NOT-REAL-PROTON")
        (self.protonroot / "proton").unlink()
        with self.assertRaisesRegex(mod.Blocked, "Previous tested-release recovery files FOUND") as error:
            mod.find_proton(self.apps)
        self.assertIn(str(home_archive), str(error.exception))
        self.assertIn("Proton launcher is missing", str(error.exception))
        self.assertTrue(home_archive.is_file())
        self.assertFalse((self.root / "state").exists())

    def test_no_verified_tool_distinguishes_hash_mismatch(self):
        with self.assertRaisesRegex(mod.Blocked, "crypt32 SHA-256 mismatch") as error:
            mod.find_proton(self.apps)
        self.assertIn("0 verified", str(error.exception))
        self.assertIn("x86_64-windows", str(error.exception))

    def test_tool_discovery_reports_other_steam_library_and_resolves_duplicates(self):
        # Production discovery must find the Steam-library fixture while
        # managed-session tests verify ONLY our disposable Proton instance.
        # Do not let the real discovery results enter a mocked hash check.
        discovered = self.original_proton_candidates(self.apps)
        self.assertIn(self.protonroot, discovered)
        self.assertEqual(
            len(discovered),
            len({str(x.resolve(strict=False)) for x in discovered}),
        )
        self.assertEqual(mod._proton_candidates(self.apps), [self.protonroot])
        with self.healthy():
            tool, root = mod.find_proton(self.apps)
            self.assertEqual(tool, self.proton.resolve())
            self.assertTrue(root.is_dir())

    def test_fixture_hash_mocks_never_verify_host_steam_installations(self):
        # Regression for a real CachyOS machine with a second installed tool
        # in /mnt/games/Steam: no host paths can reach the mock verifier.
        checked_roots = []
        original = mod._verify_isolated_tool

        def inspect(root):
            checked_roots.append(root)
            if root != self.protonroot.resolve():
                raise AssertionError("Unit test inspected a real Steam tool: " + str(root))
            return original(root)

        with self.healthy(), patch.object(mod, "_verify_isolated_tool", side_effect=inspect):
            proton, _steam_root = mod.find_proton(self.apps)
        self.assertEqual(proton, self.proton.resolve())
        self.assertEqual(checked_roots, [self.protonroot.resolve()])

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
