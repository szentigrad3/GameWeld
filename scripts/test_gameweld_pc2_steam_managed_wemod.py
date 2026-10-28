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
        self.assertIn('"--resolve-game-exe","--appid",g->appid', GUI)
        self.assertIn("DeckCheatz automatically detected game executable", GUI)
        self.assertIn("Game executable ambiguous", GUI)
        self.assertIn('"--steam-options-verified"', GUI)
        self.assertIn("if(pc2_deckcheatz_onebutton_allowed())", GUI)
        self.assertIn('"Use these options",GTK_RESPONSE_YES', GUI)
        self.assertIn('gtk_entry_set_text((GtkEntry*)entry,saved)', GUI)
        self.assertIn('if(!pc2_deckcheatz_onebutton_allowed())pack(inspect,advanced,0)', GUI)
        self.assertIn('if(pc2_deckcheatz_onebutton_allowed()){', GUI)
        self.assertIn('pack(nav,G.nav_library,0)', GUI)
        self.assertIn('pc2_deckcheatz_onebutton_allowed())nav_activate(G.nav_library,"library")', GUI)
        self.assertIn('if(!pc2_deckcheatz_onebutton_allowed())', GUI)
        self.assertIn("unset GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON", RUNNER)
        self.assertIn("GAMEWELD_PC2_ENABLE_DECKCHEATZ_ONEBUTTON=1", RUNNER)
        self.assertIn("pc2_deckcheatz_onebutton_allowed(void)", GUI)
        self.assertIn("Play with WeMod", GUI)
        self.assertIn('strcmp(s, "Play with WeMod")', GUI)
        self.assertIn("if(pc2_deckcheatz_onebutton_allowed())pc2_deckcheatz_steam_onebutton()", GUI)
        self.assertIn("static void pc2_deckcheatz_steam_onebutton(void){", GUI)
        self.assertIn('"gameweld-deckcheatz-steam-readiness.py"', GUI)
        self.assertIn('"--compat-steam-root",', GUI)
        self.assertIn('pc2_deckcheatz_folder(g->steam_root)', GUI)
        self.assertIn('pc2_steam_launch_selected(1);', GUI)
        self.assertIn('pc2_deckcheatz_auto_steam_setup(g->appid,launcher);', GUI)
        self.assertIn('if(j->resume_mode==2)pc2_deckcheatz_steam_onebutton();', GUI)
        self.assertIn("else if(pc2_steam_wemod_allowed())pc2_steam_launch_selected(0)", GUI)
        self.assertIn("pc2_deckcheatz_request_install(experimental_launch)", GUI)
        self.assertIn('execlp("python3","python3","-u",helper,"--launch"', GUI)
        self.assertIn('"--confirm-prefix-changes","--experimental-direct-launch"', GUI)
        self.assertIn("GameWeld will NOT edit Steam Launch Options. Continue?", GUI)
        self.assertIn("Steam itself will launch the game", GUI)

    def test_automatic_steam_setup_does_not_require_manual_copy(self):
        self.assertIn("static void pc2_deckcheatz_auto_steam_setup(", GUI)
        self.assertIn('"gameweld-deckcheatz-auto-steam-setup.py"', GUI)
        self.assertIn('"--confirm","--shutdown-and-launch"', GUI)
        self.assertIn("pc2_deckcheatz_auto_steam_setup(g->appid,launcher);", GUI)
        self.assertIn("You will NOT paste or type anything in Steam.", GUI)
        self.assertIn("Automatic Steam one-shot setup did not complete", GUI)

    def test_all_steam_deckcheatz_launches_require_verified_wrapper(self):
        self.assertIn("static int pc2_deckcheatz_saved_readiness(", GUI)
        self.assertIn("if(expect_deckcheatz){\n        char verified[8192]", GUI)
        self.assertIn('strcmp(mode,"direct_wrapper_configured")', GUI)
        self.assertIn('strcmp(mode,"one_shot_shim_configured")', GUI)
        self.assertIn('No Steam request was sent.', GUI)
        self.assertIn('!pc2_session_configured_for_game(id)', GUI)
        self.assertIn('if(!pc2_deckcheatz_saved_readiness(g,launcher,report,sizeof report))', GUI)
        self.assertIn('if(g->steam_root[0] && pc2_deckcheatz_folder(g->steam_root))', GUI)

    def test_one_shot_token_remains_valid_during_slow_steam_startup(self):
        # A Steam IPC request can precede the DeckCheatz shim invocation.
        # Cancelling the token on a wrapper-only observation silently launches
        # the game without the intended trainer.
        self.assertIn('int request_sent=strstr(j->output,"Steam applaunch command: STARTED")', GUI)
        self.assertIn("if(!request_sent || explicit_failure){", GUI)
        self.assertIn('pc2_deckcheatz_session_helper("disarm",j->appid', GUI)
        self.assertIn("Steam launch request sent, but the game EXE was not observed", GUI)
        self.assertIn('strstr(j->output,"Launch result: STEAM_ASSOCIATION_ONLY")', GUI)

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

    def test_no_steam_options_one_click_mode_is_separate_and_opt_in(self):
        self.assertIn("--enable-no-steam-options-test", RUNNER)
        self.assertIn("unset GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS", RUNNER)
        self.assertIn("export GAMEWELD_PC2_ENABLE_NO_STEAM_OPTIONS=1", RUNNER)
        self.assertIn("pc2_steam_no_options_allowed(void)", GUI)
        self.assertIn("pc2_steam_no_options_allowed())pc2_steam_launch_selected(0)", GUI)
        self.assertIn("Play with WeMod (no Steam settings)", GUI)
        self.assertIn("Steam will NOT be restarted", GUI)
        self.assertIn("Launch Options and Compatibility", GUI)
        self.assertIn("j->no_options_onebutton=pc2_steam_no_options_allowed()", GUI)
        self.assertIn("j->no_options_onebutton?2:1", GUI)
        self.assertIn("if(!j->live&&ready&&matching&&j->allow_start==2)", GUI)
        self.assertIn("pc2_steam_wemod_attach_selected(1);", GUI)
        # Pending one-shot tokens or existing direct wrappers cannot silently
        # start a second trainer when the new launch route is selected.
        self.assertIn('pc2_deckcheatz_session_helper("status",id,NULL,pending', GUI)
        self.assertIn('strstr(pending,"\\\"session_armed\\\": true")', GUI)
        self.assertIn('!strcmp(mode,"trainer_wrapper_present")', GUI)
        self.assertIn('!strcmp(mode,"incompatible_bridge_selected")', GUI)
        self.assertIn('!strcmp(mode,"unverified")', GUI)
        self.assertIn('"--preserve-custom-options"', GUI)
        self.assertIn('pc2_deckcheatz_saved_readiness(g,NULL,readiness,sizeof readiness)', GUI)
        self.assertIn("GameWeld will not start a second WeMod client", GUI)

    def test_no_options_button_is_not_disabled_by_discovery_guard(self):
        # PC2 disables any button absent from the centralized safe-action
        # allowlist. This was the actual cause of the user's inert Play button.
        self.assertIn('strcmp(s, "Play with WeMod (no Steam settings)")', GUI)
        self.assertIn('static void pc2_guard_button(GtkWidget *w)', GUI)
        self.assertIn('g_signal_connect_data(deckcheatz_test,"clicked",(GCallback)on_pc2_bridge_primary', GUI)
        self.assertIn('G.pc2_deckcheatz_overview_play=direct;', GUI)
        self.assertIn('pc2_bridge_apply_primary("checking"', GUI)

    def test_no_options_respects_user_steam_commands_without_autosetup(self):
        self.assertIn('pc2_deckcheatz_saved_readiness(g,NULL,readiness,sizeof readiness)', GUI)
        self.assertIn('if(launcher&&*launcher){', GUI)
        self.assertIn('"--preserve-custom-options"', GUI)
        self.assertIn('pc2_steam_launch_selected(0);', GUI)
        self.assertIn('[executable, "-applaunch", appid]', STEAM)
        self.assertNotIn('"%command%"', STEAM)
        self.assertIn('Steam will choose Proton and use its EXISTING Launch Options.', GUI)
        # Separate live-prefix WeMod handoff must not require an editable
        # saved Steam launch option or call the legacy mutating setup.
        start = GUI.index('if(pc2_steam_no_options_allowed()&&!expect_deckcheatz){')
        end = GUI.index('if(use_uri && !pc2_steam_wemod_allowed())', start)
        branch = GUI[start:end]
        self.assertNotIn('pc2_deckcheatz_auto_steam_setup(', branch)
        self.assertNotIn('pc2_deckcheatz_find_launcher(', branch)
        self.assertIn('GameWeld can restore only its own backed-up wrapper.', branch)

    def test_no_options_one_click_reuses_live_prefix_safety_rechecks(self):
        self.assertIn("if(j->steam_managed_wemod && (!strcmp(state,", GUI)
        self.assertIn('"Launch result: GAME_EXECUTABLE_OBSERVED"', GUI)
        self.assertIn('j->ok && strstr(j->output,', GUI)
        self.assertIn('"can_attempt_with_explicit_consent": true', GUI.replace(chr(92), ""))
        self.assertIn("pc2_steam_wemod_attach_selected_ex(0,j->no_options_onebutton?2:1,0)", GUI)
        self.assertIn('argv = [str(runtime["proton"]), "runinprefix", str(client / "WeMod.exe")]', ATTACH)
        self.assertIn("Steam session changed; re-run preview before client launch", ATTACH)
        self.assertIn('"steam_launch_options_changed": False', ATTACH)

    def test_wand_v2_development_mode_is_explicit_no_fallback_and_no_steam_edits(self):
        self.assertIn("--enable-v2-wemod-test", RUNNER)
        self.assertIn("unset GAMEWELD_PC2_USE_WAND_V2", RUNNER)
        self.assertIn("export GAMEWELD_PC2_USE_WAND_V2=1", RUNNER)
        self.assertIn("pc2_wand_v2_allowed(void)", GUI)
        self.assertIn("Play with WeMod (v2 development)", GUI)
        self.assertIn('strcmp(s, "Play with WeMod (v2 development)")', GUI)
        self.assertIn('"gameweld-wand-v2-proxy.py"', GUI)
        self.assertIn('if(!j->lifecycle && pc2_wand_v2_allowed())', GUI)
        self.assertIn('"--install-dir",j->install_dir,"--launch-client"', GUI)
        self.assertIn('if(pc2_deckcheatz_onebutton_allowed())pc2_deckcheatz_steam_onebutton()', GUI)
        self.assertIn('else if(pc2_steam_no_options_allowed())pc2_steam_launch_selected(0)', GUI)

    def test_v2_unreadable_risk_requires_initial_gameweld_user_approval(self):
        self.assertIn("CachyOS may hide some same-user process environments.", GUI)
        self.assertIn("you explicitly accept proceeding with at most 8 unreadable processes", GUI)
        self.assertIn('if(pc2_wand_v2_allowed())pc2_steam_wemod_attach_selected_ex(1,2,0);', GUI)
        self.assertIn('if(j->live && j->allow_start==2)', GUI)
        self.assertIn('else if(j->allow_start==2)', GUI)
        self.assertIn('"--accept-unreadable-process-risk"', GUI)
        self.assertIn('else if(j->live)', GUI)
        # An explicit manual preview does not pass the unknown-process risk flag.
        self.assertIn('else\n                execlp("python3","python3",helper,"--appid",j->appid,', GUI)
        self.assertIn("A prepared-prefix archive is NOT automatically installed.", GUI)

    def test_v2_delayed_game_launch_waits_and_does_not_repeat_steam_command(self):
        # Steam IPC can return before Proton finishes loading the executable.
        # The extended observation is V2-only; never issue another Steam launch.
        self.assertIn('"--observe-seconds","75"', GUI)
        self.assertIn('(j->no_options_onebutton&&pc2_wand_v2_allowed())?90:28', GUI)
        self.assertIn('else if(j->no_options_onebutton && pc2_wand_v2_allowed())', GUI)
        self.assertIn('pc2_steam_wemod_attach_selected_ex(0,j->no_options_onebutton?2:1,0)', GUI)
        self.assertIn('Steam\'s launcher may still be preparing the game.', GUI)
        self.assertIn("Do NOT relaunch the game.", GUI)
        self.assertIn('if(!pc2_wand_v2_allowed() &&', GUI)
        self.assertIn('!strcmp(state,"GAME EXECUTABLE OBSERVED")', GUI)

    def test_v2_manual_recovery_requires_fresh_consent_and_exact_game(self):
        self.assertIn('static void on_pc2_steam_wemod_check(GtkButton*b,void*d)', GUI)
        self.assertIn('Check the running Steam game and start Wand v2 ONLY if safe?', GUI)
        self.assertIn('GameWeld will NOT ask Steam to launch the game again.', GUI)
        self.assertIn('You explicitly accept up to 8 unreadable same-user process', GUI)
        self.assertIn('if(accepted==GTK_RESPONSE_YES)', GUI)
        self.assertIn('pc2_steam_wemod_attach_selected_ex(0,2,0);', GUI)
        self.assertIn('pc2_deckcheatz_saved_readiness(g,NULL,readiness,sizeof readiness)', GUI)
        self.assertIn('pc2_deckcheatz_session_helper("status",g->appid,NULL,pending,sizeof pending)', GUI)
        self.assertIn('strstr(pending,"\\\"session_armed\\\": true")', GUI)
        self.assertIn('GameWeld has not modified your existing Steam Launch Options.', GUI)
        self.assertIn('if(!game_is_steam(g)||game_is_steam_shortcut(g)||', GUI)
        self.assertIn('if(pc2_steam_wemod_attach_busy)return;', GUI)

    def test_v2_gpu_safe_development_mode_is_explicit_and_only_we_mod_changes(self):
        self.assertIn("--enable-v2-wemod-gpu-safe-test", RUNNER)
        self.assertIn("unset GAMEWELD_PC2_WEMOD_SOFTWARE_RENDERING", RUNNER)
        self.assertIn("export GAMEWELD_PC2_WEMOD_SOFTWARE_RENDERING=1", RUNNER)
        self.assertIn("pc2_wand_v2_gpu_safe_allowed(void)", GUI)
        self.assertIn('strcmp(s, "Play with WeMod (v2 GPU-safe test)")', GUI)
        self.assertIn("Play with WeMod (v2 GPU-safe test)", GUI)
        self.assertIn("Only WeMod.exe receives the Electron flags;", GUI)
        self.assertIn('if(pc2_wand_v2_gpu_safe_allowed()){', GUI)
        self.assertIn('"--client-software-rendering"', GUI)
        self.assertIn("Steam will run your game with its existing graphics settings", GUI)
        self.assertIn("No existing Wine or ", GUI)
        self.assertIn("Proton processes will be killed.", GUI)
        # The prepared game launch itself never receives client flags.
        pos=GUI.index('static void *pc2_steam_launch_worker(void *data)')
        end=GUI.index('static int pc2_deckcheatz_session_helper(', pos) if 'static int pc2_deckcheatz_session_helper(' in GUI[pos:] else len(GUI)
        self.assertNotIn('--client-software-rendering', GUI[pos:end])
        self.assertNotIn('steam -applaunch', RUNNER)

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
