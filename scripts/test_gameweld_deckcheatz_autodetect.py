#!/usr/bin/env python3
"""Offline Steam/DeckCheatz auto-discovery tests; never starts real games."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-autodetect.py")
SPEC = importlib.util.spec_from_file_location("gameweld_deckcheatz_auto", SOURCE)
assert SPEC and SPEC.loader
auto = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auto)


class AutoDiscoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="gw-auto-deckcheatz-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.steam = self.base / "Steam"
        self.library = self.base / "Games"
        (self.steam / "steamapps").mkdir(parents=True)
        (self.steam / "userdata").mkdir()
        (self.library / "steamapps").mkdir(parents=True)
        (self.steam / "steamapps/libraryfolders.vdf").write_text(
            '"libraryfolders" { "0" { "path" "' + str(self.steam) + '" } '
            '"1" { "path" "' + str(self.library) + '" "apps" {"3008130" "1"} } }')
        self.appid = "3008130"
        self.game = self.library / "steamapps/common/Dying Light The Beast"
        self.game.mkdir(parents=True)
        self.exe = self.game / "ph_x64/DyingLightTheBeast.exe"
        self.exe.parent.mkdir()
        self.exe.write_bytes(b"MZ-DYING-LIGHT-TEST")
        self.tool = self.game / "ph_x64/Settings.exe"
        self.tool.write_bytes(b"MZ-TOOL-TEST")
        (self.library / "steamapps/appmanifest_3008130.acf").write_text(
            '"AppState" { "appid" "3008130" "name" "Dying Light: The Beast" '
            '"installdir" "Dying Light The Beast" }')
        self.compat = self.library / "steamapps/compatdata/3008130"
        (self.compat / "pfx").mkdir(parents=True)
        (self.compat / "version").write_text("GE-Proton10.1\n")
        self.proton = self.steam / "compatibilitytools.d/GE-Proton10.1/proton"
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text("#!/bin/sh\n")
        self.proton.chmod(0o755)
        self.checkout = self.base / "DeckCheatz"
        (self.checkout / "src").mkdir(parents=True)
        (self.checkout / "src/wemod.py").write_text("#!/usr/bin/env python3\n")
        (self.checkout / "wemod").symlink_to("src/wemod.py")
        (self.checkout / "README.md").write_text("WeMod Launcher\n")
        (self.checkout / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE")
        self.launcher = self.checkout / "wemod"
        self.flags = ["--appid", self.appid,
                      "--steam-root", str(self.steam),
                      "--launcher", str(self.launcher)]
        self.env = {"GAME_EXE": "", "PROTON_DIR": ""}
        self.before = {str(p.relative_to(self.base)): p.read_bytes()
                       for p in self.base.rglob("*") if p.is_file()}

    def args(self, **changes):
        defaults = dict(appid=self.appid, steam_root=self.steam,
                        game_exe=None, proton_dir=None,
                        launcher=self.launcher, game_arg=[])
        defaults.update(changes)
        return argparse.Namespace(**defaults)

    def unchanged(self):
        for name, data in self.before.items():
            self.assertEqual((self.base / name).read_bytes(), data, name)

    def test_direct_dry_run_discovers_game_and_proton_without_writes(self):
        with patch.dict(os.environ, self.env), patch.object(
                auto, "steam_running", return_value=True):
            plan, flags = auto.build(self.args())
        self.assertEqual(plan["mode"], "READ_ONLY_AUTO_DISCOVERY")
        self.assertEqual(plan["game_exe"], str(self.exe))
        self.assertEqual(plan["proton"], str(self.proton))
        self.assertEqual(plan["game_working_directory"], str(self.exe.parent))
        self.assertEqual(plan["compatdata"], str(self.compat))
        self.assertEqual(plan["detected_proton_version"], "GE-Proton10.1")
        self.assertIn("--game-exe", flags)
        self.assertFalse(plan["steam_launch_options_modified"])
        self.assertFalse(plan["steam_runtime_container_reproduced"])
        self.assertFalse(plan["steamapi_overlay_drm_verified"])
        self.assertFalse(plan["safe_to_launch_claimed"])
        self.assertEqual(plan["env_overrides"]["WINEDLLOVERRIDES"], "version=n,b")
        self.assertEqual(plan["env_overrides"]["WEMOD_LOG"],
                         str(self.checkout / "wemod.log"))
        self.assertEqual(plan["env_overrides"]["SteamOverlayGameId"], self.appid)
        self.assertEqual(plan["env_overrides"]["STEAM_COMPAT_INSTALL_PATH"], str(self.game))
        self.unchanged()

    def test_cli_dry_run_never_runs_a_game_and_no_live_steam_required(self):
        out = io.StringIO()
        with patch.dict(os.environ, self.env), patch.object(
                auto, "steam_running", return_value=False), patch.object(
                auto.subprocess, "run",
                side_effect=AssertionError("dry-run must not invoke subprocess")):
            with contextlib.redirect_stdout(out):
                self.assertEqual(auto.main(["--dry-run", *self.flags]), 0)
        plan = json.loads(out.getvalue())
        self.assertFalse(plan["steam_running_detected"])
        self.assertIn(str(self.exe), plan["argv"])
        self.unchanged()

    def test_libraryfolders_registers_secondary_steam_library(self):
        self.assertEqual(auto.libraries(self.steam), [self.steam, self.library])
        self.assertEqual(auto.find_install(self.steam, self.appid)[0], self.game)

    def test_exe_ambiguity_blocks_instead_of_choosing_first_or_x64(self):
        another = self.game / "DyingLightTheBeastLauncher.exe"
        another.write_bytes(b"MZ")
        with self.assertRaisesRegex(auto.DiscoveryBlocked, "Ambiguous game executables"):
            auto.choose_exe(self.game)
        self.assertEqual(auto.choose_exe(self.game, self.exe), self.exe)
        another.unlink()
        self.unchanged()

    def test_proton_mismatch_blocks_without_guessing(self):
        (self.compat / "version").write_text("SOME-OTHER-PROTON\n")
        with self.assertRaisesRegex(auto.DiscoveryBlocked, "Could not unambiguously"):
            auto.choose_proton(self.steam, self.compat, [self.steam, self.library])
        proton, label = auto.choose_proton(
            self.steam, self.compat, [self.steam, self.library], self.proton.parent)
        self.assertEqual(proton, self.proton)
        self.assertEqual(label, "EXPLICIT_OVERRIDE")

    def test_symlinked_exe_or_manifest_never_autoruns(self):
        symlink = self.game / "DyingLightTheBeast.exe"
        symlink.symlink_to(self.exe)
        self.assertEqual(auto.choose_exe(self.game), self.exe)
        symlink.unlink()
        manifest = self.library / "steamapps/appmanifest_3008130.acf"
        manifest.unlink()
        target = self.base / "foreign.acf"
        target.write_text('"AppState" {"appid" "3008130"}')
        manifest.symlink_to(target)
        with self.assertRaisesRegex(auto.DiscoveryBlocked, "not found"):
            auto.find_install(self.steam, self.appid)
        self.assertEqual(target.read_text(), '"AppState" {"appid" "3008130"}')

    def test_launch_requires_both_acknowledgements_and_running_steam(self):
        with patch.dict(os.environ, self.env), patch.object(
                auto, "steam_running", return_value=True):
            rc = auto.main(["--launch", *self.flags])
        self.assertEqual(rc, 2)
        with patch.dict(os.environ, self.env), patch.object(
                auto, "steam_running", return_value=False):
            rc = auto.main(["--launch", *self.flags, "--confirm-prefix-changes",
                            "--experimental-direct-launch"])
        self.assertEqual(rc, 2)
        self.unchanged()

    def test_direct_launch_passes_authorizations_only_when_explicit(self):
        mock = type("FakeModule", (), {})()
        seen = []
        mock.main = lambda args: (seen.append(args), 3)[1]
        original = auto.import_script
        def interception(name, label):
            return mock if label == "gw_auto_launch" else original(name, label)
        with patch.dict(os.environ, self.env), patch.object(
                auto, "steam_running", return_value=True), patch.object(
                auto, "import_script", side_effect=interception):
            rc = auto.main(["--launch", *self.flags,
                            "--confirm-prefix-changes",
                            "--experimental-direct-launch"])
        self.assertEqual(rc, 3)
        self.assertEqual(len(seen), 1)
        self.assertIn("--confirm-prefix-changes", seen[0])
        self.assertIn("--experimental-direct-launch", seen[0])
        self.unchanged()

    def test_bad_appid_and_traversal_never_become_game_exe(self):
        with self.assertRaisesRegex(auto.DiscoveryBlocked, "AppID"):
            auto.build(self.args(appid="3008130;rm"))
        with self.assertRaisesRegex(auto.DiscoveryBlocked, "outside install"):
            auto.choose_exe(self.game, Path("/usr/bin/echo"))
        self.unchanged()

if __name__ == "__main__":
    unittest.main()
