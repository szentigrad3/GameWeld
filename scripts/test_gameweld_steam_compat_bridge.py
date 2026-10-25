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

    def test_installed_launcher_sync_and_explicit_upgrade_keep_configuration(self):
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            original_config = bridge.config_path().read_bytes()
            launcher = bridge.private_tool_dir() / "launcher.py"
            self.assertEqual(bridge.bridge_launcher_sync(source=SCRIPT), "UP TO DATE")
            installed, backup = bridge.upgrade_bridge(source=SCRIPT)
            self.assertEqual(installed, launcher)
            self.assertIsNone(backup)
            self.assertEqual(bridge.config_path().read_bytes(), original_config)

            # Simulate a legitimate older Steam-registered source copied at
            # a previous launch; upgrade must retain an exact backup.
            older = launcher.read_bytes() + b"\n# old source revision\n"
            launcher.write_bytes(older)
            self.assertIn("UPDATE AVAILABLE", bridge.bridge_launcher_sync(source=SCRIPT))
            installed, backup = bridge.upgrade_bridge(source=SCRIPT)
            self.assertEqual(installed, launcher)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_bytes(), older)
            self.assertEqual(launcher.read_bytes(), SCRIPT.read_bytes())
            self.assertEqual(bridge.bridge_launcher_sync(source=SCRIPT), "UP TO DATE")
            self.assertEqual(bridge.config_path().read_bytes(), original_config)
            self.assertEqual(bridge.upgrade_bridge(source=SCRIPT)[1], None)

    def test_upgrade_rejects_symlinked_launcher_and_unexpected_manifest(self):
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            install = bridge.private_tool_dir()
            launcher = install / "launcher.py"
            launcher.unlink()
            launcher.symlink_to(SCRIPT)
            with self.assertRaisesRegex(ValueError, "not safely installed"):
                bridge.upgrade_bridge(source=SCRIPT)
            launcher.unlink()
            launcher.write_bytes(SCRIPT.read_bytes())
            (install / "toolmanifest.vdf").write_text("foreign tool")
            with self.assertRaisesRegex(ValueError, "manifests"):
                bridge.upgrade_bridge(source=SCRIPT)

    def test_upgrade_backup_conflict_preserves_older_launcher(self):
        import hashlib
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            install = bridge.private_tool_dir()
            launcher = install / "launcher.py"
            old = launcher.read_bytes() + b"\n# old revision\n"
            launcher.write_bytes(old)
            backup = install / ("launcher.py.backup-" +
                                hashlib.sha256(old).hexdigest()[:16])
            backup.write_bytes(b"unrelated user backup")
            with self.assertRaisesRegex(ValueError, "unexpected contents"):
                bridge.upgrade_bridge(source=SCRIPT)
            self.assertEqual(launcher.read_bytes(), old)
            self.assertEqual(backup.read_bytes(), b"unrelated user backup")

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

    def test_primary_action_setup_enable_steam_repair_and_play_states(self):
        with patch.dict(os.environ, self.env):
            self.assertEqual(bridge.primary_ui_state("2353250")[0], "setup")
            self.assertEqual(bridge.primary_ui_state("wrong-id")[0], "blocked")
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=False)
            self.assertEqual(bridge.primary_ui_state("2353250")[0], "enable")
            bridge.set_trainer_enabled("2353250", True)
            with patch.object(bridge, "steam_compat_selection", return_value="UNVERIFIED"):
                self.assertEqual(bridge.primary_ui_state("2353250")[0], "steam")
            with patch.object(bridge, "steam_compat_selection",
                              return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"):
                self.assertEqual(bridge.primary_ui_state("2353250")[0], "repair")
                (self.client / "version.dll").write_bytes(b"fixture")
                (self.client / "resources/app.asar.backup").write_bytes(b"fixture")
                state, message = bridge.primary_ui_state("2353250")
                self.assertEqual(state, "play")
                self.assertIn("requires confirmation", message)
                self.assertTrue(bridge.load_config()["2353250"]["trainer_enabled"])

    def test_stale_installed_launcher_blocks_ui_play_and_steam_handoff(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            (self.client / "version.dll").write_bytes(b"fixture")
            (self.client / "resources/app.asar.backup").write_bytes(b"fixture")
            launcher = bridge.private_tool_dir() / "launcher.py"
            # Simulate Steam still using the previous copy after a Git update.
            launcher.write_bytes(launcher.read_bytes() + b"\\n# older installed launcher\\n")
            before = bridge.config_path().read_bytes()
            steam = self.steam / "config/config.vdf"
            play = Mock(return_value=0)
            with patch.object(
                bridge, "steam_compat_selection",
                return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
            ):
                state, message = bridge.primary_ui_state("2353250")
                self.assertEqual(state, "repair")
                self.assertIn("outdated", message)
                self.assertIn("Advanced Providers", message)
                with self.assertRaisesRegex(ValueError, "outdated"):
                    bridge.play_configured_game(
                        "2353250", launch=play,
                        associated_processes=lambda _: 0
                    )
            play.assert_not_called()
            self.assertEqual(bridge.config_path().read_bytes(), before)
            self.assertFalse(steam.exists())
            # After an explicit launcher-only update, normal readiness returns.
            bridge.upgrade_bridge(source=SCRIPT)
            with patch.object(
                bridge, "steam_compat_selection",
                return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
            ):
                self.assertEqual(bridge.primary_ui_state("2353250")[0], "play")
            self.assertEqual(bridge.config_path().read_bytes(), before)

    def test_primary_gui_offers_confirmed_launcher_only_repair(self):
        # Static integration guard: GTK itself runs in the separate native CI
        # build, while the logic lives in the source-only Steam Bridge helper.
        ui = (Path(__file__).resolve().parents[1] /
              "crates/wand-ui/appimage-gtk3/gameweld-native-040.c").read_text()
        self.assertIn("pc2_bridge_has_stale_launcher", ui)
        self.assertIn(
            'strstr(reason,"Installed Steam Bridge launcher is outdated or unverified:")',
            ui
        )
        self.assertIn('title="Update Steam Bridge"', ui)
        self.assertIn(
            'else if(pc2_bridge_has_stale_launcher(state,pc2_bridge_ready_reason))',
            ui
        )
        self.assertIn('pc2_steam_bridge_action("upgrade");', ui)
        self.assertIn(
            'else if(!strcmp(state,"steam")||!strcmp(state,"repair"))',
            ui
        )
        self.assertIn(
            'if(global_upgrade)', ui
        )
        self.assertIn(
            'GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO', ui
        )

    def test_primary_action_read_only_and_no_steam_mapping_mutations(self):
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            original = bridge.config_path().read_bytes()
            with patch.object(bridge, "steam_compat_selection",
                              return_value="OTHER TOOL SELECTED (saved Steam mapping: Proton Experimental)"):
                state, reason = bridge.primary_ui_state("2353250")
                self.assertEqual(state, "steam")
                self.assertIn("Properties > Compatibility", reason)
            self.assertEqual(bridge.config_path().read_bytes(), original)
            self.assertFalse((self.steam / "config/config.vdf").exists())

    def test_wemod_gpu_fallback_is_explicit_per_game_and_reversible(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("2353250", self.proton, self.client, enabled=True)
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            original = bridge.load_config()
            self.assertFalse(original["2353250"].get("wemod_disable_gpu", False))
            self.assertTrue(bridge.set_trainer_gpu_fallback("3008130", True))
            result = bridge.load_config()
            self.assertEqual(result["3008130"]["wemod_disable_gpu"], True)
            self.assertFalse(result["2353250"].get("wemod_disable_gpu", False))
            self.assertTrue(result["3008130"]["trainer_enabled"])
            self.assertIn("ENABLED (WeMod.exe --disable-gpu)",
                          bridge.format_status("3008130"))
            self.assertFalse(bridge.set_trainer_gpu_fallback("3008130", False))
            self.assertFalse(bridge.load_config()["3008130"]["wemod_disable_gpu"])
            self.assertNotIn("wemod_disable_gpu", bridge.load_config()["2353250"])
            with self.assertRaisesRegex(ValueError,"no configured Steam Bridge"):
                bridge.set_trainer_gpu_fallback("999888", True)

    def test_only_wemod_gets_gpu_fallback_argument(self):
        # No game or trainer executes: subprocess.Popen is replaced by a fixture.
        import subprocess
        with patch.dict(os.environ, self.env):
            (self.client / "resources/app.asar.backup").write_bytes(b"backup")
            (self.client / "version.dll").write_bytes(b"dll")
            entry={"proton":str(self.proton), "client":str(self.client),
                   "trainer_enabled":True, "wemod_disable_gpu":True}
            with patch.object(bridge.subprocess, "Popen",
                              return_value=unittest.mock.Mock(pid=1234)) as popen:
                bridge.start_trainer(entry, "3008130", self.proton)
                command=popen.call_args.args[0]
                self.assertEqual(command,
                    [str(self.proton),"runinprefix",str(self.client/"WeMod.exe"),
                     "--disable-gpu"])
            entry["wemod_disable_gpu"]=False
            with patch.object(bridge.subprocess, "Popen",
                              return_value=unittest.mock.Mock(pid=1234)) as popen:
                bridge.start_trainer(entry, "2353250", self.proton)
                self.assertEqual(popen.call_args.args[0],
                    [str(self.proton),"runinprefix",str(self.client/"WeMod.exe")])

    def test_netfx_readonly_scan_reports_prefix_evidence_without_modifying_files(self):
        with patch.dict(os.environ, self.env):
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir(parents=True)
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text('"appid" "3008130"')
            prefix = self.steam / "steamapps/compatdata/3008130/pfx"
            prefix.mkdir(parents=True)
            registry = prefix / "system.reg"
            registry.write_text('[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]\n"Release"=dword:00080cf0\n')
            before = registry.read_bytes()
            report = bridge.dotnet_prefix_status("3008130", game)
            self.assertIn("00080cf0", report)
            self.assertIn("read-only", report)
            self.assertEqual(registry.read_bytes(), before)
            self.assertFalse((self.steam / "steamapps/compatdata/2353250").exists())

    def test_netfx_scan_handles_missing_prefix_and_rejects_wrong_game(self):
        with patch.dict(os.environ, self.env):
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir(parents=True)
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text('"appid" "3008130"')
            self.assertIn("not proof of missing .NET",
                          bridge.dotnet_prefix_status("3008130", game))
            with self.assertRaisesRegex(ValueError, "matching manifest"):
                bridge.dotnet_prefix_status("2353250", game)

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
