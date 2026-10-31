#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic GameWeld Proton process-identity regression tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name("gameweld-wand-v2-live-context.py")
spec = importlib.util.spec_from_file_location("gameweld_live_context", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compat = self.root / "steamapps/compatdata/3008130"
        (self.compat / "pfx/drive_c").mkdir(parents=True)
        self.exe = (self.root / "steamapps/common/Dying Light The Beast"
                    / "DyingLightGame_TheBeast_x64_rwdi.exe")
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b"MZdummy")
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.env = (f"SteamAppId=3008130\0STEAM_COMPAT_APP_ID=3008130\0"
                    f"STEAM_COMPAT_DATA_PATH={self.compat}\0"
                    f"WINEPREFIX={self.compat / 'pfx'}\0").encode()

    def process(self, pid, *, comm="DyingLightGame_", loader="wine64-preloader",
                argv=None, env=None, maps=b"/usr/lib/wine/ntdll.so", start=100):
        d = self.proc / str(pid)
        d.mkdir()
        (d / "comm").write_text(comm + "\n")
        (d / "exe").symlink_to("/usr/bin/" + loader)
        args = [self.exe.name] if argv is None else argv
        (d / "cmdline").write_bytes(b"\0".join(x.encode() for x in args) + b"\0")
        if env is not False:
            (d / "environ").write_bytes(self.env if env is None else env)
        (d / "maps").write_bytes(maps)
        # After field 3 ('S') there are 18 filler fields before field 22.
        (d / "stat").write_text(f"{pid} ({comm}) S "
                                + " ".join(["1"] * 18 + [str(start)] + ["1"] * 4))
        return d

    def inspect(self):
        return module.inspect_context(3008130, self.compat, self.exe, self.proc)

    def test_game_candidate_from_truncated_comm(self):
        self.process(10, comm="reaper", loader="reaper", argv=[str(self.exe)])
        self.process(11, comm="steam.exe", loader="wine-preloader", argv=[str(self.exe)])
        self.process(12, comm="wineserver", loader="wineserver", argv=["wineserver"])
        self.process(13)
        r = self.inspect()
        self.assertEqual(r["candidate_linux_pid"], 13)
        self.assertEqual(r["wrapper_full_exe_pids"], [10, 11])
        self.assertEqual(r["wine_server_pids"], [12])
        self.assertTrue(r["exact_prefix_identity_crosschecked"])
        self.assertFalse(r["game_process_verified"])
        self.assertFalse(r["trainer_attachment_verified"])
        self.assertFalse(r["exact_runtime_verified"])

    def test_wrapper_never_becomes_game(self):
        self.process(10, comm="reaper", loader="reaper", argv=[str(self.exe)])
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_ambiguous_game_processes_are_blocked(self):
        self.process(10)
        self.process(11)
        r = self.inspect()
        self.assertEqual(r["state"], "ambiguous_game_process_candidates")
        self.assertIsNone(r["candidate_linux_pid"])

    def test_different_prefix_rejected(self):
        other = self.root / "other/pfx"
        other.mkdir(parents=True)
        env = (f"SteamAppId=3008130\0STEAM_COMPAT_DATA_PATH={self.compat}\0"
               f"WINEPREFIX={other}\0").encode()
        self.process(10, env=env)
        self.assertFalse(self.inspect()["matching_pids"])

    def test_wrong_appid_rejected(self):
        self.process(10, env=self.env.replace(b"3008130", b"3008131"))
        self.assertFalse(self.inspect()["matching_pids"])

    def test_conflicting_appid_markers_rejected(self):
        self.process(10, env=self.env.replace(b"STEAM_COMPAT_APP_ID=3008130",
                                               b"STEAM_COMPAT_APP_ID=10"))
        self.assertFalse(self.inspect()["matching_pids"])

    def test_unmapped_wine_module_rejected(self):
        self.process(10, maps=b"/usr/lib/libc.so")
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_unreadable_environment_rejected(self):
        self.process(10, env=False)
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_process_name_mismatch_rejected(self):
        self.process(10, comm="steam.exe")
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_game_argv_missing_rejected(self):
        self.process(10, argv=["wrong.exe"])
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_pid_reuse_rejected(self):
        self.process(10)
        original = module.process_start_ticks
        calls = 0
        def changed(proc):
            nonlocal calls
            calls += 1
            return original(proc) if calls == 1 else 999999
        with mock.patch.object(module, "process_start_ticks", side_effect=changed):
            r = self.inspect()
        self.assertEqual(r["pid_reuse_rejections"], 1)
        self.assertIsNone(r["candidate_linux_pid"])

    def test_stat_parser_last_parenthesis(self):
        proc = self.process(10, comm="something) tricky", start=8765)
        self.assertEqual(module.process_start_ticks(proc), 8765)

    def test_missing_wineprefix_marker_is_rejected(self):
        raw = self.env.replace(
            f"WINEPREFIX={self.compat / 'pfx'}".encode(), b""
        )
        self.process(10, env=raw)
        self.assertIsNone(self.inspect()["candidate_linux_pid"])

    def test_no_prefix_or_steam_config_written(self):
        missing = self.root / "steamapps/compatdata/111"
        r = module.inspect_context(111, missing, self.exe, self.proc)
        self.assertEqual(r["reason"], "compatdata_not_ready_or_appid_mismatch")
        self.assertFalse(missing.exists())
        self.process(10)
        r = self.inspect()
        self.assertFalse(r["steam_launch_options_changed"])
        self.assertFalse(r["game_prefix_modified"])
        self.assertFalse(r["monitor_attached"])


if __name__ == "__main__":
    unittest.main()
