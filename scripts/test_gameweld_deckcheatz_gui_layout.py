#!/usr/bin/env python3
"""Static regression checks for the PC2 DeckCheatz GUI surface.

No GTK display, Steam login, game startup, installation or prefix writes.
The full GTK compilation is handled by pc2-deckcheatz-aio.sh.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1] / (
    "crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
)
text = SOURCE.read_text(encoding="utf-8")
policy = SOURCE.with_name("gameweld-pc2-window-policy.h").read_text(encoding="utf-8")


def function_body(signature: str, following: str) -> str:
    start = text.index(signature)
    end = text.index(following, start)
    return text[start:end]


class DeckCheatzGuiLayoutTests(unittest.TestCase):
    def test_primary_launch_is_available_on_overview_and_library(self):
        self.assertEqual(
            text.count('button("Play with WeMod","primary-action")'),
            2,
        )
        self.assertIn("G.pc2_deckcheatz_overview_play=direct", text)
        self.assertIn("G.pc2_deckcheatz_library_play=deckcheatz_test", text)

    def test_button_is_steam_only_and_other_games_stay_experimental(self):
        self.assertIn("game_is_steam(g)&&!game_is_steam_shortcut(g)", text)
        self.assertIn("gtk_widget_set_sensitive(G.pc2_deckcheatz_overview_play,allowed)", text)
        self.assertIn("gtk_widget_set_sensitive(G.pc2_deckcheatz_library_play,allowed)", text)
        self.assertIn('!strcmp(g->appid,"2353250")', text)
        self.assertIn("Experimental for this game", text)

    def test_advanced_launch_controls_are_collapsed(self):
        self.assertIn('gtk_expander_new("Advanced Steam / WeMod diagnostics")', text)
        self.assertIn('gtk_expander_new("Advanced trainer / launch diagnostics")', text)
        self.assertIn("gtk_widget_set_no_show_all(plays,TRUE)", text)
        self.assertIn("gtk_widget_set_no_show_all(launchwith,TRUE)", text)

    def test_screen_policy_is_windowed_at_every_resolution(self):
        self.assertIn("static void pc2_primary_monitor_pixels(", text)
        self.assertIn("gdk_screen_get_monitor_geometry(screen,monitor,&geometry)", text)
        self.assertIn("gdk_screen_get_monitor_scale_factor(screen,monitor)", text)
        self.assertIn("geometry.width*scale", text)
        self.assertIn("geometry.height*scale", text)
        self.assertIn("GameWeldPC2WindowPolicy size=gameweld_pc2_window_policy(", text)
        self.assertIn("GameWeldPC2WindowPolicy result = {w, h, 0};", policy)
        self.assertIn("int soft_max_w = 1720, soft_max_h = 1020;", policy)
        self.assertIn("soft_max_w = 2200; soft_max_h = 1280;", policy)
        self.assertIn("PC2 monitor sizing: windowed", text)

    def test_no_automatic_maximize_and_manual_maximize_remains(self):
        self.assertIn("static gboolean pc2_startup_fit_window(void *unused)", text)
        self.assertIn("g_timeout_add(180,pc2_startup_fit_window,NULL);", text)
        self.assertIn("gtk_window_resize((GtkWindow*)G.window,ww,hh);", text)
        self.assertNotIn("pc2_primary_monitor_is_4k", text)
        self.assertNotIn("g_idle_add(pc2_startup_fit_monitor,NULL)", text)
        self.assertNotIn("if(pc2_discovery_only())gtk_window_maximize", text)
        self.assertIn("if(gtk_window_is_maximized((GtkWindow*)G.window))", text)
        self.assertIn("gtk_window_unmaximize((GtkWindow*)G.window)", text)
        self.assertIn("gtk_window_maximize((GtkWindow*)G.window);", text)
        self.assertIn("/* Preserve the former PC1 window sizing", text)

    def test_saved_window_size_is_clamped_and_respects_manual_resize(self):
        self.assertIn("static int pc2_window_state_path(", text)
        self.assertIn("pc2-window-size.txt", text)
        self.assertIn('getenv("XDG_CONFIG_HOME")', text)
        self.assertIn("pc2_load_window_size(&ww,&hh,maxw,maxh)", text)
        self.assertIn("if(w>max_w)w=max_w", text)
        self.assertIn("if(h>max_h)h=max_h", text)
        self.assertIn('"configure-event",(GCallback)pc2_window_configure', text)
        self.assertIn("static gboolean pc2_window_configure(", text)
        self.assertIn("gtk_window_get_size((GtkWindow*)window,&w,&h)", text)
        self.assertIn("pc2_window_last_w=w;", text)
        self.assertIn("pc2_window_last_h=h;", text)
        self.assertIn("g_timeout_add(750,pc2_window_save_after_resize,NULL)", text)
        self.assertIn("pc2_window_save_queued=0;", text)
        self.assertIn("pc2_window_observation_ready=1;", text)
        self.assertIn("gtk_window_is_maximized((GtkWindow*)window))return FALSE;", text)
        self.assertIn("pc2_save_window_size();if(G.backend_pid", text)
        self.assertIn("gameweld_pc2_state_read(path,out_w,out_h,max_w,max_h)", text)
        self.assertIn("gameweld_pc2_state_write(path,w,h)", text)
        self.assertIn('#include "gameweld-pc2-window-state.h"', text)
        self.assertIn("PC2 saved live window size", text)

    def test_reset_window_size_is_available_without_game_side_effects(self):
        self.assertIn("static void on_pc2_window_size_reset(", text)
        self.assertIn('button("Reset window size","action")', text)
        self.assertIn("gtk_window_resize((GtkWindow*)G.window,ww,hh);", text)
        self.assertIn("if(pc2_window_state_path(path,sizeof path,0))unlink(path);", text)
        self.assertIn("GameWeld remembers your last normal-window size", text)
        self.assertIn("pc2_save_window_size();", text)
        self.assertIn("pc2_window_last_w=ww;pc2_window_last_h=hh;", text)
        self.assertIn(
            'g_signal_connect_data(window_reset,"clicked",'
            '(GCallback)on_pc2_window_size_reset',
            text,
        )
        # PC2's global button factory disables any action not on its
        # allow-list. A wired click handler is insufficient: the button must
        # remain sensitive under PC2 discovery-only mode.
        button_factory = function_body(
            "static GtkWidget *button(const char *s, const char *cls)",
            "static GtkWidget *box(int orient, int spacing)",
        )
        self.assertIn('&& strcmp(s, "Reset window size")', button_factory)
        self.assertIn("pc2_guard_button(w);", button_factory)

    def test_library_adapts_and_keeps_game_list_readable(self):
        self.assertIn("static void pc2_library_size_allocate(", text)
        self.assertIn("gtk_orientable_set_orientation(body", text)
        self.assertIn('"size-allocate",(GCallback)pc2_library_size_allocate', text)
        self.assertIn("stacked?GTK_ORIENTATION_VERTICAL:GTK_ORIENTATION_HORIZONTAL", text)
        self.assertIn("gtk_widget_set_size_request(layout->list_sc,-1,stacked?300:-1)", text)
        self.assertIn("gtk_widget_set_size_request(layout->inspector,stacked?-1:350,-1)", text)
        self.assertIn("return pc2_outer?pc2_outer:p", text)
        self.assertIn("gtk_scrolled_window_set_policy((GtkScrolledWindow*)pc2_outer", text)

    def test_settings_separates_maintenance_and_advanced(self):
        self.assertIn('label("Quick Start",NULL)', text)
        self.assertIn('label("DeckCheatz / WeMod",NULL)', text)
        self.assertIn('label("Advanced Providers",NULL)', text)
        self.assertIn("pack(deckpage,dc,0)", text)
        self.assertIn("pack(advancedpage,cols,1)", text)
        self.assertIn("gtk_notebook_set_current_page((GtkNotebook*)tabs,0)", text)

    def test_about_and_compatibility_are_scoped_to_pc2(self):
        self.assertIn('pack(head,label("GameWeld PC2","workspace-title"),0)', text)
        self.assertIn('GtkWidget*intro=card("What GameWeld does"', text)
        self.assertIn('GtkWidget*tested=card("Validation"', text)
        self.assertIn("It is NOT required for the independent DeckCheatz", text)
        self.assertIn("Other titles and machines must be tested", text)

    def test_launch_preview_and_prefix_consent_remain_separate(self):
        self.assertIn("pc2_deckcheatz_flow(1)", text)
        self.assertIn("pc2_deckcheatz_show_preview(output)", text)
        self.assertIn("if(!ok || !experimental_launch)return", text)
        self.assertIn("GTK_BUTTONS_YES_NO", text)
        self.assertIn('"--confirm-prefix-changes","--experimental-direct-launch"', text)

    def test_no_default_automatic_update_or_steam_option_edit(self):
        self.assertIn("pc2_deckcheatz_request_install(experimental_launch)", text)
        self.assertIn('"--check-update"', text)
        self.assertIn('"--update","--confirm"', text)
        self.assertIn("GameWeld will NOT edit Steam Launch Options", text)


if __name__ == "__main__":
    unittest.main()
