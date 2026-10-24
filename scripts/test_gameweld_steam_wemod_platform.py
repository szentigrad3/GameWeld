#!/usr/bin/env python3
"""No Steam, Proton, Wine, WeMod, network or game launched in these fixtures."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("gameweld-steam-wemod-platform.py")
spec = importlib.util.spec_from_file_location("gw_pc2_steam_wemod", SCRIPT)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


class SteamOwnedWeModTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="gw-steam-wemod-")
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.steam = self.root / "steam"
        steamapps = self.steam / "steamapps"
        self.install = steamapps / "common" / "ASTROMETICA"
        self.install.mkdir(parents=True)
        (steamapps / "appmanifest_2353250.acf").write_text('"appid" "2353250"')
        self.game = self.install / "Astrometica.exe"
        self.game.write_bytes(b"MZ" + b"\0" * 128)
        self.compat = steamapps / "compatdata" / "2353250"
        (self.compat / "pfx").mkdir(parents=True)
        self.proton = self.steam / "steamapps" / "common" / "Proton" / "proton"
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text("#!/bin/sh\nexit 0\n")
        self.proton.chmod(0o755)
        self.checkout = self.root / "deckcheatz"
        (self.checkout / "src").mkdir(parents=True)
        source = self.checkout / "src" / "wemod.py"
        source.write_text("# upstream launcher fixture\n")
        self.launcher = self.checkout / "wemod"
        self.launcher.symlink_to("src/wemod.py")
        self.wemod = self.checkout / "wemod_data" / "wemod_bin" / "WeMod.exe"
        self.wemod.parent.mkdir(parents=True)
        self.wemod.write_bytes(b"MZ" + b"\0" * 128)
        self.wine = self.proton.parent / "files" / "bin" / "wine"
        self.wineserver = self.proton.parent / "files" / "bin" / "wineserver"
        self.wine.parent.mkdir(parents=True)
        for toolpath in (self.wine, self.wineserver):
            toolpath.write_text("#!/bin/sh\nexit 0\n")
            toolpath.chmod(0o755)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.set_proc_env(889)
        self.set_proc_env(100)
        real_handoff = tool.active_wine_handoff
        patcher = patch.object(tool, "active_wine_handoff",
            side_effect=lambda plan, pid: real_handoff(plan, pid, self.proc))
        patcher.start()
        self.addCleanup(patcher.stop)
        # Offline fixture: no live X server is available in CI.
        display_patcher = patch.object(tool, "_x11_display_accessible",
                                       return_value=True)
        display_patcher.start()
        self.addCleanup(display_patcher.stop)

    def set_proc_env(self, pid, *, wrong_prefix=False):
        task = self.proc / str(pid)
        task.mkdir(exist_ok=True)
        prefix = str(self.compat if not wrong_prefix else self.root / "other-prefix")
        variables = [
            "SteamAppId=2353250",
            "STEAM_COMPAT_DATA_PATH=" + prefix,
            "STEAM_COMPAT_TOOL_PATHS=" + str(self.proton.parent),
            "DISPLAY=:44",
        ]
        (task / "environ").write_bytes("\0".join(variables).encode() + b"\0")

    def prepare(self):
        with patch.object(tool.shutil, "which", return_value="/usr/bin/steam"):
            return tool.preflight("2353250", self.install, self.game, self.compat,
                                  self.proton, self.steam, self.launcher)

    def test_x11_prefers_verified_gui_display_and_cookie_as_pair(self):
        current = {"DISPLAY": ":1", "XAUTHORITY": "/runtime/gui-xauth"}
        live = {"DISPLAY": ":0", "XAUTHORITY": "/runtime/game-xauth"}
        observed = []
        def check(env):
            observed.append((env.get("DISPLAY"), env.get("XAUTHORITY")))
            return (env.get("DISPLAY"), env.get("XAUTHORITY")) == (
                ":1", "/runtime/gui-xauth"
            )
        result, origin = tool.authenticated_x11_environment(
            current, live, probe=check)
        self.assertEqual(origin, "gameweld")
        self.assertEqual(result["DISPLAY"], ":1")
        self.assertEqual(result["XAUTHORITY"], "/runtime/gui-xauth")
        self.assertEqual(observed, [(":1", "/runtime/gui-xauth")])

    def test_x11_falls_back_to_verified_steam_game_pair(self):
        current = {"DISPLAY": ":1", "XAUTHORITY": "/runtime/gui-xauth"}
        live = {"DISPLAY": ":0", "XAUTHORITY": "/runtime/game-xauth"}
        attempts = []
        def check(env):
            pair = (env.get("DISPLAY"), env.get("XAUTHORITY"))
            attempts.append(pair)
            return pair == (":0", "/runtime/game-xauth")
        result, origin = tool.authenticated_x11_environment(
            current, live, probe=check)
        self.assertEqual(origin, "steam-game")
        self.assertEqual(attempts, [
            (":1", "/runtime/gui-xauth"),
            (":0", "/runtime/game-xauth"),
        ])
        self.assertEqual(result["XAUTHORITY"], "/runtime/game-xauth")

    def test_x11_refuses_unauthorized_or_missing_display(self):
        current = {"DISPLAY": ":1", "XAUTHORITY": "/bad/gui"}
        live = {"DISPLAY": ":0", "XAUTHORITY": "/bad/game"}
        with self.assertRaisesRegex(ValueError, "X11 authorization failed"):
            tool.authenticated_x11_environment(
                current, live, probe=lambda env: False)
        with self.assertRaisesRegex(ValueError, "X11 authorization failed"):
            tool.authenticated_x11_environment(
                {}, {}, probe=lambda env: True)

    def test_x11_never_splices_game_display_to_gui_xauthority(self):
        current = {"DISPLAY": ":1", "XAUTHORITY": "/gui"}
        live = {"DISPLAY": ":0"}  # Game has no authorization path.
        seen = []
        def check(env):
            seen.append((env.get("DISPLAY"), env.get("XAUTHORITY")))
            return False
        with self.assertRaises(ValueError):
            tool.authenticated_x11_environment(current, live, probe=check)
        self.assertEqual(seen, [(":1", "/gui"), (":0", None)])
        self.assertFalse(tool._x11_display_accessible(
            {"DISPLAY": "untrusted.example.com:0"}))

    def test_preflight_existing_installed_runtime(self):
        plan = self.prepare()
        self.assertEqual(plan["appid"], "2353250")
        self.assertEqual(plan["wemod_exe"], str(self.wemod.resolve()))
        self.assertEqual(plan["mode"], "STEAM_OWNED_GAME_THEN_SAME_PREFIX_WEMOD")

    def test_missing_runtime_fails_before_steam(self):
        self.wemod.unlink()
        with self.assertRaisesRegex(ValueError, "No previously installed"):
            self.prepare()

    def test_reject_wrong_game_identity(self):
        with patch.object(tool.shutil, "which", return_value="/usr/bin/steam"):
            with self.assertRaisesRegex(ValueError, "matching Steam appmanifest"):
                tool.preflight("12345", self.install, self.game, self.compat,
                               self.proton, self.steam, self.launcher)

    def test_existing_game_does_not_start_second_copy(self):
        plan = self.prepare()
        invocations = []
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        def start(appid):
            invocations.append(("steam", appid))
        def spawn(args, **kwargs):
            invocations.append(("wemod", args, kwargs))
            return SimpleNamespace(pid=890, poll=lambda: None)
        messages = []
        result = tool.launch(plan, observer=Observer(), start_steam=start,
                             spawn=spawn, log=messages.append)
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertFalse(result["trainer_verified"])
        self.assertEqual(len(invocations), 1)
        self.assertEqual(invocations[0][0], "wemod")
        self.assertEqual(invocations[0][1], [str(self.wine), str(self.wemod)])
        self.assertEqual(invocations[0][2]["env"]["WINEPREFIX"],
                         str(self.compat / "pfx"))
        self.assertEqual(invocations[0][2]["env"]["WINESERVER"], str(self.wineserver))
        self.assertEqual(invocations[0][2]["env"]["STEAM_COMPAT_APP_ID"], "2353250")
        self.assertEqual(invocations[0][2]["env"]["STEAM_COMPAT_DATA_PATH"],
                         plan["compatdata"])

    def test_proton_output_is_private_and_captured_without_claiming_attach(self):
        plan = self.prepare()
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        output = self.root / "wemod-session.proton.log"
        invocations = []
        def spawn(args, **kwargs):
            invocations.append(kwargs)
            return SimpleNamespace(pid=890, poll=lambda: None)
        result = tool.launch(
            plan, observer=Observer(),
            start_steam=lambda _appid: self.fail("Duplicate Steam launch"),
            spawn=spawn, log=lambda _msg: None, proton_output=output,
        )
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertFalse(result["trainer_verified"])
        self.assertTrue(output.is_file())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertIsNotNone(invocations[0]["stdout"])
        self.assertEqual(invocations[0]["stderr"], tool.subprocess.STDOUT)

    def test_failed_wemod_exec_retains_private_output_and_fails_closed(self):
        plan = self.prepare()
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        output = self.root / "failed-wemod.proton.log"
        statuses = []
        def spawn(args, **kwargs):
            raise OSError("mock launcher unavailable")
        result = tool.launch(plan, observer=Observer(), spawn=spawn,
                             log=statuses.append, proton_output=output)
        self.assertEqual(result["state"], "WEMOD_START_FAILED")
        self.assertFalse(result["trainer_verified"])
        self.assertTrue(output.is_file())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertTrue(any("WEMOD_START_FAILED" in s for s in statuses))

    def test_wine_exits_with_error_and_never_claims_success(self):
        plan = self.prepare()
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        output = self.root / "failed-start.proton.log"
        events = []
        with patch.object(tool.time, "sleep", return_value=None):
            result = tool.launch(
                plan, observer=Observer(),
                spawn=lambda argv, **kwargs:
                    SimpleNamespace(pid=891, poll=lambda: 12),
                log=events.append, proton_output=output,
            )
        self.assertEqual(result["state"], "WEMOD_STARTUP_EXITED_WITH_ERROR")
        self.assertEqual(result["returncode"], 12)
        self.assertFalse(result["trainer_verified"])
        self.assertTrue(output.exists())
        self.assertTrue(any("WEMOD_STARTUP_EXITED_WITH_ERROR" in e for e in events))

    def test_game_must_appear_before_wemod(self):
        plan = self.prepare()
        calls = []
        class Observer:
            count = 0
            @classmethod
            def matching_game_processes(cls, *args):
                cls.count += 1
                return [100] if cls.count == 2 else []
        def start(appid):
            calls.append(("steam", appid))
        def spawn(args, **kwargs):
            calls.append(("wemod", args))
            return SimpleNamespace(pid=101, poll=lambda: None)
        with patch.object(tool.time, "sleep", return_value=None):
            result = tool.launch(plan, observer=Observer(), start_steam=start,
                                 spawn=spawn, log=lambda msg: None, timeout=3)
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertEqual(calls[0], ("steam", "2353250"))
        self.assertEqual(calls[1][0], "wemod")
        self.assertFalse(result["trainer_verified"])

    def test_active_wine_join_blocks_wrong_live_game_prefix(self):
        plan = self.prepare()
        self.set_proc_env(889, wrong_prefix=True)
        messages = []
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        result = tool.launch(
            plan, observer=Observer(),
            start_steam=lambda _appid: self.fail("Duplicate game launch"),
            spawn=lambda *args, **kwargs: self.fail("Wine must not launch"),
            log=messages.append,
        )
        self.assertEqual(result["state"], "WEMOD_HANDOFF_BLOCKED")
        self.assertFalse(result["trainer_verified"])
        self.assertTrue(any("prefix identity" in item for item in messages))

    def test_active_wine_join_does_not_spawn_second_proton(self):
        plan = self.prepare()
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return [889]
        command = []
        def spawn(argv, **kwargs):
            command.append(argv)
            return SimpleNamespace(pid=890, poll=lambda: None)
        result = tool.launch(plan, observer=Observer(), spawn=spawn,
                             log=lambda _message: None)
        self.assertEqual(result["state"], "WEMOD_PROCESS_REQUESTED")
        self.assertEqual(command[0][0], str(self.wine))
        self.assertNotIn("runinprefix", command[0])
        self.assertEqual(command[0][-1], str(self.wemod))

    def test_no_game_never_starts_trainer(self):
        plan = self.prepare()
        calls = []
        class Observer:
            @staticmethod
            def matching_game_processes(*args):
                return []
        result = tool.launch(plan, observer=Observer(),
                             start_steam=lambda appid: calls.append(("steam", appid)),
                             spawn=lambda *args, **kwargs: self.fail("spawn called"),
                             log=lambda msg: None, timeout=0)
        self.assertEqual(calls, [("steam", "2353250")])
        self.assertEqual(result["state"], "GAME_PROCESS_UNCONFIRMED")
        self.assertFalse(result["trainer_verified"])

    def test_prefix_validation_never_creates_prefix(self):
        (self.compat / "pfx").rmdir()
        with self.assertRaisesRegex(ValueError, "uninitialized game Proton prefix"):
            self.prepare()
        self.assertFalse((self.compat / "pfx").exists())


if __name__ == "__main__":
    unittest.main()
