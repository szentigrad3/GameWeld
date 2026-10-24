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
                with self.assertRaisesRegex(ValueError, "Source directory exists without Git metadata"):
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
                            with patch.object(builder, "ensure_sha256_header") as header:
                                with patch.object(builder, "run_log", side_effect=pretend_run):
                                    with patch.object(builder.subprocess, "check_output", return_value="PE32+ executable (DLL)"):
                                        self.assertEqual(builder.compile_only(work), 0)

            pinned.assert_called_once()
            bootstrap.assert_called_once()
            header.assert_called_once()
            self.assertTrue(any(c[0][0] == "make" for c in visited))
            self.assertTrue(any(c[0][0].endswith("configure") for c in visited))
            self.assertEqual(
                builder.crypt32_targets(),
                ["dlls/crypt32/x86_64-windows/crypt32.dll",
                 "dlls/crypt32/i386-windows/crypt32.dll"],
            )
            # No generic full-Wine target or unrelated multimedia builds.
            make_calls = [c for c in visited if c[0][0] == "make"]
            self.assertEqual(len(make_calls), 1)
            self.assertEqual(make_calls[0][0][1][:2], "-j")
            self.assertTrue((work / "candidate/SHA256SUMS").is_file())
            self.assertIn("Original configure FileNotFoundError", old_log.read_text())
            self.assertTrue(source.is_dir())
            self.assertTrue(build.is_dir())


    def test_missing_property_107_header_patch_applies_and_second_pass_is_readonly(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix="gw-wine-crypt32-header-") as temp:
            source = Path(temp)
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            header = source / "include" / "wincrypt.h"
            header.parent.mkdir()
            header.write_text(
                "#define CERT_ROOT_PROGRAM_NAME_CONSTRAINTS_PROP_ID 84\n"
                "\n"
                "#define CERT_SIGN_HASH_CNG_ALG_PROP_ID             89\n"
                "\n"
                "#define CERT_FIRST_RESERVED_PROP_ID                130\n"
                "#define CERT_LAST_RESERVED_PROP_ID                 0x00007fff\n"
                "#define CERT_FIRST_USER_PROP_ID                    0x00008000\n"
                "#define CERT_LAST_USER_PROP_ID                     0x0000ffff\n")
            self.assertTrue(builder.HEADER_PATCH.is_file())
            # git apply runs a real subprocess and needs an OS file descriptor;
            # StringIO is valid for purely mocked calls but not stdout= here.
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
                builder.ensure_sha256_header(source, log)
                first = header.read_text()
                self.assertIn("#define CERT_SHA256_HASH_PROP_ID                    107", first)
                builder.ensure_sha256_header(source, log)
                self.assertEqual(header.read_text(), first)
                self.assertEqual(first.count("#define CERT_SHA256_HASH_PROP_ID"), 1)

    def test_conflicting_crypt32_property_definition_refused_without_writes(self):
        with tempfile.TemporaryDirectory(prefix="gw-wine-crypt32-conflict-") as temp:
            source = Path(temp)
            header = source / "include/wincrypt.h"
            header.parent.mkdir()
            header.write_text("#define CERT_SHA256_HASH_PROP_ID 108\n")
            with patch.object(builder, "run_log") as runner:
                with self.assertRaisesRegex(ValueError, "incompatibly"):
                    builder.ensure_sha256_header(source, io.StringIO())
                runner.assert_not_called()
            self.assertEqual(header.read_text(), "#define CERT_SHA256_HASH_PROP_ID 108\n")


    def test_build_does_not_invoke_full_wine_or_winedmo(self):
        with tempfile.TemporaryDirectory(prefix="gw-crypt32-target-") as temp:
            work = Path(temp)
            source = work / "wine-source"
            source.mkdir()
            (source / ".git").mkdir()
            build = work / "wine-build"
            build.mkdir()
            (build / "Makefile").write_text("all:\n")
            called = []

            def fake_run(command, output, *, cwd=None):
                called.append(command)
                if command[0] == "make":
                    for arch in builder.HISTORIC:
                        dll = build / "dlls/crypt32" / arch / "crypt32.dll"
                        dll.parent.mkdir(parents=True)
                        dll.write_bytes(b"MZ-TEST-" + arch.encode())

            with patch.object(builder, "ensure_pinned_source"):
                with patch.object(builder, "ensure_configure"):
                    with patch.object(builder, "ensure_sha256_header"):
                        with patch.object(builder, "run_log", side_effect=fake_run):
                            with patch.object(builder.subprocess, "check_output",
                                              return_value="PE32+ executable (DLL)"):
                                builder.compile_only(work)

            self.assertEqual(len(called), 1)
            self.assertEqual(called[0][0], "make")
            self.assertEqual(called[0][2:], builder.crypt32_targets())
            self.assertNotIn("all", called[0])
            self.assertTrue(all("winedmo" not in value for value in called[0]))
            self.assertTrue((work / "candidate/SHA256SUMS").is_file())


    def test_status_verifies_both_staged_dlls_and_manifest_without_writes(self):
        with tempfile.TemporaryDirectory(prefix="gw-crypt32-status-") as temp:
            work = Path(temp)
            output = work / "candidate"
            output.mkdir()
            hashes = {}
            for arch in builder.HISTORIC:
                folder = output / arch
                folder.mkdir()
                binary = folder / "crypt32.dll"
                binary.write_bytes(b"MZ-COMPILED-NOT-PROVEN-" + arch.encode())
                hashes[arch] = builder.sha256(binary)
            (output / "SHA256SUMS").write_text(
                "".join(hashes[arch] + "  " + arch +
                        "/crypt32.dll\n" for arch in builder.HISTORIC))
            output_text = io.StringIO()

            def identify(command, **kwargs):
                if "x86_64-windows" in command[-1]:
                    return "PE32+ executable (DLL) x86-64"
                return "PE32 executable (DLL) Intel 80386"

            with patch.object(builder.shutil, "which", return_value="/usr/bin/file"):
                with patch.object(builder.subprocess, "check_output", side_effect=identify):
                    with patch.object(builder.subprocess, "run") as run:
                        with redirect_stdout(output_text):
                            self.assertEqual(builder.status_candidates(work), 0)
                        run.assert_not_called()
            rendered = output_text.getvalue()
            self.assertIn("SHA256SUMS VERIFIED", rendered)
            self.assertIn("NEW BINARY BUILD", rendered)
            self.assertTrue((output / "SHA256SUMS").is_file())

    def test_status_rejects_missing_dll_and_corrupt_manifest(self):
        with tempfile.TemporaryDirectory(prefix="gw-crypt32-status-missing-") as temp:
            work = Path(temp)
            with redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(builder.status_candidates(work), 2)
            self.assertIn("STATUS: INCOMPLETE", captured.getvalue())
            output = work / "candidate"
            output.mkdir()
            for arch in builder.HISTORIC:
                folder = output / arch
                folder.mkdir()
                (folder / "crypt32.dll").write_bytes(b"MZ-TEST-" + arch.encode())
            (output / "SHA256SUMS").write_text(
                "".join(("f" * 64) + "  " + arch +
                        "/crypt32.dll\n" for arch in builder.HISTORIC))
            with patch.object(builder.shutil, "which", return_value=None):
                with self.assertRaisesRegex(ValueError, "does NOT match SHA256SUMS"):
                    with redirect_stdout(io.StringIO()):
                        builder.status_candidates(work)

    def test_status_option_cannot_run_build_or_request_confirmation(self):
        with patch.object(builder, "status_candidates", return_value=2) as status:
            with patch.object(builder, "compile_only") as compile:
                self.assertEqual(builder.main(["--status"]), 2)
                status.assert_called_once_with(builder.WORK)
                compile.assert_not_called()
                with self.assertRaisesRegex(ValueError, "does not accept --confirm"):
                    builder.main(["--status", "--confirm"])
                compile.assert_not_called()

    def test_fingerprints_and_revision_are_pinned(self):
        self.assertEqual(builder.REV,
            "46b29104e3741fe23bf5e2547196a253aab88c89")
        self.assertEqual(builder.HISTORIC["x86_64-windows"],
            "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775")
        self.assertEqual(builder.HISTORIC["i386-windows"],
            "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da")

if __name__ == "__main__":
    unittest.main()
