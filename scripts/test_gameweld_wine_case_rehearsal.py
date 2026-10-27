#!/usr/bin/env python3
"""Synthetic, no-Wine regression checks for the disposable Wine case rehearsal."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-wine-case-rehearsal.py")
spec = importlib.util.spec_from_file_location("gw_wine_case_rehearsal", SCRIPT)
assert spec and spec.loader
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)


class WineCaseRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-wine-synthetic-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private/gameweld/prepared-wemod"
        self.root.mkdir(parents=True, mode=0o700)
        self.root.chmod(0o700)
        self.game = Path(self.tmp.name) / "steamapps/compatdata/361420/pfx"
        self.game.mkdir(parents=True)
        (self.game / "system.reg").write_bytes(b"DO-NOT-TOUCH")

    def assert_safe(self):
        self.assertEqual((self.game / "system.reg").read_bytes(), b"DO-NOT-TOUCH")
        self.assertEqual(list(self.root.glob(".synthetic-wine-case-*")), [])
        self.assertFalse((self.root / "staging").exists())
        self.assertFalse((self.root / "downloads").exists())

    def fake_wine(self, args, *, env, **kwargs):
        self.assertEqual(args[0:3], ["/synthetic-wine", "cmd", "/c"])
        prefix = Path(env["WINEPREFIX"])
        self.assertTrue(str(prefix).startswith(str(self.root)))
        self.assertNotEqual(prefix, self.game)
        self.assertNotIn("STEAM_COMPAT_DATA_PATH", env)
        self.assertNotIn("LD_PRELOAD", env)
        self.assertEqual(env["WINEDEBUG"], "-all")
        if args[3] == "ver":
            (prefix / "drive_c").mkdir(parents=True)
            return subprocess.CompletedProcess(args, 0, stdout=b"mock-wine", stderr=b"")
        self.assertEqual(args[3], "type")
        target = args[4]
        by_name = {
            r"C:\GWCaseProbe\InstallUtil.exe": "upper_file",
            r"C:\GWCaseProbe\installutil.exe": "lower_file",
            r"C:\GWCaseProbe\INSTALLUTIL.EXE": "upper_file",
            r"C:\GWCaseProbe\CONFIG\machine.config": "upper_dir",
            r"C:\GWCaseProbe\Config\machine.config": "lower_dir",
            r"C:\GWCaseProbe\config\machine.config": "lower_dir",
        }
        self.assertIn(target, by_name)
        return subprocess.CompletedProcess(
            args, 0, stdout=rehearsal.TOKENS[by_name[target]], stderr=b"")

    def test_pure_synthetic_test_and_cleanup(self):
        with patch.dict(os.environ, {"STEAM_COMPAT_DATA_PATH": "/private/game",
                                     "LD_PRELOAD": "/private/custom.so"}):
            result = rehearsal.run_rehearsal(
                self.root, runner=self.fake_wine, wine_exe="/synthetic-wine")
        self.assertIn("MATCHED EXPECTED CASE", result)
        self.assertIn("ONE VARIANT RETURNED", result)
        self.assertIn("Proton or .NET validation", result)
        self.assertIn("STILL BLOCKED", result)
        self.assert_safe()

    def test_both_case_variants_written_as_distinct_synthetic_files(self):
        prefix = self.root / "prefix"
        (prefix / "drive_c").mkdir(parents=True)
        rehearsal.synthetic_files(prefix)
        path = prefix / "drive_c/GWCaseProbe"
        self.assertNotEqual((path / "InstallUtil.exe").read_bytes(),
                            (path / "installutil.exe").read_bytes())
        self.assertNotEqual((path / "CONFIG/machine.config").read_bytes(),
                            (path / "Config/machine.config").read_bytes())
        self.assert_safe()

    def test_timeout_refuses_and_cleans_temporary_prefix(self):
        def timeout(args, *, env, **kwargs):
            raise subprocess.TimeoutExpired(args, 1)
        with self.assertRaisesRegex(rehearsal.WineCaseRefused, "timeout"):
            rehearsal.run_rehearsal(self.root, runner=timeout, wine_exe="/synthetic-wine")
        self.assert_safe()

    def test_case_lookup_disagrees_without_granting_install(self):
        def inverted(args, *, env, **kwargs):
            result = self.fake_wine(args, env=env, **kwargs)
            if args[3] == "type" and args[4].endswith(r"\InstallUtil.exe"):
                result.stdout = rehearsal.TOKENS["lower_file"]
            return result
        result = rehearsal.run_rehearsal(
            self.root, runner=inverted, wine_exe="/synthetic-wine")
        self.assertIn("RESOLVED DIFFERENT VARIANT", result)
        self.assertIn("STILL BLOCKED", result)
        self.assert_safe()

    def test_missing_windows_path_is_unresolved_not_a_false_success(self):
        def missing(args, *, env, **kwargs):
            result = self.fake_wine(args, env=env, **kwargs)
            if args[3] == "type" and args[4].endswith(r"\INSTALLUTIL.EXE"):
                result.returncode = 1
                result.stdout = b"File not found"
            return result
        report = rehearsal.run_rehearsal(
            self.root, runner=missing, wine_exe="/synthetic-wine")
        self.assertIn("Ambiguous mixed-case file: UNRESOLVED", report)
        self.assertIn("STILL BLOCKED", report)
        self.assert_safe()

    def test_order_matrix_with_two_disposable_prefixes_cleans_everything(self):
        out = rehearsal.run_creation_order_matrix(
            self.root, runner=self.fake_wine, wine_exe="/synthetic-wine")
        self.assertIn("Order-dependent lookup groups: 0", out)
        self.assertIn("CASE-COLLIDING ARCHIVES STILL BLOCKED", out)
        self.assertIn("EXACT CASE OK IN BOTH", out)
        self.assertIn("Real archive staging and installation: STILL BLOCKED", out)
        self.assert_safe()

    def test_order_matrix_reports_changing_ambiguous_resolution(self):
        flags = []
        def fake_report(root, *, reverse_creation_order=False, **kwargs):
            flags.append(reverse_creation_order)
            lines = []
            for label, _, expected in rehearsal.WIN_TESTS:
                token = (expected or (
                    "lower_file" if reverse_creation_order else "upper_file"))
                lines.append(f"{label}: {token} — simulated")
            return "\n".join(lines)
        with patch.object(rehearsal, "run_rehearsal", side_effect=fake_report):
            out = rehearsal.run_creation_order_matrix(self.root)
        self.assertEqual(flags, [False, True])
        self.assertIn("Order-dependent lookup groups: 2", out)
        self.assertIn("RUNTIME VERDICT: CASE-AMBIGUOUS PATH RESOLUTION CHANGES", out)
        self.assertIn("ORDER-DEPENDENT", out)
        self.assertIn("Real archive staging and installation: STILL BLOCKED", out)
        self.assert_safe()

    def test_reverse_file_creation_keeps_distinct_synthetic_payloads(self):
        prefix = self.root / "reverse-prefix"
        (prefix / "drive_c").mkdir(parents=True)
        rehearsal.synthetic_files(prefix, reverse_creation_order=True)
        base = prefix / "drive_c/GWCaseProbe"
        self.assertEqual(
            (base / "InstallUtil.exe").read_bytes(),
            rehearsal.TOKENS["upper_file"] + b"\r\n")
        self.assertEqual(
            (base / "installutil.exe").read_bytes(),
            rehearsal.TOKENS["lower_file"] + b"\r\n")
        self.assertEqual(
            (base / "Config/machine.config").read_bytes(),
            rehearsal.TOKENS["lower_dir"] + b"\r\n")
        self.assert_safe()

    def test_rejects_prefix_root_under_game_prefix(self):
        unsafe = self.game / "gameweld/prepared-wemod"
        unsafe.mkdir(parents=True)
        with self.assertRaisesRegex(rehearsal.WineCaseRefused, "unsafe"):
            rehearsal.safe_root(unsafe)
        self.assert_safe()

    def test_no_wine_no_guess_about_proton(self):
        with patch.object(rehearsal.shutil, "which", return_value=None):
            with self.assertRaisesRegex(rehearsal.WineCaseRefused, "System Wine not found"):
                rehearsal.run_rehearsal(self.root)
        self.assert_safe()


if __name__ == "__main__":
    unittest.main()
