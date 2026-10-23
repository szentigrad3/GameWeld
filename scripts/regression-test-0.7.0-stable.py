#!/usr/bin/env python3
"""Focused promotion tests; real game launches separately validated by the user."""
import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
P=ROOT/'scripts/gameweld-stability-preflight.py'
BUILD=ROOT/'scripts/build-gameweld-0.7.0-appimage.sh'

class StablePromotion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.env=dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home/'cfg'),
                      XDG_STATE_HOME=str(self.home/'state'), XDG_CACHE_HOME=str(self.home/'cache'))
        self.cfg=self.home/'cfg/gameweld';self.cfg.mkdir(parents=True)
    def runpre(self,*args):
        p=subprocess.run(['python3',str(P),*args],env=self.env,capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        return p.stdout
    def test_stable_native_identity(self):
        self.assertIn('"--version","0.7.0"',C)
        self.assertNotIn('0.7.0-rc11',C)
        self.assertIn('0.7.0 PC1 • Game & Trainer Management',C)
    def test_main_window_stable_identity(self):
        self.assertIn('"0.7.0"',C)
        self.assertNotIn('"0.7.0 RC10"',C)
    def test_release_metadata(self):
        text=BUILD.read_text()
        self.assertIn('X-AppImage-Version=0.7.0',text)
        self.assertIn('RELEASE-NOTES-0.7.0.md',text)
        self.assertIn('SIGNED-CATALOGS-0.7.0.md',text)
    def test_launcher_helpers_retained_in_build(self):
        b=BUILD.read_text()
        for name in ['gameweld-lutris-session.sh','gameweld-steam-shortcut-live-launch.sh',
                     'gameweld-steam-shortcuts.py','gameweld-trainer-library.py',
                     'gameweld-trainer-updates.py','gameweld-update-monitor.py',
                     'gameweld-wand-discovery.py','gameweld-stability-preflight.py']:
            self.assertIn(name,b)
    def test_clean_seven_assignment_preflight(self):
        p=self.home/'trainer.exe';p.write_bytes(b'MZ')
        lines=''.join(f'steam:{j}\t{p}\n' for j in range(7))
        t=self.cfg/'local-trainers.tsv';t.write_text(lines)
        before=t.read_bytes()
        res=json.loads(self.runpre('--json'))
        self.assertEqual(res['version'],'0.7.0')
        self.assertEqual(res['status'],'READY_FOR_FIELD_TEST')
        c=res['checks']['assignments'];self.assertEqual((c['assignments'],c['missing_targets']),(7,0))
        self.assertEqual(t.read_bytes(),before)
    def test_one_missing_target_two_assignments(self):
        missing='/mnt/games/Ghostbusters v1.0 Plus 6 Trainer.exe'
        (self.cfg/'local-trainers.tsv').write_text('heroic:legendary:Mint\t'+missing+'\nheroic:legendary:abc\t'+missing+'\n')
        res=json.loads(self.runpre('--json'))
        c=res['checks']['assignments']
        self.assertEqual(res['status'],'REVIEW')
        self.assertEqual((c['missing_targets'],c['unique_missing_paths']),(2,1))
    def test_no_launchs_auto_checked(self):
        p=self.home/'trainer.exe';p.write_bytes(b'MZ')
        (self.cfg/'local-trainers.tsv').write_text(f'steam:1\t{p}\n')
        report=self.runpre()
        self.assertIn('PRESENT (launch untested)',report)
        self.assertIn('- [ ] **Steam**',report)
    def test_export_is_private_and_does_not_edit_assignments(self):
        p=self.home/'trainer.exe';p.write_bytes(b'MZ')
        target=self.cfg/'local-trainers.tsv';target.write_text(f'heroic:legendary:Nautilus\t{p}\n')
        before=target.read_bytes()
        self.runpre('--export')
        report=self.home/'state/gameweld/stability-preflight.md'
        self.assertTrue(report.is_file())
        self.assertEqual(report.stat().st_mode & 0o777,0o600)
        self.assertEqual(target.read_bytes(),before)
    def test_bad_cache_review(self):
        folder=self.home/'cache/gameweld';folder.mkdir(parents=True)
        (folder/'update-monitor-state.json').write_text('{bad')
        self.assertEqual(json.loads(self.runpre('--json'))['status'],'REVIEW')
    def test_stable_release_notes(self):
        notes=(ROOT/'docs/RELEASE-NOTES-0.7.0.md').read_text()
        self.assertIn('GameWeld 0.7.0',notes)
        self.assertIn('No official signed release catalogs',notes)

if __name__=='__main__': unittest.main(verbosity=2)
