#!/usr/bin/env python3
"""Guard against reintroducing unchecked Steam config and backup paths."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "crates/wand-ui/appimage-gtk3/gameweld-native-040.c"

class SteamPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
    def test_backup_and_temp_paths_reject_oversize(self):
        self.assertIn('strlen(path)+48>=sizeof backup', self.source)
        self.assertIn('strlen(path)+48>=sizeof tmp', self.source)
    def test_steam_userdata_paths_have_bounds(self):
        self.assertIn('strlen(canon)>sizeof user-sizeof "/userdata"', self.source)
        self.assertIn('strlen(roots[ri])+sizeof "/userdata">sizeof userroot', self.source)
    def test_mount_and_config_paths_have_bounds(self):
        self.assertIn('strlen(base)+strlen(de->d_name)+2>sizeof p1', self.source)
        self.assertIn('strlen(p1)+strlen(de2->d_name)+2>sizeof p2', self.source)
        self.assertIn('strlen(userroot)+strlen(de->d_name)+sizeof "//config/localconfig.vdf">sizeof cfg', self.source)

if __name__ == "__main__":
    unittest.main()
