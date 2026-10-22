#!/usr/bin/env python3
"""RC6: Ed25519 signature, user key pin, downgrade/expiry protections."""
import base64, contextlib, datetime, hashlib, importlib.util, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
TOOL=Path(__file__).with_name('gameweld-trainer-updates.py')
spec=importlib.util.spec_from_file_location('gameweld_rc6_signed',TOOL)
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)

class SignedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.dir/'config'),'XDG_DATA_HOME':str(self.dir/'data')})
        self.env.start();self.addCleanup(self.env.stop)
        self.private=self.dir/'private.pem';self.public=self.dir/'publisher.pem'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(self.private)],check=True,capture_output=True)
        subprocess.run(['openssl','pkey','-in',str(self.private),'-pubout','-out',str(self.public)],check=True,capture_output=True)
        self.fingerprint=u.fingerprint_key(self.public)
        self.e={'id':'control-resonant-update','game':'CONTROL Resonant','provider':'fling','version':'1.4','url':'https://flingtrainer.com/download/control-resonant.exe','sha256':'f'*64}
        now=datetime.datetime.now(datetime.timezone.utc)
        self.doc={'schema':2,'provider':'fling','issued_at':(now-datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'expires_at':(now+datetime.timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'key_fingerprint':self.fingerprint,'entries':[self.e]}
        self.cat=self.dir/'catalog.json'
    def sign(self,doc=None):
        doc=dict(doc or self.doc)
        b=u._signed_payload(doc);msg=self.dir/'message';sig=self.dir/'signature'
        msg.write_bytes(b)
        subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.private),'-rawin','-in',str(msg),'-out',str(sig)],check=True,capture_output=True)
        doc['signature']=base64.b64encode(sig.read_bytes()).decode('ascii')
        self.cat.write_text(json.dumps(doc),'utf-8');return doc
    def pin(self):u.pin_key('fling',self.public,self.fingerprint,True)
    def test_signed_manifest_requires_pinned_key(self):
        self.sign()
        with self.assertRaisesRegex(u.UpdateError,'No independently pinned'):u.read_catalog(self.cat)
    def test_pinned_signed_manifest_verifies_offline(self):
        self.pin();self.sign()
        rows=u.read_catalog(self.cat)
        self.assertEqual(rows[0]['_provenance'],'key-pinned-signature')
        self.assertEqual(rows[0]['_fingerprint'],self.fingerprint)
        self.assertEqual(u.check_catalog('CONTROL Resonant',self.cat)[0]['catalog_provenance'],'key-pinned-signature')
    def test_tampered_entry_rejected(self):
        self.pin();doc=self.sign();doc['entries'][0]['sha256']='0'*64;self.cat.write_text(json.dumps(doc),'utf-8')
        with self.assertRaisesRegex(u.UpdateError,'signature verification failed'):u.read_catalog(self.cat)
    def test_tampered_provider_rejected(self):
        self.pin();doc=self.sign();doc['provider']='hextrainer';self.cat.write_text(json.dumps(doc),'utf-8')
        with self.assertRaises(u.UpdateError):u.read_catalog(self.cat)
    def test_signature_is_not_implicitly_trusted(self):
        self.pin();self.sign();self.assertEqual(u.catalog_audit(self.cat)['catalog_status'],'key-pinned-signature')
    def test_unsupported_private_key_rejected(self):
        with self.assertRaises(u.UpdateError):u.fingerprint_key(self.private)
    def test_wrong_expected_key_fingerprint_rejected(self):
        with self.assertRaisesRegex(u.UpdateError,'does not match'):u.pin_key('fling',self.public,'0'*64,True)
    def test_key_pin_requires_approval(self):
        with self.assertRaisesRegex(u.UpdateError,'approval'):u.pin_key('fling',self.public,self.fingerprint,False)
    def test_key_rotation_is_not_silent(self):
        self.pin();another=self.dir/'other.pem';anotherpub=self.dir/'other.pub'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(another)],check=True,capture_output=True)
        subprocess.run(['openssl','pkey','-in',str(another),'-pubout','-out',str(anotherpub)],check=True,capture_output=True)
        with self.assertRaisesRegex(u.UpdateError,'rotation rejected'):u.pin_key('fling',anotherpub,u.fingerprint_key(anotherpub),True)
    def test_unsigned_downgrade_rejected_when_pinned(self):
        self.pin();self.cat.write_text(json.dumps({'schema':1,'entries':[self.e]}),'utf-8')
        with self.assertRaisesRegex(u.UpdateError,'Unsigned catalog rejected'):u.read_catalog(self.cat)
    def test_legacy_unsigned_works_without_pin(self):
        self.cat.write_text(json.dumps({'schema':1,'entries':[self.e]}),'utf-8')
        self.assertEqual(u.read_catalog(self.cat)[0]['_provenance'],'legacy-unsigned')
    def test_expired_signed_catalog_rejected(self):
        self.pin();doc=dict(self.doc);doc['expires_at']='2020-01-01T00:00:00Z';self.sign(doc)
        with self.assertRaisesRegex(u.UpdateError,'expired'):u.read_catalog(self.cat)
    def test_future_signed_catalog_rejected(self):
        self.pin();doc=dict(self.doc);doc['issued_at']='2090-01-01T00:00:00Z';self.sign(doc)
        with self.assertRaisesRegex(u.UpdateError,'future-dated'):u.read_catalog(self.cat)
    def test_signed_catalog_mixed_providers_rejected(self):
        self.pin();doc=dict(self.doc);doc['entries']=[self.e,dict(self.e,id='other',provider='hextrainer',url='https://hextrainer.com/x.exe')];self.sign(doc)
        with self.assertRaisesRegex(u.UpdateError,'mixes providers'):u.read_catalog(self.cat)
    def test_duplicate_json_keys_rejected(self):
        self.cat.write_text('{"schema":1,"schema":2,"entries":[]}')
        with self.assertRaisesRegex(u.UpdateError,'Duplicate key'):u.read_catalog(self.cat)
    def test_symlinked_key_store_rejected(self):
        path=u.trust_path();path.parent.mkdir(parents=True);path.symlink_to(self.public)
        with self.assertRaisesRegex(u.UpdateError,'Symlinked'):u.read_trust_store()
    def test_unpin_requires_approval(self):
        self.pin()
        with self.assertRaisesRegex(u.UpdateError,'approval'):u.unpin_key('fling')
        u.unpin_key('fling',True)
        self.assertEqual(u.read_trust_store(),{})
    def test_cli_trust_report_and_plain_protocol(self):
        self.pin();self.sign()
        env=os.environ.copy();p=subprocess.run([sys.executable,str(TOOL),'trust-report','--catalog',str(self.cat),'--plain'],env=env,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('TRUST\tkey-pinned-signature\t1\t1',p.stdout)
    def test_import_signed_atomic_with_backup_and_rejects_downgrade(self):
        self.pin();self.sign();old={'schema':1,'entries':[]};target=u.paths()[1]
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(old))
        r=u.import_signed_catalog(self.cat,True)
        self.assertEqual(r['imported'],1)
        self.assertEqual(u.catalog_audit()['catalog_status'],'key-pinned-signature')
        self.assertEqual(json.loads(target.with_name(target.name+'.previous').read_text()),old)
        doc=dict(self.doc);doc['issued_at']='2020-01-01T00:00:00Z';self.sign(doc)
        with self.assertRaisesRegex(u.UpdateError,'expired|rollback'):u.import_signed_catalog(self.cat,True)
        self.assertEqual(u.catalog_audit()['catalog_status'],'key-pinned-signature')
    def test_import_requires_approval(self):
        self.pin();self.sign()
        with self.assertRaisesRegex(u.UpdateError,'approval'):u.import_signed_catalog(self.cat)
    def test_import_rejects_tampered_manifest_without_touching_catalog(self):
        self.pin();doc=self.sign();target=u.paths()[1]
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text('marker')
        doc['entries'][0]['version']='evil';self.cat.write_text(json.dumps(doc))
        with self.assertRaisesRegex(u.UpdateError,'signature'):u.import_signed_catalog(self.cat,True)
        self.assertEqual(target.read_text(),'marker')
    def test_import_rejects_symlink_source(self):
        self.pin();self.sign();bad=self.dir/'link.json';bad.symlink_to(self.cat)
        with self.assertRaisesRegex(u.UpdateError,'Symlinked'):u.import_signed_catalog(bad,True)
    def test_import_same_catalog_is_idempotent(self):
        self.pin();self.sign();u.import_signed_catalog(self.cat,True)
        self.assertEqual(u.import_signed_catalog(self.cat,True)['status'],'already-imported')
    def test_ui_wires_audit_and_displays_provenance(self):
        c=(TOOL.parents[1]/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
        for token in ('Inspect catalog trust (offline)','Pin selected provider key','Import signed catalog','on_audit_trainer_catalog','key-pinned-signature','trust-report','Catalog signature VERIFIED'):
            self.assertIn(token,c)

if __name__=='__main__':unittest.main(verbosity=2)
