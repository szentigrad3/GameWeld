"""Offline tests for the new GameWeld desktop core."""
import tempfile
import unittest
from pathlib import Path
from gameweld.core import installed_games, load_settings, save_settings, valid_settings, find_games, libraries

class CoreTests(unittest.TestCase):
    def test_settings_normalize(self):
        self.assertEqual(valid_settings({"favourites":[2,2,1,False,0,"3"]})["favourites"], [1,2])

    def test_settings_private_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config" / "desktop.json"
            save_settings({"favourites":[4,3]}, path)
            self.assertEqual(load_settings(path)["favourites"], [3,4])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_symlink_config_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file"
            target.write_text("{}")
            link = Path(tmp) / "link"
            link.symlink_to(target)
            self.assertEqual(load_settings(link)["favourites"], [])
            with self.assertRaises(ValueError):
                save_settings({}, link)

    def test_manifest_library_and_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "steamapps"
            root.mkdir()
            (root / "appmanifest_3008130.acf").write_text(
                '"AppState" { "appid" "3008130" "name" "Dying Light: The Beast" "buildid" "123" }')
            games = installed_games(root)
            self.assertEqual(games[0]["appid"], 3008130)
            self.assertEqual(games[0]["buildid"], "123")
            self.assertEqual(len(find_games(games, "beast")), 1)
            self.assertEqual(len(find_games(games, "", [11], True)), 0)
            self.assertEqual(len(libraries(root)), 1)

    def test_ignores_bad_manifest_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "steamapps"
            root.mkdir()
            outside = Path(tmp) / "elsewhere"
            outside.write_text('"name" "Bad Game"')
            (root / "appmanifest_9.acf").symlink_to(outside)
            self.assertEqual(installed_games(root), [])

if __name__ == "__main__":
    unittest.main()
