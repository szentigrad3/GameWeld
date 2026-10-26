#!/usr/bin/env python3
"""Realistic synthetic DeckCheatz GE-Proton prefix import regression.

All changes are in temporary private test state, never the original game.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-prepared-prefix-import.py")
SPEC = importlib.util.spec_from_file_location("gameweld_prepared_import", SOURCE)
assert SPEC and SPEC.loader
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PreparedPrefixImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-prefix-import-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.appid = "2353250"
        self.library = self.root / "steamapps"
        self.game = self.library / "common" / "Astrometica"
        self.compat = self.library / "compatdata" / self.appid
        self.game.mkdir(parents=True)
        (self.library / f"appmanifest_{self.appid}.acf").write_text("test appid")
        (self.compat / "pfx/drive_c/users/steamuser").mkdir(parents=True)
        (self.compat / "pfx/dosdevices").mkdir(parents=True)
        (self.compat / "pfx/dosdevices/z:").symlink_to("/")
        (self.compat / "version").write_text("GE-Proton10-1")
        (self.compat / "pfx/system.reg").write_bytes(b"ORIGINAL_GAME_REGISTRY")
        (self.compat / "pfx/user.reg").write_bytes(b"ORIGINAL_USER_REGISTRY")
        (self.compat / "pfx/drive_c/users/steamuser/save.dat").write_bytes(b"SAVE")
        self.cache = self.root / "cache/gameweld/prepared-wemod"
        self.state = self.root / "state/gameweld/prefix-imports"
        stageid = "c" * 64
        self.stage = self.cache / "staging" / stageid
        self.stage.mkdir(parents=True)
        self.cache.chmod(0o700)
        self.items = {
            "version": b"GE-Proton10.1",
            "pfx/.wemod_installer": b"true",
            "pfx/system.reg": b"REGISTRY_WITH_DOTNET48",
            "pfx/drive_c/windows/Microsoft.NET/Framework/v4.0.30319/mscorlib.dll":
                b"SYNTHETIC_DOTNET48_DLL",
        }
        self.write_template()
        self.original = self.game_state()

    def game_state(self):
        def digest(entry):
            if entry.is_symlink():
                return "link:" + os.readlink(entry)
            return hash_bytes(entry.read_bytes())
        return {
            item.relative_to(self.compat).as_posix(): digest(item)
            for item in self.compat.rglob("*")
            if item.is_file() or item.is_symlink()
        }

    def write_template(self):
        payload = self.stage / "payload"
        if payload.exists():
            shutil.rmtree(payload)
        payload.mkdir()
        for name, content in self.items.items():
            file = payload / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
        manifest = {
            "source_archive_sha256": self.stage.name,
            "source_asset": "GE-Proton10.1.zip",
            "source_release": "PfxVer10.1",
            "source_repo": "DeckCheatz/BuiltPrefixes-dev",
            "installed_to_game": False,
            "files": [
                {"path": name, "bytes": len(contents),
                 "sha256": hash_bytes(contents)}
                for name, contents in self.items.items()
            ],
        }
        (self.stage / "manifest.json").write_text(json.dumps(manifest))

    def preview(self):
        return plugin.preview(self.appid, self.game, self.stage,
                              cache_root=self.cache, state_root=self.state)

    def prepare(self, report, paths, approved=True):
        with patch.object(plugin.shutil, "disk_usage",
                          return_value=type("Disk", (), {"free": 100 * 1024**3})()):
            return plugin.prepare_candidate(
                report, paths, state_root=self.state, approved=approved)

    def test_read_only_preview_matches_proton_and_reports_registry_conflict(self):
        result, paths = self.preview()
        self.assertEqual(result["ge_proton_major"], 10)
        self.assertEqual(result["ge_proton_minor"], 1)
        self.assertTrue(result["version_match"])
        self.assertEqual(result["registry_conflicts"], 1)
        self.assertEqual(result["overlapping_files"], 2)
        self.assertFalse(result["live_game_modified"])
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["live_install_supported"])
        self.assertFalse(self.state.exists())
        self.assertEqual(self.game_state(), self.original)

    def test_candidate_preserves_game_saves_and_overlays_dotnet_off_game(self):
        report, paths = self.preview()
        result = self.prepare(report, paths)
        candidate = Path(result["candidate_dir"]) / "compatdata"
        self.assertTrue(candidate.is_dir())
        self.assertEqual((candidate / "pfx/system.reg").read_bytes(),
                         b"REGISTRY_WITH_DOTNET48")
        self.assertEqual((candidate / "pfx/user.reg").read_bytes(),
                         b"ORIGINAL_USER_REGISTRY")
        self.assertEqual(
            (candidate / "pfx/drive_c/users/steamuser/save.dat").read_bytes(), b"SAVE")
        self.assertTrue((candidate / "pfx/dosdevices/z:").is_symlink())
        self.assertEqual(os.readlink(candidate / "pfx/dosdevices/z:"), "/")
        self.assertEqual(
            (candidate / "pfx/drive_c/windows/Microsoft.NET/Framework/"
             "v4.0.30319/mscorlib.dll").read_bytes(), b"SYNTHETIC_DOTNET48_DLL")
        self.assertFalse(result["live_game_modified"])
        self.assertFalse(result["live_install_supported"])
        self.assertTrue((Path(result["candidate_dir"]) / "candidate.json").exists())
        self.assertEqual(self.game_state(), self.original)

    def test_no_approval_refuses_all_writes(self):
        report, paths = self.preview()
        with self.assertRaisesRegex(plugin.ImportBlocked, "Explicit"):
            self.prepare(report, paths, approved=False)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.game_state(), self.original)

    def test_mismatched_ge_proton_version_blocks(self):
        (self.compat / "version").write_text("GE-Proton9-26")
        with self.assertRaisesRegex(plugin.ImportBlocked, "does not match"):
            self.preview()
        self.assertFalse(self.state.exists())

    def test_unknown_proton_version_blocks(self):
        (self.compat / "version").write_text("Proton Experimental")
        with self.assertRaisesRegex(plugin.ImportBlocked, "cannot be established"):
            self.preview()

    def test_realistic_deckcheatz_archive_without_version_file(self):
        # DeckCheatz intentionally excludes the compatdata/version file when
        # creating downloadable prefixes; the asset name provides its version.
        self.items.pop("version")
        self.write_template()
        report, paths = self.preview()
        self.assertTrue(report["version_match"])
        candidate = self.prepare(report, paths)
        clone = Path(candidate["candidate_dir"]) / "compatdata"
        self.assertEqual((clone / "version").read_text(), "GE-Proton10-1")
        self.assertEqual((clone / "pfx/system.reg").read_bytes(),
                         b"REGISTRY_WITH_DOTNET48")
        self.assertEqual(self.game_state(), self.original)

    def test_missing_version_and_unidentified_release_block(self):
        self.items.pop("version")
        self.write_template()
        path = self.stage / "manifest.json"
        info = json.loads(path.read_text())
        info["source_asset"] = None
        info["source_release"] = None
        path.write_text(json.dumps(info))
        with self.assertRaisesRegex(plugin.ImportBlocked, "cannot be established"):
            self.preview()

    def test_staged_tampering_blocks_import(self):
        (self.stage / "payload/pfx/system.reg").write_bytes(b"TAMPERED")
        with self.assertRaisesRegex(plugin.ImportBlocked, "altered"):
            self.preview()
        self.assertEqual(self.game_state(), self.original)

    def test_untracked_file_blocks_import(self):
        (self.stage / "payload/untracked.dll").write_bytes(b"EVIL")
        with self.assertRaisesRegex(plugin.ImportBlocked, "untracked"):
            self.preview()

    def test_symlink_destination_collision_blocks_candidate_and_cleans(self):
        (self.compat / "pfx/drive_c/windows").parent.mkdir(exist_ok=True)
        (self.compat / "pfx/drive_c/windows").symlink_to(self.root)
        report, paths = self.preview()
        with self.assertRaisesRegex(plugin.ImportBlocked, "symlink"):
            self.prepare(report, paths)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_wrong_appid_manifest_rejected(self):
        (self.library / f"appmanifest_{self.appid}.acf").unlink()
        with self.assertRaisesRegex(plugin.ImportBlocked, "AppID manifest"):
            self.preview()

    def test_symlinked_staged_file_rejected(self):
        target = self.stage / "payload/pfx/system.reg"
        target.unlink()
        target.symlink_to(self.compat / "pfx/system.reg")
        with self.assertRaisesRegex(plugin.ImportBlocked, "altered"):
            self.preview()

    def test_missing_deckcheatz_marker_blocks(self):
        (self.stage / "payload/pfx/.wemod_installer").unlink()
        with self.assertRaisesRegex(plugin.ImportBlocked, "marker"):
            self.preview()

    def test_duplicate_candidate_never_overwritten(self):
        report, paths = self.preview()
        result = self.prepare(report, paths)
        marker = Path(result["candidate_dir"]) / "candidate.json"
        original_bytes = marker.read_bytes()
        with self.assertRaisesRegex(plugin.ImportBlocked, "already exists"):
            self.prepare(report, paths)
        self.assertEqual(marker.read_bytes(), original_bytes)
        self.assertEqual(self.game_state(), self.original)

    def test_outside_game_prefix_not_a_valid_target(self):
        with self.assertRaisesRegex(plugin.ImportBlocked, "steamapps/common"):
            plugin.preview(self.appid, self.root, self.stage,
                           cache_root=self.cache, state_root=self.state)


if __name__ == "__main__":
    unittest.main()
