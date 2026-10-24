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

    def test_screen_policy_uses_monitor_geometry_and_hidpi_scale(self):
        self.assertIn("static void pc2_primary_monitor_pixels(", text)
        self.assertIn("gdk_screen_get_monitor_geometry(screen,monitor,&geometry)", text)
        self.assertIn("gdk_screen_get_monitor_scale_factor(screen,monitor)", text)
        self.assertIn("geometry.width*scale", text)
        self.assertIn("geometry.height*scale", text)
        self.assertIn("gameweld_pc2_window_policy(1280,720,w,h).maximize", text)
        self.assertIn("physical_w >= 3840 && physical_h >= 2160", policy)
        self.assertIn("PC2 monitor sizing: GTK restored logical size", text)
        self.assertIn("maximized (UHD)", text)
        self.assertIn("proportional window", text)

    def test_4k_maximizes_but_other_resolutions_remain_windowed(self):
        self.assertIn("static gboolean pc2_startup_fit_monitor(void *unused)", text)
        self.assertIn(
            "if(pc2_discovery_only()&&G.window&&pc2_primary_monitor_is_4k())",
            text,
        )
        self.assertIn(
            "if(pc2_discovery_only()&&pc2_primary_monitor_is_4k())gtk_window_maximize",
            text,
        )
        self.assertIn("g_idle_add(pc2_startup_fit_monitor,NULL)", text)
        self.assertIn("GameWeldPC2WindowPolicy size=gameweld_pc2_window_policy(", text)
        self.assertIn("int width_pct = 90, height_pct = 88;", policy)
        self.assertIn("width_pct = 95; height_pct = 93;", policy)
        self.assertIn("width_pct = 92; height_pct = 90;", policy)
        self.assertIn("int w = (logical_w * width_pct) / 100;", policy)
        self.assertIn("int h = (logical_h * height_pct) / 100;", policy)
        self.assertIn("if (w > maxw) w = maxw;", policy)
        self.assertIn("if (h > maxh) h = maxh;", policy)

    def test_4k_does_not_force_old_window_geometry_after_startup(self):
        self.assertIn("if(gtk_window_is_maximized((GtkWindow*)G.window))", text)
        self.assertIn("gtk_window_unmaximize((GtkWindow*)G.window)", text)
        self.assertIn("g_idle_add(force_mockup_geometry,NULL);", text)
        self.assertIn("g_timeout_add(180,force_mockup_geometry,NULL);", text)
        self.assertIn("if(pc2_discovery_only()){\n        /* Exactly one conditional UHD maximization", text)
        self.assertIn("/* Preserve the former PC1 window sizing", text)

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
