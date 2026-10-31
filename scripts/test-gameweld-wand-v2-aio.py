#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hermetic Steam library + live Wine process discovery tests for GameWeld."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name: str):
    script = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location("gameweld_test_" + name.replace("-", "_"), script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aio = load("gameweld-wand-v2-aio.py")
steam = load("gameweld-steam-shortcuts.py")
context = load("gameweld-wand-v2-live-context.py")
anchor = load("gameweld-wand-v2-live-anchor.py")
APPID = 3008130
EXE_NAME = "DyingLightGame_TheBeast_x64_rwdi.exe"


class SteamAIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.steam = self.root / "Steam"
        self.apps = self.steam / "steamapps"
        self.apps.mkdir(parents=True)
        self.install = self.apps / "common/Dying Light The Beast"
        self.install.mkdir(parents=True)
        self.exe = self.install / EXE_NAME
        self.exe.write_bytes(b"MZtest")
        self.compat = self.apps / "compatdata" / str(APPID)
        (self.compat / "pfx/drive_c").mkdir(parents=True)
        self.write_manifest()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.env = (f"SteamAppId={APPID}\0STEAM_COMPAT_APP_ID={APPID}\0"
                    f"STEAM_COMPAT_DATA_PATH={self.compat}\0"
                    f"WINEPREFIX={self.compat / 'pfx'}\0").encode()

    def write_manifest(self, name="Dying Light The Beast", appid=APPID):
        (self.apps / f"appmanifest_{APPID}.acf").write_text(
            f'"AppState" {{ "appid" "{appid}" "installdir" "{name}" }}')

    def process(self, pid, comm, loader, argv, env=None, maps=b"/usr/lib/wine/ntdll.so"):
        d = self.proc / str(pid)
        d.mkdir()
        (d / "comm").write_text(comm + "\n")
        (d / "exe").symlink_to("/usr/bin/" + loader)
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        (d / "environ").write_bytes(self.env if env is None else env)
        (d / "maps").write_bytes(maps)
        (d / "stat").write_text(
            f"{pid} ({comm}) S " + " ".join(["1"] * 18 + ["3641164"] + ["1"] * 4))

    def running(self):
        self.process(101, "steam.exe", "wine-preloader", [str(self.exe)])
        self.process(102, "DyingLightGame_", "wine64-preloader", [EXE_NAME])
        self.process(103, "wineserver", "wineserver", ["wineserver"])

    def discover(self):
        return aio.discover(APPID, self.steam, proc_root=self.proc,
                            steam=steam, context=context)

    def run_aio(self):
        return aio.run(APPID, self.steam, proc_root=self.proc,
                       steam=steam, context=context, anchor=anchor,
                       samples=3, interval_ms=0)

    def test_finds_true_game_and_auto_resamples(self):
        self.running()
        r = self.run_aio()
        self.assertEqual(r["state"], "linux_runtime_anchor_stable")
        self.assertEqual(r["candidate_linux_pid"], 102)
        self.assertEqual(r["samples_completed"], 3)
        self.assertEqual(r["game_executable_basename"], EXE_NAME)
        self.assertEqual(r["manifest_install_dirs_found"], 1)
        self.assertTrue(r["unique_linux_game_candidate"])
        self.assertFalse(r["win32_pid_verified"])
        self.assertFalse(r["trainer_attachment_verified"])
        self.assertFalse(r["steam_configuration_written"])
        self.assertNotIn("_game_exe", r)

    def test_missing_manifest_fails_closed(self):
        self.running()
        (self.apps / f"appmanifest_{APPID}.acf").unlink()
        r = self.discover()
        self.assertEqual(r["reason"], "game_manifest_or_compatdata_missing")

    def test_missing_prefix_fails_closed(self):
        self.running()
        (self.compat / "pfx/drive_c").rmdir()
        self.assertEqual(self.discover()["reason"], "game_manifest_or_compatdata_missing")

    def test_wrong_manifest_appid_fails_closed(self):
        self.running()
        self.write_manifest(appid=77)
        self.assertEqual(self.discover()["reason"], "game_manifest_or_compatdata_missing")

    def test_manifest_installdir_path_traversal_rejected(self):
        self.write_manifest(name="../outside")
        self.assertIsNone(aio.manifest_installdir(
            steam, self.apps / f"appmanifest_{APPID}.acf", APPID))

    def test_only_full_exe_path_launcher_matches(self):
        self.process(101, "steam.exe", "wine-preloader", [EXE_NAME])
        self.process(102, "DyingLightGame_", "wine64-preloader", [EXE_NAME])
        self.process(103, "wineserver", "wineserver", ["wineserver"])
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_wrong_prefix_not_selected(self):
        self.running()
        badenv = self.env.replace(str(self.compat / "pfx").encode(), b"/other/prefix")
        (self.proc / "101" / "environ").write_bytes(badenv)
        (self.proc / "102" / "environ").write_bytes(badenv)
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_game_not_running_is_not_falsely_detected(self):
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_no_such_steam_root_blocks(self):
        r = aio.discover(APPID, self.root / "missing", proc_root=self.proc,
                         steam=steam, context=context)
        self.assertEqual(r["reason"], "steam_root_not_found")

    def test_invalid_appid_blocks(self):
        r = aio.discover(0, self.steam, proc_root=self.proc,
                         steam=steam, context=context)
        self.assertEqual(r["reason"], "invalid_steam_appid")

    def test_game_process_without_wine_maps_rejected(self):
        self.running()
        (self.proc / "102" / "maps").write_bytes(b"/lib/libc.so")
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_unrelated_executable_not_selected(self):
        self.running()
        other = self.root / "other"
        other.mkdir()
        f = other / EXE_NAME
        f.write_bytes(b"MZ")
        (self.proc / "101" / "cmdline").write_bytes(str(f).encode() + b"\0")
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_steam_manifest_never_modified(self):
        self.running()
        path = self.apps / f"appmanifest_{APPID}.acf"
        before = path.read_bytes()
        r = self.run_aio()
        self.assertEqual(r["state"], "linux_runtime_anchor_stable")
        self.assertEqual(path.read_bytes(), before)

    def test_non_game_wine_wrapper_does_not_count(self):
        self.process(101, "steam.exe", "wine-preloader", [str(self.exe)])
        self.process(103, "wineserver", "wineserver", ["wineserver"])
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_incomplete_environment_does_not_count(self):
        self.running()
        for pid in ("101", "102"):
            (self.proc / pid / "environ").write_bytes(f"SteamAppId={APPID}\0".encode())
        self.assertEqual(self.discover()["reason"], "no_unique_linux_game_process_identity")

    def test_manifest_parser_existing_steam_helper(self):
        name = aio.manifest_installdir(
            steam, self.apps / f"appmanifest_{APPID}.acf", APPID)
        self.assertEqual(name, "Dying Light The Beast")


if __name__ == "__main__":
    unittest.main()
