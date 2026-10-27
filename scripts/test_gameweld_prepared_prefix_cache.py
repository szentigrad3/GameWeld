#!/usr/bin/env python3
"""Offline tests for opt-in, shared, game-independent WeMod ZIP cache download."""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).with_name("gameweld-prepared-prefix-cache.py")
spec = importlib.util.spec_from_file_location("prepared_prefix_cache", SOURCE)
assert spec and spec.loader
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)

URL = "https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/GE-Proton10-34/GE-Proton10-34.zip"


class FakeResponse(io.BytesIO):
    def __init__(self, content: bytes, url: str = URL):
        super().__init__(content)
        self.url = url
    def geturl(self):
        return self.url


class PreparedPrefixCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-prefix-cache-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache_root = self.root / "cache/gameweld/prepared-wemod"
        self.game = self.root / "steamapps/compatdata/361420/pfx"
        self.game.mkdir(parents=True)
        (self.game / "system.reg").write_text("PRESERVE-THIS-REGISTRY")
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("pfx/user.reg", b"TEST-ONLY")
            z.writestr("pfx/drive_c/test.bin", os.urandom(1_200_000))
        self.archive = memory.getvalue()

    def opener(self, request, timeout=30):
        self.assertEqual(timeout, cache.TIMEOUT)
        self.assertIn("BuiltPrefixes-dev/releases/download", request.full_url)
        return FakeResponse(self.archive)

    def assert_game_untouched(self):
        self.assertEqual((self.game / "system.reg").read_text(),
                         "PRESERVE-THIS-REGISTRY")
        self.assertEqual(sorted(p.name for p in self.game.iterdir()),
                         ["system.reg"])

    def test_not_approved_never_opens_network_or_writes(self):
        with patch.object(cache, "urlopen", side_effect=AssertionError("No network")):
            with self.assertRaisesRegex(cache.CacheRefused, "Explicit"):
                cache.acquire_to_cache(URL, declared_size=len(self.archive),
                                       cache_root=self.cache_root,
                                       approved=False, opener=self.opener)
        self.assertFalse(self.cache_root.exists())
        self.assert_game_untouched()

    def test_success_is_cache_only_and_never_extracts_to_game(self):
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            result = cache.acquire_to_cache(
                URL, declared_size=len(self.archive), cache_root=self.cache_root,
                approved=True, opener=self.opener
            )
        stored = Path(result["cache_path"])
        self.assertTrue(stored.exists())
        self.assertEqual(stored.read_bytes(), self.archive)
        self.assertEqual(result["archive_structural_check"], "PASS")
        self.assertEqual(result["publisher_authenticity"], "UNVERIFIED")
        self.assertFalse(result["installed_to_game"])
        self.assertFalse(result["trainer_verified"])
        self.assertEqual(list((self.cache_root / "incoming").glob("*.part")), [])
        self.assert_game_untouched()

    def test_cached_archive_keeps_release_version_metadata(self):
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            result = cache.acquire_to_cache(URL, declared_size=len(self.archive),
                                            cache_root=self.cache_root, approved=True,
                                            opener=self.opener)
        source_file = Path(result["cache_path"]).with_suffix(".source.json")
        self.assertTrue(source_file.is_file())
        import json
        record = json.loads(source_file.read_text())
        self.assertEqual(record["asset_name"], "GE-Proton10-34.zip")
        self.assertEqual(record["source"], "DeckCheatz/BuiltPrefixes-dev")
        self.assertEqual(record["sha256"], result["sha256"])
        self.assertEqual(record["publisher_authenticity"], "UNVERIFIED")
        self.assert_game_untouched()

    def test_source_symlinked_appdir_resolves_trusted_audit_helper(self):
        fake = self.root / "dev-AppDir/usr/libexec/gameweld-prepared-prefix-cache.py"
        fake.parent.mkdir(parents=True)
        fake.symlink_to(SOURCE)
        with patch.object(cache, "__file__", str(fake)):
            audit = cache._load_zip_audit()
        self.assertTrue(callable(audit.inspect_zip_members))
        self.assert_game_untouched()

    def test_download_progress_is_monotonic_and_never_installs(self):
        updates = []
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            result = cache.acquire_to_cache(
                URL, declared_size=len(self.archive),
                cache_root=self.cache_root, approved=True, opener=self.opener,
                progress=lambda stage, done, total: updates.append((stage, done, total))
            )
        self.assertEqual(updates[0], ("DOWNLOAD", 0, len(self.archive)))
        downloads = [done for stage, done, total in updates if stage == "DOWNLOAD"]
        self.assertEqual(downloads, sorted(downloads))
        self.assertEqual(downloads[-1], len(self.archive))
        self.assertEqual(updates[-2], ("VERIFY", len(self.archive), len(self.archive)))
        self.assertEqual(updates[-1], ("CACHED", len(self.archive), len(self.archive)))
        self.assertFalse(result["installed_to_game"])
        self.assert_game_untouched()

    def test_user_cancellation_discards_incomplete_temp_without_changing_games(self):
        events = []
        def cancel_at_chunk(stage, done, total):
            events.append(stage)
            if stage == "DOWNLOAD" and done > 0:
                raise cache.CacheRefused("Cancelled by user")
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            with self.assertRaisesRegex(cache.CacheRefused, "Cancelled"):
                cache.acquire_to_cache(
                    URL, declared_size=len(self.archive),
                    cache_root=self.cache_root, approved=True, opener=self.opener,
                    progress=cancel_at_chunk
                )
        self.assertIn("DOWNLOAD", events)
        self.assertEqual(list((self.cache_root / "incoming").glob("*.part")), [])
        self.assertEqual(list((self.cache_root / "downloads").glob("*.zip")), [])
        self.assert_game_untouched()

    def test_invalid_hosts_and_redirects_fail_closed(self):
        for url in (
            "https://evil.example/file.zip",
            "http://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/t/a.zip",
            "https://github.com/Other/BuiltPrefixes-dev/releases/download/t/a.zip",
            "https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/t/../evil.zip",
            "https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/t/a.exe",
        ):
            with self.subTest(url=url), self.assertRaises(cache.CacheRefused):
                cache.validate_release_url(url)
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            with self.assertRaisesRegex(cache.CacheRefused, "redirect"):
                cache.acquire_to_cache(
                    URL, declared_size=len(self.archive), cache_root=self.cache_root,
                    approved=True,
                    opener=lambda request, timeout: FakeResponse(
                        self.archive, "https://untrusted.example/archive.zip"),
                )
        self.assertEqual(list((self.cache_root / "incoming").glob("*.part")), [])
        self.assert_game_untouched()

    def test_traversal_or_truncated_archive_cannot_enter_stored_cache(self):
        bad_bytes = io.BytesIO()
        with zipfile.ZipFile(bad_bytes, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("../run.exe", os.urandom(1_200_000))
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 5_000_000_000})()):
            with self.assertRaisesRegex(cache.CacheRefused, "ZIP safety check failed: Path traversal"):
                cache.acquire_to_cache(
                    URL, declared_size=len(bad_bytes.getvalue()),
                    cache_root=self.cache_root, approved=True,
                    opener=lambda request, timeout: FakeResponse(bad_bytes.getvalue()),
                )
            with self.assertRaisesRegex(cache.CacheRefused, "size"):
                cache.acquire_to_cache(
                    URL, declared_size=len(self.archive) + 1,
                    cache_root=self.cache_root, approved=True,
                    opener=self.opener,
                )
        self.assertEqual(list((self.cache_root / "downloads").glob("*.zip")), [])
        self.assertEqual(list((self.cache_root / "incoming").glob("*.part")), [])
        self.assert_game_untouched()

    def test_symlinked_cache_ancestry_and_game_prefix_path_blocked(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root / "steamapps", target_is_directory=True)
        with self.assertRaisesRegex(cache.CacheRefused, "Symlinked"):
            cache.safe_cache_root(alias / "managed-cache")
        with self.assertRaisesRegex(cache.CacheRefused, "game prefix"):
            cache.safe_cache_root(self.game / "GameWeldCache")
        self.assert_game_untouched()

    def test_low_disk_space_blocks_before_cache_created(self):
        with patch.object(cache.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 1_000_000})()):
            with self.assertRaisesRegex(cache.CacheRefused, "free space"):
                cache.acquire_to_cache(
                    URL, declared_size=len(self.archive), cache_root=self.cache_root,
                    approved=True, opener=self.opener
                )
        self.assertFalse(self.cache_root.exists())

if __name__ == "__main__":
    unittest.main()
