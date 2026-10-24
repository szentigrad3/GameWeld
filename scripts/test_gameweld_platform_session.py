#!/usr/bin/env python3
"""Isolated /proc fixtures, no Steam/Proton/game launch or system mutation."""
import importlib.util
from pathlib import Path
import os
import sys
import tempfile
import unittest

p = Path(__file__).with_name("gameweld-platform-session.py")
spec = importlib.util.spec_from_file_location("gameweld_platform_session", p)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class PlatformSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-proc-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.game = self.root / "Steam" / "steamapps" / "common" / "ASTROMETICA"
        self.game.mkdir(parents=True)
        self.exe = self.game / "Astrometica.exe"
        self.exe.write_bytes(b"MZ" + b"\0" * 120)
        self.compat = self.root / "Steam" / "steamapps" / "compatdata" / "2353250"
        self.compat.mkdir(parents=True)

    def proc_entry(self, pid=123, *, name="Astrometica.exe", appid="2353250",
                   prefix=None, cmdline=None):
        directory = self.proc / str(pid)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "comm").write_text(name + "\n")
        data = [
            ("SteamAppId=" + appid).encode(),
            ("STEAM_COMPAT_DATA_PATH=" + str(prefix or self.compat.resolve())).encode(),
        ]
        (directory / "environ").write_bytes(b"\0".join(data) + b"\0")
        (directory / "cmdline").write_bytes((cmdline or name).encode() + b"\0")
        return directory

    def test_exact_game_process_identity_only(self):
        self.proc_entry()
        report = module.observe("2353250", self.exe, self.compat, self.proc)
        self.assertEqual(report["state"], "GAME_PROCESS_IDENTITY_OBSERVED")
        self.assertEqual(report["game_process_pids"], [123])
        self.assertFalse(report["trainer_attached_verified"])
        self.assertFalse(report["steam_supervisor_verified"])

    def test_proton_wrapper_is_not_game_process(self):
        self.proc_entry(name="proton")
        self.assertEqual(module.observe("2353250", self.exe, self.compat, self.proc)
                         ["game_process_pids"], [])

    def test_exact_wineprefix_is_accepted_when_proton_child_lacks_compatdata_env(self):
        self.proc_entry()
        envfile = self.proc / "123" / "environ"
        envfile.write_bytes(
            b"SteamAppId=2353250\0WINEPREFIX=" +
            str((self.compat / "pfx").resolve()).encode() + b"\0"
        )
        report = module.observe("2353250", self.exe, self.compat, self.proc)
        self.assertEqual(report["game_process_pids"], [123])
        self.assertFalse(report["trainer_attached_verified"])

    def test_wrong_wineprefix_is_not_accepted(self):
        self.proc_entry()
        other = self.root / "Steam" / "steamapps" / "compatdata" / "888888" / "pfx"
        other.mkdir(parents=True)
        (self.proc / "123" / "environ").write_bytes(
            b"SteamAppId=2353250\0WINEPREFIX=" + str(other).encode() + b"\0"
        )
        self.assertEqual(module.observe("2353250", self.exe, self.compat, self.proc)
                         ["game_process_pids"], [])

    def test_different_appid_is_ignored(self):
        self.proc_entry(appid="999999")
        self.assertFalse(module.observe("2353250", self.exe, self.compat, self.proc)
                         ["game_process_pids"])

    def test_different_compatdata_is_ignored(self):
        other = self.root / "Steam" / "steamapps" / "compatdata" / "888888"
        other.mkdir()
        self.proc_entry(prefix=other)
        self.assertFalse(module.observe("2353250", self.exe, self.compat, self.proc)
                         ["game_process_pids"])

    def test_long_name_requires_complete_command_line(self):
        exe = self.game / "AnUnusuallyLongGameName.exe"
        exe.write_bytes(b"MZ" + b"\0" * 120)
        self.proc_entry(name=exe.name[:15], cmdline="wine-wrapper")
        self.assertFalse(module.observe("2353250", exe, self.compat, self.proc)
                         ["game_process_pids"])
        (self.proc / "123" / "cmdline").write_bytes(exe.name.encode() + b"\0")
        self.assertEqual(module.observe("2353250", exe, self.compat, self.proc)
                         ["game_process_pids"], [123])

    def test_no_matching_game_never_claims_trainer(self):
        self.proc_entry(name="WeMod.exe")
        report = module.observe("2353250", self.exe, self.compat, self.proc)
        self.assertEqual(report["state"], "UNCONFIRMED")
        self.assertFalse(report["trainer_attached_verified"])

    def test_bad_appid_or_prefix_rejected(self):
        self.proc_entry()
        for appid in ("", "0", "2353250;cmd", "x"):
            self.assertFalse(module.observe(appid, self.exe, self.compat, self.proc)
                             ["game_process_pids"])
        wrong = self.root / "custom-prefix"
        wrong.mkdir()
        self.assertFalse(module.observe("2353250", self.exe, wrong, self.proc)
                         ["game_process_pids"])

    def test_no_environment_dump_leaked(self):
        self.proc_entry()
        report = module.observe("2353250", self.exe, self.compat, self.proc)
        self.assertNotIn("environ", str(report))
        self.assertTrue(report["read_only"])


if __name__ == "__main__":
    unittest.main()
