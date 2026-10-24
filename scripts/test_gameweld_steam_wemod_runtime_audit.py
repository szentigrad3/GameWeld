#!/usr/bin/env python3
"""Synthetic-only /proc and GameWeld log fixtures; never run Steam or Wine."""
from pathlib import Path
import importlib.util
import os
import sys
import tempfile
import unittest

src = Path(__file__).with_name("gameweld-steam-wemod-runtime-audit.py")
spec = importlib.util.spec_from_file_location("gw_runtime_diff", src)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


class RuntimeAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gw-runtime-audit-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / "state"
        self.dir = self.state / "gameweld" / "steam-wemod"
        self.dir.mkdir(parents=True)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.log = self.dir / "2353250-1000-100.log"
        self.log.write_text(
            "GAMEWELD_STEAM_WEMOD_V1: appid=2353250\n"
            "STEAM_LAUNCH_REQUESTED: 2353250\n"
            "GAME_PROCESS_IDENTITY_OBSERVED: 337341\n"
            "WEMOD_LAUNCHER_RUNNING: pid 337399; trainer attach/render remains UNVERIFIED\n"
        )

    def add_process(self, pid, ns, *, gpu=False):
        d = self.proc / str(pid)
        d.mkdir()
        (d / "comm").write_text("WeMod.exe\n" if gpu else "Astrometica.exe\n")
        (d / "environ").write_bytes(
            b"SteamAppId=2353250\0DISPLAY=:0\0"
            b"XAUTHORITY=/run/user/1000/secret-cookie\0"
            b"WINEPREFIX=/mnt/Steam/compatdata/2353250/pfx\0"
            b"MY_SECRET_TOKEN=never-print-this\0"
        )
        (d / "ns").mkdir()
        (d / "ns" / "mnt").symlink_to(ns)
        (d / "exe").symlink_to("/bin/sh")
        return d

    def test_matching_runtime_namespace(self):
        self.add_process(337341, "mnt:[4026531837]")
        self.add_process(337399, "mnt:[4026531837]", gpu=True)
        a = tool.audit("2353250", state_dir=self.state, proc_root=self.proc)
        self.assertTrue(a["same_mount_namespace"])
        self.assertFalse(a["steam_runtime_difference_indicated"])
        self.assertTrue(a["game"]["process_observed"])
        self.assertEqual(a["wemod_launcher"]["task_name"], "WeMod.exe")
        self.assertEqual(a["actions_performed"], "none")
        self.assertNotIn("never-print-this", str(a))
        self.assertNotIn("secret-cookie", str(a))

    def test_separate_container_is_reported_without_claiming_fix(self):
        self.add_process(337341, "mnt:[4026531837]")
        self.add_process(337399, "mnt:[4026532940]", gpu=True)
        result = tool.audit("2353250", state_dir=self.state, proc_root=self.proc)
        self.assertEqual(result["same_mount_namespace"], False)
        self.assertTrue(result["steam_runtime_difference_indicated"])
        self.assertIn("does not by itself", result["interpretation"])

    def test_exited_launcher_is_not_claimed_crashed(self):
        self.add_process(337341, "mnt:[4026531837]")
        result = tool.audit("2353250", state_dir=self.state, proc_root=self.proc)
        self.assertIsNone(result["same_mount_namespace"])
        self.assertEqual(result["wemod_launcher"]["reason"], "process_no_longer_available")
        self.assertFalse(result["steam_runtime_difference_indicated"])

    def test_session_must_match_appid(self):
        self.log.write_text("GAMEWELD_STEAM_WEMOD_V1: appid=5555555\n"
                            "GAME_PROCESS_IDENTITY_OBSERVED: 337341\n")
        self.assertEqual(tool.ids_from_session(self.log, "2353250"), (None, None))

    def test_no_matching_session(self):
        self.log.unlink()
        self.assertEqual(tool.audit("2353250", state_dir=self.state,
                                    proc_root=self.proc)["status"], "NO_SESSION_LOG")

    def test_invalid_appids_are_rejected(self):
        for val in ("", "0", "2353250;rm", "../data", "2353250\n"):
            with self.assertRaises(ValueError):
                tool.latest_log(val, state_dir=self.state)

    def test_registry_and_prefix_untouched(self):
        pfx = self.root / "Steam" / "steamapps" / "compatdata" / "2353250"
        pfx.mkdir(parents=True)
        (pfx / "sentinel").write_text("unchanged")
        self.add_process(337341, "mnt:[4026531837]")
        self.add_process(337399, "mnt:[4026532940]", gpu=True)
        tool.audit("2353250", state_dir=self.state, proc_root=self.proc)
        self.assertEqual((pfx / "sentinel").read_text(), "unchanged")


if __name__ == "__main__":
    unittest.main()
