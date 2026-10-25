#!/usr/bin/env python3
"""Offline filesystem fixtures for read-only GameWeld Proton prefix comparison."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-wemod-prefix-compare.py")
spec = importlib.util.spec_from_file_location("gw_prefix_compare", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrefixComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root / "Steam"
        self.steamapps = self.library / "steamapps"
        self.steamapps.mkdir(parents=True)
        self.backup = self.root / "backup"
        self.working = self.steamapps / "compatdata/2353250/pfx"
        self.failing = self.steamapps / "compatdata/3008130/pfx"
        for appid, target in (("2353250",self.working), ("3008130",self.failing)):
            target.mkdir(parents=True)
            (self.steamapps / f"appmanifest_{appid}.acf").write_text(f'"appid" "{appid}"')
        header = "[Software\\\\Microsoft\\\\NET Framework Setup\\\\NDP\\\\v4\\\\Full]\n"
        (self.working / "system.reg").write_text(header + '"Release"=dword:00080cf0\n')
        (self.failing / "system.reg").write_text("[Software\\\\Wine\\\\Compat]\n")
        (self.working / "drive_c/windows/system32").mkdir(parents=True)
        (self.working / "drive_c/windows/system32/mscoree.dll").write_bytes(b"test")
        (self.backup / "pfx").mkdir(parents=True)
        (self.backup / "pfx/system.reg").write_text("[Software\\\\Wine\\\\Original]\n")
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({
            "2353250": {"proton": "/steam/Proton Experimental/proton",
                        "client": "/wemod/shared", "trainer_enabled": True},
            "3008130": {"proton": "/steam/Proton Experimental/proton",
                        "client": "/wemod/shared", "wemod_disable_gpu": True,
                        "trainer_enabled": True},
        }))

    def test_prefix_diff_preserves_every_file(self):
        paths = [self.working/"system.reg", self.failing/"system.reg",
                 self.backup/"pfx/system.reg",self.config]
        before = {str(p): p.read_bytes() for p in paths}
        report = mod.compare(self.library,"2353250","3008130",self.backup,self.config)
        self.assertIn("read-only",report["scope"])
        self.assertTrue(report["evidence"]["working"]["prefix"]["registry"]["framework_v4_full"])
        self.assertFalse(report["evidence"]["failing"]["prefix"]["registry"]["framework_v4_full"])
        self.assertFalse(report["backup"]["registry_matches_current"])
        self.assertTrue(any("registry differs" in n for n in report["observations"]))
        self.assertTrue(any("same WeMod client" in n for n in report["observations"]))
        self.assertEqual(before,{str(p): p.read_bytes() for p in paths})

    def test_same_backup_registry_is_not_full_restore_proof(self):
        (self.backup/"pfx/system.reg").write_bytes((self.failing/"system.reg").read_bytes())
        report=mod.compare(self.library,"2353250","3008130",self.backup,self.config)
        self.assertTrue(report["backup"]["registry_matches_current"])
        self.assertTrue(any("does not prove" in n for n in report["observations"]))

    def test_missing_prefix_is_inconclusive(self):
        (self.failing / "system.reg").unlink()
        (self.failing / "drive_c").mkdir(parents=True,exist_ok=True)
        result=mod.compare(self.library,"2353250","3008130")
        self.assertIsNone(result["evidence"]["failing"]["prefix"]["registry"]["registry_sha256"])
        self.assertFalse(result["evidence"]["failing"]["prefix"]["registry"]["framework_v4_full"])

    def test_rejects_bad_appid_and_library_without_mutation(self):
        with self.assertRaisesRegex(ValueError,"must differ"):
            mod.compare(self.library,"2353250","2353250")
        with self.assertRaisesRegex(ValueError,"positive decimal"):
            mod.compare(self.library,"../bad","3008130")
        with self.assertRaisesRegex(ValueError,"steamapps"):
            mod.compare(self.root,"2353250","3008130")


if __name__ == "__main__":
    unittest.main()
