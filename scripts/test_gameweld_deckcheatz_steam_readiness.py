#!/usr/bin/env python3
"""No-launch regression tests for per-game saved Steam wrapper recognition."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-steam-readiness.py")
spec = importlib.util.spec_from_file_location("gw_saved_steam_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SavedSteamReadinessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.launcher = root / "DeckCheatz" / "wemod"
        self.launcher.parent.mkdir()
        self.launcher.write_bytes(b"example")
        self.shim = root / "GameWeld" / "shim.py"
        self.shim.parent.mkdir()
        self.shim.write_bytes(b"example")
        self.appid = "3008130"

    def check(self, text):
        return module.classify_saved_option(text, self.launcher, self.shim, self.appid)

    def test_detects_existing_deckcheatz_wrapper_and_preserves_custom_options(self):
        for string in (
            f"{self.launcher} %command%",
            f'PROTON_LOG=1 MANGOHUD=1 {self.launcher} %command% -vulkan',
        ):
            report = self.check(string)
            self.assertEqual(report["state"], "direct_wrapper_configured")
            self.assertFalse(report["steam_options_modified"])
            self.assertFalse(report["live_client_options_verified"])

    def test_detects_one_shot_shim_and_exact_appid(self):
        options = f"/usr/bin/python3 {self.shim} run --appid {self.appid} -- %command%"
        self.assertEqual(self.check(options)["state"], "one_shot_shim_configured")
        self.assertEqual(self.check(options.replace(self.appid, "999999"))["state"],
                         "needs_setup")

    def test_other_wrappers_and_unsafe_or_ambiguous_options_do_not_authorize(self):
        options = ("", "mangohud %command%", "PROTON_LOG=1 %command%",
                   f"{self.launcher} %command% %command%",
                   f"{self.launcher} %command%",
                   f"{self.launcher} \"%command%")
        # The configured case deliberately uses a real path. An ambiguous
        # shell expression with additional commands does not mean safe to
        # *edit* the user's Steam settings; no such edit exists here.
        for option in options[:4] + options[5:]:
            with self.subTest(option=option):
                self.assertEqual(self.check(option)["state"], "needs_setup")

    def test_spoofed_path_or_missing_binary_is_not_a_valid_saved_wrapper(self):
        shadow = self.launcher.with_name("other-wemod")
        shadow.write_bytes(b"example")
        self.assertEqual(self.check(f"{shadow} %command%")["state"], "needs_setup")
        self.launcher.unlink()
        self.assertEqual(self.check(f"{self.launcher} %command%")["state"], "needs_setup")

    def test_old_gameweld_bridge_selection_is_incompatible_with_deckcheatz(self):
        """Do not allow nested legacy bridge -> DeckCheatz -> Proton launch."""
        from types import SimpleNamespace
        class Bridge:
            @staticmethod
            def steam_compat_selection(_appid, *, steam_roots=None):
                return "GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
        class Options:
            @staticmethod
            def find_config(_appid, _root, _account):
                return self.launcher, "123"
            @staticmethod
            def launch_option(_cfg, _appid):
                return ""
        class Shim:
            @staticmethod
            def installed_wrapper_path():
                return self.shim
        peers = {
            "gameweld-steam-launch-options-preserve.py": Options,
            "gameweld-deckcheatz-session.py": Shim,
            "gameweld-steam-compat-bridge.py": Bridge,
        }
        with patch.object(module, "import_peer",
                          side_effect=lambda filename, label: peers[filename]):
            report = module.readiness(
                self.appid, self.launcher, steam_root=self.launcher.parent)
        self.assertEqual(report["state"], "incompatible_bridge_selected")
        self.assertEqual(report["saved_compatibility"]["state"],
                         "gameweld_bridge_selected")
        self.assertIn("real Proton", report["reason"])
        self.assertFalse(report["steam_options_modified"])

    def test_compatibility_tool_is_only_classified_when_explicitly_selected(self):
        class Bridge:
            selection = "OTHER TOOL SELECTED (saved Steam mapping: GE-Proton)"
            @classmethod
            def steam_compat_selection(cls, _appid, *, steam_roots=None):
                return cls.selection
        with patch.object(module, "import_peer", return_value=Bridge):
            result = module.saved_compatibility_bridge_state(self.appid)
            self.assertEqual(result["state"],
                             "other_compatibility_tool_selected")
            Bridge.selection = "UNVERIFIED (no saved exact game mapping readable)"
            result = module.saved_compatibility_bridge_state(self.appid)
            self.assertEqual(result["state"], "unverified")
            Bridge.selection = "GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
            result = module.saved_compatibility_bridge_state(self.appid)
            self.assertEqual(result["state"], "gameweld_bridge_selected")

    def test_live_and_saved_options_are_not_mistaken_for_each_other(self):
        with patch.object(module, "import_peer", side_effect=ValueError("read failed")):
            with self.assertRaisesRegex(ValueError, "read failed"):
                module.readiness(self.appid, self.launcher)

if __name__ == "__main__":
    unittest.main()
