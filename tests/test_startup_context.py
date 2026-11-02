"""User-confirmed bootstrap context, format preservation and fail-closed history tests."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gameweld import history, startup

ROOT = Path(__file__).resolve().parents[1]


def report(values):
    attempts=[]
    for ms in values:
        attempts.append({
            'state': 'owned_win64_v2_protocol_verified',
            'ready_verified': True, 'ping_pong_verified': True,
            'status_verified': True, 'stop_ack_verified': True,
            'launcher_exit_zero': True, 'owned_launcher_reaped': True,
            'temporary_prefix_cleanup_verified': True,
            'startup_elapsed_ms': ms, 'session_elapsed_ms': ms+1000,
            'roundtrip_ms': {'ping': .02, 'status': .01, 'stop': .02},
            'observed_helper_review': {'observed_identities': 1,
                                       'observed_identities_absent_twice': True},
            'error_category': 'none'})
    return {'operation':'gameweld-ipc-benchmark', 'schema_version': 1,
            'state': 'isolated_ipc_benchmark_verified',
            'runs_requested':len(attempts), 'runs_completed':len(attempts),
            'attempts':attempts}

class ContextTests(unittest.TestCase):
    def test_context_allowlist(self):
        for item in history.STARTUP_CONTEXTS:
            self.assertEqual(history.validate_context(item), item)
        for item in ('/tmp/secrets','mono install',42,False,'mono_setup\nTOKEN=abc', None):
            with self.assertRaises(ValueError): history.validate_context(item)

    def test_monoinstall_excluded_only_after_explicit_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            older=history.sanitise_benchmark(report([9025,6824]))
            mono=history.sanitise_benchmark(report([35247]))
            history.record_summary(older,path=path)
            history.record_summary(mono,path=path)
            before=startup.startup_trend(path=path)
            self.assertEqual(before['successful_session_count'], 3)
            self.assertAlmostEqual(before['session_weighted_mean_ms'],(9025+6824+35247)/3,places=3)
            self.assertAlmostEqual(before['latest_vs_earlier_ratio'],4.448,places=3)
            result=history.annotate_summary(mono,'mono_setup',path=path)
            self.assertEqual(result['state'],'context_recorded')
            after=startup.startup_trend(path=path)
            self.assertEqual(after['successful_session_count'],3)
            self.assertEqual(after['comparable_session_count'],2)
            self.assertEqual(after['comparable_mean_ms'],7924.5)
            self.assertEqual(after['confirmed_setup_session_count'],1)
            self.assertEqual(after['confirmed_setup_mean_ms'],35247)
            self.assertTrue(after['latest_comparison_suppressed_setup'])
            self.assertIsNone(after['latest_vs_earlier_ratio'])
            self.assertFalse(after['cause_verified'])
            self.assertEqual(history.load_history(path)[-1]['summary'],mono)

    def test_old_history_without_context_remains_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            one=history.sanitise_benchmark(report([6000]))
            history.record_summary(one,path=path)
            original=json.loads(path.read_text())
            del original['entries'][0]['startup_context']
            path.write_text(json.dumps(original))
            loaded=history.load_history(path)
            self.assertEqual(loaded[0]['startup_context'],'unclassified')
            self.assertEqual(startup.startup_trend(path=path)['comparable_session_count'],1)
            history.annotate_summary(one,'mono_setup',path=path)
            self.assertEqual(history.load_history(path)[0]['startup_context'],'mono_setup')

    def test_other_context_categories_group_as_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            history.record_summary(history.sanitise_benchmark(report([9000])),path=path,startup_context='routine')
            history.record_summary(history.sanitise_benchmark(report([12000])),path=path,startup_context='gecko_setup')
            history.record_summary(history.sanitise_benchmark(report([14000])),path=path,startup_context='other_setup')
            result=startup.startup_trend(path=path)
            self.assertEqual(result['comparable_session_count'],1)
            self.assertEqual(result['confirmed_setup_session_count'],2)
            self.assertEqual(result['routine_labelled_sessions'],1)
            self.assertEqual(result['latest_report_startup_context'],'other_setup')

    def test_dedup_does_not_override_existing_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json';val=history.sanitise_benchmark(report([7000]))
            history.record_summary(val,path=path,startup_context='mono_setup')
            again=history.record_summary(val,path=path,startup_context='routine')
            self.assertEqual(again['state'],'already_recorded')
            self.assertEqual(history.load_history(path)[0]['startup_context'],'mono_setup')

    def test_annotation_requires_recorded_exact_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json';val=history.sanitise_benchmark(report([7000]))
            history.record_summary(val,path=path)
            original=path.read_bytes()
            other=history.sanitise_benchmark(report([8000]))
            self.assertEqual(history.annotate_summary(other,'mono_setup',path=path)['state'],'summary_not_recorded')
            self.assertEqual(original,path.read_bytes())
            forged=copy.deepcopy(val);forged['id']='0'*20
            with self.assertRaises(ValueError):history.annotate_summary(forged,'mono_setup',path=path)
            self.assertEqual(original,path.read_bytes())

    def test_symlink_history_blocks_annotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hist.json';link=Path(tmp)/'link.json'
            val=history.sanitise_benchmark(report([9000]))
            history.record_summary(val,path=path);link.symlink_to(path)
            with self.assertRaises(ValueError):history.annotate_summary(val,'mono_setup',path=link)
            self.assertEqual(history.load_history(path)[0]['startup_context'],'unclassified')

    def test_unknown_entry_field_and_context_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hist.json'
            history.record_summary(history.sanitise_benchmark(report([9000])),path=path)
            original=json.loads(path.read_text())
            for k,v in [('secret','ABC'),('startup_context','../bad')]:
                obj=copy.deepcopy(original)
                obj['entries'][0][k]=v
                path.write_text(json.dumps(obj))
                with self.assertRaises(ValueError):history.load_history(path)

    def test_history_report_discloses_only_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'hist.json';one=history.sanitise_benchmark(report([6000]))
            history.record_summary(one,path=path,startup_context='mono_setup')
            result=history.history_report(path=path)
            self.assertEqual(result['contexts']['mono_setup'],1)
            self.assertEqual(result['records'][0]['startup_context'],'mono_setup')
            self.assertFalse(result['raw_paths_disclosed'])
            self.assertNotIn(str(path),json.dumps(result))

    def test_empty_and_setup_only_histories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            self.assertEqual(startup.startup_trend(path=path)['state'],'no_successful_sessions')
            history.record_summary(history.sanitise_benchmark(report([34000])),path=path,startup_context='mono_setup')
            self.assertEqual(startup.startup_trend(path=path)['state'],'setup_only_session_history')

    def test_actual_cli_annotation_without_wine(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state'
            raw=Path(tmp)/'run.json';raw.write_text(json.dumps(report([35247])))
            env=os.environ.copy();env['XDG_STATE_HOME']=str(state)
            def call(*args):
                return subprocess.run([sys.executable,'-m','gameweld',*args],cwd=ROOT,env=env,
                                      text=True,capture_output=True,timeout=12)
            imported=call('--record-benchmark',str(raw))
            self.assertEqual(imported.returncode,0,imported.stderr)
            marked=call('--annotate-benchmark',str(raw),'--startup-context','mono_setup')
            self.assertEqual(marked.returncode,0,marked.stderr)
            self.assertEqual(json.loads(marked.stdout)['state'],'context_recorded')
            trend=json.loads(call('--startup-trend').stdout)
            self.assertEqual(trend['confirmed_setup_session_count'],1)
            self.assertEqual(trend['comparable_session_count'],0)
            self.assertEqual(trend['latest_report_startup_context'],'mono_setup')

    def test_no_untrusted_context_in_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state';env=os.environ.copy();env['XDG_STATE_HOME']=str(state)
            run=subprocess.run([sys.executable,'-m','gameweld','--startup-context','/etc/shadow','--startup-trend'],
                               cwd=ROOT,env=env,text=True,capture_output=True,timeout=8)
            self.assertNotEqual(run.returncode,0)
            self.assertFalse(state.exists())

if __name__=='__main__': unittest.main()

class LatestContextTests(unittest.TestCase):
    def test_latest_only_and_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            old=history.sanitise_benchmark(report([4000]))
            newer=history.sanitise_benchmark(report([35000]))
            history.record_summary(old,path=path)
            history.record_summary(newer,path=path)
            value=history.annotate_latest('mono_setup',path=path)
            self.assertEqual(value['state'],'context_recorded')
            self.assertEqual(value['id'],newer['id'])
            entries=history.load_history(path)
            self.assertEqual(entries[0]['startup_context'],'unclassified')
            self.assertEqual(entries[1]['startup_context'],'mono_setup')
            self.assertEqual(entries[1]['summary'],newer)

    def test_no_history_no_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'missing.json'
            self.assertEqual(history.annotate_latest('mono_setup',path=path)['state'],'no_saved_benchmarks')
            self.assertFalse(path.exists())

    def test_cli_annotate_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state'
            raw=Path(tmp)/'bench.json';raw.write_text(json.dumps(report([35247])))
            env=os.environ.copy();env['XDG_STATE_HOME']=str(state)
            def invoke(*args):
                return subprocess.run([sys.executable,'-m','gameweld',*args],cwd=ROOT,env=env,
                                      capture_output=True,text=True,timeout=12)
            self.assertEqual(invoke('--record-benchmark',str(raw)).returncode,0)
            response=invoke('--annotate-latest','--startup-context','mono_setup')
            self.assertEqual(response.returncode,0,response.stderr)
            self.assertEqual(json.loads(response.stdout)['state'],'context_recorded')
            trend=json.loads(invoke('--startup-trend').stdout)
            self.assertEqual(trend['confirmed_setup_session_count'],1)
