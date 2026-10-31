#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""No Wine, Steam or trainer launches: synthetic same-prefix residue evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    p = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location("gameweld_" + name.replace("-", "_"), p)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load("gameweld-wand-v2-residue-audit.py")
context = load("gameweld-wand-v2-live-context.py")


class ResidueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.compat = self.root / "compatdata/3008130"
        (self.compat / "pfx/drive_c").mkdir(parents=True)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.env = (f"WINEPREFIX={self.compat / 'pfx'}\0"
                    "SteamAppId=3008130\0").encode()

    def process(self, pid=12, name="WeMod.exe", comm=None, loader="wine64-preloader",
                environ=None, maps=b"/usr/lib/wine/ntdll.dll", argv=None, ticks=123456):
        d = self.proc / str(pid)
        d.mkdir()
        (d / "comm").write_text((name if comm is None else comm) + "\n")
        (d / "exe").symlink_to("/usr/bin/" + loader)
        if argv is None:
            argv = [name]
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        (d / "environ").write_bytes(self.env if environ is None else environ)
        (d / "maps").write_bytes(maps)
        (d / "stat").write_text(
            f"{pid} ({name}) S " + " ".join(["1"] * 18 + [str(ticks)] + ["1"] * 4))
        return d

    def inspect(self):
        return audit.report_possible_residue(
            3008130, self.compat, proc_root=self.proc, context=context)

    def test_same_prefix_wemod_candidate(self):
        self.process()
        r = self.inspect()
        self.assertEqual(r["same_prefix_provider_candidate_count"], 1)
        self.assertEqual(r["same_prefix_provider_candidates"][0]["linux_pid"], 12)
        self.assertFalse(r["provider_process_ownership_verified"])
        self.assertFalse(r["trainer_cleanup_verified"])
        self.assertEqual(r["processes_signalled"], 0)

    def test_no_provider_is_not_verified_cleanup(self):
        self.process(name="DyingLightGame_TheBeast_x64_rwdi.exe", comm="DyingLightGame_",
                     argv=["DyingLightGame_TheBeast_x64_rwdi.exe"])
        r = self.inspect()
        self.assertEqual(r["same_prefix_provider_candidate_count"], 0)
        self.assertFalse(r["trainer_cleanup_verified"])

    def test_wand_candidate(self):
        self.process(name="Wand.exe")
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 1)

    def test_provider_without_steam_appid_still_correlation_only(self):
        self.process(environ=f"WINEPREFIX={self.compat / 'pfx'}\0".encode())
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 1)
        self.assertFalse(self.inspect()["provider_process_ownership_verified"])

    def test_unrelated_appid_rejected(self):
        self.process(environ=(f"WINEPREFIX={self.compat / 'pfx'}\0"
                              "SteamAppId=42\0").encode())
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_wrong_prefix_rejected(self):
        wrong = self.root / "other/pfx"
        wrong.mkdir(parents=True)
        self.process(environ=f"WINEPREFIX={wrong}\0".encode())
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_missing_prefix_marker_rejected(self):
        self.process(environ=b"SteamAppId=3008130\0")
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_steam_helper_not_misidentified(self):
        self.process(name="steam.exe", argv=["WeMod.exe"])
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_nonwine_loader_rejected(self):
        self.process(loader="python3")
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_unmapped_wine_rejected(self):
        self.process(maps=b"/usr/lib/libc.so")
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_wrong_exe_arguments_rejected(self):
        self.process(argv=["wineserver"])
        self.assertEqual(self.inspect()["same_prefix_provider_candidate_count"], 0)

    def test_prefix_missing_fails_closed(self):
        (self.compat / "pfx/drive_c").rmdir()
        r = self.inspect()
        self.assertEqual(r["state"], "residue_audit_unavailable")

    def test_no_proc_directory_fails_closed(self):
        self.proc.rmdir()
        r = self.inspect()
        self.assertEqual(r["reason"], "proc_directory_unavailable")

    def test_invalid_appid_fails_closed(self):
        r = audit.report_possible_residue(0, self.compat, proc_root=self.proc, context=context)
        self.assertEqual(r["reason"], "invalid_appid_or_compatdata")

    def test_two_provider_candidates_are_not_owned_by_assumption(self):
        self.process(12)
        self.process(13, name="Wand.exe")
        r = self.inspect()
        self.assertEqual(r["same_prefix_provider_candidate_count"], 2)
        self.assertFalse(r["provider_process_ownership_verified"])
        self.assertFalse(r["trainer_cleanup_verified"])

    def test_start_ticks_change_is_rejected(self):
        self.process()
        real = context.process_start_ticks
        count = 0
        def changed(proc):
            nonlocal count
            count += 1
            return real(proc) if count == 1 else 56789
        with patch.object(context, "process_start_ticks", side_effect=changed):
            r = self.inspect()
        self.assertEqual(r["same_prefix_provider_candidate_count"], 0)

    def test_no_profile_or_steam_modifications(self):
        self.process()
        before = sorted(self.root.rglob("*"))
        r = self.inspect()
        after = sorted(self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse(r["steam_launch_options_changed"])
        self.assertFalse(r["game_prefix_modified"])
        self.assertEqual(r["processes_signalled"], 0)


if __name__ == "__main__":
    unittest.main()
