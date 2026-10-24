#!/usr/bin/env python3
"""Offline synthetic Steam prefixes: never launches or changes Steam/Wine."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

script = Path(__file__).with_name("gameweld-wemod-prefix-readiness.py")
spec = importlib.util.spec_from_file_location("gameweld_wemod_prefix_readiness", script)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


class PrefixReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gw-dotnet-fixture-")
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.library = self.home / "games" / "SteamLibrary"
        self.apps = self.library / "steamapps"
        self.apps.mkdir(parents=True)
        self.prefix = self.apps / "compatdata" / "2353250"
        (self.prefix / "pfx").mkdir(parents=True)
        self.reg = self.prefix / "pfx" / "system.reg"
        self.steam = self.home / ".local/share/Steam"
        (self.steam / "steamapps").mkdir(parents=True)
        (self.steam / "steamapps" / "libraryfolders.vdf").write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"' +
            str(self.library) + '"\n\t}\n}\n'
        )

    def write_reg(self, release, *, install=True):
        self.reg.write_text(
            "WINE REGISTRY Version 2\n"
            "[Software\\\\Microsoft\\\\Other]\n"
            '"Release"=dword:ffffffff\n'
            "[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]\n"
            f'"Install"=dword:{int(install):08x}\n'
            f'"Release"=dword:{release:08x}\n'
            "[Software\\\\Microsoft\\\\Next]\n"
            '"Release"=dword:ffffffff\n'
        )

    def test_finds_library_from_vdf(self):
        self.assertEqual(
            tool.find_prefixes("2353250", home=self.home), [self.prefix]
        )

    def test_pinned_dotnet48_registry_proof_is_only_a_hint(self):
        self.write_reg(528040)
        result = tool.inspect("2353250", home=self.home)
        self.assertEqual(result["result"], "prefixes_found")
        p = result["matching_prefixes"][0]
        self.assertEqual(p["state"], "registry_indicates_net48_or_later")
        self.assertTrue(p["registry_indicates_net48"])
        self.assertFalse(p["net48_verified"])
        self.assertEqual(result["actions_performed"], "none")

    def test_v47_is_below_threshold(self):
        self.write_reg(461808)
        p = tool.inspect("2353250", home=self.home)["matching_prefixes"][0]
        self.assertEqual(p["state"], "registry_below_net48_or_not_installed")
        self.assertFalse(p["registry_indicates_net48"])

    def test_missing_key_not_claimed_absent(self):
        self.reg.write_text(
            "[Software\\\\Microsoft\\\\Other]\n"
            '"Release"=dword:ffffffff\n'
        )
        p = tool.inspect("2353250", home=self.home)["matching_prefixes"][0]
        self.assertEqual(p["state"], "net48_release_not_detected")
        self.assertFalse(p["net48_verified"])

    def test_missing_registry_retains_prefix(self):
        p = tool.inspect("2353250", home=self.home)["matching_prefixes"][0]
        self.assertEqual(p["state"], "system_reg_missing_or_unreadable")
        self.assertTrue(self.prefix.exists())

    def test_bad_appids_are_rejected(self):
        for appid in ("", "0", "../../tmp", "2353250;rm -rf", "not-a-number"):
            with self.assertRaises(ValueError):
                tool.find_prefixes(appid, home=self.home)

    def test_prefix_without_pfx_not_discovered(self):
        (self.prefix / "pfx").rmdir()
        self.assertEqual(tool.find_prefixes("2353250", home=self.home), [])

    def test_registry_read_does_not_modify_any_files(self):
        self.write_reg(528040)
        before = self.reg.read_bytes()
        tool.inspect("2353250", home=self.home)
        self.assertEqual(self.reg.read_bytes(), before)
        self.assertEqual(self.reg.stat().st_mode & 0o222, 0o200)

    def test_uninstalled_flag_prevents_positive(self):
        self.write_reg(528040, install=False)
        p = tool.inspect("2353250", home=self.home)["matching_prefixes"][0]
        self.assertFalse(p["registry_indicates_net48"])

    def test_duplicate_steam_roots_do_not_duplicate_prefix(self):
        self.write_reg(528040)
        p = tool.find_prefixes(
            "2353250", steam_roots=[self.library, self.library]
        )
        self.assertEqual(p, [self.prefix])


if __name__ == "__main__":
    unittest.main()
