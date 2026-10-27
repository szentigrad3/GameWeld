#!/usr/bin/env python3
"""Offline tests for read-only DeckCheatz prepared prefix release discovery."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HELPER = Path(__file__).with_name("gameweld-deckcheatz-prefix-catalog.py")
spec = importlib.util.spec_from_file_location("deckcheatz_catalog", HELPER)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def release(tag, name, size=95_000_000, *, url=None):
    url = url or f"https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/{tag}/{name}"
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets": [{"name": name, "browser_download_url": url, "size": size}],
    }


class PreparedPrefixCatalogTests(unittest.TestCase):
    def test_matching_tag_is_ranked_above_same_and_different_major(self):
        releases = [
            release("GE-Proton10-34", "GE-Proton10-34.zip"),
            release("GE-Proton11-1", "GE-Proton11-1.zip"),
            release("GE-Proton11-2", "GE-Proton11-2.zip"),
        ]
        matches = mod.list_release_assets(releases, "Proton Experimental GE-Proton11-1")
        self.assertEqual(matches[0]["release"], "GE-Proton11-1")
        self.assertEqual(matches[0]["rank"], 3)
        self.assertEqual(matches[1]["rank"], 2)
        self.assertEqual(matches[2]["rank"], 1)

    def test_never_confuse_unknown_version_with_verified_compatibility(self):
        options = mod.list_release_assets(
            [release("GE-Proton11-1", "GE-Proton11-1.zip")],
            "Proton Experimental"
        )
        self.assertEqual(options[0]["rank"], 0)
        self.assertIn("UNVERIFIED", options[0]["compatibility"])
        report = mod.catalog_report("Proton Experimental", releases=[
            release("GE-Proton11-1", "GE-Proton11-1.zip"),
        ])
        self.assertIn("Detected Proton version label: UNKNOWN", report)
        self.assertIn("No archive downloaded; no files copied", report)

    def test_reject_untrusted_assets_and_prereleases(self):
        releases = [
            release("GE-Proton11-1", "GE-Proton11-1.zip",
                    url="https://untrusted.example/payload.zip"),
            release("GE-Proton11-1", "GE-Proton11-1.zip", size=22),
            {**release("GE-Proton11-1", "GE-Proton11-1.zip"), "prerelease": True},
            release("GE-Proton11-1", "GE-Proton11-1.exe"),
        ]
        self.assertEqual(mod.list_release_assets(releases, "GE-Proton11-1"), [])

    def test_no_install_or_download_with_local_release_fixture(self):
        with patch.object(mod, "fetch_release_metadata",
                          side_effect=AssertionError("must not use network")):
            report = mod.catalog_report(
                "GE-Proton11-1",
                releases=[release("GE-Proton11-1", "GE-Proton11-1.zip")]
            )
        self.assertIn("EXACT VERSION LABEL MATCH", report)
        self.assertIn("No automated replacement is enabled.", report)
        self.assertIn("Before any future install:", report)
        self.assertIn("NOT VERIFIED", report)

    def test_global_catalog_cli_requires_no_game_appid_or_steam_settings(self):
        import contextlib
        import io
        import sys
        result = io.StringIO()
        with patch.object(mod, "fetch_release_metadata",
                          return_value=[release("GE-Proton10-34", "GE-Proton10-34.zip")]), \
             patch.object(sys, "argv", ["gameweld-deckcheatz-prefix-catalog.py"]), \
             contextlib.redirect_stdout(result):
            rc = mod.main()
        self.assertEqual(rc, 0)
        self.assertIn("SHARED PREPARED-PREFIX LIBRARY for Steam, Heroic and Lutris", result.getvalue())
        self.assertIn("Configured Proton label: Shared GameWeld WeMod environment", result.getvalue())
        self.assertIn("Detected Proton version label: UNKNOWN", result.getvalue())
        self.assertIn("No archive downloaded; no files copied", result.getvalue())

    def test_machine_lines_offer_bounded_choices_without_download(self):
        import contextlib
        import io
        import sys
        releases = [
            release("GE-Proton10-34", "GE-Proton10-34.zip"),
            release("GE-Proton11-1", "GE-Proton11-1.zip"),
        ]
        output = io.StringIO()
        with patch.object(mod, "fetch_release_metadata",
                          return_value=releases) as fetched, \
             patch.object(sys, "argv", [
                 "gameweld-deckcheatz-prefix-catalog.py", "--machine-lines"
             ]), contextlib.redirect_stdout(output):
            self.assertEqual(mod.main(), 0)
        lines = output.getvalue().splitlines()
        assets = [line for line in lines if line.startswith("ASSET\t")]
        self.assertEqual(len(assets), 2)
        self.assertIn("GE-Proton10-34.zip", assets[0])
        self.assertIn("https://github.com/DeckCheatz/BuiltPrefixes-dev/", assets[0])
        self.assertIn("No archive downloaded; no files copied", output.getvalue())
        fetched.assert_called_once()

    def test_rejected_local_asset_is_not_offered_again(self):
        import contextlib
        import io
        import sys
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir) / "gameweld/prepared-wemod"
            quarantine = root / "rejected"
            quarantine.mkdir(parents=True, mode=0o700)
            quarantine.chmod(0o700)
            content = b"DIAGNOSTIC ZIP PLACEHOLDER" * 50000
            sha = hashlib.sha256(content).hexdigest()
            (quarantine / (sha + ".zip")).write_bytes(content)
            (quarantine / (sha + ".rejected.json")).write_text(json.dumps({
                "sha256": sha, "source": "DeckCheatz/BuiltPrefixes-dev",
                "status": "REJECTED_NOT_STAGEABLE", "release_tag": "PfxVer10.1",
                "asset_name": "GE-Proton10.1.zip", "bytes": len(content),
            }))
            rejected_asset = release("PfxVer10.1", "GE-Proton10.1.zip", size=len(content))
            new_asset = release("PfxVer10.2", "GE-Proton10.2.zip", size=95_000_000)
            offered, rejected = mod.filter_locally_rejected(
                mod.list_release_assets([rejected_asset, new_asset], "GE-Proton10.1"),
                root)
            self.assertEqual([x["asset"] for x in offered], ["GE-Proton10.2.zip"])
            self.assertEqual(rejected[0]["asset"], "GE-Proton10.1.zip")
            output = io.StringIO()
            with patch.object(mod, "fetch_release_metadata",
                              return_value=[rejected_asset, new_asset]), \
                 patch.object(sys, "argv", [
                     "gameweld-deckcheatz-prefix-catalog.py",
                     "--machine-lines", "--cache-root", str(root),
                     "--proton-label", "GE-Proton10.1",
                 ]), contextlib.redirect_stdout(output):
                self.assertEqual(mod.main(), 0)
            lines = output.getvalue().splitlines()
            self.assertEqual(sum(line.startswith("BLOCKED\t") for line in lines), 1)
            self.assertEqual(sum(line.startswith("ASSET\t") for line in lines), 1)
            self.assertIn("BLOCKED\tPfxVer10.1\tGE-Proton10.1.zip\tCASE_COLLISIONS", lines)
            self.assertIn("ASSET\tPfxVer10.2\tGE-Proton10.2.zip\t", output.getvalue())
            self.assertIn("Known rejected releases excluded: 1", output.getvalue())
            self.assertFalse((root / "downloads").exists())

    def test_invalid_quarantine_metadata_blocks_catalog_choices(self):
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir) / "gameweld/prepared-wemod"
            quarantine = root / "rejected"
            quarantine.mkdir(parents=True, mode=0o700)
            quarantine.chmod(0o700)
            (quarantine / ("a" * 64 + ".rejected.json")).write_text("{not json")
            result = mod.catalog_report("GE-Proton10.1", releases=[
                release("PfxVer10.1", "GE-Proton10.1.zip")
            ], cache_root=root)
            self.assertIn("Local rejection records: UNAVAILABLE or UNSAFE.", result)
            self.assertNotIn("Prepared prefix archives listed:", result)

    def test_absent_quarantine_does_not_block_other_choices(self):
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir) / "gameweld/prepared-wemod"
            result = mod.catalog_report("GE-Proton10.1", releases=[
                release("PfxVer10.2", "GE-Proton10.2.zip")
            ], cache_root=root)
            self.assertIn("Prepared prefix archives listed: 1", result)
            self.assertNotIn("Known rejected releases excluded:", result)

    def test_invalid_catalog_shape_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "list"):
            mod.list_release_assets({"assets": []}, "GE-Proton11-1")

    def test_metadata_fetch_bounded_and_timeout(self):
        request_args = []
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n):
                request_args.append(n)
                return json.dumps([release("GE-Proton11-1", "GE-Proton11-1.zip")]).encode()
        with patch.object(mod, "urlopen", return_value=FakeResponse()) as fake:
            releases = mod.fetch_release_metadata()
        self.assertEqual(len(releases), 1)
        self.assertEqual(request_args, [mod.MAX_RELEASE_BYTES + 1])
        self.assertEqual(fake.call_args.kwargs["timeout"], 8)

if __name__ == "__main__":
    unittest.main()
