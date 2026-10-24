#!/usr/bin/env python3
"""No-download unit tests of the opt-in isolated Wine rebuild entrypoint."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from unittest.mock import patch
import io
from contextlib import redirect_stdout
import tempfile
import unittest

SRC = Path(__file__).with_name("pc2-wand-crypt32-rebuild.py")
spec = importlib.util.spec_from_file_location("pc2_wine_builder", SRC)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class WineRebuildSafetyTests(unittest.TestCase):
    def test_default_and_explicit_preflight_never_clone_or_build(self):
        for args in ([], ["--preflight"]):
            with self.subTest(args=args):
                capture = io.StringIO()
                with patch.object(builder, "compile_only") as compile, \
                     patch.object(builder.subprocess, "run") as run, \
                     redirect_stdout(capture):
                    self.assertEqual(builder.main(args), 0)
                    compile.assert_not_called()
                    run.assert_not_called()
                self.assertIn("Mode: READ ONLY", capture.getvalue())
                self.assertIn("No Steam", capture.getvalue()) if "No Steam" in capture.getvalue() else None

    def test_build_is_never_selected_without_explicit_confirmation(self):
        with patch.object(builder, "compile_only") as compile:
            with self.assertRaisesRegex(ValueError, "explicit --confirm"):
                builder.main(["--build"])
            compile.assert_not_called()
            with self.assertRaisesRegex(ValueError, "only valid with --build"):
                builder.main(["--confirm"])
            compile.assert_not_called()

    def test_confirmation_calls_isolated_compile_once(self):
        with patch.object(builder, "compile_only", return_value=0) as compile:
            self.assertEqual(builder.main(["--build", "--confirm"]), 0)
            compile.assert_called_once_with(builder.WORK)

    def test_existing_artifact_or_source_tree_fails_before_network(self):
        with tempfile.TemporaryDirectory(prefix="gw-wine-build-safety-") as temp:
            root = Path(temp)
            source = root / "wine-source"
            source.mkdir()
            with patch.object(builder, "PATCH", Path(__file__)), \
                 patch.object(builder, "safe_dirs"), \
                 patch.object(builder.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "Source directory already exists"):
                    builder.compile_only(root)
                run.assert_not_called()

    def test_fingerprints_and_revision_are_pinned(self):
        self.assertEqual(builder.REV,
            "46b29104e3741fe23bf5e2547196a253aab88c89")
        self.assertEqual(builder.HISTORIC["x86_64-windows"],
            "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775")
        self.assertEqual(builder.HISTORIC["i386-windows"],
            "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da")

if __name__ == "__main__":
    unittest.main()
