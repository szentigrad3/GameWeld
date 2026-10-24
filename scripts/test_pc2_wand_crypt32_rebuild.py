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
                self.assertIn('This builder does not use sudo', capture.getvalue())

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


    def test_wine_git_checkout_bootstraps_missing_configure(self):
        with tempfile.TemporaryDirectory(prefix="gw-wine-autogen-") as temp:
            source = Path(temp) / "wine-source"
            source.mkdir()
            (source / "autogen.sh").write_text("#!/bin/sh\necho generated\n")
            (source / "configure.ac").write_text("AC_INIT([Wine],[1])\n")
            log = io.StringIO()
            invoked = []

            def generate(command, output, *, cwd=None):
                invoked.append((command, cwd))
                (source / "configure").write_text("#!/bin/sh\nexit 0\n")

            with patch.object(builder, "run_log", side_effect=generate):
                with patch.object(builder.shutil, "which", return_value="/usr/bin/autoreconf"):
                    builder.ensure_configure(source, log)
                    builder.ensure_configure(source, log)
            self.assertEqual(invoked, [(["sh", "./autogen.sh"], source)])
            self.assertTrue((source / "configure").is_file())

    def test_existing_exact_revision_and_applied_patch_are_reused(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory(prefix="gw-wine-reuse-") as temp:
            source = Path(temp) / "wine-source"
            source.mkdir()
            (source / ".git").mkdir()
            cert = source / "dlls/crypt32/cert.c"
            cert.parent.mkdir(parents=True)
            cert.write_text("case CERT_SHA256_HASH_PROP_ID: CALG_SHA_256")
            log = io.StringIO()
            reverse_ok = Mock(returncode=0)
            with patch.object(builder.subprocess, "check_output", return_value=builder.REV):
                with patch.object(builder.subprocess, "run", return_value=reverse_ok) as subprocess_run:
                    with patch.object(builder, "run_log") as run_log:
                        builder.ensure_pinned_source(source, log)
            subprocess_run.assert_called_once()
            self.assertIn("--reverse", subprocess_run.call_args.args[0])
            run_log.assert_not_called()
            self.assertTrue(cert.is_file())

    def test_resume_preserves_failed_source_and_empty_build_dir(self):
        with tempfile.TemporaryDirectory(prefix="gw-wine-resume-") as temp:
            work = Path(temp)
            source = work / "wine-source"
            source.mkdir()
            (source / ".git").mkdir()
            build = work / "wine-build"
            build.mkdir()
            old_log = work / "build-output.log"
            old_log.write_text("Original configure FileNotFoundError\n")
            visited = []

            def pretend_run(command, output, *, cwd=None):
                visited.append((command[:2], cwd))
                if command[0].endswith("configure"):
                    (build / "Makefile").write_text("all:\n")
                elif command[0] == "make":
                    for arch in builder.HISTORIC:
                        dll = build / "dlls/crypt32" / arch / "crypt32.dll"
                        dll.parent.mkdir(parents=True)
                        dll.write_bytes(b"MZ-TEST-SYNTHETIC-" + arch.encode())

            with patch.object(builder, "PATCH", Path(__file__)):
                with patch.object(builder, "safe_dirs"):
                    with patch.object(builder, "ensure_pinned_source") as pinned:
                        with patch.object(builder, "ensure_configure") as bootstrap:
                            with patch.object(builder, "run_log", side_effect=pretend_run):
                                with patch.object(builder.subprocess, "check_output", return_value="PE32+ executable (DLL)"):
                                    self.assertEqual(builder.compile_only(work), 0)

            pinned.assert_called_once()
            bootstrap.assert_called_once()
            self.assertTrue(any(c[0][0] == "make" for c in visited))
            self.assertTrue(any(c[0][0].endswith("configure") for c in visited))
            self.assertTrue((work / "candidate/SHA256SUMS").is_file())
            self.assertIn("Original configure FileNotFoundError", old_log.read_text())
            self.assertTrue(source.is_dir())
            self.assertTrue(build.is_dir())

    def test_fingerprints_and_revision_are_pinned(self):
        self.assertEqual(builder.REV,
            "46b29104e3741fe23bf5e2547196a253aab88c89")
        self.assertEqual(builder.HISTORIC["x86_64-windows"],
            "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775")
        self.assertEqual(builder.HISTORIC["i386-windows"],
            "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da")

if __name__ == "__main__":
    unittest.main()
