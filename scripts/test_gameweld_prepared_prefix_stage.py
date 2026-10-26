#!/usr/bin/env python3
"""Offline tests: managed ZIP staging never overwrites a Steam/Heroic/Lutris game."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).with_name("gameweld-prepared-prefix-stage.py")
spec = importlib.util.spec_from_file_location("prepared_prefix_stage", SOURCE)
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class PreparedPrefixStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-stage-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / "cache/gameweld/prepared-wemod"
        (self.cache / "downloads").mkdir(parents=True, mode=0o700)
        self.cache.chmod(0o700)  # pathlib parents=True uses default mode for parent nodes
        self.games = [
            self.root / "steamapps/compatdata/361420/pfx",
            self.root / "Heroic/Prefixes/game-a",
            self.root / "Lutris/wineprefixes/game-b",
        ]
        for prefix in self.games:
            prefix.mkdir(parents=True)
            (prefix / "system.reg").write_text("KEEP ORIGINAL GAME DATA")
        self.archive = self.make_zip([
            ("pfx/drive_c/windows/test.bin", b"stub-binary-data"),
            ("pfx/user.reg", b"TEST-ONLY-REGISTRY"),
        ])

    def make_zip(self, members):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in members:
                archive.writestr(name, data)
        blob = memory.getvalue()
        path = self.cache / "downloads" / (hashlib.sha256(blob).hexdigest() + ".zip")
        path.write_bytes(blob)
        return path

    def untouched(self):
        for prefix in self.games:
            self.assertEqual((prefix / "system.reg").read_text(),
                             "KEEP ORIGINAL GAME DATA")
            self.assertEqual([item.name for item in prefix.iterdir()], ["system.reg"])

    def call(self, **kwargs):
        with patch.object(stage.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 20 * 1024 ** 3})()):
            return stage.stage_cached_archive(
                kwargs.pop("archive", self.archive), cache_root=kwargs.pop("root", self.cache),
                approved=kwargs.pop("approved", True), **kwargs
            )

    def test_approval_required_and_no_staging_directory_created(self):
        with self.assertRaisesRegex(stage.StageRefused, "Explicit"):
            self.call(approved=False)
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_copies_only_into_private_content_addressed_staging(self):
        events = []
        result = self.call(progress=lambda phase, current, total:
                           events.append((phase, current, total)))
        destination = Path(result["stage_path"])
        self.assertEqual(destination, self.cache / "staging" / self.archive.stem)
        self.assertEqual((destination / "payload/pfx/user.reg").read_bytes(),
                         b"TEST-ONLY-REGISTRY")
        self.assertEqual((destination / "payload/pfx/drive_c/windows/test.bin").read_bytes(),
                         b"stub-binary-data")
        self.assertEqual(result["source_archive_sha256"], self.archive.stem)
        self.assertEqual(result["publisher_authenticity"], "UNVERIFIED")
        self.assertEqual(result["game_compatibility"], "UNVERIFIED")
        self.assertFalse(result["installed_to_game"])
        self.assertFalse(result["apply_supported"])
        self.assertFalse(result["trainer_verified"])
        self.assertEqual(events[0][0], "STAGE")
        self.assertEqual(events[-1][0], "STAGED")
        self.assertEqual(stat.S_IMODE((destination / "payload/pfx/user.reg").stat().st_mode), 0o600)
        self.assertTrue((destination / "manifest.json").exists())
        self.assertEqual(list((self.cache / "staging").glob(".incoming-*")), [])
        self.untouched()

    def test_source_asset_version_record_is_retained_when_staged(self):
        import json
        record = {
            "sha256": self.archive.stem,
            "source": "DeckCheatz/BuiltPrefixes-dev",
            "asset_name": "GE-Proton10.1.zip",
            "release_tag": "PfxVer10.1",
            "publisher_authenticity": "UNVERIFIED",
        }
        (self.cache / "downloads" / (self.archive.stem + ".source.json")).write_text(
            json.dumps(record))
        result = self.call()
        self.assertEqual(result["source_asset"], "GE-Proton10.1.zip")
        self.assertEqual(result["source_release"], "PfxVer10.1")
        self.assertFalse(result["installed_to_game"])
        self.untouched()

    def test_symlinked_appdir_can_load_trusted_zip_inspector(self):
        fake = self.root / "dev-AppDir/usr/libexec/gameweld-prepared-prefix-stage.py"
        fake.parent.mkdir(parents=True)
        fake.symlink_to(SOURCE)
        with patch.object(stage, "__file__", str(fake)):
            audit = stage.load_audit()
        self.assertTrue(callable(audit.inspect_zip_members))
        self.untouched()

    def test_hash_mismatch_blocks_before_extraction(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"changed")
        with self.assertRaisesRegex(stage.StageRefused, "SHA-256"):
            self.call()
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_bad_zip_traversal_blocked(self):
        self.archive = self.make_zip([("../outside.txt", b"NEVER")])
        with self.assertRaisesRegex(stage.StageRefused, "structural"):
            self.call()
        self.assertFalse((self.cache / "staging").exists())
        self.assertFalse((self.root / "outside.txt").exists())
        self.untouched()

    def test_unmanaged_archive_and_symlinked_paths_refused(self):
        outside = self.root / "outside.zip"
        outside.write_bytes(self.archive.read_bytes())
        with self.assertRaisesRegex(stage.StageRefused, "GameWeld downloads"):
            self.call(archive=outside)
        linked = self.cache / "downloads" / ("a" * 64 + ".zip")
        linked.symlink_to(self.archive)
        with self.assertRaisesRegex(stage.StageRefused, "symlinked"):
            self.call(archive=linked)
        self.untouched()

    def test_cancel_rolls_back_partially_unpacked_staging(self):
        def cancel(phase, done, total):
            if phase == "STAGE" and done > 0:
                raise stage.StageRefused("cancelled")
        with self.assertRaisesRegex(stage.StageRefused, "cancelled"):
            self.call(progress=cancel)
        self.assertEqual(list((self.cache / "staging").iterdir()), [])
        self.untouched()

    def test_restage_refuses_to_overwrite_existing_payload(self):
        self.call()
        manifest = (self.cache / "staging" / self.archive.stem / "manifest.json")
        original = manifest.read_bytes()
        with self.assertRaisesRegex(stage.StageRefused, "already exists"):
            self.call()
        self.assertEqual(manifest.read_bytes(), original)
        self.untouched()

    def test_bad_disk_capacity_blocks_without_writes(self):
        with patch.object(stage.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 0})()):
            with self.assertRaisesRegex(stage.StageRefused, "Insufficient"):
                stage.stage_cached_archive(self.archive, cache_root=self.cache, approved=True)
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_refuses_to_use_steam_prefix_as_cache_root(self):
        bad = self.games[0] / "gameweld/prepared-wemod"
        with self.assertRaisesRegex(stage.StageRefused, "Steam library or game prefix"):
            stage.safe_root(bad)
        self.untouched()


if __name__ == "__main__":
    unittest.main()
