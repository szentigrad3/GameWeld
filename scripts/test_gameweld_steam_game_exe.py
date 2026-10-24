#!/usr/bin/env python3
"""Offline EXE resolver checks; no Steam, Proton, game or GUI execution."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).with_name("gameweld-steam-game-exe.py")
spec = importlib.util.spec_from_file_location("gameweld_steam_game_exe", MODULE)
resolver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resolver
spec.loader.exec_module(resolver)


class SteamGameExeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-steam-exe-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.steamapps = root / "SteamLibrary" / "steamapps"
        self.game = self.steamapps / "common" / "Astrometica"
        self.game.mkdir(parents=True)
        (self.steamapps / "appmanifest_2353250.acf").write_text('"appid" "2353250"')

    def exe(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ" + b"\0" * 62)
        return path

    def test_simple_astrometica_launch_without_picker(self):
        exe = self.exe(self.game / "Astrometica.exe")
        r = resolver.resolve("2353250", self.game, "Astrometica")
        self.assertEqual(r["selected"], str(exe))
        self.assertEqual(r["candidate_count"], 1)

    def test_detects_unreal_engine_win64_shipping(self):
        exe = self.exe(self.game / "Binaries" / "Win64" / "Astrometica-Win64-Shipping.exe")
        r = resolver.resolve("2353250", self.game, "Astrometica")
        self.assertEqual(r["selected"], str(exe))

    def test_rejects_ambiguous_generic_executables(self):
        self.exe(self.game / "game.exe")
        self.exe(self.game / "application.exe")
        r = resolver.resolve("2353250", self.game, "Astrometica")
        self.assertFalse(r["selected"])
        self.assertTrue(r["ambiguous"])

    def test_ignores_installers_and_redistributables(self):
        self.exe(self.game / "_CommonRedist" / "vcredist.exe")
        self.exe(self.game / "Setup.exe")
        target = self.exe(self.game / "Astrometica.exe")
        r = resolver.resolve("2353250", self.game, "Astrometica")
        self.assertEqual(r["selected"], str(target))

    def test_rejects_symlink_and_outside_install_preference(self):
        root = Path(self.tmp.name)
        external = self.exe(root / "external.exe")
        (self.game / "Astrometica.exe").symlink_to(external)
        r = resolver.resolve("2353250", self.game, "Astrometica",
                             preferred=str(external))
        self.assertFalse(r["selected"])

    def test_preferred_valid_pe_within_install(self):
        target = self.exe(self.game / "Binaries" / "Win64" / "Unusual.exe")
        r = resolver.resolve("2353250", self.game, "Astrometica",
                             preferred=str(target))
        self.assertEqual(r["selected"], str(target))
        self.assertEqual(r["reason"], "Verified game-discovery target")

    def test_rejects_wrong_or_missing_appmanifest(self):
        self.exe(self.game / "Astrometica.exe")
        r = resolver.resolve("123456", self.game, "Astrometica")
        self.assertFalse(r["selected"])

    def test_rejects_non_executable_magic(self):
        target = self.game / "Astrometica.exe"
        target.write_bytes(b"NOT_EXE" + b"\0" * 100)
        r = resolver.resolve("2353250", self.game, "Astrometica")
        self.assertFalse(r["selected"])


if __name__ == "__main__":
    unittest.main()
