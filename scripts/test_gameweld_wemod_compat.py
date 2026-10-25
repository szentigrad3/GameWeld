#!/usr/bin/env python3
"""Offline tests for the opt-in official WeMod compatibility build staging."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).with_name("gameweld-wemod-compat.py")
spec = importlib.util.spec_from_file_location("gameweld_wemod_compat", SCRIPT)
assert spec and spec.loader
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)


def fixture_package(package: Path, *, bad_member: str | None = None) -> None:
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("lib/net45/WeMod.exe", b"MZ-TEST")
        archive.writestr("lib/net45/resources/app.asar", b"ASAR-TEST")
        if bad_member:
            archive.writestr(bad_member, b"BAD")


class WeModCompatTests(unittest.TestCase):
    def test_checksum_matches_pinned_coproton_source(self):
        self.assertEqual(compat.VERSION, "11.6.0")
        self.assertEqual(compat.SHA256,
                         "5b94ae5592e698b13cbc06fae4c096fe2438cbd362daac3f842e13190bf836ba")
        self.assertEqual(compat.PACKAGE_URL,
                         "https://storage-cdn.wemod.com/app/releases/stable/WeMod-11.6.0-full.nupkg")

    def test_unpacks_only_portable_client_without_touching_other_install(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            archive = path / "package.nupkg"
            fixture_package(archive)
            with zipfile.ZipFile(archive, "a") as z:
                z.writestr("random-file.txt", "not portable")
            target = path / "client"
            compat.unpack(archive, target)
            self.assertTrue(compat.installed(target))
            self.assertFalse((target / "random-file.txt").exists())

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            archive = path / "package.nupkg"
            fixture_package(archive, bad_member="lib/net45/../../outside")
            with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                compat.unpack(archive, path / "client")

    def test_rejects_case_colliding_paths(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            archive = path / "package.nupkg"
            fixture_package(archive, bad_member="lib/net45/wemod.exe")
            with self.assertRaisesRegex(ValueError, "Duplicate case-insensitive"):
                compat.unpack(archive, path / "client")

    def test_rejects_download_with_wrong_checksum(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            archive = path / "package.nupkg"
            class FakeResponse:
                def __enter__(self): return io.BytesIO(b"unknown binary")
                def __exit__(self, *_args): return None
            with patch.object(compat, "urlopen", return_value=FakeResponse()):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    compat.download(archive, expected_sha="0" * 64)
            self.assertTrue(archive.exists())  # caller stages inside disposable temp dir

    def test_stage_creates_verified_manifest_without_network(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            archive = base / "fixture.nupkg"
            fixture_package(archive)
            output = base / "staged" / "11.6.0"
            with patch.object(compat, "download",
                              side_effect=lambda target: __import__("shutil").copyfile(archive, target)):
                compat.stage(output)
            self.assertTrue(compat.installed(output))
            import json
            manifest = json.loads((output / ".gameweld-baseline.json").read_text())
            self.assertEqual(manifest["version"], "11.6.0")
            self.assertEqual(manifest["package_sha256"], compat.SHA256)
            self.assertEqual(manifest["exe_sha256"],
                             hashlib.sha256((output / "WeMod.exe").read_bytes()).hexdigest())
            self.assertEqual(manifest["asar_sha256"],
                             hashlib.sha256((output / "resources/app.asar").read_bytes()).hexdigest())

    def test_existing_install_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "client"
            path.mkdir()
            (path / "arbitrary-user-file").write_text("KEEP")
            with self.assertRaisesRegex(ValueError, "Refusing to replace"):
                compat.stage(path)
            self.assertEqual((path / "arbitrary-user-file").read_text(), "KEEP")


if __name__ == "__main__":
    unittest.main()
