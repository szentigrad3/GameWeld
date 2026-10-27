#!/usr/bin/env python3
"""Regression for the separate opt-in PC2 native Rust wrapper GUI controls.

Static contract: the regular discovery build remains unchanged and native
launch cannot silently fall back to Steam Launch Options or the Bridge.
Rust binary behaviour is compiled and tested by pc2-rust-native-wrapper.yml.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
RUNNER = ROOT / "scripts/run-pc2-source-frontend.sh"
BINARY = ROOT / "crates/wand-runtime/src/bin/gameweld-native-wrapper.rs"

class NativeWrapperGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = GUI.read_text()
        cls.runner = RUNNER.read_text()
        cls.binary = BINARY.read_text()

    def test_optin_is_separate_from_steam_game_only_and_bridge(self):
        self.assertIn("GAMEWELD_PC2_ENABLE_NATIVE_WRAPPER", self.ui)
        self.assertIn('pc2_native_wrapper_allowed(void)', self.ui)
        self.assertIn('--enable-native-wrapper-test', self.runner)
        self.assertIn('unset GAMEWELD_PC2_ENABLE_NATIVE_WRAPPER', self.runner)
        self.assertIn('cargo build -p wand-runtime --bin gameweld-native-wrapper',
                      self.runner)

    def test_library_buttons_have_native_callbacks_and_visible_result(self):
        for text in ("Preview native Rust wrapper (no launch)",
                     "Launch native Rust wrapper + WeMod (experimental)"):
            self.assertIn(text, self.ui)
        self.assertIn('on_pc2_native_wrapper_preview,NULL,NULL,0', self.ui)
        self.assertIn('on_pc2_native_wrapper_launch,NULL,NULL,0', self.ui)
        self.assertIn('pack(inspect,npreview,0)', self.ui)
        self.assertIn('pack(inspect,nlaunch,0)', self.ui)
        self.assertIn('g_idle_add(pc2_native_wrapper_done,j)', self.ui)
        self.assertIn('Native Rust wrapper BLOCKED or failed.', self.ui)

    def test_live_launch_requires_confirmation_and_rust_cli_approvals(self):
        self.assertIn('if(response!=GTK_RESPONSE_YES)return;', self.ui)
        self.assertIn('"--launch","--approve-experimental"', self.ui)
        self.assertIn('"--acknowledge-game-closed"', self.ui)
        self.assertIn('result.launch && !(result.approve && result.game_closed)',
                      self.binary)
        self.assertIn('run_native_wrapper_launch_plan(&plan, &game.install_dir, false)',
                      self.binary)

    def test_preview_is_read_only_and_separate_from_launch(self):
        self.assertIn('run_native_wrapper_launch_plan(&plan, &game.install_dir, true)',
                      self.binary)
        self.assertIn('"--preview"', self.ui)
        self.assertIn('STEAM_LAUNCH_OPTIONS_MODIFIED=false', self.binary)
        self.assertIn('TRAINER_ATTACHMENT_VERIFIED=false', self.binary)
        self.assertIn('GAME_START_VERIFIED=false', self.binary)

if __name__ == "__main__":
    unittest.main()
