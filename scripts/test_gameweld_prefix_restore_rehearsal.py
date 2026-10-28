#!/usr/bin/env python3
"""Offline restore rehearsal tests, never restoring real games."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).parent


def load(name, module_name):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = load("gameweld-prefix-backup.py", "gameweld_backup_for_rehearsal_tests")
rehearsal = load("gameweld-prefix-restore-rehearsal.py",
                 "gameweld_prefix_restore_rehearsal_tests")


class RestoreRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-restore-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_backups = self.root / "state/gameweld/prefix-backups"
        self.games = {
            ("steam", "361420"): self.root / "steamapps/compatdata/361420/pfx",
            ("heroic", "gog-game-a"): self.root / "heroic/games/game-a/prefix",
            ("lutris", "lutris:game-b"): self.root / "lutris/game-b/wineprefix",
        }
        for prefix in self.games.values():
            prefix.mkdir(parents=True)
            (prefix / "system.reg").write_text("ORIGINAL REGISTRY")
            (prefix / "drive_c").mkdir()
            (prefix / "drive_c/savedata.bin").write_bytes(b"ORIGINAL SAVE DATA")
            (prefix / "dosdevices").mkdir()
            (prefix / "dosdevices/c:").symlink_to("../drive_c")
            # Wine commonly has external DOS drive symlinks. The rehearsal
            # preserves the string but never follows it.
            (prefix / "dosdevices/z:").symlink_to("/")
        self.game_origins = self.capture_games()

    def capture_games(self):
        return {
            key: sorted([
                (p.relative_to(prefix).as_posix(),
                 ("symlink", os.readlink(p)) if p.is_symlink() else
                 ("file", p.read_bytes()) if p.is_file() else
                 ("directory", ""))
                for p in prefix.rglob("*")
            ])
            for key, prefix in self.games.items()
        }

    def snapshot(self, provider="steam", game_id="361420"):
        prefix = self.games[(provider, game_id)]
        with patch.object(backup.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            return Path(backup.create_backup(
                provider, game_id, prefix,
                backup_root=self.root_backups,
                approved=True, acknowledged_game_closed=True
            )["backup_path"])

    def restore(self, location, **kwargs):
        with patch.object(rehearsal.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 200 * 1024 ** 3})()):
            return rehearsal.rehearsal_restore(
                location, backup_root=self.root_backups,
                approved=kwargs.pop("approved", True), **kwargs
            )

    def test_refuses_without_explicit_opt_in(self):
        source = self.snapshot()
        with self.assertRaisesRegex(rehearsal.RehearsalRefused, "Explicit"):
            self.restore(source, approved=False)
        self.assertFalse((self.root_backups / "restore-rehearsals").exists())
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_steam_heroic_lutris_restore_into_disposable_copy_only(self):
        for provider, game_id in self.games:
            with self.subTest(provider=provider):
                source = self.snapshot(provider, game_id)
                # Assert we are restoring original backup contents, not
                # reading the live game after a later user modification.
                game = self.games[(provider, game_id)]
                (game / "system.reg").write_text("GAME MODIFIED AFTER BACKUP")
                events = []
                outcome = self.restore(
                    source, progress=lambda phase, done, total:
                    events.append((phase, done, total))
                )
                dest = Path(outcome["restored_test_path"])
                self.assertEqual(
                    (dest / "payload/system.reg").read_text(), "ORIGINAL REGISTRY"
                )
                self.assertEqual(
                    (dest / "payload/drive_c/savedata.bin").read_bytes(),
                    b"ORIGINAL SAVE DATA"
                )
                self.assertTrue((dest / "payload/dosdevices/c:").is_symlink())
                self.assertEqual(
                    os.readlink(dest / "payload/dosdevices/c:"), "../drive_c"
                )
                self.assertEqual(os.readlink(dest / "payload/dosdevices/z:"), "/")
                self.assertEqual(outcome["status"], "REHEARSAL PASSED — TEST COPY ONLY")
                self.assertFalse(outcome["real_game_prefix_changed"])
                self.assertFalse(outcome["can_restore_real_game"])
                self.assertEqual(outcome["files_verified"], 2)
                self.assertEqual(outcome["symlinks_preserved_without_following"], 2)
                self.assertEqual(events[0][0], "RESTORE_TEST")
                self.assertEqual(events[-1][0], "RESTORE_TEST_COMPLETE")
                self.assertEqual((game / "system.reg").read_text(),
                                 "GAME MODIFIED AFTER BACKUP")
                self.assertEqual(stat.S_IMODE(
                    (dest / "payload/system.reg").stat().st_mode), 0o600)
        # All changes to games are deliberately made above, not by rehearsal.
        for prefix in self.games.values():
            self.assertEqual((prefix / "system.reg").read_text(),
                             "GAME MODIFIED AFTER BACKUP")

    def test_unchanged_game_prefix_on_cancel_and_cleanup(self):
        source = self.snapshot()
        def stop(phase, copied, total):
            if phase == "RESTORE_TEST" and copied > 0:
                raise rehearsal.RehearsalRefused("simulated cancel")
        with self.assertRaisesRegex(rehearsal.RehearsalRefused, "simulated cancel"):
            self.restore(source, progress=stop)
        self.assertEqual(
            list((self.root_backups / "restore-rehearsals").iterdir()), []
        )
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_corrupt_archive_blocks_before_creating_rehearsal(self):
        source = self.snapshot()
        with (source / "prefix.tar").open("ab") as stream:
            stream.write(b"TAMPER")
        with self.assertRaisesRegex(rehearsal.RehearsalRefused, "verification"):
            self.restore(source)
        self.assertFalse((self.root_backups / "restore-rehearsals").exists())
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_no_replace_existing_rehearsal(self):
        source = self.snapshot()
        self.restore(source)
        marker = (self.root_backups / "restore-rehearsals" /
                  source.name / "rehearsal.json")
        original = marker.read_bytes()
        with self.assertRaisesRegex(rehearsal.RehearsalRefused, "already exists"):
            self.restore(source)
        self.assertEqual(marker.read_bytes(), original)
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_symlinked_destination_is_rejected(self):
        source = self.snapshot()
        area = self.root_backups / "restore-rehearsals"
        area.symlink_to(self.games[("steam", "361420")], target_is_directory=True)
        with self.assertRaisesRegex(rehearsal.RehearsalRefused, "unsafe"):
            self.restore(source)
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_low_disk_space_fails_without_writes(self):
        source = self.snapshot()
        with patch.object(rehearsal.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 1})()):
            with self.assertRaisesRegex(rehearsal.RehearsalRefused, "disk space"):
                rehearsal.rehearsal_restore(source, backup_root=self.root_backups,
                                            approved=True)
        self.assertFalse((self.root_backups / "restore-rehearsals").exists())
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_unsupported_tar_link_types_cannot_escape(self):
        source = self.snapshot()
        tar_path = source / "prefix.tar"
        # Rebuild an internally consistent but malicious archive: a hard link
        # cannot be written by this tool even when attacker changes manifest.
        with tarfile.open(tar_path, "w") as archive:
            link = tarfile.TarInfo("prefix/escape")
            link.type = tarfile.LNKTYPE
            link.linkname = "../../outside"
            archive.addfile(link)
        manifest_path = source / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["entries"] = 1
        manifest["regular_files"] = 0
        manifest["file_hashes"] = []
        manifest["symlinks"] = 0
        manifest["total_file_bytes"] = 0
        manifest["archive_bytes"] = tar_path.stat().st_size
        manifest["archive_sha256"] = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(rehearsal.RehearsalRefused):
            self.restore(source)
        self.assertFalse((self.root_backups / "restore-rehearsals").exists())
        self.assertEqual(self.capture_games(), self.game_origins)

    def test_tar_symlink_ancestor_blocks_before_writing(self):
        source = self.snapshot()
        tar_path = source / "prefix.tar"
        with tarfile.open(tar_path, "w") as archive:
            parent = tarfile.TarInfo("prefix/shortcut")
            parent.type = tarfile.SYMTYPE
            parent.linkname = "/tmp"
            archive.addfile(parent)
            child = tarfile.TarInfo("prefix/shortcut/escape.txt")
            child.size = 1
            archive.addfile(child, fileobj=__import__("io").BytesIO(b"x"))
        manifest_file = source / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest.update(entries=2, regular_files=1, symlinks=1,
                        total_file_bytes=1, archive_bytes=tar_path.stat().st_size,
                        archive_sha256=hashlib.sha256(tar_path.read_bytes()).hexdigest(),
                        file_hashes=[{
                            "path": "shortcut/escape.txt", "size": 1,
                            "sha256": hashlib.sha256(b"x").hexdigest()
                        }])
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(rehearsal.RehearsalRefused,
                                    "non-directory parent"):
            self.restore(source)
        self.assertFalse((self.root_backups / "restore-rehearsals" /
                          source.name).exists())
        self.assertEqual(self.capture_games(), self.game_origins)


if __name__ == "__main__":
    unittest.main()
