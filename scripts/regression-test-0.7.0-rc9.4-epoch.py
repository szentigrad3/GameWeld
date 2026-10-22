#!/usr/bin/env python3
"""Verify RC9.4 context generation, including A→B→A asynchronous completions."""
import unittest, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'crates/wand-ui/appimage-gtk3/gameweld-native-040.c').read_text()

def section(a,b):
    return SOURCE[SOURCE.index(a):SOURCE.index(b,SOURCE.index(a))]

class EpochGuards(unittest.TestCase):
    def test_completion_guard_precedes_catalog_and_status_handling(self):
        block=section('static gboolean trainer_updates_done(void *user){','static void *trainer_updates_worker(')
        self.assertIn('j->context_epoch!=G.trainer_updates_context_epoch',block)
        self.assertLess(block.index('j->context_epoch!='),block.index('if(j->catalog_id[0])'))
        self.assertIn('trainer_update_disable_staging();',block)
    def test_all_jobs_capture_owner_generation(self):
        block=section('static void start_trainer_update_job(TrainerUpdateJob*j){','static void on_inspect_release_sources(')
        self.assertIn('j->context_epoch=G.trainer_updates_context_epoch;',block)
        self.assertLess(block.index('j->context_epoch='),block.index('pthread_create('))
    def test_new_unassigned_game_resets_provider_to_fling(self):
        block=section('static void trainer_update_context_refresh(void){','static void on_trainer_provider_changed(')
        self.assertIn('const char *default_source="fling";',block)
        self.assertLess(block.index('const char *default_source="fling";'),block.index('if(load_local_trainer('))
        self.assertIn('gtk_combo_box_set_active_id((GtkComboBox*)G.trainer_updates_provider,default_source);',block)
        self.assertIn('G.trainer_updates_context_epoch++;',block)
        self.assertIn('trainer_update_disable_staging();',block)
    def test_both_context_and_invalid_selection_advance_epoch(self):
        block=section('static void trainer_update_context_refresh(void){','static void on_trainer_provider_changed(')
        self.assertEqual(block.count('G.trainer_updates_context_epoch++;'),2)
    def test_busy_check_explains_block(self):
        block=section('static void on_check_trainer_updates(','static void on_audit_trainer_catalog(')
        self.assertIn('if(G.trainer_updates_busy){',block)
        self.assertIn('old result will not apply',block)
    def test_compiled_owner_guard_rejects_aba(self):
        function=section('static int trainer_update_job_matches(','static void trainer_update_disable_staging(')
        fixture=r'''
#include <stdio.h>
#include <string.h>
typedef void GtkComboBox;
typedef struct {char key[320]; char name[512];} Game;
struct {unsigned long long trainer_updates_context_epoch; int selected,game_count; Game games[2]; void *trainer_updates_provider; char provider[64];} G;
const char *game_key(Game *g){return g->key;}
const char *gtk_combo_box_get_active_id(GtkComboBox *cb){(void)cb; return G.provider;}
typedef struct {char game[512],key[320],provider[64]; unsigned long long context_epoch;} TrainerUpdateJob;
'''+function+r'''
int main(void){
  TrainerUpdateJob job={0};G.selected=0;G.game_count=2;G.trainer_updates_provider=&G;
  strcpy(G.games[0].name,"CONTROL Resonant");strcpy(G.games[0].key,"steam:control-resonant");
  strcpy(G.games[1].name,"7 Days to Die");strcpy(G.games[1].key,"steam:7days");
  strcpy(G.provider,"fling");G.trainer_updates_context_epoch=10;
  strcpy(job.game,"CONTROL Resonant");strcpy(job.key,"steam:control-resonant");strcpy(job.provider,"fling");job.context_epoch=10;
  if(!trainer_update_job_matches(&job))return 1;
  G.selected=1;strcpy(G.provider,"hextrainer");G.trainer_updates_context_epoch=11;
  if(trainer_update_job_matches(&job))return 2;
  G.selected=0;strcpy(G.provider,"fling");G.trainer_updates_context_epoch=12;
  if(trainer_update_job_matches(&job))return 3; /* A-B-A: identical key is NOT enough */
  job.context_epoch=12;if(!trainer_update_job_matches(&job))return 4;
  strcpy(job.provider,"hextrainer");if(trainer_update_job_matches(&job))return 5;
  strcpy(job.provider,"fling");strcpy(job.key,"steam:control");if(trainer_update_job_matches(&job))return 6;
  strcpy(job.key,"steam:control-resonant");G.selected=-1;if(trainer_update_job_matches(&job))return 7;
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'test.c';exe=Path(d)/'test';src.write_text(fixture)
            c=subprocess.run(['gcc','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(c.returncode,0,c.stderr)
            run=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
