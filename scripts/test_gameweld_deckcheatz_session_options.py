#!/usr/bin/env python3
"""Offline tests for ephemeral user Steam option + DeckCheatz command composition."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-session-options.py")
SPEC = importlib.util.spec_from_file_location("gw_deckcheatz_session_options", SOURCE)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class CustomSteamOptionsTests(unittest.TestCase):
    def setUp(self):
        self.command = ["/usr/bin/python3", "/home/test/DeckCheatz/wemod",
                        "/tools/proton", "waitforexitandrun", "/game/DyingLight.exe"]
        self.env = {"SteamAppId": "3008130", "WINEDLLOVERRIDES": "version=n,b"}

    def compose(self, value):
        return mod.compose(value, self.command, self.env)

    def test_empty_is_exact_command_without_steam_writes(self):
        argv, env, status = self.compose("")
        self.assertEqual(argv, self.command)
        self.assertEqual(env, self.env)
        self.assertFalse(status["steam_launch_options_modified"])
        self.assertFalse(status["steam_launch_options_restoration_required"])

    def test_environment_and_game_flags_survive(self):
        argv, env, status = self.compose('PROTON_LOG=1 DXVK_HUD=fps %command% -dx11')
        self.assertEqual(argv, [*self.command, "-dx11"])
        self.assertEqual(env["PROTON_LOG"], "1")
        self.assertEqual(env["DXVK_HUD"], "fps")
        self.assertEqual(env["SteamAppId"], "3008130")
        self.assertEqual(status["environment_keys_applied"], ["PROTON_LOG", "DXVK_HUD"])

    def test_safe_wrappers_kept_in_original_order(self):
        argv, env, report = self.compose(
            'MANGOHUD=1 gamemoderun gamescope -f -W 1920 -- mangohud %command% -vulkan')
        self.assertEqual(argv, ["gamemoderun", "gamescope", "-f", "-W", "1920",
                                "--", "mangohud", *self.command, "-vulkan"])
        self.assertEqual(env["MANGOHUD"], "1")
        self.assertEqual(report["wrapper_argv"],
                         ["gamemoderun", "gamescope", "-f", "-W", "1920", "--", "mangohud"])

    def test_flags_only_without_placeholder(self):
        argv, _, _ = self.compose("-windowed -noborder")
        self.assertEqual(argv[-2:], ["-windowed", "-noborder"])

    def test_bad_or_unhandled_custom_options_block_instead_of_disappearing(self):
        cases = [
            "bash -c 'echo hi' %command%", "gamescope -f %command%",
            "PROTON_LOG=1 %command% && echo hi",
            "MANGOHUD=1 $(touch /tmp/unsafe) %command%",
            "mangohud %command% %command%",
            "WEMOD_LOG=/tmp/other %command%",
            "WINEDLLOVERRIDES=foo %command%",
            "SteamAppId=123 %command%",
            "/home/user/customwrapper %command%",
            "/home/user/wemod %command%",
            "gamescope -f -- %command% /path/to/args",
            "%command% --", "mangohud",
            "PROTON_LOG=1 %command% -x ; exit",
            "DXVK_HUD=fps \0 %command%",
        ]
        for bad in cases:
            with self.subTest(bad=bad):
                with self.assertRaises(mod.OptionBlocked):
                    self.compose(bad)

    def test_unmatched_quote_and_oversize_rejected(self):
        for value in ("'incomplete", "x" * (mod.MAX_OPTION + 1)):
            with self.assertRaises(mod.OptionBlocked):
                self.compose(value)

if __name__ == "__main__":
    unittest.main()
