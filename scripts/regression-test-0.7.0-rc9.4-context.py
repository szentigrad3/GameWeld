#!/usr/bin/env python3
"""RC9.4 scoped publisher UI and offline catalog protocol tests."""
import json, subprocess, tempfile, os, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()
SCRIPT=ROOT/'scripts/gameweld-trainer-updates.py'
def part(a,b):return S[S.index(a):S.index(b,S.index(a))]

class ContextSafety(unittest.TestCase):
 def test_refresh_invalidates_on_exact_game_key_or_provider(self):
  b=part('static void trainer_update_context_refresh(void){','static void on_trainer_provider_changed')
  self.assertIn('strcmp(G.trainer_updates_context_key,selected_key)',b)
  self.assertIn('strcmp(G.trainer_updates_context_provider,provider?provider:"")',b)
  self.assertIn('trainer_update_disable_staging();',b)
  self.assertIn('Not checked for %s with %s',b)
 def test_refresh_ui_covers_library_navigation(self):
  b=part('static void refresh_ui(void) {','static void on_health(')
  self.assertIn('trainer_update_context_refresh();',b)
 def test_late_async_results_are_ignored(self):
  b=part('static gboolean trainer_updates_done(void *user){','static void *trainer_updates_worker(')
  self.assertIn('j->context_epoch!=G.trainer_updates_context_epoch',b)
  self.assertIn('j->key[0]&&!trainer_update_job_matches(j)',b)
  self.assertLess(b.index('trainer_update_job_matches(j)'),b.index('if(j->catalog_id[0])'))
 def test_owner_snapshot_before_thread_launch(self):
  b=part('static void start_trainer_update_job(TrainerUpdateJob*j){','static void on_inspect_release_sources(')
  self.assertIn('game_key(&G.games[G.selected])',b)
  self.assertIn('gtk_combo_box_get_active_id',b)
  self.assertLess(b.index('snprintf(j->key'),b.index('pthread_create('))
 def test_no_all_provider_query(self):
  b=part('static int trainer_updates_command(TrainerUpdateJob*j','static int trainer_update_job_matches(')
  self.assertNotIn('"--all-providers"',b)
  self.assertIn('"--catalog-provider",j->provider',b)
  self.assertIn('"--official","--provider",j->provider',b)
 def test_disabled_staging_by_default_and_context(self):
  b=part('static int trainer_update_staging_matches(void){','static gboolean trainer_updates_done(')
  for x in ['G.trainer_updates_ready_key','G.trainer_updates_ready_provider','G.trainer_updates_game']:
   self.assertIn(x,b)
  for cb in ['static void on_install_verified_trainer(','static void on_staged_trainer_action(']:
   self.assertIn('if(!trainer_update_staging_matches()){',S[S.index(cb):S.index('start_trainer_update_job(j);',S.index(cb))])
 def test_labels_disambiguate_evidence(self):
  for x in ['Not checked for %s with %s','Checking publisher sources','Publisher page found for %s','Catalog entry available for review']:
   self.assertIn(x,S)
 def test_offline_multi_provider_filter_cli(self):
  with tempfile.TemporaryDirectory() as d:
   catalog=Path(d)/'catalog.json'
   catalog.write_text(json.dumps({'schema':1,'entries':[
    {'id':'fling-demo','game':'CONTROL Resonant','provider':'fling','version':'1.0','url':'https://flingtrainer.com/f.zip','sha256':'a'*64},
    {'id':'hex-demo','game':'CONTROL Resonant','provider':'hextrainer','version':'1.1','url':'https://hextrainer.com/h.zip','sha256':'b'*64},
    {'id':'other-demo','game':'CONTROL','provider':'fling','version':'1.5','url':'https://flingtrainer.com/other.zip','sha256':'c'*64}] }))
   env=dict(os.environ,XDG_CONFIG_HOME=d+'/cfg',XDG_DATA_HOME=d+'/data')
   for provider,expected,forbidden in [('fling','fling-demo','hex-demo'),('hextrainer','hex-demo','fling-demo')]:
    cmd=[sys.executable,str(SCRIPT),'check','--game','CONTROL Resonant','--catalog',str(catalog),'--plain','--provider',provider,'--catalog-provider',provider]
    run=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
    self.assertEqual(run.returncode,0,run.stderr)
    self.assertIn(expected,run.stdout)
    self.assertNotIn(forbidden,run.stdout)
    self.assertNotIn('other-demo',run.stdout)
   # Prior clients using no provider filter still receive every matching catalog entry.
   old=subprocess.run([sys.executable,str(SCRIPT),'check','--game','CONTROL Resonant','--catalog',str(catalog),'--plain'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
   self.assertEqual(old.returncode,0,old.stderr)
   self.assertIn('fling-demo',old.stdout)
   self.assertIn('hex-demo',old.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
