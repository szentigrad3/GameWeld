#!/usr/bin/env python3
"""Validate intentional absence of uncleared distribution components."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CandidateDistribution(unittest.TestCase):
    def test_native_profiles_not_advertised(self):
        s=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
        self.assertIn('(void)appid;return NULL; /* third-party native profile excluded',s)
        self.assertIn('0.7.0 PC1',s)
    def test_native_launchers_fail_closed(self):
        for n in ('gameweld','gameforge','wand'):
            s=(ROOT/'scripts'/f'{n}-native-profile.sh').read_text()
            self.assertIn('disabled',s)
            self.assertIn('exit 4',s)
    def test_uncleared_trainer_code_removed(self):
        self.assertFalse((ROOT/'tools/resonance-native-trainer.c').exists())
        self.assertFalse((ROOT/'scripts/build-resonance-native-trainer.sh').exists())
        self.assertFalse((ROOT/'crates/wand-ui/appimage-gtk3/resonance-hero-appimage.jpg').exists())
    def test_build_script_explicitly_scrubs_old_appimage(self):
        s=(ROOT/'scripts/build-gameweld-0.7.0-pc1-appimage.sh').read_text()
        self.assertIn('8e1906a488de83f51378ed593c75f643c9640ef5d23e503aa3dab78941b1756a',s)
        self.assertIn('resonance-native-trainer.exe',s)
        self.assertIn('resonance-hero-reference.png',s)
        self.assertIn('2713000/hero.png',s)
        self.assertIn('0.7.0-pc1',s)
if __name__=='__main__':unittest.main(verbosity=2)
