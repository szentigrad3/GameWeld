#!/usr/bin/env python3
"""Offline GameWeld Steam Compatibility Bridge contract tests."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
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

    def test_preflight_is_game_scoped_read_only_and_never_claims_runtime(self):
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            bridge.set_trainer_gpu_fallback("3008130", True)
            (self.client / "version.dll").write_bytes(b"enhancer")
            (self.client / "resources/app.asar.backup").write_bytes(b"original")
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir(parents=True)
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text(
                '"appid" "3008130"'
            )
            prefix = self.steam / "steamapps/compatdata/3008130/pfx"
            prefix.mkdir(parents=True)
            registry = prefix / "system.reg"
            registry.write_text(
                '[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]\n'
                '"Install"=dword:00000001\n'
            )
            state_dir = self.home / ".local/state/gameweld"
            state_dir.mkdir(parents=True)
            (state_dir / "steam-bridge-3008130-111-222.log").write_text(
                "GameWeld Steam bridge: unverified WeMod runtime\n"
                "WeMod GPU fallback: enabled\n"
            )
            # A different title's GPU failures must never appear in the
            # selected-game report.
            (state_dir / "steam-bridge-2353250-333-444.log").write_text(
                "WeMod GPU fallback: disabled\n"
                "GPU process has crashed 1603 time(s)\n"
            )
            before_registry = registry.read_bytes()
            before_config = bridge.config_path().read_bytes()
            with patch.object(
                bridge, "steam_compat_selection",
                return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)",
            ):
                report = bridge.preflight_report("3008130", game_dir=game)
            self.assertIn("Next action: PLAY", report)
            self.assertIn("GPU fallback: ENABLED", report)
            self.assertIn("Previous Bridge handoff log: found; GPU fallback: ENABLED", report)
            self.assertIn("registration entries found", report)
            self.assertIn("runtime functionality NOT verified", report)
            self.assertIn("Live game/WeMod connection: NOT VERIFIED", report)
            self.assertNotIn("GPU process has crashed 1603", report)
            self.assertEqual(registry.read_bytes(), before_registry)
            self.assertEqual(bridge.config_path().read_bytes(), before_config)
            self.assertFalse((self.steam / "config/config.vdf").exists())

    def test_missing_clr_both_architectures_warns_even_with_registry_claim(self):
        with patch.dict(os.environ, self.env):
            bridge.register(self.steam, source=SCRIPT)
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            (self.client / "version.dll").write_bytes(b"fixture")
            (self.client / "resources/app.asar.backup").write_bytes(b"fixture")
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir(parents=True)
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text(
                '"appid" "3008130"'
            )
            prefix = self.steam / "steamapps/compatdata/3008130/pfx"
            prefix.mkdir(parents=True)
            registry = prefix / "system.reg"
            registry.write_text(
                '[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]\n'
                '"Release"=dword:00082348\n'
            )
            folder = prefix / "drive_c/windows/Microsoft.NET"
            for arch in ("Framework", "Framework64"):
                runtime = folder / arch / "v4.0.30319"
                runtime.mkdir(parents=True)
                (runtime / "mscorlib.dll").write_bytes(b"short-placeholder")
            before = registry.read_bytes()
            with patch.object(
                bridge, "steam_compat_selection",
                return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
            ), patch.object(
                bridge.subprocess, "Popen",
                side_effect=AssertionError("read-only inspection started a process")
            ):
                report = bridge.preflight_report("3008130", game_dir=game)
            with patch.object(
                bridge, "steam_compat_selection",
                return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
            ):
                self.assertEqual(
                    bridge.primary_ui_state("3008130", game_dir=game)[0],
                    "runtime"
                )
            self.assertIn("Next action: INVESTIGATE WINDOWS .NET RUNTIME", report)
            self.assertIn("no game prefix or Steam setting was changed", report)
            self.assertIn("registration entries found", report)
            self.assertIn(".NET CLR Framework/clr.dll: MISSING", report)
            self.assertIn(".NET CLR Framework64/clr.dll: MISSING", report)
            self.assertIn("both Windows .NET Framework v4 clr.dll files are missing", report)
            self.assertIn("registration alone cannot establish a working CLR", report)
            self.assertIn("Live game/WeMod connection: NOT VERIFIED", report)
            self.assertEqual(registry.read_bytes(), before)

    def test_clr_evidence_present_is_not_proof_of_runtime(self):
        with patch.dict(os.environ, self.env):
            prefix = self.root / "independent-game/pfx"
            for arch in ("Framework", "Framework64"):
                runtime = prefix / "drive_c/windows/Microsoft.NET" / arch / "v4.0.30319"
                runtime.mkdir(parents=True)
                (runtime / "clr.dll").write_bytes(b"test-mock-dll")
                (runtime / "mscorlib.dll").write_bytes(b"test-mock-mscorlib")
            report = "\n".join(bridge.netfx_clr_evidence(prefix))
            self.assertIn("Framework/clr.dll: present", report)
            self.assertIn("Framework64/clr.dll: present", report)
            self.assertIn("loading and WeMod compatibility NOT verified", report)
            self.assertNotIn("WARNING:", report)

    def test_clr_evidence_missing_or_symlinked_prefix_is_inconclusive(self):
        with patch.dict(os.environ, self.env):
            absent = self.root / "missing/pfx"
            self.assertIn("INCONCLUSIVE", "\n".join(bridge.netfx_clr_evidence(absent)))
            prefix = self.root / "working/pfx"
            (prefix / "drive_c/windows/Microsoft.NET").mkdir(parents=True)
            link = self.root / "prefix-link"
            link.symlink_to(prefix, target_is_directory=True)
            self.assertIn("INCONCLUSIVE", "\n".join(bridge.netfx_clr_evidence(link)))
            self.assertNotIn("WARNING:", "\n".join(bridge.netfx_clr_evidence(link)))

    def test_preflight_unconfigured_does_not_run_installers(self):
        with patch.dict(os.environ, self.env):
            with patch.object(
                bridge.subprocess, "Popen",
                side_effect=AssertionError("preflight must not launch processes"),
            ):
                report = bridge.preflight_report("3008130")
            self.assertIn("Next action: SETUP", report)
            self.assertIn("not configured", report)
            self.assertIn("Live game/WeMod connection: NOT VERIFIED", report)
            self.assertFalse(bridge.config_path().exists())

    def test_isolated_netfx_plan_never_creates_a_prefix_or_runs_proton(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text(
                '"appid" "3008130"'
            )
            live = self.steam / "steamapps/compatdata/3008130/pfx"
            live.mkdir(parents=True)
            existing = live / "user.reg"
            existing.write_text("KEEP-ME")
            cache = self.home / ".cache/gameweld/netfx-isolation/appid-3008130"
            before = bridge.config_path().read_bytes()
            with patch.object(bridge.subprocess, "Popen",
                              side_effect=AssertionError("Proton must not execute")), \
                 patch.object(bridge.subprocess, "call",
                              side_effect=AssertionError("Winetricks must not execute")), \
                 patch.object(bridge.shutil, "disk_usage",
                              return_value=SimpleNamespace(free=16 * 1024 ** 3)), \
                 patch.object(bridge, "steam_compat_selection",
                              return_value="GAMEWELD BRIDGE SELECTED (saved Steam mapping)"):
                plan = bridge.netfx_isolation_plan("3008130", game)
            self.assertIn("PLAN ONLY (READ-ONLY", plan)
            self.assertIn("Saved Proton executable:", plan)
            self.assertIn("Scratch filesystem free space: 16.0 GiB available", plan)
            self.assertIn("Steam saved compatibility selection: GAMEWELD BRIDGE SELECTED", plan)
            self.assertIn("Actual live Proton executable/version: NOT VERIFIED", plan)
            self.assertIn("Workspace check: AVAILABLE FOR A FUTURE APPROVED TEST", plan)
            self.assertIn("NOT SELECTED OR VERIFIED", plan)
            self.assertIn("Experiment gate: NOT READY — no GE-Proton10 candidate detected", plan)
            self.assertIn("proton-ge-custom/releases/tag/GE-Proton10-34", plan)
            self.assertIn("dotnet.microsoft.com/en-us/download/dotnet-framework/net48", plan)
            self.assertIn("No automatic promotion/copying", plan)
            self.assertFalse(cache.exists())
            self.assertEqual(existing.read_text(), "KEEP-ME")
            self.assertEqual(bridge.config_path().read_bytes(), before)
            self.assertFalse((self.steam / "config/config.vdf").exists())

    def test_isolated_netfx_plan_blocks_occupied_and_symlinked_scratch(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            target = self.home / ".cache/gameweld/netfx-isolation/appid-3008130"
            target.mkdir(parents=True)
            self.assertIn("Workspace check: BLOCKED",
                          bridge.netfx_isolation_plan("3008130", game))
            target.rmdir()
            target.symlink_to(self.steam / "steamapps", target_is_directory=True)
            self.assertIn("Workspace check: BLOCKED",
                          bridge.netfx_isolation_plan("3008130", game))
            self.assertTrue(target.is_symlink())

    def test_isolated_netfx_plan_blocks_symlinked_cache_ancestor(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=False)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            cache_alias = self.home / "cache-link"
            cache_alias.symlink_to(self.steam / "steamapps", target_is_directory=True)
            with patch.dict(os.environ, {"XDG_CACHE_HOME": str(cache_alias)}):
                report = bridge.netfx_isolation_plan("3008130", game)
            self.assertIn("Workspace check: BLOCKED", report)
            self.assertTrue(cache_alias.is_symlink())
            self.assertFalse((self.steam / "steamapps/gameweld").exists())

    def test_isolated_netfx_plan_refuses_workspace_inside_steam_library(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=False)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            unsafe_cache = self.steam / "steamapps/other-diagnostics"
            with patch.dict(os.environ, {"XDG_CACHE_HOME": str(unsafe_cache)}), \
                 patch.object(bridge.shutil, "disk_usage",
                              return_value=SimpleNamespace(free=16 * 1024 ** 3)):
                report = bridge.netfx_isolation_plan("3008130", game)
            self.assertIn("Workspace check: BLOCKED", report)
            self.assertFalse(unsafe_cache.exists())

    def test_ge_proton10_candidate_found_without_selection_or_execution(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            candidate = self.home / ".steam/root/compatibilitytools.d/GE-Proton10-34"
            candidate.mkdir(parents=True)
            executable = candidate / "proton"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
            (candidate / "toolmanifest.vdf").write_text('"manifest" {}\n')
            before = bridge.config_path().read_bytes()
            with patch.object(bridge.shutil, "disk_usage",
                              return_value=SimpleNamespace(free=16 * 1024 ** 3)), \
                 patch.object(bridge.subprocess, "Popen",
                              side_effect=AssertionError("no candidate may launch")):
                plan = bridge.netfx_isolation_plan("3008130", game)
            self.assertIn("GE-Proton10 possible runners found: 1", plan)
            self.assertIn("Experiment gate: NOT READY — no offline .NET installer selected", plan)
            self.assertIn(str(executable), plan)
            self.assertIn("Wine engine version and .NET installation compatibility: UNVERIFIED", plan)
            self.assertIn("preserve the saved game Proton", plan)
            self.assertIn(str(self.proton.resolve()), plan)
            self.assertEqual(bridge.config_path().read_bytes(), before)
            self.assertFalse((self.home / ".cache").exists())

    def test_ge_proton10_managed_runtime_is_discovered_without_running_it(self):
        with patch.dict(os.environ, self.env):
            managed = self.data / "gameweld/repair-runtimes/GE-Proton10-34"
            managed.mkdir(parents=True)
            exe = managed / "proton"
            exe.write_text("#!/bin/sh\nexit 77\n")
            exe.chmod(0o755)
            (managed / "toolmanifest.vdf").write_text('"manifest" {}\n')
            with patch.object(
                bridge.subprocess, "Popen",
                side_effect=AssertionError("candidate must never run"),
            ), patch.object(
                bridge.subprocess, "run",
                side_effect=AssertionError("candidate must never run"),
            ):
                matches = bridge.discover_ge_proton10_candidates(
                    self.steam / "steamapps"
                )
            self.assertEqual(matches, [exe.resolve()])

    def test_ge_proton10_heroic_runtime_is_discovered_without_settings_change(self):
        with patch.dict(os.environ, self.env):
            heroic = self.home / ".config/heroic/tools/proton/GE-Proton10-34"
            heroic.mkdir(parents=True)
            exe = heroic / "proton"
            exe.write_text("#!/bin/sh\nexit 77\n")
            exe.chmod(0o755)
            (heroic / "toolmanifest.vdf").write_text('"manifest" {}\n')
            matches = bridge.discover_ge_proton10_candidates(self.steam / "steamapps")
            self.assertEqual(matches, [exe.resolve()])
            self.assertFalse(bridge.config_path().exists())

    def test_ge_proton10_managed_runtime_rejects_missing_manifest(self):
        with patch.dict(os.environ, self.env):
            managed = self.data / "gameweld/repair-runtimes/GE-Proton10-34"
            managed.mkdir(parents=True)
            exe = managed / "proton"
            exe.write_text("#!/bin/sh\nexit 77\n")
            exe.chmod(0o755)
            matches = bridge.discover_ge_proton10_candidates(self.steam / "steamapps")
            self.assertEqual(matches, [])
            self.assertTrue(exe.exists())

    def test_ge_proton10_candidate_skips_symlink_and_invalid_lookalikes(self):
        with patch.dict(os.environ, self.env):
            root = self.steam / "compatibilitytools.d"
            root.mkdir()
            good = root / "GE-Proton10-34"
            good.mkdir()
            exe = good / "proton"
            exe.write_bytes(b"#!/bin/sh\n")
            exe.chmod(0o755)
            (good / "toolmanifest.vdf").write_text("manifest")
            bad11 = root / "GE-Proton11-1"
            bad11.mkdir()
            (bad11 / "proton").write_bytes(b"not-validated")
            bad10 = root / "GE-Proton10-35"
            bad10.mkdir()
            (bad10 / "proton").write_bytes(b"not-validated")
            alias = self.home / ".steam/root/compatibilitytools.d/GE-Proton10-36"
            alias.parent.mkdir(parents=True)
            alias.symlink_to(good, target_is_directory=True)
            items = bridge.discover_ge_proton10_candidates(self.steam / "steamapps")
            self.assertEqual(items, [exe.resolve()])
            self.assertTrue(alias.is_symlink())

    def test_isolated_netfx_plan_low_disk_space_blocks_future_test(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=False)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            with patch.object(bridge.shutil, "disk_usage",
                              return_value=SimpleNamespace(free=3 * 1024 ** 3)):
                plan = bridge.netfx_isolation_plan("3008130", game)
            self.assertIn("Workspace check: BLOCKED", plan)
            self.assertIn("3.0 GiB available", plan)
            self.assertIn("(LOW SPACE)", plan)
            self.assertIn("Experiment gate: BLOCKED", plan)
            self.assertFalse((self.home / ".cache").exists())

    def test_isolated_netfx_plan_optional_installer_hash_is_evidence_only(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            candidate = self.root / "offline-net-installer.exe"
            candidate.write_bytes(b"MZ-MOCK-NOT-AN-INSTALLER")
            expected = bridge.hashlib.sha256(candidate.read_bytes()).hexdigest()
            with patch.object(bridge.shutil, "disk_usage",
                              return_value=SimpleNamespace(free=16 * 1024 ** 3)), \
                 patch.object(bridge.subprocess, "Popen",
                              side_effect=AssertionError("installer must not run")):
                plan = bridge.netfx_isolation_plan("3008130", game, installer_path=candidate)
                self.assertIn("NOT VERIFIED against a trusted publisher", plan)
                checked = bridge.netfx_isolation_plan(
                    "3008130", game, installer_path=candidate, expected_sha256=expected
                )
                mismatch = bridge.netfx_isolation_plan(
                    "3008130", game, installer_path=candidate, expected_sha256="0" * 64
                )
            self.assertIn("MATCHES supplied digest", checked)
            self.assertIn("publisher provenance must still be independently verified", checked)
            self.assertIn("MISMATCH — DO NOT EXECUTE", mismatch)
            self.assertIn("prefix creation, registry changes and DLL copies: NOT PERFORMED", checked)
            self.assertEqual(candidate.read_bytes(), b"MZ-MOCK-NOT-AN-INSTALLER")

    def test_isolated_netfx_plan_rejects_symlinked_installer(self):
        with patch.dict(os.environ, self.env):
            bridge.configure("3008130", self.proton, self.client, enabled=True)
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            file = self.root / "candidate.exe"
            file.write_bytes(b"MZ-TEST")
            symlink = self.root / "installer-link.exe"
            symlink.symlink_to(file)
            with self.assertRaisesRegex(ValueError, "non-symlinked"):
                bridge.netfx_isolation_plan("3008130", game, installer_path=symlink)
            with self.assertRaisesRegex(ValueError, "requires --installer-path"):
                bridge.netfx_isolation_plan("3008130", game, expected_sha256="0" * 64)

    def test_isolated_netfx_plan_rejects_wrong_game_and_unconfigured(self):
        with patch.dict(os.environ, self.env):
            game = self.steam / "steamapps/common/Dying Light The Beast"
            game.mkdir()
            (self.steam / "steamapps/appmanifest_3008130.acf").write_text("manifest")
            with self.assertRaisesRegex(ValueError, "Configure this game"):
                bridge.netfx_isolation_plan("3008130", game)
            bridge.configure("3008130", self.proton, self.client, enabled=False)
            with self.assertRaisesRegex(ValueError, "matching AppID"):
                bridge.netfx_isolation_plan("2353250", game)
            self.assertFalse((self.home / ".cache").exists())

    def test_preflight_gui_wiring_stays_read_only(self):
        ui = (Path(__file__).resolve().parents[1] /
              "crates/wand-ui/appimage-gtk3/gameweld-native-040.c").read_text()
        # Discovery mode's button factory explicitly disables all actions
        # except its exact allowlist. A label rename must update that list
        # or the GTK button stays greyed out before the click handler runs.
        guard = ui.split('static GtkWidget *button(const char *s, const char *cls) {', 1)[1]
        guard = guard.split('static GtkWidget *box(', 1)[0]
        self.assertIn('strcmp(s, "Check WeMod readiness")', guard)
        self.assertIn('strcmp(s, "Open WeMod & DeckCheatz setup")', guard)
        self.assertIn('gtk_notebook_set_current_page((GtkNotebook*)notebook,1);', ui)
        self.assertNotIn('strcmp(s, "Steam Bridge: Check selected game")', guard)
        self.assertIn('pc2_guard_button(w)', guard)
        self.assertIn('button("Check WeMod readiness","action")', ui)
        self.assertIn('strcmp(s, "Plan safe .NET test (read-only)")', guard)
        self.assertIn('button("Plan safe .NET test (read-only)","action")', ui)
        self.assertIn('pack(bridge_maintenance_box,netfx_plan,0);', ui)
        self.assertNotIn('pack(bridge_card,netfx_plan,0);', ui)
        self.assertIn('pc2_steam_bridge_action("netfx-plan");', ui)
        self.assertIn('!strcmp(job->result,"runtime")', ui)
        self.assertIn('gtk_button_set_label((GtkButton*)buttons[i],"Check WeMod setup");', ui)
        self.assertIn('pc2_steam_bridge_action("native-route");', ui)
        self.assertIn('strcmp(action,"netfx-plan")', ui)
        self.assertIn('strcmp(j->action,"netfx-plan")', ui)
        self.assertIn('strcmp(s, "Find prepared WeMod setup")', guard)
        self.assertIn('button("Find prepared WeMod setup","action")', ui)
        self.assertIn('pack(deckpage,shared_card,0);', ui)
        self.assertIn('pc2_shared_wemod_status', ui)
        self.assertIn('int global_catalog=!strcmp(action,"prefix-catalog");', ui)
        self.assertIn('int native_route=!strcmp(action,"native-route");', ui)
        self.assertIn('button("Check game WeMod connection","action")', ui)
        self.assertIn('pack(deckpage,native_card,0);', ui)
        self.assertIn('strcmp(s, "Check game WeMod connection")', guard)
        self.assertIn('strcmp(s, "Check WeMod setup")', guard)
        self.assertNotIn('strcmp(s, "Legacy: Play using existing Steam Bridge")', guard)
        self.assertIn('argv[n++]=pc2_native_route_helper();', ui)
        self.assertIn('argv[n++]="--format";argv[n++]="text";', ui)
        self.assertIn('strcmp(j->action,"native-route")', ui)
        self.assertIn('if(native_route)', ui)
        self.assertIn('if(!global_upgrade&&!global_catalog&&!global_cache)', ui)
        self.assertIn('pc2_prepared_prefix_catalog_helper()', ui)
        self.assertIn('argv[n++]=pc2_prepared_prefix_catalog_helper();', ui)
        self.assertIn('pc2_steam_bridge_action("prefix-catalog");', ui)
        self.assertIn('pc2_prepared_catalog_display(msg)', ui)
        self.assertIn('gtk_combo_box_set_active((GtkComboBox*)pc2_shared_wemod_choices,-1);', ui)
        self.assertIn('pc2_cache_collect_output(pid,pipefd[0]', ui)
        self.assertIn('argv[n++]="--progress";', ui)
        self.assertIn('pc2_cache_progress_update', ui)
        self.assertIn('button("Cancel cache download","action")', ui)
        self.assertIn('if(child>0)kill(child,SIGINT);', ui)
        self.assertIn('pc2_cache_cancel_requested=1;', ui)
        self.assertNotIn('strcmp(s, "Cancel cache download")', guard)
        self.assertIn('argv[n++]="--machine-lines";', ui)
        self.assertIn('pc2_prepared_prefix_cache_helper()', ui)
        self.assertIn('argv[n++]="--approve-cache-download";', ui)
        self.assertIn('button(\n            "Download selected prepared setup (cache only)","action");', ui)
        self.assertIn('(GCallback)on_pc2_prepared_prefix_cache,NULL,NULL,0);', ui)
        self.assertIn('if(response==GTK_RESPONSE_YES)pc2_steam_bridge_action("prefix-cache");', ui)
        self.assertIn('gtk_widget_set_sensitive(pc2_shared_wemod_download,FALSE);', ui)
        self.assertIn('!pc2_discovery_only() && pc2_provider_controls_allowed()', ui)
        self.assertIn('strcmp(j->action,"prefix-cache")', ui)
        self.assertNotIn('strcmp(s, "Download selected prepared setup (cache only)")', guard)
        self.assertIn('strcmp(action,"prefix-catalog")', ui)
        self.assertIn('strcmp(j->action,"prefix-catalog")', ui)
        self.assertIn('pc2_steam_bridge_action("preflight");', ui)
        self.assertIn('strcmp(action,"preflight")', ui)
        self.assertIn('strcmp(j->action,"preflight")', ui)
        self.assertIn('!strcmp(j->action,"preflight")', ui)
        self.assertIn('strcmp(s, "Update Steam Bridge")', guard)
        self.assertIn('button("Update Steam Bridge","action")', ui)
        self.assertIn('pc2_steam_bridge_quick_upgrade,FALSE', ui)
        self.assertIn('selected_matches &&', ui)
        self.assertIn('strstr(j->output,"Next action: REPAIR")', ui)
        self.assertIn(
            'strstr(j->output,"Installed Steam Bridge: UPDATE AVAILABLE (")', ui
        )
        self.assertIn('pc2_quick_upgrade_state(update_available,is_current)', ui)
        self.assertIn('is_current?"Steam Bridge is up to date":"Update Steam Bridge"', ui)
        self.assertIn('gtk_style_context_remove_class(style,"primary-action")', ui)
        self.assertIn('if(update_available)gtk_style_context_add_class(style,"primary-action")', ui)
        self.assertIn('gtk_widget_set_sensitive(button,update_available)', ui)
        self.assertIn('(GCallback)on_pc2_bridge_upgrade,NULL,NULL,0);', ui)

    def test_legacy_bridge_is_optional_not_primary_and_never_claims_success(self):
        ui = (Path(__file__).resolve().parents[1] /
              "crates/wand-ui/appimage-gtk3/gameweld-native-040.c").read_text()
        self.assertIn(
            "Legacy Steam Bridge — optional compatibility fallback", ui
        )
        self.assertIn('gtk_expander_set_expanded(legacy_bridge,FALSE);', ui)
        self.assertIn('legacy_bridge_play=button(', ui)
        self.assertIn('"Legacy: Play using existing Steam Bridge","action");', ui)
        self.assertIn('(GCallback)on_pc2_bridge_play,NULL,NULL,0);', ui)
        self.assertIn('pc2_steam_bridge_action("native-route");', ui)
        self.assertIn(
            'gtk_button_set_label((GtkButton*)buttons[i],"Check WeMod setup");', ui
        )
        self.assertNotIn('pack(deckpage,bridge_card,0);', ui)
        self.assertIn('GTK_MESSAGE_QUESTION,GTK_BUTTONS_YES_NO', ui)
        self.assertIn(
            "Steam Play request accepted. Game and WeMod startup are NOT YET VERIFIED",
            ui
        )
        self.assertNotIn("Steam launch ASSOCIATION OBSERVED", ui)

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
