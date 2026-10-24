#!/usr/bin/env python3
"""PC2 Test22: synthetic-only safety and SHA256 fixture regression tests.

CI never calls real Proton, Wine, Steam, Wand or a real game.
"""
from __future__ import annotations
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import sys

SCRIPT = Path(__file__).with_name("pc2-crypt32-validation.py")
spec = importlib.util.spec_from_file_location("gameweld_pc2_test22", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class Crypt32CertificateValidationFixtures(unittest.TestCase):
    def test_offline_certificate_der_digest_is_independent(self):
        size, hashes = mod.check_fixture()
        self.assertGreater(size, 300)
        self.assertEqual(hashes["expected_sha256"],
                         "3bf3473eeac9e2dac73cc1a66982ea799389c72a5951c7d5870d89cc030e957e")
        self.assertEqual(hashes["expected_sha1"],
                         "d492b75fdb0fa2f9a1f7abe933527451b5b598e1")

    def test_status_and_probe_compilation_never_run_without_optin(self):
        with patch.object(mod, "audit", return_value=0) as audit:
            with patch.object(mod, "compile_probes") as compile:
                with patch.object(mod, "runtime_probes") as runtime:
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(mod.main([]), 0)
                    audit.assert_called_once()
                    with self.assertRaisesRegex(mod.ValidationBlocked, "--confirm"):
                        mod.main(["--compile-probes"])
                    with self.assertRaisesRegex(mod.ValidationBlocked, "--confirm"):
                        mod.main(["--runtime-probes"])
                    compile.assert_not_called()
                    runtime.assert_not_called()

    def test_compile_probes_writes_only_under_disposable_directory(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-build-") as temp:
            root = Path(temp)
            with patch.object(mod, "TESTROOT", root):
                with patch.object(mod, "audit", return_value=0):
                    with patch.object(mod.shutil, "which", return_value="/usr/bin/fake"):
                        calls = []

                        def fake_cc(command, **kwargs):
                            calls.append(command)
                            dest = Path(command[command.index("-o")+1])
                            dest.write_bytes(b"MZ" + b"probe" * 350)
                            return SimpleNamespace(returncode=0, stderr="")

                        with patch.object(mod.subprocess, "run", side_effect=fake_cc):
                            with redirect_stdout(io.StringIO()):
                                self.assertEqual(mod.main(["--compile-probes", "--confirm"]), 0)
                self.assertEqual(len(calls), 2)
                for arch in mod.ARCHS:
                    self.assertTrue(mod.probe_path(arch).is_file())
                self.assertTrue(all("-lcrypt32" in c for c in calls))
                with self.assertRaisesRegex(mod.ValidationBlocked, "output folder exists"):
                    with patch.object(mod, "audit", return_value=0):
                        mod.compile_probes()

    def test_prefix_link_is_renamed_not_followed_or_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-sandbox-") as temp:
            root = Path(temp)
            pfx = root / "data/pfx"
            system = pfx / "drive_c/windows/system32"
            system.mkdir(parents=True)
            original = root / "outside-real-original.dll"
            original.write_bytes(b"DO NOT MODIFY")
            target = system / "crypt32.dll"
            target.symlink_to(original)
            candidate = root / "candidate-64.dll"
            candidate.write_bytes(b"MZ-TEST-CANDIDATE")
            copy = mod._safe_replace_prefix_dll(pfx, "x86_64-windows", candidate)
            self.assertEqual(copy.read_bytes(), b"MZ-TEST-CANDIDATE")
            self.assertEqual(original.read_bytes(), b"DO NOT MODIFY")
            self.assertTrue((system / "crypt32.gameweld-original.dll").is_symlink())

    def test_non_local_prefix_directory_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-escape-") as temp:
            root = Path(temp)
            pfx = root / "data/pfx"
            folder = pfx / "drive_c/windows"
            folder.mkdir(parents=True)
            outside = root / "actual-other-prefix"
            outside.mkdir()
            (folder / "system32").symlink_to(outside, target_is_directory=True)
            candidate = root / "candidate"
            candidate.write_bytes(b"MZ")
            with self.assertRaisesRegex(mod.ValidationBlocked, "outside sandbox"):
                mod._safe_replace_prefix_dll(pfx, "x86_64-windows", candidate)
            self.assertEqual(list(outside.iterdir()), [])



    def test_direct_wine_runner_does_not_invoke_steam_game_shim_for_probes(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-launchverb-") as temp:
            root = Path(temp)
            proton = root / "proton"
            exe = root / "probe.exe"
            steam = root / "Steam"
            steam.mkdir()
            exe.write_bytes(b"MZ-probe")
            proton.write_text("#!/bin/sh\nexit 0\n")
            proton.chmod(0o755)
            logfile = root / "run.log"
            invoked = []

            def fake_subprocess(command, *, env, text, stdout, stderr, timeout, check):
                invoked.append((command, env.copy()))
                return SimpleNamespace(returncode=0, stdout="GW_PROBE_STARTED\n")

            with patch.object(mod.subprocess, "run", side_effect=fake_subprocess):
                with redirect_stdout(io.StringIO()):
                    rc, output = mod.run_proton(proton, exe, root / "scratch", steam,
                                                {"WINEDLLOVERRIDES": "crypt32=n"}, logfile)
            self.assertEqual(rc, 0)
            self.assertEqual(output, "GW_PROBE_STARTED\n")
            self.assertEqual(invoked[0][0], [str(proton), "runinprefix", str(exe)])
            self.assertEqual(invoked[0][1]["WINEDLLOVERRIDES"], "crypt32=n")
            self.assertEqual(invoked[0][1]["STEAM_COMPAT_DATA_PATH"], str(root / "scratch"))
            self.assertNotIn("waitforexitandrun", invoked[0][0])
            self.assertEqual(logfile.read_text(), "GW_PROBE_STARTED\n")

            with patch.object(mod.subprocess, "run", side_effect=fake_subprocess):
                mod.run_proton(proton, exe, root / "scratch", steam, {}, logfile, verb="run")
            self.assertEqual(invoked[1][0][1], "run")

            with self.assertRaisesRegex(mod.ValidationBlocked, "Unsupported Proton invocation"):
                mod.run_proton(proton, exe, root / "scratch", steam, {}, logfile, verb="waitforexitandrun")


    def test_crypt32_error_extraction_not_swamped_by_module_traces(self):
        huge_trace = "".join(
            f"000c:trace:module:MODULE_InitDLL ({i:016x},PROCESS_DETACH) - RETURN 1\n"
            for i in range(3000))
        raw = (
            "GW_CRYPT32_MODULE=C:\\windows\\system32\\crypt32.dll\n"
            "err:module:import_dll Library msvcrt.dll not found (0xc0000135)\n"
            "trace:loaddll:build_module Loaded L\"C:\\windows\\system32\\crypt32.dll\": native\n"
            + huge_trace
        )
        lines = mod.summarize_runtime_log(raw, name="x86_64.log")
        text = "\n".join(lines)
        self.assertIn("GW_CRYPT32_MODULE=", text)
        self.assertIn("msvcrt.dll not found", text)
        self.assertIn("crypt32.dll", text)
        self.assertNotIn("3000:trace:module:MODULE_InitDLL", text)
        self.assertIn("PROBE MAIN REACHED; API NOT PASSING", text)

    def test_all_probe_stdout_preserved_when_traces_exceed_old_tail_limit(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-marker-retention-") as temp:
            root = Path(temp)
            proton = root / "proton"
            proton.write_text("#!/bin/sh\n")
            proton.chmod(0o755)
            probe = root / "probe.exe"
            probe.write_bytes(b"MZ")
            steam = root / "Steam"
            steam.mkdir()
            out = root / "output.log"
            raw = "GW_CRYPT32_MODULE=C:\\windows\\system32\\crypt32.dll\n" + \
                  ("00a8:trace:module:MODULE_InitDLL\n" * 9500)
            self.assertGreater(len(raw), 250000)

            def fake_proc(command, **kwargs):
                return SimpleNamespace(returncode=53, stdout=raw)

            with patch.object(mod.subprocess, "run", side_effect=fake_proc):
                rc, stdout = mod.run_proton(
                    proton, probe, root / "scratch", steam, {}, out)
            self.assertEqual(rc, 53)
            self.assertEqual(stdout, raw)
            self.assertEqual(out.read_text(), raw)
            self.assertIn("GW_CRYPT32_MODULE=", "\n".join(
                mod.summarize_runtime_log(stdout, name="x86_64.log")))

    def test_runtime_log_diagnostics_reports_existing_exit_without_launching(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-diagnose-") as temp:
            root = Path(temp)
            older = root / "runtime/isolated-aaaaaaaaaaaa"
            newer = root / "runtime/isolated-bbbbbbbbbbbb"
            for session in (older, newer):
                session.mkdir(parents=True)
                (session / "bootstrap.log").write_text("prefix bootstrap ok\n")
                (session / "x86_64.log").write_text("err:module:load_dll c0000135\n")
                (session / "i386.log").write_text("wine: process exited 53\n")
                (session / "report.txt").write_text("RESULT: BLOCKED\n")
            # stable explicit mtime ordering for the selected session
            import os
            os.utime(older, (100, 100))
            os.utime(newer, (200, 200))
            with patch.object(mod, "TESTROOT", root):
                with patch.object(mod.subprocess, "run") as runner:
                    with redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(mod.main(["--diagnose-runtime"]), 0)
                    runner.assert_not_called()
                    self.assertIn(str(newer), output.getvalue())
                    self.assertIn("c0000135", output.getvalue())
                    self.assertIn("RESULT: BLOCKED", output.getvalue())
                    with self.assertRaisesRegex(mod.ValidationBlocked, "read-only"):
                        mod.main(["--diagnose-runtime", "--confirm"])

    def test_runtime_log_diagnostics_refuses_symlinked_session(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-loglink-") as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "x86_64.log").write_text("private data\n")
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "isolated-cccccccccccc").symlink_to(outside, target_is_directory=True)
            with patch.object(mod, "TESTROOT", root):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(mod.diagnose_runtime_logs(), 2)
                self.assertIn("No previous Test22 disposable runtime session", output.getvalue())


    def test_baseline_failure_prevents_candidate_prefix_modification(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-control-fail-") as temp:
            root = Path(temp)
            dllroot = root / "candidates"
            destroot = root / "validation"
            proton = root / "GE-Proton-Wand-SHA256/proton"
            proton.parent.mkdir()
            proton.write_text("#!/bin/sh\nexit 0\n")
            proton.chmod(0o755)
            for arch in mod.ARCHS:
                dll = dllroot / "candidate" / arch / "crypt32.dll"
                dll.parent.mkdir(parents=True)
                dll.write_bytes(b"MZ-CANDIDATE-" + arch.encode())
                exe = destroot / "probes" / (mod.ARCHS[arch][2] + "-crypt32-property.exe")
                exe.parent.mkdir(parents=True, exist_ok=True)
                exe.write_bytes(b"MZ-PROBE-" + arch.encode())
            steam = root / "Steam"
            steam.mkdir()
            invoked = []

            def fail_control(proton_path, exe, session, steam_root, env, log, *, verb="runinprefix"):
                invoked.append((env["WINEDLLOVERRIDES"], verb))
                sandbox = session / "pfx/drive_c/windows"
                for archdir in ("system32", "syswow64"):
                    (sandbox / archdir).mkdir(parents=True, exist_ok=True)
                output = "err:module:import_dll Library crypt32.dll not found (STATUS_DLL_NOT_FOUND)\n"
                log.write_text(output)
                return 53, output

            with patch.object(mod, "TESTROOT", destroot):
                with patch.object(mod, "BUILD", dllroot):
                    with patch.object(mod, "audit", return_value=0):
                        with patch.object(mod, "find_steam", return_value=steam):
                            with patch.object(mod, "run_proton", side_effect=fail_control):
                                with redirect_stdout(io.StringIO()) as output:
                                    with self.assertRaisesRegex(mod.ValidationBlocked, "no candidate DLLs copied"):
                                        mod.runtime_probes(proton)
            self.assertEqual(invoked, [
                ("crypt32=b", "run"),
                ("crypt32=b", "runinprefix"),
                ("crypt32=b", "runinprefix"),
            ])
            for session in (destroot / "runtime").iterdir():
                self.assertFalse((session / "pfx/drive_c/windows/system32/crypt32.gameweld-original.dll").exists())
                self.assertFalse((session / "pfx/drive_c/windows/system32/crypt32.dll").exists())
            self.assertIn("err:module", output.getvalue())
            for arch in mod.ARCHS:
                self.assertEqual((dllroot / "candidate" / arch / "crypt32.dll").read_bytes(),
                                 b"MZ-CANDIDATE-" + arch.encode())

    def test_loader_failure_summary_identifies_missing_module(self):
        output = io.StringIO()
        with redirect_stdout(output):
            mod.print_loader_failures(
                "trace:module:load something\n"
                "err:module:import_dll Library crypt32.dll not found (0xc0000135)\n")
        self.assertIn("crypt32.dll not found", output.getvalue())
        self.assertIn("no GW_CRYPT32_MODULE", output.getvalue())

    def test_runtime_requires_probes_and_never_touches_game_prefix(self):
        with tempfile.TemporaryDirectory(prefix="gw-test22-live-") as temp:
            root = Path(temp)
            candidate_dir = root / "build"
            validation = root / "validation"
            original_proton = root / "GE-Proton-Wand-SHA256/proton"
            original_proton.parent.mkdir()
            original_proton.write_text("#!/bin/sh\nexit 0\n")
            original_proton.chmod(0o755)
            for arch in mod.ARCHS:
                dll = candidate_dir / "candidate" / arch / "crypt32.dll"
                dll.parent.mkdir(parents=True)
                dll.write_bytes(b"MZ" + arch.encode())
                exe = validation / "probes" / (mod.ARCHS[arch][2]+"-crypt32-property.exe")
                exe.parent.mkdir(parents=True, exist_ok=True)
                exe.write_bytes(b"MZ-test-probe-" + arch.encode())
            steam = root / "Steam"
            steam.mkdir()
            calls = []

            def simulated_runner(proton, exe, session, steam_root, overrides, logfile, *, verb="runinprefix"):
                calls.append((exe.name, overrides["WINEDLLOVERRIDES"], verb))
                pfx = session / "pfx"
                for part in ("system32", "syswow64"):
                    dest = pfx / "drive_c/windows" / part
                    dest.mkdir(parents=True, exist_ok=True)
                windows_dir = ("syswow64" if "i386" in exe.name
                               else "system32")
                markers = ("\nGW_CRYPT32_MODULE=C:\\windows\\" + windows_dir +
                           "\\crypt32.dll\nGW_SHA256_OK\nGW_SHA1_OK\nGW_SHA256_AFTER_SET_OK\n"
                           "GW_CRYPT32_CERT_SHA256_RESULT=PASS\n")
                logfile.write_text(markers)
                return 0, markers

            with patch.object(mod, "TESTROOT", validation):
                with patch.object(mod, "BUILD", candidate_dir):
                    with patch.object(mod, "audit", return_value=0):
                        with patch.object(mod, "find_steam", return_value=steam):
                            with patch.object(mod, "run_proton", side_effect=simulated_runner):
                                with redirect_stdout(io.StringIO()) as output:
                                    self.assertEqual(mod.runtime_probes(original_proton), 0)
            self.assertEqual(len(calls), 5)  # bootstrap, builtin baseline x2, candidate x2
            self.assertEqual(calls[0][1], "crypt32=b")
            self.assertEqual([c[1] for c in calls[1:]],
                             ["crypt32=b", "crypt32=b", "crypt32=n", "crypt32=n"])
            self.assertEqual([c[2] for c in calls],
                             ["run", "runinprefix", "runinprefix", "runinprefix", "runinprefix"])
            self.assertTrue((validation / "runtime").is_dir())
            self.assertIn("API FUNCTIONAL PASS", output.getvalue())
            for arch in mod.ARCHS:
                self.assertEqual((candidate_dir / "candidate" / arch / "crypt32.dll")
                                 .read_bytes(), b"MZ" + arch.encode())
            self.assertEqual(original_proton.read_text(), "#!/bin/sh\nexit 0\n")


if __name__ == "__main__":
    unittest.main()
