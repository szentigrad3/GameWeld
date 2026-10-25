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
        self.env = {
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
            self.assertIn("Actual Steam compatibility-tool selection: NOT VERIFIED", report)
            self.assertEqual(bridge.config_path().read_bytes(), prior)
            self.assertIn("NOT CONFIGURED", bridge.format_status("2353251"))

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
