#!/usr/bin/env python3
"""Offline regression: independent prefix backup may read, never modify games."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-prefix-backup.py")
spec = importlib.util.spec_from_file_location("gameweld_prefix_backup", SOURCE)
assert spec and spec.loader
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class PrefixBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-backup-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.backup_root = self.root / "state/gameweld/prefix-backups"
        self.game_dirs = {
            ("steam", "361420"): self.root / "steamapps/compatdata/361420/pfx",
            ("heroic", "gog-a"): self.root / "Heroic/Prefixes/game-a",
            ("lutris", "lutris:game-b"): self.root / "Lutris/wineprefixes/game-b",
        }
        for prefix in self.game_dirs.values():
            prefix.mkdir(parents=True)
            (prefix / "system.reg").write_bytes(b"EXISTING USER CONFIG\n")
            (prefix / "drive_c").mkdir()
            (prefix / "drive_c" / "userdata.bin").write_bytes(b"KEEP SAVES AND ACCOUNT DATA")
            (prefix / "dosdevices").mkdir()
            (prefix / "dosdevices" / "c:").symlink_to("../drive_c")
        self.before = self.game_snapshot()

    def game_snapshot(self):
        result = {}
        for key, prefix in self.game_dirs.items():
            result[key] = sorted(
                (str(p.relative_to(prefix)), p.lstat().st_mode,
                 os.readlink(p) if p.is_symlink() else
                 p.read_bytes() if p.is_file() else None)
                for p in prefix.rglob("*")
            )
        return result

    def call(self, provider="steam", game_id="361420", prefix=None, **kwargs):
        chosen = self.game_dirs[(provider, game_id)] if prefix is None else prefix
        return backup.create_backup(
            provider, game_id, chosen, backup_root=kwargs.get("backup_root", self.backup_root),
            approved=kwargs.get("approved", True),
            acknowledged_game_closed=kwargs.get("game_closed", True)
        )

    def test_read_only_preview_creates_no_backup_or_prefix_changes(self):
        for (provider, game_id), prefix in self.game_dirs.items():
            with self.subTest(provider=provider):
                outcome = backup.preview_backup(provider, game_id, prefix, self.backup_root)
                self.assertFalse(outcome["backup_created"])
                self.assertFalse(outcome["runtime_idle_verified"])
                self.assertFalse(outcome["ready_to_install"])
                self.assertGreater(outcome["regular_files"], 0)
                self.assertEqual(outcome["symlinks"], 1)
        self.assertFalse(self.backup_root.exists())
        self.assertEqual(self.game_snapshot(), self.before)

    def test_both_explicit_approvals_required_before_any_write(self):
        for approved, game_closed in [(False, False), (True, False), (False, True)]:
            with self.subTest(approved=approved, game_closed=game_closed):
                with self.assertRaisesRegex(backup.BackupRefused, "Explicit"):
                    self.call(approved=approved, game_closed=game_closed)
        self.assertFalse(self.backup_root.exists())
        self.assertEqual(self.game_snapshot(), self.before)

    def test_create_separate_private_verified_backups_for_each_provider(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            for provider, game_id in self.game_dirs:
                result = self.call(provider, game_id)
                output = Path(result["backup_path"])
                self.assertTrue(output.is_dir())
                self.assertEqual(stat.S_IMODE(self.backup_root.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((output / "prefix.tar").stat().st_mode), 0o600)
                with tarfile.open(output / "prefix.tar", "r") as archive:
                    self.assertEqual(archive.extractfile("prefix/system.reg").read(),
                                     b"EXISTING USER CONFIG\n")
                    link = archive.getmember("prefix/dosdevices/c:")
                    self.assertTrue(link.issym())
                    self.assertEqual(link.linkname, "../drive_c")
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertFalse(manifest["restoration_available"])
                self.assertFalse(manifest["runtime_idle_verified"])
                self.assertTrue(manifest["backup_created"])
                self.assertFalse(manifest["ready_to_install"])
                self.assertFalse(result["game_prefix_mutated"])
                self.assertEqual(
                    manifest["file_hashes"][0]["sha256"].__class__, str
                )
        self.assertEqual(self.game_snapshot(), self.before)

    def test_symlinked_prefix_ancestry_and_destination_overlap_rejected(self):
        shortcut = self.root / "shortcut"
        shortcut.symlink_to(self.game_dirs[("steam", "361420")], target_is_directory=True)
        with self.assertRaisesRegex(backup.BackupRefused, "symlinked|Symlinked"):
            self.call(prefix=shortcut)
        with self.assertRaisesRegex(backup.BackupRefused, "must not overlap"):
            self.call(backup_root=self.game_dirs[("steam", "361420")] /
                      "gameweld/prefix-backups")
        self.assertEqual(self.game_snapshot(), self.before)

    def test_fifo_special_file_refused_before_backup(self):
        prefix = self.game_dirs[("steam", "361420")]
        pipe = prefix / "unsafe-pipe"
        os.mkfifo(pipe)
        with self.assertRaisesRegex(backup.BackupRefused, "Special files"):
            self.call()
        self.assertFalse(self.backup_root.exists())
        pipe.unlink()
        self.assertEqual(self.game_snapshot(), self.before)

    def test_low_space_refuses_before_creating_folder(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 0})()):
            with self.assertRaisesRegex(backup.BackupRefused, "Insufficient"):
                self.call()
        self.assertFalse(self.backup_root.exists())
        self.assertEqual(self.game_snapshot(), self.before)

    def test_failed_copy_cleans_partial_backup_without_touching_game(self):
        original = backup.DigestReader.read
        state = {"has_failed": False}
        def explode(reader, count=-1):
            if not state["has_failed"]:
                state["has_failed"] = True
                raise OSError("simulated disk interrupted")
            return original(reader, count)
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            with patch.object(backup.DigestReader, "read", explode):
                with self.assertRaisesRegex(OSError, "simulated disk"):
                    self.call()
        self.assertEqual(list(self.backup_root.iterdir()), [])
        self.assertEqual(self.game_snapshot(), self.before)

    def test_snapshot_verification_reads_archive_without_restoring_game(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            saved = self.call()
        result = backup.verify_backup(Path(saved["backup_path"]),
                                      backup_root=self.backup_root)
        self.assertEqual(result["status"],
                         "BACKUP READABLE AND CHECKSUMS VERIFIED — restoration unavailable")
        self.assertEqual(result["verified_files"], 2)
        self.assertEqual(result["symlinks_not_followed"], 1)
        self.assertFalse(result["ready_to_install"])
        self.assertFalse(result["restoration_available"])
        self.assertEqual(self.game_snapshot(), self.before)

    def test_archive_corruption_or_manifest_forgery_refused(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            first = self.call()
            second = self.call()
        damaged = Path(first["backup_path"]) / "prefix.tar"
        with damaged.open("ab") as stream:
            stream.write(b"CORRUPTION")
        with self.assertRaisesRegex(backup.BackupRefused, "checksum/size"):
            backup.verify_backup(Path(first["backup_path"]),
                                 backup_root=self.backup_root)

        manifest_file = Path(second["backup_path"]) / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["file_hashes"][0]["sha256"] = "0" * 64
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(backup.BackupRefused, "SHA-256"):
            backup.verify_backup(Path(second["backup_path"]),
                                 backup_root=self.backup_root)
        self.assertEqual(self.game_snapshot(), self.before)

    def test_external_backup_directory_and_symlinked_manifest_refused(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            saved = self.call()
        with self.assertRaisesRegex(backup.BackupRefused, "GameWeld-managed"):
            backup.verify_backup(self.root, backup_root=self.backup_root)
        manifest = Path(saved["backup_path"]) / "manifest.json"
        replaced = manifest.with_name("original.json")
        manifest.rename(replaced)
        manifest.symlink_to(replaced)
        with self.assertRaisesRegex(backup.BackupRefused, "symlinked"):
            backup.verify_backup(Path(saved["backup_path"]),
                                 backup_root=self.backup_root)
        self.assertEqual(self.game_snapshot(), self.before)

    def test_non_object_manifest_is_cleanly_refused(self):
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            saved = self.call()
        manifest = Path(saved["backup_path"]) / "manifest.json"
        manifest.write_text("[]")
        with self.assertRaisesRegex(backup.BackupRefused, "JSON object"):
            backup.verify_backup(Path(saved["backup_path"]),
                                 backup_root=self.backup_root)
        self.assertEqual(self.game_snapshot(), self.before)

    def test_invalid_provider_or_game_id_refused(self):
        for provider, game_id in [("steam", "0"), ("steam", "../x"),
                                  ("heroic", "bad/id"), ("unknown", "123")]:
            with self.subTest(provider=provider, game_id=game_id):
                with self.assertRaises(backup.BackupRefused):
                    backup.preview_backup(provider, game_id,
                                          self.game_dirs[("steam", "361420")],
                                          self.backup_root)
        self.assertFalse(self.backup_root.exists())


if __name__ == "__main__":
    unittest.main()
