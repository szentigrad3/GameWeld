#!/usr/bin/env python3
"""Offline GameWeld Steam Compatibility Bridge contract tests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-steam-compat-bridge.py")
spec = importlib.util.spec_from_file_location("gameweld_steam_bridge", SCRIPT)
assert spec and spec.loader
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class GameWeldSteamCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-steam-bridge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "share"
        self.config = self.root / "config"
        self.steam = self.root / "Steam"
        (self.steam / "steamapps/common").mkdir(parents=True)
        self.proton = self.steam / "steamapps/common/Proton - Experimental/proton"
        self.proton.parent.mkdir(exist_ok=True)
        self.proton.write_text("#!/bin/sh\nexit 0\n")
        self.proton.chmod(0o755)
        (self.proton.parent / "toolmanifest.vdf").write_text(
            '"manifest" {"require_tool_appid" "4183110"}\n'
        )
        self.client = self.root / "wemod"
        (self.client / "resources").mkdir(parents=True)
        (self.client / "WeMod.exe").write_bytes(b"MZ-TEST")
        (self.client / "resources/app.asar").write_bytes(b"ASAR")
        # Isolate HOME as well as XDG paths: Steam compatibility lookups
        # inspect ~/.steam/root and ~/.local/share/Steam unless explicitly
        # pointed at a fixture root. Do not read the developer's actual
        # installed games or Steam per-AppID mappings during unit tests.
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.data),
            "XDG_CONFIG_HOME": str(self.config),
        }

    def test_registration_does_not_select_game_or_modify_steam_configs(self):
        with patch.dict(os.environ, self.env):
            target = bridge.register(self.steam, source=SCRIPT)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), bridge.private_tool_dir())
            tool = target.resolve()
            self.assertTrue((tool / "launcher.py").is_file())
            self.assertIn("gameweld-bridge-experimental",
                          (tool / "compatibilitytool.vdf").read_text())
            self.assertIn("/launcher.py %verb%", (tool / "toolmanifest.vdf").read_text())
            self.assertFalse(bridge.config_path().exists())
            self.assertFalse((self.steam / "config/config.vdf").exists())
            self.assertEqual(bridge.register(self.steam, source=SCRIPT), target)

    def test_configure_requires_explicit_game_and_uses_private_file(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client)
            data = bridge.load_config()
            self.assertEqual(list(data), ["2353250"])
            self.assertEqual(data["2353250"]["proton"], str(self.proton.resolve()))
            self.assertFalse(data["2353250"]["trainer_enabled"])
            self.assertEqual(bridge.config_path().stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                bridge.configure("2353250;rm", self.proton, self.client)
            with self.assertRaises(ValueError):
                bridge.configure("2353250", self.proton, self.client, delay=999)

    def test_no_steam_launch_options_are_modified(self):
        with patch.dict(os.environ, self.env):
            config_file = self.steam / "config/config.vdf"
            config_file.parent.mkdir()
            config_file.write_bytes(b"existing launch options: preserve exactly")
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client)
            self.assertEqual(config_file.read_bytes(), b"existing launch options: preserve exactly")

    def test_status_reports_saved_configuration_without_changes(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            prior = bridge.config_path().read_bytes()
            report = bridge.format_status("2353250")
            self.assertIn("GameWeld Bridge AppID: 2353250", report)
            self.assertIn("Trainer auto-start: ENABLED", report)
            self.assertIn("Steam Compatibility selection: UNVERIFIED", report)
            # Deliberately assert the fixture report, independent of any
            # real Steam mapping under the invoking developer's HOME.
            self.assertNotIn("GAMEWELD BRIDGE SELECTED", report)
            self.assertIn("Enhancer patch prerequisites: MISSING or unverified", report)
            self.assertEqual(bridge.config_path().read_bytes(), prior)
            self.assertIn("NOT CONFIGURED", bridge.format_status("2353251"))

    def test_saved_steam_selection_status_is_read_only_and_exact_appid_scoped(self):
        local = self.steam / "userdata/100/config/localconfig.vdf"
        local.parent.mkdir(parents=True, exist_ok=True)
        with patch.dict(os.environ, self.env):
            self.assertIn(
                "UNVERIFIED",
                bridge.steam_compat_selection("2353250", steam_roots=[self.steam]))
            local.write_text(
                '"UserLocalConfigStore" {\n'
                '  "Software" { "Valve" { "Steam" {\n'
                '    "CompatToolMapping" {\n'
                '      "2353250" { "name" "gameweld-bridge-experimental" "config" "" "priority" "250" }\n'
                '      "2353251" { "name" "Proton Experimental" "config" "" "priority" "250" }\n'
                '    }\n'
                '  } } }\n'
                '}\n', encoding="utf-8")
            original = local.read_bytes()
            self.assertIn(
                "GAMEWELD BRIDGE SELECTED",
                bridge.steam_compat_selection("2353250", steam_roots=[self.steam]))
            self.assertIn(
                "OTHER TOOL SELECTED",
                bridge.steam_compat_selection("2353251", steam_roots=[self.steam]))
            self.assertEqual(local.read_bytes(), original)
            with self.assertRaises(ValueError):
                bridge.steam_compat_selection("2353250;rm", steam_roots=[self.steam])

    def test_status_reports_patch_file_presence_without_claiming_runtime_load(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            (self.client / "version.dll").write_bytes(b"test")
            (self.client / "resources/app.asar.backup").write_bytes(b"original")
            report = bridge.format_status("2353250")
            self.assertIn("PRESENT (files only; DLL runtime loading not verified)", report)
            self.assertIn("Steam Compatibility selection:", report)

    def test_confirmed_existing_game_trainer_toggle_preserves_paths(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client, enabled=True, delay=21)
            self.assertFalse(bridge.set_trainer_enabled("2353250", False))
            entry = bridge.load_config()["2353250"]
            self.assertFalse(entry["trainer_enabled"])
            self.assertEqual(entry["delay_seconds"], 21)
            self.assertEqual(entry["client"], str(self.client.resolve()))
            self.assertEqual(entry["proton"], str(self.proton.resolve()))
            self.assertTrue(bridge.set_trainer_enabled("2353250", True))
            self.assertIn("Trainer auto-start: ENABLED", bridge.format_status("2353250"))
            with self.assertRaisesRegex(ValueError, "not yet configured"):
                bridge.set_trainer_enabled("2353251", True)

    def test_read_only_first_time_readiness_uses_prefix_proton_evidence(self):
        game = self.steam / "steamapps/common/ASTROMETICA"
        game.mkdir()
        (self.steam / "steamapps/appmanifest_2353250.acf").write_text("manifest")
        compat = self.steam / "steamapps/compatdata/2353250"
        (compat / "pfx").mkdir(parents=True)
        (self.proton.parent / "files").mkdir()
        (compat / "config_info").write_text(
            str(self.proton.parent / "files") + "\n", encoding="utf-8")
        managed = self.data / "gameweld/deckcheatz/wemod_data/wemod_bin"
        (managed / "resources").mkdir(parents=True)
        (managed / "WeMod.exe").write_bytes(b"MZ")
        (managed / "resources/app.asar").write_bytes(b"ASAR")
        with patch.dict(os.environ, self.env):
            report = bridge.format_status(
                "2353250", game_dir=game, steam_root=self.steam)
            self.assertIn("First-time setup readiness: READY (read-only)", report)
            self.assertIn("Exact Proton candidate: " + str(self.proton), report)
            self.assertIn("Existing managed WeMod client: " + str(managed), report)
            self.assertIn("WeMod auto-start DISABLED", report)
            self.assertFalse(bridge.config_path().exists())
            self.assertFalse((self.steam / "compatibilitytools.d").exists())

    def test_first_time_readiness_blocker_does_not_change_game(self):
        game = self.steam / "steamapps/common/ASTROMETICA"
        game.mkdir()
        (self.steam / "steamapps/appmanifest_2353250.acf").write_text("manifest")
        with patch.dict(os.environ, self.env):
            report = bridge.format_status(
                "2353250", game_dir=game, steam_root=self.steam)
            self.assertIn("First-time setup readiness: BLOCKED", report)
            self.assertIn("No exact Proton mapping or prefix runtime hint", report)
            self.assertFalse(bridge.config_path().exists())

    def test_setup_registers_new_game_only_without_changing_steam_config(self):
        game = self.steam / "steamapps/common/ASTROMETICA"
        game.mkdir()
        (self.steam / "steamapps/appmanifest_2353250.acf").write_text("manifest")
        existing = self.steam / "config/config.vdf"
        existing.parent.mkdir()
        existing.write_bytes(b"untouched steam user settings")
        with patch.dict(os.environ, dict(self.env, HOME=str(self.root / "home"))):
            target = bridge.setup_game("2353250", game, steam_root=self.steam,
                                       proton=self.proton, client=self.client)
            self.assertTrue(target.is_symlink())
            entry = bridge.load_config()["2353250"]
            self.assertEqual(entry["proton"], str(self.proton.resolve()))
            self.assertEqual(entry["client"], str(self.client.resolve()))
            self.assertFalse(entry["trainer_enabled"])
            self.assertEqual(existing.read_bytes(), b"untouched steam user settings")
            with self.assertRaisesRegex(ValueError, "already configured"):
                bridge.setup_game("2353250", game, steam_root=self.steam,
                                  proton=self.proton, client=self.client)
            self.assertFalse(bridge.load_config()["2353250"]["trainer_enabled"])

    def test_setup_wrong_manifest_fails_before_any_registration(self):
        game = self.steam / "steamapps/common/ASTROMETICA"
        game.mkdir()
        with patch.dict(os.environ, self.env):
            with self.assertRaisesRegex(ValueError, "matching AppID manifest"):
                bridge.setup_game("2353250", game, steam_root=self.steam,
                                  proton=self.proton, client=self.client)
            self.assertFalse((self.steam / "compatibilitytools.d").exists())
            self.assertFalse(bridge.config_path().exists())

    def test_setup_no_proton_mapping_never_guesses_an_installed_tool(self):
        from argparse import Namespace
        from unittest.mock import patch as mocked
        game = self.steam / "steamapps/common/ASTROMETICA"
        game.mkdir()
        (self.steam / "steamapps/appmanifest_2353250.acf").write_text("manifest")
        resolver = SCRIPT.parent / "gameweld-deckcheatz-proton.py"
        self.assertTrue(resolver.is_file())
        with patch.dict(os.environ, dict(self.env, HOME=str(self.root / "home"))):
            with self.assertRaisesRegex(ValueError, "Cannot unambiguously locate"):
                bridge.resolve_setup("2353250", game, client=self.client)
            self.assertFalse(bridge.config_path().exists())

    def test_bridge_play_uses_steam_and_never_starts_a_second_proton(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            play = Mock(return_value=0)
            count = Mock(return_value=0)
            result = bridge.play_configured_game(
                "2353250", launch=play, associated_processes=count)
            self.assertEqual(result, 0)
            play.assert_called_once_with("2353250")
            count.assert_called_once_with("2353250")

    def test_bridge_play_refuses_disabled_unconfigured_or_duplicate_sessions(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=False)
            play = Mock(return_value=0)
            with self.assertRaisesRegex(ValueError, "DISABLED"):
                bridge.play_configured_game(
                    "2353250", launch=play, associated_processes=lambda _: 0)
            with self.assertRaisesRegex(ValueError, "no GameWeld Bridge"):
                bridge.play_configured_game(
                    "2353251", launch=play, associated_processes=lambda _: 0)
            bridge.set_trainer_enabled("2353250", True)
            with self.assertRaisesRegex(ValueError, "existing same-AppID"):
                bridge.play_configured_game(
                    "2353250", launch=play, associated_processes=lambda _: 1)
            play.assert_not_called()

    def test_bridge_play_requires_installed_tool_without_changing_steam(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            play = Mock(return_value=0)
            with self.assertRaisesRegex(ValueError, "not registered"):
                bridge.play_configured_game(
                    "2353250", launch=play, associated_processes=lambda _: 0)
            play.assert_not_called()

    def test_runtime_comes_from_exact_configured_proton(self):
        with patch.dict(os.environ, self.env):
            runtime = (self.steam /
                       "steamapps/common/SteamLinuxRuntime_4/_v2-entry-point")
            runtime.parent.mkdir(parents=True)
            runtime.write_text("#!/bin/sh\nexit 0\n")
            runtime.chmod(0o755)
            self.assertEqual(bridge.runtime_entry(self.proton, self.steam), runtime)

    def test_nonlaunch_proton_chore_never_starts_we_mod(self):
        with patch.object(bridge.subprocess, "call", return_value=0) as forwarded:
            status = bridge.inner(
                ["getcompatpath", "2353250"],
                {"proton": str(self.proton), "client": str(self.client),
                 "trainer_enabled": True},
                "2353250")
        self.assertEqual(status, 0)
        forwarded.assert_called_once_with([str(self.proton), "getcompatpath", "2353250"])

    def test_game_starts_inside_runtime_without_trainer_by_default(self):
        class FakeGame:
            def poll(self): return None
            def wait(self): return 0
        with patch.object(bridge.subprocess, "Popen", return_value=FakeGame()) as game:
            with patch.object(bridge, "start_trainer") as trainer:
                result = bridge.inner(
                    ["waitforexitandrun", "ASTROMETICA.exe"],
                    {"proton": str(self.proton), "client": str(self.client),
                     "trainer_enabled": False}, "2353250")
        self.assertEqual(result, 0)
        game.assert_called_once_with([str(self.proton), "waitforexitandrun", "ASTROMETICA.exe"])
        trainer.assert_not_called()

    def test_outer_enters_required_steam_container(self):
        with patch.dict(os.environ, dict(self.env,
                STEAM_COMPAT_DATA_PATH=str(self.steam / "steamapps/compatdata/2353250"),
                STEAM_COMPAT_CLIENT_INSTALL_PATH=str(self.steam)), clear=False):
            bridge.configure("2353250", self.proton, self.client)
            runtime = self.steam / "steamapps/common/SteamLinuxRuntime_4/_v2-entry-point"
            runtime.parent.mkdir(parents=True, exist_ok=True)
            runtime.write_text("#!/bin/sh\nexit 0\n")
            runtime.chmod(0o755)
            with patch.object(bridge.subprocess, "call", return_value=0) as launch:
                result = bridge.steam_invocation(["waitforexitandrun", "ASTROMETICA.exe"])
            self.assertEqual(result, 0)
            command = launch.call_args.args[0]
            self.assertEqual(command[0], str(runtime))
            self.assertEqual(command[1:3], ["--verb=waitforexitandrun", "--"])
            self.assertEqual(command[-2:], ["waitforexitandrun", "ASTROMETICA.exe"])
            self.assertEqual(launch.call_args.kwargs["env"]["GAMEWELD_BRIDGE_INNER"], "1")

    def test_unconfigured_title_fails_closed(self):
        with patch.dict(os.environ, dict(
                self.env,
                STEAM_COMPAT_DATA_PATH=str(self.steam / "steamapps/compatdata/2353250"))):
            with self.assertRaisesRegex(ValueError, "unconfigured"):
                bridge.steam_invocation(["waitforexitandrun", "ASTROMETICA.exe"])


if __name__ == "__main__":
    unittest.main()
