#!/usr/bin/env python3
"""No Steam, Proton, Wine, WeMod, network or game launched in these fixtures."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-steam-wemod-platform.py")
spec = importlib.util.spec_from_file_location("gw_pc2_steam_wemod", SCRIPT)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


class SteamOwnedWeModTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="gw-steam-wemod-")
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.steam = self.root / "steam"
        steamapps = self.steam / "steamapps"
        self.install = steamapps / "common" / "ASTROMETICA"
        self.install.mkdir(parents=True)
        (steamapps / "appmanifest_2353250.acf").write_text('"appid" "2353250"')
        self.game = self.install / "Astrometica.exe"
        self.game.write_bytes(b"MZ" + b"\0" * 128)
        self.compat = steamapps / "compatdata" / "2353250"
        (self.compat / "pfx").mkdir(parents=True)
        self.proton = self.steam / "steamapps" / "common" / "Proton" / "proton"
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text("#!/bin/sh\nexit 0\n")
        self.proton.chmod(0o755)
        self.checkout = self.root / "deckcheatz"
        (self.checkout / "src").mkdir(parents=True)
        source = self.checkout / "src" / "wemod.py"
        source.write_text("# upstream launcher fixture\n")
        self.launcher = self.checkout / "wemod"
        self.launcher.symlink_to("src/wemod.py")
        self.wemod = self.checkout / "wemod_data" / "wemod_bin" / "WeMod.exe"
        self.wemod.parent.mkdir(parents=True)
        self.wemod.write_bytes(b"MZ" + b"\0" * 128)

    def prepare(self):
        with patch.object(tool.shutil, "which", return_value="/usr/bin/steam"):
            return tool.preflight("2353250", self.install, self.game, self.compat,
                                  self.proton, self.steam, self.launcher)

    def test_preflight_existing_installed_runtime(self):
        plan = self.prepare()
        self.assertEqual(plan["appid"], "2353250")
        self.assertEqual(plan["wemod_exe"], str(self.wemod.resolve()))
        self.assertEqual(plan["mode"], "STEAM_OWNED_GAME_THEN_SAME_PREFIX_WEMOD")

    def test_missing_runtime_fails_before_steam(self):
        self.wemod.unlink()
        with self.assertRaisesRegex(ValueError, "No previously installed"):
            self.prepare()

    def test_reject_wrong_game_identity(self):
        with patch.object(tool.shutil, "which", return_value="/usr/bin/steam"):
            with self.assertRaisesRegex(ValueError, "matching Steam appmanifest"):
                tool.preflight("12345", self.install, self.game, self.compat,
                               self.proton, self.steam, self.launcher)

    def test_existing_game_does_not_start_second_copy(self):
        plan = self.prepare()
        invocations = []
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        def start(appid):
            invocations.append(("steam", appid))
        def spawn(args, **kwargs):
            invocations.append(("wemod", args, kwargs))
            return SimpleNamespace(pid=890)
        messages = []
        result = tool.launch(plan, observer=Observer(), start_steam=start,
                             spawn=spawn, log=messages.append)
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertFalse(result["trainer_verified"])
        self.assertEqual(len(invocations), 1)
        self.assertEqual(invocations[0][0], "wemod")
        self.assertEqual(invocations[0][1][1], "runinprefix")
        self.assertEqual(invocations[0][2]["env"]["STEAM_COMPAT_APP_ID"], "2353250")
        self.assertEqual(invocations[0][2]["env"]["STEAM_COMPAT_DATA_PATH"],
                         plan["compatdata"])

    def test_game_must_appear_before_wemod(self):
        plan = self.prepare()
        calls = []
        class Observer:
            count = 0
            @classmethod
            def matching_game_processes(cls, *args):
                cls.count += 1
                return [100] if cls.count == 2 else []
        def start(appid):
            calls.append(("steam", appid))
        def spawn(args, **kwargs):
            calls.append(("wemod", args))
            return SimpleNamespace(pid=101)
        with patch.object(tool.time, "sleep", return_value=None):
            result = tool.launch(plan, observer=Observer(), start_steam=start,
                                 spawn=spawn, log=lambda msg: None, timeout=3)
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertEqual(calls[0], ("steam", "2353250"))
        self.assertEqual(calls[1][0], "wemod")
        self.assertFalse(result["trainer_verified"])

    def test_no_game_never_starts_trainer(self):
        plan = self.prepare()
        calls = []
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return []
        result = tool.launch(plan, observer=Observer(),
                             start_steam=lambda appid: calls.append(("steam", appid)),
                             spawn=lambda *args, **kwargs: self.fail("spawn called"),
                             log=lambda msg: None, timeout=0)
        self.assertEqual(calls, [("steam", "2353250")])
        self.assertEqual(result["state"], "GAME_PROCESS_UNCONFIRMED")
        self.assertFalse(result["trainer_verified"])

    def test_prefix_validation_never_creates_prefix(self):
        (self.compat / "pfx").rmdir()
        with self.assertRaisesRegex(ValueError, "uninitialized game Proton prefix"):
            self.prepare()
        self.assertFalse((self.compat / "pfx").exists())


if __name__ == "__main__":
    unittest.main()
