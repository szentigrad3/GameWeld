#!/usr/bin/env python3
"""0.8.0 Dev1 release-file review: structural GUI safety guards."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
C=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
B=(ROOT/'scripts/build-gameweld-0.8.0-dev1-appimage.sh').read_text()
class UI(unittest.TestCase):
    def test_review_button_connected(self):
        self.assertIn('button("Review official files…"',C)
        self.assertIn('"clicked",(GCallback)on_review_official_files',C)
    def test_no_cross_game_async_results(self):
        start=C.index('static gboolean official_files_done(')
        part=C[start:C.index('static void*official_files_worker',start)]
        self.assertIn('j->epoch!=G.trainer_updates_context_epoch',part)
        self.assertIn('strcmp(j->key,game_key(&G.games[G.selected]))',part)
    def test_selected_provider_strict(self):
        start=C.index('static void on_review_official_files(')
        part=C[start:C.index('static void on_find_official_trainer',start)]
        self.assertIn('strcmp(provider,"fling")',part)
        self.assertIn('j->epoch=G.trainer_updates_context_epoch',part)
    def test_no_staging_by_review(self):
        start=C.index('static void*official_files_worker(')
        part=C[start:C.index('static void on_find_official_trainer',start)]
        self.assertNotIn('"install"',part)
        self.assertNotIn('"stage-status"',part)
        self.assertNotIn('"rollback"',part)
        self.assertIn('"publisher-files"',part)
    def test_dev_identity_and_protected_build(self):
        self.assertIn('0.8.0 Dev 1 • Game & Trainer Management',C)
        self.assertIn('X-AppImage-Version=0.8.0-dev1',B)
        self.assertIn('gameweld-lutris-session.sh',B)
        self.assertIn('gameweld-steam-shortcut-live-launch.sh',B)
if __name__=='__main__':unittest.main(verbosity=2)
