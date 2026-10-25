#!/usr/bin/env python3
"""Offline tests for Steam Proton runtime context discovery."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("gameweld-wemod-runtime-audit.py")
spec = importlib.util.spec_from_file_location("gameweld_wemod_runtime_audit", SCRIPT)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class WeModRuntimeAuditTests(unittest.TestCase):
    def test_runtime_requirement_handles_comments(self):
        sample = ('// "require_tool_appid" "1234"\n'
                  '"tool" { "require_tool_appid" "4183110" }\n')
        self.assertEqual(audit.parse_required_runtime(sample), "4183110")
        self.assertIsNone(audit.parse_required_runtime('// "require_tool_appid" "4183110"'))

    def test_service_probe_only_queries_name_has_owner(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        with patch.object(audit.shutil, "which", return_value="/usr/bin/gdbus"):
            with patch.object(audit.subprocess, "run", return_value=CompletedProcess(
                ["gdbus"], 0, stdout="(true,)\n", stderr="")) as probe:
                self.assertTrue(audit.game_launcher_service_owned("2353250"))
                args = probe.call_args.args[0]
                self.assertEqual(args[-1], "com.steampowered.App2353250")
                self.assertIn("org.freedesktop.DBus.NameHasOwner", args)
            with patch.object(audit.subprocess, "run", return_value=CompletedProcess(
                ["gdbus"], 0, stdout="(false,)\n", stderr="")):
                self.assertFalse(audit.game_launcher_service_owned("2353250"))
        with patch.object(audit.shutil, "which", return_value=None):
            self.assertIsNone(audit.game_launcher_service_owned("2353250"))
        with self.assertRaises(ValueError):
            audit.game_launcher_service_owned("2353250;sh")

    def test_reports_runtime_entry_point_without_starting_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proton = root / "steamapps/common/Proton - Experimental/proton"
            proton.parent.mkdir(parents=True)
            proton.write_text("#!/bin/sh\nexit 0\n")
            (proton.parent / "toolmanifest.vdf").write_text('"require_tool_appid" "4183110"')
            entry = root / "steamapps/common/SteamLinuxRuntime_4/_v2-entry-point"
            entry.parent.mkdir(parents=True)
            entry.write_text("fixture")
            proc = root / "proc"
            (proc / "701/ns").mkdir(parents=True)
            (proc / "self/ns").mkdir(parents=True)
            (proc / "701/ns/mnt").symlink_to("mnt:[100]")
            (proc / "self/ns/mnt").symlink_to("mnt:[200]")
            report = audit.audit({
                "proton": str(proton),
                "steamroot": str(root),
                "game_pid": 701,
            }, proc=proc)
            self.assertIn("Required Steam runtime AppID: 4183110", report)
            self.assertIn("Runtime entry point exists: True", report)
            self.assertIn("Mount namespaces differ: True", report)
            self.assertIn("Existing game launcher service: UNVERIFIED", report)


if __name__ == "__main__":
    unittest.main()
