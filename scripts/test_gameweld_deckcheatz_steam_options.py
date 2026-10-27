#!/usr/bin/env python3
"""Offline Steam launch-option recipe tests; no Steam or prefix writes."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-deckcheatz-steam-options.py")
SPEC = importlib.util.spec_from_file_location("gw_steam_deckcheatz_options", SCRIPT)
assert SPEC and SPEC.loader
recipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipe)


class SteamOptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-steam-options-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.launcher = self.root / "gameweld/deckcheatz/wemod"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/usr/bin/env python3\n# harmless fixture\n")
        self.launcher.chmod(0o700)
        self.before = self.launcher.read_bytes()

    def test_working_steam_wrapper_recipe(self):
        result = recipe.build_recipe(self.launcher)
        self.assertEqual(result["mode"], "DECKCHEATZ_STEAM_LAUNCH_OPTION")
        self.assertEqual(
            result["launch_option"],
            'WINEDLLOVERRIDES="version=n,b" WEMOD_LOG='
            + str(self.launcher.parent / "wemod.log")
            + " " + str(self.launcher) + " %command%"
        )
        self.assertTrue(result["requires_manual_steam_launch_option"])
        self.assertFalse(result["steam_bridge_used"])
        self.assertFalse(result["steam_launch_options_changed"])
        self.assertFalse(result["wemod_launched"])
        self.assertFalse(result["game_launched"])
        self.assertFalse(result["trainer_attachment_verified"])
        self.assertEqual(self.before, self.launcher.read_bytes())
        self.assertFalse((self.launcher.parent / "wemod.log").exists())

    def test_paths_with_spaces_and_shell_characters_are_quoted(self):
        launcher = self.root / "name with spaces;$(touch no)/wemod"
        launcher.parent.mkdir()
        launcher.write_bytes(b"fixture")
        launcher.chmod(0o700)
        result = recipe.build_recipe(launcher)
        import shlex
        pieces = shlex.split(result["launch_option"])
        self.assertEqual(pieces[0], "WINEDLLOVERRIDES=version=n,b")
        self.assertEqual(pieces[1], "WEMOD_LOG=" + str(launcher.parent / "wemod.log"))
        self.assertEqual(pieces[2], str(launcher))
        self.assertEqual(pieces[3], "%command%")
        self.assertFalse((self.root / "no").exists())

    def test_refuses_missing_nonexecutable_and_symlinked_wrapper(self):
        self.launcher.chmod(0o600)
        with self.assertRaisesRegex(recipe.RecipeBlocked, "executable"):
            recipe.build_recipe(self.launcher)
        self.launcher.chmod(0o700)
        linked = self.root / "linked/wemod"
        linked.parent.mkdir()
        linked.symlink_to(self.launcher)
        with self.assertRaisesRegex(recipe.RecipeBlocked, "symlink target"):
            recipe.build_recipe(linked)
        with self.assertRaisesRegex(recipe.RecipeBlocked, "executable"):
            recipe.build_recipe(self.root / "missing/wemod")

    def test_official_deckcheatz_symlink_to_src_wemod_py_is_accepted(self):
        # Real upstream 1.x checkout uses wemod -> src/wemod.py.
        # Steam and the original GUI successfully use this same launcher.
        src = self.launcher.parent / "src"
        src.mkdir()
        entry = src / "wemod.py"
        entry.write_text("#!/usr/bin/env python3\n")
        entry.chmod(0o755)
        self.launcher.unlink()
        self.launcher.symlink_to("src/wemod.py")
        result = recipe.build_recipe(self.launcher)
        self.assertEqual(result["mode"], "DECKCHEATZ_STEAM_LAUNCH_OPTION")
        self.assertIn(str(self.launcher) + " %command%", result["launch_option"])
        self.assertTrue(self.launcher.is_symlink())
        self.assertFalse((self.launcher.parent / "wemod.log").exists())

    def test_deckcheatz_wrapper_symlink_cannot_escape_checkout(self):
        outside = self.root / "outside.py"
        outside.write_text("#!/usr/bin/env python3\n")
        outside.chmod(0o755)
        src = self.launcher.parent / "src"
        src.mkdir()
        target = src / "wemod.py"
        target.write_text("placeholder")
        target.chmod(0o755)
        self.launcher.unlink()
        self.launcher.symlink_to(outside)
        with self.assertRaisesRegex(recipe.RecipeBlocked, "outside"):
            recipe.build_recipe(self.launcher)
        self.assertTrue(self.launcher.is_symlink())
        self.assertEqual(outside.read_text(), "#!/usr/bin/env python3\n")

    def test_deckcheatz_nested_symlink_target_is_rejected(self):
        src = self.launcher.parent / "src"
        src.mkdir()
        outside = self.root / "outside.py"
        outside.write_text("#!/usr/bin/env python3\n")
        outside.chmod(0o755)
        (src / "wemod.py").symlink_to(outside)
        self.launcher.unlink()
        self.launcher.symlink_to("src/wemod.py")
        with self.assertRaisesRegex(recipe.RecipeBlocked, "target"):
            recipe.build_recipe(self.launcher)

    def test_official_symlink_without_execute_permission_is_rejected(self):
        src = self.launcher.parent / "src"
        src.mkdir()
        target = src / "wemod.py"
        target.write_text("#!/usr/bin/env python3\n")
        target.chmod(0o600)
        self.launcher.unlink()
        self.launcher.symlink_to("src/wemod.py")
        with self.assertRaisesRegex(recipe.RecipeBlocked, "executable"):
            recipe.build_recipe(self.launcher)

    def test_refuses_log_symlink(self):
        target = self.root / "private.txt"
        target.write_text("must not overwrite")
        log = self.launcher.parent / "wemod.log"
        log.symlink_to(target)
        with self.assertRaisesRegex(recipe.RecipeBlocked, "symlinked log"):
            recipe.build_recipe(self.launcher)
        self.assertEqual(target.read_text(), "must not overwrite")

    def test_discovery_prioritizes_managed_installed_checkout(self):
        preferred = self.root / ".local/share"
        candidates = recipe.candidates(self.root, preferred)
        self.assertEqual(candidates[0], preferred / "gameweld/deckcheatz/wemod")
        self.assertEqual(candidates[1], self.root / "wemod-launcher/wemod")
        self.assertEqual(len(set(candidates)), len(candidates))

    def test_no_steam_config_or_game_files_ever_created(self):
        recipe.build_recipe(self.launcher)
        self.assertEqual(list(self.root.rglob("*.vdf")), [])
        self.assertEqual(list(self.root.rglob("*.acf")), [])
        self.assertEqual(self.launcher.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
