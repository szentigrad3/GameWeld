#!/usr/bin/env python3
"""Offline fixture tests for DeckCheatz managed install (no remote network)."""
from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-install.py")
spec = importlib.util.spec_from_file_location("_gw_deckcheatz_installer_fixture", SOURCE)
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


class DeckCheatzInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-installer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.data = self.home / ".local/share"
        self.home.mkdir()
        self.origin = self.root / "offline-origin"
        self.origin.mkdir()
        source = self.origin / "src"
        source.mkdir()
        (source / "wemod.py").write_text("# fixture: do not run\n")
        (self.origin / "wemod").symlink_to("src/wemod.py")
        (self.origin / "README.md").write_text("WeMod Launcher fixture\n")
        (self.origin / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE\n")
        self.git("init", "-b", "main", str(self.origin), cwd=self.root)
        self.git("add", ".", cwd=self.origin)
        self.git("-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "fixture", cwd=self.origin)
        self.target = self.data / "gameweld/deckcheatz"
        context = patch.dict(os.environ, {
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.data),
            "GAMEWELD_DECKCHEATZ_LAUNCHER": "",
        })
        context.start()
        self.addCleanup(context.stop)
        context2 = patch.object(Path, "home", return_value=self.home)
        context2.start()
        self.addCleanup(context2.stop)
        context3 = patch.object(installer, "SOURCE_URL", str(self.origin))
        context3.start()
        self.addCleanup(context3.stop)

    def git(self, *cmd, cwd):
        return subprocess.run(
            ["git", *cmd], cwd=cwd, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )

    def test_readonly_status_does_not_install_or_launch(self):
        with patch.object(installer.subprocess, "run") as runner:
            data = installer.status()
            runner.assert_not_called()
        self.assertFalse(data["installed"])
        self.assertFalse(data["game_or_trainer_launched"])
        self.assertFalse(data["modifies_steam_launch_options"])
        self.assertFalse(self.target.exists())

    def test_offline_git_checkout_installs_and_recognizes_valid_source(self):
        data = installer.install()
        self.assertEqual(data["result"], "installed")
        self.assertTrue(data["installed"])
        self.assertEqual(data["available_count"], 1)
        self.assertEqual(data["upstream_revision"], self.git("-C", str(self.origin),
                            "rev-parse", "HEAD", cwd=self.root).stdout.strip())
        self.assertTrue(self.target.joinpath("wemod").is_symlink())
        self.assertFalse(data["modifies_steam_launch_options"])
        self.assertFalse(data["game_or_trainer_launched"])
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-staging-*")))

    def test_install_is_idempotent_preserves_existing_checkout(self):
        installer.install()
        marker = self.target / "DO-NOT-DELETE"
        marker.write_text("user data")
        result = installer.install()
        self.assertEqual(result["result"], "already_installed")
        self.assertEqual(marker.read_text(), "user data")

    def test_occupied_noncheckout_directory_is_never_overwritten(self):
        self.target.mkdir(parents=True)
        marker = self.target / "custom-data"
        marker.write_bytes(b"preserve")
        with self.assertRaisesRegex(installer.InstallError, "not a valid"):
            installer.install()
        self.assertEqual(marker.read_bytes(), b"preserve")

    def test_failed_source_clone_rolls_back_staging(self):
        with patch.object(installer, "SOURCE_URL", str(self.root / "does-not-exist")):
            with self.assertRaisesRegex(installer.InstallError, "clone failed"):
                installer.install()
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-staging-*")))

    def test_external_checkout_is_reused_not_duplicated(self):
        with patch.dict(os.environ, {
            "GAMEWELD_DECKCHEATZ_LAUNCHER": str(self.origin / "wemod"),
        }):
            result = installer.install()
        self.assertEqual(result["result"], "already_installed")
        self.assertFalse(self.target.exists())

    def test_install_confirmation_is_required(self):
        with patch.object(sys, "argv", ["installer", "--install"]):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    installer.main()
        self.assertEqual(exc.exception.code, 2)
        self.assertFalse(self.target.exists())

    def test_no_steam_launch_options_or_game_prefix_mutation(self):
        config = self.root / "Steam/userdata/config/localconfig.vdf"
        config.parent.mkdir(parents=True)
        config.write_bytes(b"LaunchOptions=preserve")
        prefix = self.root / "Steam/steamapps/compatdata/2353250/pfx"
        prefix.mkdir(parents=True)
        (prefix / "marker").write_text("preserve prefix")
        installer.install()
        self.assertEqual(config.read_bytes(), b"LaunchOptions=preserve")
        self.assertEqual((prefix / "marker").read_text(), "preserve prefix")


if __name__ == "__main__":
    unittest.main()
