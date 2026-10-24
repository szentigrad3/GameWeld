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

    def next_upstream_commit(self):
        marker = self.origin / "UPSTREAM-FIX"
        marker.write_text("second 1.x bugfix revision")
        self.git("add", ".", cwd=self.origin)
        self.git("-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "upstream-fix", cwd=self.origin)
        return self.git("-C", str(self.origin), "rev-parse", "HEAD",
                        cwd=self.root).stdout.strip()

    def test_fresh_checkout_has_managed_version_record(self):
        report = installer.install()
        self.assertTrue(report["managed_install"])
        meta = installer.managed_metadata(self.target)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["revision"], report["upstream_revision"])
        self.assertEqual(installer.inspect_managed_checkout(self.target), meta["revision"])

    def test_check_update_is_read_only(self):
        report = installer.install()
        installed = report["upstream_revision"]
        new = self.next_upstream_commit()
        result = installer.check_update()
        self.assertEqual(result["result"], "update_available")
        self.assertEqual(result["installed_revision"], installed)
        self.assertEqual(result["upstream_revision"], new)
        self.assertFalse((self.target / "UPSTREAM-FIX").exists())
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-backup-*")))

    def test_opt_in_update_keeps_previous_checkout_as_backup(self):
        result = installer.install()
        old = result["upstream_revision"]
        new = self.next_upstream_commit()
        report = installer.update()
        self.assertEqual(report["result"], "updated")
        self.assertEqual(report["previous_revision"], old)
        self.assertEqual(report["upstream_revision"], new)
        self.assertTrue((self.target / "UPSTREAM-FIX").is_file())
        self.assertEqual(installer.inspect_managed_checkout(self.target), new)
        backup = Path(report["rollback_path"])
        self.assertTrue(backup.is_dir())
        self.assertEqual(installer.inspect_managed_checkout(backup), old)
        self.assertFalse((backup / "UPSTREAM-FIX").exists())
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-staging-*")))

    def test_adopt_clean_manual_checkout_for_managed_updates(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", str(self.origin), str(self.target), cwd=self.root)
        self.assertFalse(installer.status()["managed_install"])
        result = installer.adopt_existing()
        self.assertEqual(result["result"], "adopted")
        self.assertTrue(result["managed_install"])
        self.assertEqual(installer.inspect_managed_checkout(self.target),
                         result["upstream_revision"])
        new = self.next_upstream_commit()
        updated = installer.update()
        self.assertEqual(updated["upstream_revision"], new)

    def test_official_git_url_with_or_without_suffix_is_allowed(self):
        with patch.object(installer, "SOURCE_URL",
                          "https://github.com/DeckCheatz/wemod-launcher.git"):
            self.assertTrue(installer.official_origin(
                "https://github.com/DeckCheatz/wemod-launcher.git"))
            self.assertTrue(installer.official_origin(
                "https://github.com/DeckCheatz/wemod-launcher"))
            self.assertFalse(installer.official_origin(
                "https://example.invalid/DeckCheatz/wemod-launcher.git"))

    def test_adopt_refuses_dirty_manual_checkout(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", str(self.origin), str(self.target), cwd=self.root)
        marker = self.target / "KEEP-ME"
        marker.write_text("personal file")
        with self.assertRaisesRegex(installer.InstallError, "local files or edits"):
            installer.adopt_existing()
        self.assertTrue(marker.is_file())
        self.assertFalse((self.target / installer.MANAGED_MARKER).exists())

    def test_adopt_rejects_wrong_origin(self):
        other = self.root / "unknown-repo"
        other.mkdir()
        (other / "src").mkdir()
        (other / "src/wemod.py").write_text("# source\\n")
        (other / "wemod").symlink_to("src/wemod.py")
        (other / "README.md").write_text("WeMod Launcher fixture")
        (other / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE")
        self.git("init", "-b", "main", str(other), cwd=self.root)
        self.git("add", ".", cwd=other)
        self.git("-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "fixture", cwd=other)
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", str(other), str(self.target), cwd=self.root)
        with self.assertRaisesRegex(installer.InstallError, "not the official"):
            installer.adopt_existing()

    def test_update_noop_when_already_current(self):
        installer.install()
        result = installer.update()
        self.assertEqual(result["result"], "up_to_date")
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-backup-*")))

    def test_update_refuses_external_unmanaged_checkout(self):
        self.target.mkdir(parents=True)
        with self.assertRaisesRegex(installer.InstallError, "not installed by GameWeld"):
            installer.update()

    def test_update_refuses_local_changes_without_overwriting(self):
        installer.install()
        src = self.target / "src/wemod.py"
        src.write_text("# modified privately\\n")
        self.next_upstream_commit()
        with self.assertRaisesRegex(installer.InstallError, "local changes"):
            installer.update()
        self.assertEqual(src.read_text(), "# modified privately\\n")
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-backup-*")))

    def test_update_blocks_running_launcher(self):
        installer.install()
        self.next_upstream_commit()
        with patch.object(installer, "running_launcher", return_value=True):
            with self.assertRaisesRegex(installer.InstallError, "running"):
                installer.update()
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-backup-*")))

    def test_failed_update_preserves_previous_version(self):
        initial = installer.install()["upstream_revision"]
        self.next_upstream_commit()
        with patch.object(installer, "_clone_to",
                          side_effect=installer.InstallError("simulated download failure")):
            with self.assertRaisesRegex(installer.InstallError, "download failure"):
                installer.update()
        self.assertEqual(installer.inspect_managed_checkout(self.target), initial)
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-staging-*")))
        self.assertFalse(list(self.target.parent.glob(".deckcheatz-backup-*")))

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
