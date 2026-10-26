#!/usr/bin/env python3
"""Offline tests for read-only DeckCheatz prepared prefix release discovery."""
from __future__ import annotations

import importlib.util
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
