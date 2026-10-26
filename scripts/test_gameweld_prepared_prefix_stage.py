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

    def test_cache_status_identifies_orphan_download_without_redownloading(self):
        result = stage.cache_status(self.cache)
        self.assertIn("ZIP archives found: 1", result)
        self.assertIn("Source metadata records found: 0", result)
        self.assertIn("ZIP(s) without matching metadata records: 1", result)
        self.assertNotIn(str(self.root), result)
        self.untouched()

    def test_cache_status_lists_valid_release_without_exposing_paths(self):
        self.add_source_record(self.archive)
        result = stage.cache_status(self.cache)
        self.assertIn("PfxVer10.1 / GE-Proton10.1.zip", result)
        self.assertIn("ZIP FOUND + SIZE MATCH", result)
        self.assertNotIn(str(self.root), result)
        self.untouched()

    def test_cache_status_detects_missing_or_mismatched_download(self):
        self.add_source_record(self.archive)
        self.archive.unlink()
        result = stage.cache_status(self.cache)
        self.assertIn("ZIP MISSING OR SIZE MISMATCH", result)
        self.untouched()

    def test_cache_status_detects_bad_record_without_following_links(self):
        record = self.add_source_record(self.archive)
        record.unlink()
        record.symlink_to(self.root / "steamapps/compatdata/361420/pfx/system.reg")
        result = stage.cache_status(self.cache)
        self.assertIn("Invalid or unreadable metadata records: 1", result)
        self.assertNotIn("KEEP ORIGINAL", result)
        self.untouched()

    def test_missing_download_explains_first_step(self):
        self.archive.unlink()
        with self.assertRaisesRegex(stage.StageRefused, "Step 1: choose a release"):
            stage.select_single_cached_zip(self.cache)
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_single_cached_zip_selects_exact_archive(self):
        self.assertEqual(stage.select_single_cached_zip(self.cache), self.archive)
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_multiple_downloads_explains_explicit_selection(self):
        self.make_zip([("pfx/second-file.bin", b"SECOND")])
        with self.assertRaisesRegex(stage.StageRefused, "Multiple prepared ZIPs"):
            stage.select_single_cached_zip(self.cache)
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def add_source_record(self, archive, tag="PfxVer10.1", asset="GE-Proton10.1.zip"):
        import json
        record = {
            "sha256": archive.stem,
            "source": "DeckCheatz/BuiltPrefixes-dev",
            "release_tag": tag,
            "asset_name": asset,
            "bytes": archive.stat().st_size,
            "publisher_authenticity": "UNVERIFIED",
        }
        path = archive.with_suffix(".source.json")
        path.write_text(json.dumps(record))
        return path

    def selected_url(self, tag="PfxVer10.1", asset="GE-Proton10.1.zip"):
        return (f"https://github.com/DeckCheatz/BuiltPrefixes-dev/"
                f"releases/download/{tag}/{asset}")

    def test_actual_cache_download_then_selected_release_staging(self):
        """Run the real download-cache and stage selection APIs end-to-end."""
        import json
        import os
        import importlib.util
        cache_script = SOURCE.with_name("gameweld-prepared-prefix-cache.py")
        spec = importlib.util.spec_from_file_location(
            "gameweld_real_cache_e2e", cache_script)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.archive.unlink()  # Start with a completely empty managed cache.
        body = io.BytesIO()
        with zipfile.ZipFile(body, "w", zipfile.ZIP_STORED) as zipout:
            zipout.writestr("pfx/user.reg", os.urandom(1_200_000))
            zipout.writestr("pfx/.wemod_installer", b"")
        archive_bytes = body.getvalue()
        url = self.selected_url()

        class Response(io.BytesIO):
            def geturl(self):
                return url

        with patch.object(module.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 20 * 1024 ** 3})()):
            result = module.acquire_to_cache(
                url, declared_size=len(archive_bytes), cache_root=self.cache,
                approved=True,
                opener=lambda request, timeout: Response(archive_bytes)
            )
        self.assertEqual(result["archive_structural_check"], "PASS")
        chosen = stage.select_cached_release(self.cache, url)
        self.assertEqual(chosen, Path(result["cache_path"]))
        record = chosen.with_suffix(".source.json")
        self.assertEqual(json.loads(record.read_text())["release_tag"], "PfxVer10.1")
        staged = self.call(archive=chosen)
        self.assertEqual(staged["source_release"], "PfxVer10.1")
        self.assertEqual(staged["source_asset"], "GE-Proton10.1.zip")
        self.assertFalse(staged["installed_to_game"])
        self.untouched()

    def test_selected_release_chooses_matching_zip_among_multiple_cached(self):
        self.add_source_record(self.archive)
        other = self.make_zip([("pfx/unrelated.bin", b"UNRELATED")])
        self.add_source_record(other, tag="PfxVer9.26", asset="GE-Proton9.26.zip")
        chosen = stage.select_cached_release(self.cache, self.selected_url())
        self.assertEqual(chosen, self.archive)
        result = self.call(archive=chosen)
        self.assertEqual(result["source_asset"], "GE-Proton10.1.zip")
        self.assertFalse(result["installed_to_game"])
        self.untouched()

    def test_selected_release_not_downloaded_does_not_stage_other_version(self):
        other = self.make_zip([("pfx/unrelated.bin", b"UNRELATED")])
        self.add_source_record(other, tag="PfxVer9.26", asset="GE-Proton9.26.zip")
        with self.assertRaisesRegex(stage.StageRefused, "Step 1"):
            stage.select_cached_release(self.cache, self.selected_url())
        self.assertFalse((self.cache / "staging").exists())
        self.untouched()

    def test_selected_release_fails_closed_on_corrupted_source_record(self):
        record = self.add_source_record(self.archive)
        import json
        value = json.loads(record.read_text())
        value["sha256"] = "0" * 64
        record.write_text(json.dumps(value))
        with self.assertRaisesRegex(stage.StageRefused, "inconsistent provenance"):
            stage.select_cached_release(self.cache, self.selected_url())
        self.untouched()

    def test_selected_release_rejects_ambiguous_same_release(self):
        self.add_source_record(self.archive)
        second = self.make_zip([("pfx/second.bin", b"SECOND")])
        self.add_source_record(second)
        with self.assertRaisesRegex(stage.StageRefused, "Multiple cached copies"):
            stage.select_cached_release(self.cache, self.selected_url())
        self.untouched()

    def test_selected_release_rejects_metadata_symlink(self):
        record = self.add_source_record(self.archive)
        record.unlink()
        record.symlink_to(self.archive)
        with self.assertRaisesRegex(stage.StageRefused, "Unsafe cached release metadata"):
            stage.select_cached_release(self.cache, self.selected_url())
        self.untouched()

    def test_selected_release_rejects_foreign_url(self):
        with self.assertRaisesRegex(stage.StageRefused, "Invalid selected"):
            stage.select_cached_release(self.cache, "https://evil.example/prefix.zip")
        self.untouched()

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
