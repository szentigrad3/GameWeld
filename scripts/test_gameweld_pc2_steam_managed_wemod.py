#!/usr/bin/env python3
"""Contract regression for Steam-owned game launch plus separate WeMod handoff.

No Steam client, prefix, game, WeMod binary, or third-party checkout is run.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "crates/wand-ui/appimage-gtk3/gameweld-native-040.c").read_text()
RUNNER = (ROOT / "scripts/run-pc2-source-frontend.sh").read_text()
STEAM = (ROOT / "scripts/gameweld-steam-handoff.py").read_text()
ATTACH = (ROOT / "scripts/gameweld-wemod-live-attach.py").read_text()


class SteamManagedWeModTests(unittest.TestCase):
    def test_one_button_deckcheatz_command_mode_is_opt_in_and_separate(self):
        self.assertIn("--enable-deckcheatz-onebutton-test", RUNNER)
        self.assertIn("export GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1", RUNNER)
        self.assertIn("pc2_deckcheatz_current_options_dialog", GUI)
        self.assertIn('"--steam-launch-options",current_steam_options', GUI)
        self.assertIn('"--steam-options-verified"', GUI)
        self.assertIn("if(pc2_deckcheatz_onebutton_allowed())", GUI)
        self.assertIn("unset GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON", RUNNER)
        self.assertIn("GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON=1", RUNNER)
        self.assertIn("pc2_deckcheatz_onebutton_allowed(void)", GUI)
        self.assertIn("Play with WeMod (DeckCheatz private test)", GUI)
        self.assertIn('strcmp(s, "Play with WeMod (DeckCheatz private test)")', GUI)
        self.assertIn("if(pc2_deckcheatz_onebutton_allowed())pc2_deckcheatz_flow(1)", GUI)
        self.assertIn("else if(pc2_steam_wemod_allowed())pc2_steam_launch_selected(0)", GUI)
        self.assertIn("pc2_deckcheatz_request_install(experimental_launch)", GUI)
        self.assertIn('execlp("python3","python3","-u",helper,"--launch"', GUI)
        self.assertIn('"--confirm-prefix-changes","--experimental-direct-launch"', GUI)
        self.assertIn("GameWeld will NOT edit Steam Launch Options. Continue?", GUI)

    def test_private_mode_launches_through_steam(self):
        self.assertIn("--enable-steam-wemod-test", RUNNER)
        self.assertIn("unset GAMEWELD_PC2_ENABLE_STEAM_WEMOD", RUNNER)
        self.assertIn("GAMEWELD_PC2_ENABLE_STEAM_LAUNCH=1", RUNNER)
        self.assertIn("pc2_steam_wemod_allowed(void)", GUI)
        self.assertIn("Play via Steam + WeMod (private test)", GUI)
        self.assertIn('strcmp(s, "Play via Steam + WeMod (private test)")', GUI)
        self.assertIn("if(pc2_steam_wemod_allowed())pc2_steam_launch_selected(0);", GUI)
        self.assertIn('[executable, "-applaunch", appid]', STEAM)
        self.assertIn("if(j->expect_deckcheatz||j->steam_managed_wemod)", GUI)
        self.assertIn('"--require-idle-before-launch"', GUI)

    def test_no_launch_options_or_bridge_requirements(self):
        self.assertIn("j->steam_managed_wemod=pc2_steam_wemod_allowed()&&!expect_deckcheatz", GUI)
        self.assertIn("pc2_steam_wemod_attach_selected(0);", GUI)
        self.assertIn('"steam_launch_options_changed": False', ATTACH)
        self.assertIn('"steam_bridge_required": False', ATTACH)
        self.assertIn('"new_game_launched": False', ATTACH)
        self.assertIn('argv = [str(runtime["proton"]), "runinprefix", str(client / "WeMod.exe")]', ATTACH)

    def test_preview_is_separate_and_consent_before_prefix_writes(self):
        self.assertIn('"can_attempt_with_explicit_consent": true', GUI.replace('\\', ''))
        self.assertIn("if(consent==GTK_RESPONSE_YES)pc2_steam_wemod_attach_selected(1)", GUI)
        self.assertIn('"--launch-client","--approve-prefix-may-change"', GUI)
        self.assertIn('"--approve-experimental-live-attach"', GUI)
        self.assertIn('"--format","json",(char*)NULL)', GUI)
        self.assertIn("pc2_steam_wemod_attach_busy", GUI)
        self.assertIn("Start the existing WeMod client in THIS game's Proton prefix?", GUI)
        self.assertIn('"trainer_attachment_verified": False', ATTACH)

    def test_explicit_steam_url_fallback_is_not_automatic(self):
        self.assertIn('button("Launch via Steam URL (fallback)"', GUI)
        self.assertIn('on_pc2_steam_uri_fallback,NULL,NULL,0', GUI)
        self.assertIn('if(j->steam_uri)', GUI)
        self.assertIn('"--transport","steam-uri"', GUI)
        self.assertIn('pc2_steam_launch_selected_transport(0,1)', GUI)
        self.assertIn('if(use_uri && !pc2_steam_wemod_allowed())', GUI)
        self.assertIn('Retry launch via the registered Steam URL handler?', GUI)
        self.assertIn('"--require-idle-before-launch"', GUI)

    def test_process_exit_inspector_is_read_only_and_never_kills_wine(self):
        self.assertIn('button("Inspect game and WeMod processes (read-only)"', GUI)
        self.assertIn('on_pc2_steam_wemod_lifecycle,NULL,NULL,0', GUI)
        self.assertIn('pc2_steam_wemod_attach_selected_ex(0,0,1)', GUI)
        self.assertIn('if(j->lifecycle){', GUI)
        self.assertIn('"--appid",j->appid,"--details","--lifecycle"', GUI)
        self.assertIn('GameWeld did not terminate any process.', GUI)
        self.assertIn('pc2_steam_wemod_attach_selected_ex(0,0,0)', GUI)
        self.assertIn('if(!j->live&&ready&&matching&&j->allow_start)', GUI)

    def test_visible_feedback_instead_of_dead_button(self):
        self.assertIn('strcmp(s, "Check / start WeMod in running Steam game")', GUI)
        self.assertIn("on_pc2_steam_wemod_check,NULL,NULL,0", GUI)
        self.assertIn("gtk_message_dialog_new", GUI)
        self.assertIn("WeMod handoff not ready; see the exact blockers in the dialog.", GUI)
        self.assertIn("Steam launch not verified for %.140s.", GUI)


if __name__ == "__main__":
    unittest.main()
