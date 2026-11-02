"""Exercise the real command-line history workflow without launching Wine."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from test_history import fixture_report

ROOT = Path(__file__).resolve().parents[1]

class HistoryCliTests(unittest.TestCase):
    def cli(self, *args, state_root):
        env = os.environ.copy()
        env['XDG_STATE_HOME'] = str(state_root)
        result=subprocess.run([sys.executable, '-m', 'gameweld', *args],
                              cwd=ROOT, env=env, text=True, capture_output=True,
                              timeout=8, check=False)
        return result.returncode, json.loads(result.stdout)

    def test_review_record_duplicate_list_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            report=root/'report.json'
            report.write_text(json.dumps(fixture_report()))
            rc, review = self.cli('--review-benchmark', str(report), state_root=root)
            self.assertEqual(rc,0)
            self.assertEqual(review['startup_mean_ms'],7900.0)
            self.assertNotIn('SENSITIVE',str(review))
            self.assertFalse((root/'gameweld').exists())
            rc, imported = self.cli('--record-benchmark',str(report),state_root=root)
            self.assertEqual(rc,0)
            self.assertEqual(imported['state'],'summary_recorded')
            rc, duplicate = self.cli('--record-benchmark',str(report),state_root=root)
            self.assertEqual(duplicate['state'],'already_recorded')
            rc, history = self.cli('--history',state_root=root)
            self.assertEqual(history['record_count'],1)
            self.assertEqual(history['success_count'],1)
            rc, comparison = self.cli('--compare-benchmarks',str(report),str(report),state_root=root)
            self.assertEqual(rc,0)
            self.assertEqual(comparison['change_ms'],0)
            self.assertTrue(comparison['comparison_is_not_causal'])
            self.assertNotIn(str(root),json.dumps(history))

    def test_invalid_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, result=self.cli('--review-benchmark',str(Path(tmp)/'missing.json'),state_root=tmp)
            self.assertEqual(rc,1)
            self.assertEqual(result['state'],'invalid_or_unreadable_report')

    def test_save_history_requires_live_benchmark_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=os.environ.copy();env['XDG_STATE_HOME']=tmp
            result=subprocess.run([sys.executable,'-m','gameweld','--history','--save-history'],
                                  cwd=ROOT,env=env,text=True,capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('--save-history',result.stderr)

    def test_no_consent_never_records_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, report=self.cli('--ipc-benchmark','--runs','2','--save-history',state_root=tmp)
            self.assertEqual(rc,1)
            self.assertEqual(report['state'],'consent_required')
            self.assertFalse((Path(tmp)/'gameweld').exists())

if __name__=='__main__':unittest.main()
