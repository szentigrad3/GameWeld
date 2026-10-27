#!/usr/bin/env python3
"""Offline regression checks for the GameWeld PC2 Recent Games strip.

Only compiles/runs an isolated GTK-free history helper, and inspects source
contracts. Does not read the user's library, Steam config, prefixes, or games.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
UI = ROOT / "crates/wand-ui/appimage-gtk3/gameweld-native-040.c"
HEADER = ROOT / "crates/wand-ui/appimage-gtk3/gameweld-pc2-recent-history.h"


class RecentGamesTests(unittest.TestCase):
    def test_bounded_deduplicated_recent_selection_order(self):
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        harness = r'''
#include <assert.h>
#include <string.h>
#include "gameweld-pc2-recent-history.h"
int main(void) {
    GameWeldPC2RecentHistory r = {0};
    assert(!gameweld_pc2_recent_push(&r,""));
    assert(!gameweld_pc2_recent_push(&r,"invalid\nkey"));
    assert(r.count==0);
    for(int i=0;i<8;i++) {
        char id[32];
        snprintf(id,sizeof id,"steam:%d",100+i);
        assert(gameweld_pc2_recent_push(&r,id));
    }
    assert(r.count==6);
    assert(!strcmp(r.keys[0],"steam:107"));
    assert(!strcmp(r.keys[5],"steam:102"));
    assert(!gameweld_pc2_recent_push(&r,"steam:107"));
    assert(gameweld_pc2_recent_push(&r,"steam:104"));
    assert(!strcmp(r.keys[0],"steam:104"));
    assert(!strcmp(r.keys[1],"steam:107"));
    assert(!strcmp(r.keys[5],"steam:102"));
    assert(gameweld_pc2_recent_push(&r,"heroic:game-1"));
    assert(!strcmp(r.keys[0],"heroic:game-1"));
    assert(r.count==6);
    return 0;
}'''
        with tempfile.TemporaryDirectory(prefix="gameweld-recent-test-") as temp:
            source = pathlib.Path(temp) / "test.c"
            program = pathlib.Path(temp) / "test"
            source.write_text("#include <stdio.h>\n" + harness, encoding="utf-8")
            subprocess.run([compiler, "-std=c11", "-D_GNU_SOURCE", "-Wall",
                            "-Wextra", "-Werror", "-I", str(HEADER.parent),
                            str(source), "-o", str(program)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(program)], check=True, timeout=5)

    def test_overview_uses_selection_only_cards_with_artwork_fallback(self):
        text = UI.read_text(encoding="utf-8")
        start = text.index("static void pc2_recent_render(void){")
        end = text.index("static void selected_changed(", start)
        render = text[start:end]
        self.assertIn("pc2_recent_index_of", render)
        self.assertIn("resolve_game_art(game,1,art,sizeof art)", render)
        self.assertIn("resolve_game_art(game,0,art,sizeof art)", render)
        self.assertIn('style(tile,"recent-tile")', render)
        self.assertIn("pc2_recent_select", render)
        self.assertNotIn("on_pc2_bridge_play", render)
        self.assertIn("for(int idx=0;idx<G.game_count", render)
        self.assertIn('is_recent[i]?"Recently selected":"Library"', render)
        self.assertIn('gtk_scrolled_window_set_policy((GtkScrolledWindow*)scroll,', text)
        self.assertIn("GTK_POLICY_AUTOMATIC,GTK_POLICY_NEVER", text)

    def test_selection_uses_exact_library_row_and_persists_only_in_pc2(self):
        text = UI.read_text(encoding="utf-8")
        selection = text[text.index("static void pc2_recent_select("):
                         text.index("static void pc2_recent_clear_child(")]
        self.assertIn("gtk_list_box_select_row", selection)
        self.assertNotIn("proton", selection.lower())
        self.assertNotIn("Steam", selection)
        self.assertIn("if(!pc2_discovery_only())return;", text)
        self.assertIn("pc2-recent-games.txt", text)
        self.assertIn("G.selected=last;", text)
        self.assertIn("gtk_widget_set_no_show_all(lower,TRUE)", text)
        self.assertIn("G.pc2_deckcheatz_overview_play=direct", text)
        self.assertIn('"Play via Steam + WeMod (private test)"', text)
        self.assertIn('g_signal_connect_data(direct,"clicked",(GCallback)on_pc2_bridge_primary', text)


if __name__ == "__main__":
    unittest.main()
