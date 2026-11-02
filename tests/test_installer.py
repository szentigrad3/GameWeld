"""Native user-local installation/uninstallation safety tests."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gameweld import installer

ROOT=Path(__file__).resolve().parents[1]

class DesktopInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/'home'
        self.home.mkdir()
        self.data=self.home/'.local/share'
        self.patch_home=patch.dict(os.environ, {'HOME':str(self.home),'XDG_DATA_HOME':str(self.data)})
        self.patch_home.start()
        self.addCleanup(self.patch_home.stop)

    def test_dry_run_makes_no_files(self):
        out=installer.install(dry_run=True)
        self.assertEqual(out['state'],'dry_run')
        self.assertFalse(self.data.exists())

    def test_install_and_uninstall(self):
        out=installer.install()
        loc=installer.locations()
        self.assertEqual(out['modules_installed'],len(installer.MODULES))
        self.assertTrue(loc['code'].is_dir())
        self.assertTrue(loc['desktop'].is_file())
        self.assertTrue(loc['launcher'].is_file())
        self.assertIn('Icon=applications-games',loc['desktop'].read_text())
        self.assertIn('X-GameWeld-Managed=true',loc['desktop'].read_text())
        self.assertTrue(os.access(loc['launcher'],os.X_OK))
        self.assertFalse(any(p.suffix=='.exe' for p in loc['code'].rglob('*')))
        self.assertEqual(len(list((loc['code']/'gameweld').glob('*.py'))),len(installer.MODULES))
        pref=self.home/'.config/gameweld/desktop.json';pref.parent.mkdir(parents=True)
        pref.write_text('PREFERENCES_KEPT')
        state=self.home/'.local/state/gameweld/benchmarks.json';state.parent.mkdir(parents=True)
        state.write_text('HISTORY_KEPT')
        result=installer.uninstall()
        self.assertEqual(result['state'],'uninstalled')
        self.assertFalse(loc['code'].exists())
        self.assertFalse(loc['desktop'].exists())
        self.assertFalse(loc['launcher'].exists())
        self.assertEqual(pref.read_text(),'PREFERENCES_KEPT')
        self.assertEqual(state.read_text(),'HISTORY_KEPT')

    def test_reinstall_is_idempotent(self):
        installer.install();installer.install()
        self.assertEqual(len(list((installer.locations()['code']/'gameweld').glob('*.py'))),len(installer.MODULES))
        self.assertTrue(installer.locations()['launcher'].exists())

    def test_refuse_unmanaged_launcher(self):
        loc=installer.locations();loc['launcher'].parent.mkdir(parents=True)
        loc['launcher'].write_text('#!/bin/sh\necho user custom\n')
        with self.assertRaises(ValueError):installer.install()
        self.assertEqual(loc['launcher'].read_text(),'#!/bin/sh\necho user custom\n')
        self.assertFalse(loc['code'].exists())

    def test_refuse_unmanaged_desktop(self):
        loc=installer.locations();loc['desktop'].parent.mkdir(parents=True)
        loc['desktop'].write_text('[Desktop Entry]\nName=Other\n')
        with self.assertRaises(ValueError):installer.install()
        self.assertEqual(loc['desktop'].read_text(),'[Desktop Entry]\nName=Other\n')

    def test_refuse_unmanaged_application_tree(self):
        loc=installer.locations();loc['code'].mkdir(parents=True)
        (loc['code']/'user.txt').write_text('preserve')
        with self.assertRaises(ValueError):installer.install()
        self.assertEqual((loc['code']/'user.txt').read_text(),'preserve')

    def test_refuse_symlinks_for_launcher_or_code(self):
        loc=installer.locations();loc['launcher'].parent.mkdir(parents=True)
        target=self.home/'target';target.write_text('preserve')
        loc['launcher'].symlink_to(target)
        with self.assertRaises(ValueError):installer.install()
        self.assertEqual(target.read_text(),'preserve')

    def test_refuse_symlink_parent(self):
        loc=installer.locations();outside=Path(self.tmp.name)/'outside';outside.mkdir()
        self.data.parent.mkdir(parents=True)
        self.data.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):installer.install()
        self.assertEqual(list(outside.iterdir()),[])

    def test_refuse_uninstall_unknown_file(self):
        loc=installer.locations();loc['launcher'].parent.mkdir(parents=True)
        loc['launcher'].write_text('personal')
        with self.assertRaises(ValueError):installer.uninstall()
        self.assertEqual(loc['launcher'].read_text(),'personal')

    def test_installed_launcher_smoke(self):
        installer.install()
        env=os.environ.copy();env['XDG_STATE_HOME']=str(self.home/'state')
        proc=subprocess.run([str(installer.locations()['launcher']),'--smoke','--steamapps',str(self.home/'none')],
                            capture_output=True,text=True,env=env,timeout=10,cwd=self.home)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['installed_games'],0)

    def test_no_privileged_or_unknown_copy(self):
        self.assertFalse(any(path.startswith('/') for path in installer.MODULES))
        self.assertNotIn('ui.pyc',installer.MODULES)
        self.assertNotIn('gameweld_sidecar_probe_v2.exe',installer.MODULES)

    def test_uninstall_dry_run_leaves_installation(self):
        installer.install()
        self.assertEqual(installer.uninstall(dry_run=True)['state'],'dry_run')
        self.assertTrue(installer.locations()['code'].exists())

    def test_invalid_exec_path_cannot_inject_desktop(self):
        with self.assertRaises(ValueError):installer._desktop_exec('/tmp/evil\nExec=rm')

if __name__=='__main__':unittest.main()
