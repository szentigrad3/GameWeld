#!/usr/bin/env python3
"""GameWeld RC11 offline field-gate and shared missing-target tests."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'scripts/gameweld-stability-preflight.py'
C=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()

class ReleaseGates(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.base=Path(t.name)
        self.env=dict(os.environ,HOME=str(self.base),XDG_CONFIG_HOME=str(self.base/'config'),XDG_STATE_HOME=str(self.base/'state'),XDG_CACHE_HOME=str(self.base/'cache'),XDG_DATA_HOME=str(self.base/'data'))
        self.cfg=self.base/'config/gameweld';self.cfg.mkdir(parents=True)
    def runp(self,*args):
        r=subprocess.run([sys.executable,str(P),*args],env=self.env,text=True,capture_output=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr);return r.stdout
    def addassign(self,text):
        f=self.cfg/'local-trainers.tsv';f.write_text(text);return f
    def test_duplicate_missing_file_two_game_assignments(self):
        p='/mnt/games/Ghostbusters v1.0 Plus 6 Trainer.exe'
        self.addassign(f'heroic:legendary:ab374ffb0bab4b399a5d5cbdfde77a37\t{p}\nheroic:legendary:Mint\t{p}\n')
        d=json.loads(self.runp('--json'))
        a=d['checks']['assignments']
        self.assertEqual((a['assignments'],a['missing_targets'],a['unique_missing_paths']),(2,2,1))
        self.assertEqual(len(a['missing_groups'][0]['game_keys']),2)
        self.assertEqual(d['status'],'REVIEW')
        r=self.runp()
        self.assertIn('2 assignments,',r) if False else None
        self.assertIn('2 assignment(s)',r)
        self.assertIn('1 distinct targets',r)
        self.assertIn('heroic:legendary:Mint',r)
    def test_after_cleanup_seven_ready_but_unverified(self):
        f=self.base/'trainer.exe';f.write_bytes(b'MZ--test')
        values=['steam:111','steam:222','heroic:legendary:123','heroic:legendary:456','lutris:333','lutris:444','steam:shortcut:55']
        assigned=self.addassign(''.join(f'{g}\t{f}\n' for g in values))
        previous=assigned.read_bytes()
        r=json.loads(self.runp('--json'))
        self.assertEqual(r['status'],'READY_FOR_FIELD_TEST')
        self.assertEqual((r['checks']['assignments']['assignments'],r['checks']['assignments']['missing_targets']),(7,0))
        self.assertEqual(r['checks']['assignments']['platform_counts'],{'Steam':3,'Heroic':2,'Lutris':2})
        self.assertIn('launch success',str(r['limits']))
        self.assertEqual(assigned.read_bytes(),previous)
        self.assertFalse((self.base/'state').exists())
    def test_manual_checkboxes_not_auto_passed(self):
        t=self.base/'trainer.exe';t.write_bytes(b'MZ')
        self.addassign('steam:10\t'+str(t)+'\n')
        md=self.runp()
        self.assertIn('- [ ] **Steam**',md)
        self.assertIn('PRESENT (launch untested)',md)
        self.assertNotIn('- [x]',md)
    def test_private_export_without_config_mutation(self):
        t=self.base/'exe';t.write_bytes(b'MZ')
        p=self.addassign('heroic:legendary:Mint\t'+str(t)+'\n')
        before=p.read_bytes()
        self.runp('--export')
        report=self.base/'state/gameweld/stability-preflight.md'
        self.assertTrue(report.exists())
        self.assertEqual(report.stat().st_mode&0o777,0o600)
        self.assertIn('Field launch checklist',report.read_text())
        self.assertEqual(p.read_bytes(),before)
    def test_bad_cache_is_review_not_clean(self):
        d=self.base/'cache/gameweld';d.mkdir(parents=True)
        (d/'update-monitor-state.json').write_text('invalid json')
        self.assertEqual(json.loads(self.runp('--json'))['status'],'REVIEW')
    def test_symlinked_assignment_file_fails_closed(self):
        source=self.base/'source';source.write_text('steam:1\t/tmp/file.exe')
        (self.cfg/'local-trainers.tsv').symlink_to(source)
        d=json.loads(self.runp('--json'))
        self.assertEqual(d['status'],'REVIEW')
        self.assertEqual(d['checks']['assignments']['status'],'symlink')
    def test_no_auto_launch_or_download(self):
        self.assertNotIn('subprocess',P.read_text())
        self.assertNotIn('urllib',P.read_text())
    def test_native_button_and_version(self):
        self.assertIn('Export stability and launcher checklist',C)
        self.assertIn('"--version","0.7.0-rc11"',C)
    def test_build_includes_preflight_and_protects_launchers(self):
        b=(ROOT/'scripts/build-gameweld-0.7.0-rc11-appimage.sh').read_text()
        for part in ['gameweld-stability-preflight.py','gameweld-lutris-session.sh','gameweld-steam-shortcut-live-launch.sh','0.7.0-rc11']:
            self.assertIn(part,b)

if __name__=='__main__':unittest.main(verbosity=2)
