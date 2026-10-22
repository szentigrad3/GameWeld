#!/usr/bin/env python3
"""RC5: offline stage verification, corruption refusal, rollback, CLI, UI."""
import contextlib,hashlib,importlib.util,io,json,os,struct,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
TOOL=Path(__file__).with_name('gameweld-trainer-updates.py')
spec=importlib.util.spec_from_file_location('gameweld_rc5_stage',TOOL)
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)

def exe(tag):
    b=bytearray(180);b[0:2]=b'MZ';struct.pack_into('<I',b,60,128);b[128:132]=b'PE\0\0';b[132:]=tag.encode()[:48];return bytes(b)

def archive(tag):
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:z.writestr('Trainer.exe',exe(tag))
    return f.getvalue()

class StageLifecycle(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.cfg=self.root/'config';self.data=self.root/'data'
        self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.cfg),'XDG_DATA_HOME':str(self.data)})
        self.env.start();self.addCleanup(self.env.stop)
        self.cat=self.root/'catalog.json';self.blob=archive('OLD')
        self.e={'id':'control-resonant','game':'CONTROL Resonant','version':'1.0','provider':'fling',
                'url':'https://flingtrainer.com/files/control-resonant.zip','sha256':''}
        self.update_catalog('OLD','1.0')
    def update_catalog(self,tag,version):
        self.blob=archive(tag);self.e['version']=version;self.e['sha256']=hashlib.sha256(self.blob).hexdigest()
        self.cat.write_text(json.dumps({'schema':1,'entries':[self.e]}))
    def factory(self,url):return contextlib.closing(io.BytesIO(self.blob))
    def stage(self):return Path(u.install(self.e['game'],self.e['id'],self.cat,True,response_factory=self.factory))
    def prepare(self):
        self.first=self.stage();self.update_catalog('NEW','1.4');self.second=self.stage()
        self.backup=self.second.parent.with_name(self.second.parent.name+'.previous')

    def test_staging_and_rollback_full_cycle(self):
        self.prepare()
        state=u.stage_status(self.e['game'],self.e['id'],self.cat)
        self.assertEqual(state['current'],'verified-locally')
        self.assertEqual(state['backup'],'verified-locally')
        self.assertEqual(state['backup_version'],'1.0')
        self.assertTrue(state['can_rollback'])
        self.assertNotEqual(self.first,self.second)
        result=u.rollback(self.e['game'],self.e['id'],self.cat,True)
        self.assertTrue(Path(result['restored']).is_file())
        self.assertEqual(u.read_receipt(self.second.parent)['version'],'1.0')
        self.assertEqual(u.read_receipt(self.backup)['version'],'1.4')
        self.assertTrue(u.verified_staged_file(self.second.parent))
        self.assertTrue(u.verified_staged_file(self.backup))
        # An explicit second rollback restores the newly staged release.
        u.rollback(self.e['game'],self.e['id'],self.cat,True)
        self.assertEqual(u.read_receipt(self.second.parent)['version'],'1.4')

    def test_rollback_optin(self):
        self.prepare()
        with self.assertRaisesRegex(u.UpdateError,'approval'):u.rollback(self.e['game'],self.e['id'],self.cat)
        self.assertEqual(u.read_receipt(self.second.parent)['version'],'1.4')

    def test_tampered_backup_blocks_rollback(self):
        self.prepare()
        (self.backup/self.first.name).write_bytes(b'bad')
        state=u.stage_status(self.e['game'],self.e['id'],self.cat)
        self.assertEqual(state['backup'],'invalid')
        self.assertFalse(state['can_rollback'])
        with self.assertRaisesRegex(u.UpdateError,'verified'):u.rollback(self.e['game'],self.e['id'],self.cat,True)
        self.assertEqual(u.read_receipt(self.second.parent)['version'],'1.4')

    def test_corrupted_current_blocks_rollback(self):
        self.prepare();self.second.write_bytes(b'MZcorrupt')
        self.assertFalse(u.stage_status(self.e['game'],self.e['id'],self.cat)['can_rollback'])
        with self.assertRaises(u.UpdateError):u.rollback(self.e['game'],self.e['id'],self.cat,True)

    def test_symlink_receipt_denied(self):
        self.prepare();p=self.backup/'receipt.json';p.unlink();p.symlink_to(self.second.parent/'receipt.json')
        self.assertIsNone(u.read_receipt(self.backup))
        self.assertFalse(u.stage_status(self.e['game'],self.e['id'],self.cat)['can_rollback'])

    def test_symlink_exe_denied(self):
        self.prepare();p=self.backup/self.first.name;p.unlink();p.symlink_to(self.second)
        self.assertFalse(u.stage_status(self.e['game'],self.e['id'],self.cat)['can_rollback'])

    def test_symlink_backup_dir_denied(self):
        self.prepare();import shutil
        shutil.rmtree(self.backup);self.backup.symlink_to(self.second.parent,target_is_directory=True)
        with self.assertRaisesRegex(u.UpdateError,'Symlink'):u.stage_status(self.e['game'],self.e['id'],self.cat)

    def test_cross_game_denied(self):
        self.prepare()
        with self.assertRaisesRegex(u.UpdateError,'exact game'):u.rollback('CONTROL',self.e['id'],self.cat,True)

    def test_no_backup(self):
        self.stage()
        self.assertEqual(u.stage_status(self.e['game'],self.e['id'],self.cat)['backup'],'absent')

    def test_cli_status_and_no_automatic_rollback(self):
        self.prepare()
        cmd=[sys.executable,str(TOOL),'stage-status','--game',self.e['game'],'--id',self.e['id'],'--catalog',str(self.cat)]
        p=subprocess.run(cmd,text=True,capture_output=True,env=os.environ.copy())
        self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(json.loads(p.stdout)['can_rollback'])
        cmd[2]='rollback';p=subprocess.run(cmd,text=True,capture_output=True,env=os.environ.copy())
        self.assertEqual(p.returncode,2);self.assertIn('approval',p.stdout)

    def test_offline_catalog_provides_exact_source_and_digest(self):
        cmd=[sys.executable,str(TOOL),'check','--game',self.e['game'],'--catalog',str(self.cat),'--plain']
        proc=subprocess.run(cmd,text=True,capture_output=True,env=os.environ.copy())
        self.assertEqual(proc.returncode,0,proc.stderr)
        cols=proc.stdout.strip().split('\t')
        self.assertEqual(cols[:4],['CATALOG',self.e['id'],self.e['version'],'available'])
        self.assertEqual(cols[4],self.e['sha256'])
        self.assertEqual(cols[5],self.e['url'])

    def test_ui_buttons_wired(self):
        code=(TOOL.parents[1]/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
        for token in ('Inspect staged trainer','Restore previous staged copy','stage-status','rollback','on_staged_trainer_action','Previous assignments are unchanged'):
            self.assertIn(token,code)

    def test_catalog_not_publisher_authentication(self):
        self.prepare()
        self.assertIn('not established',u.stage_status(self.e['game'],self.e['id'],self.cat)['provenance'])

if __name__=='__main__':unittest.main(verbosity=2)
