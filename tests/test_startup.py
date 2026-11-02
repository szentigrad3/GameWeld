"""Batch 0.5 read-only timing comparison and weighted trend tests."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gameweld import history, ipc, startup
from test_history import fixture_report

ROOT=Path(__file__).resolve().parents[1]


def verified(starts):
    baseline=fixture_report()
    baseline['runs_requested']=len(starts)
    baseline['runs_completed']=len(starts)
    baseline['attempts']=[copy.deepcopy(baseline['attempts'][0]) for _ in starts]
    for i, ms in enumerate(starts):
        baseline['attempts'][i]['startup_elapsed_ms']=ms
        baseline['attempts'][i]['session_elapsed_ms']=ms+4200
    return baseline


class StartupComparisonTests(unittest.TestCase):
    def test_real_host_numbers_single_new_run_are_inconclusive(self):
        old=history.sanitise_benchmark(verified([9025,6824]))
        new=history.sanitise_benchmark(verified([35247]))
        result=startup.compare_startup(old,new)
        self.assertEqual(result['state'],'single_new_session_inconclusive')
        self.assertAlmostEqual(result['previous_mean_ms'],7924.5)
        self.assertEqual(result['current_mean_ms'],35247)
        self.assertEqual(result['change_ms'],27322.5)
        self.assertAlmostEqual(result['ratio'],4.448,places=3)
        self.assertFalse(result['cause_verified'])
        self.assertTrue(result['single_new_session'])

    def test_multiple_new_runs_are_significant_variation_not_cause(self):
        old=history.sanitise_benchmark(verified([9000,7000]))
        new=history.sanitise_benchmark(verified([35000,34000]))
        r=startup.compare_startup(old,new)
        self.assertEqual(r['state'],'large_startup_variation_observed')
        self.assertFalse(r['cause_verified'])
        self.assertEqual(r['ratio'],4.312)

    def test_small_variation_is_not_regression_claim(self):
        a=history.sanitise_benchmark(verified([9000,8000]))
        b=history.sanitise_benchmark(verified([8500,8000]))
        self.assertEqual(startup.compare_startup(a,b)['state'],'startup_samples_compared')

    def test_forged_summary_rejected(self):
        a=history.sanitise_benchmark(verified([9000]))
        fake=copy.deepcopy(a);fake['attempts'][0]['state']='bad/secret'
        with self.assertRaises(ValueError):startup.compare_startup(a,fake)

    def test_unknown_private_keys_rejected(self):
        a=history.sanitise_benchmark(verified([9000]))
        fake=copy.deepcopy(a);fake['environment']='/home/private/secret'
        with self.assertRaises(ValueError):startup.compare_startup(a,fake)

    def test_old_comparison_does_not_echo_untrusted_text(self):
        for secret in ('/home/test/private/secret','x'*10000):
            with self.assertRaises(ValueError):history.compare_summaries(
                {'startup_mean_ms': secret},{'startup_mean_ms':7900})

    def test_compatibility_with_old_summary_schema(self):
        original=history.sanitise_benchmark(verified([9000]))
        self.assertEqual(history._validated_summary(original),original)
        self.assertNotIn('wine_ready_wait_ms',original)

    def test_no_wine_launch_in_comparison(self):
        a=history.sanitise_benchmark(verified([9000]))
        with patch('gameweld.ipc.run_probe',side_effect=AssertionError('unexpected Wine launch')):
            self.assertEqual(startup.compare_startup(a,a)['ratio'],1)

    def test_report_is_redacted(self):
        a=history.sanitise_benchmark(verified([9000]))
        r=startup.compare_startup(a,a)
        self.assertNotIn('path',repr(r).lower().replace('raw_paths_disclosed',''))
        self.assertFalse(r['raw_stderr_disclosed'])
        self.assertFalse(r['trainer_launched'])
        self.assertFalse(r['detached_helpers_fully_verified'])


class StartupTrendTests(unittest.TestCase):
    def test_weighting_is_by_successful_session_not_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            for group in ([9000,8000,7000],[35000]):
                history.record_summary(history.sanitise_benchmark(verified(group)),path=path)
            trend=startup.startup_trend(path=path)
            self.assertEqual(trend['successful_session_count'],4)
            self.assertEqual(trend['session_weighted_mean_ms'],14750)
            self.assertEqual(trend['session_median_ms'],8500)
            self.assertEqual(trend['latest_vs_earlier_ratio'],4.375)
            self.assertTrue(trend['latest_comparison_is_single_run'])
            report=history.history_report(path=path)
            self.assertEqual(report['startup_session_count'],4)
            self.assertEqual(report['startup_weighted_mean_ms'],14750)
            self.assertNotEqual(report['startup_mean_of_recorded_sessions_ms'],14750)

    def test_empty_history_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'not-yet-created.json'
            trend=startup.startup_trend(path=path)
            self.assertEqual(trend['state'],'no_successful_sessions')
            self.assertFalse(path.exists())

    def test_single_saved_report_no_prior_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            history.record_summary(history.sanitise_benchmark(verified([35247])),path=path)
            r=startup.startup_trend(path=path)
            self.assertIsNone(r['latest_vs_earlier_ratio'])
            self.assertEqual(r['state'],'limited_session_sample')

    def test_symlinked_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            real=Path(tmp)/'data.json'
            real.write_text('{}')
            link=Path(tmp)/'link.json';link.symlink_to(real)
            with self.assertRaises(ValueError):startup.startup_trend(path=link)

    def test_repeated_sessions_have_no_fabricated_speedup_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.json'
            history.record_summary(history.sanitise_benchmark(verified([7000,8000,9000])),path=path)
            r=startup.startup_trend(path=path)
            self.assertFalse(r['cause_verified'])
            self.assertTrue(r['comparison_is_not_causal'])
            self.assertFalse(r['detached_helpers_fully_verified'])


class TimingInstrumentationTests(unittest.TestCase):
    def test_owned_runner_records_spawn_vs_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner=Path(tmp)/'fake-wine'
            runner.write_text(f'''#!{sys.executable}
import sys
print('GW77_READY',flush=True)
for command,prefix in [('PING','GW77_PONG'),('STATUS','GW77_STATUS OK'),('STOP','GW77_STOPPED')]:
    name,nonce=sys.stdin.readline().strip().split()
    if name!=command:sys.exit(2)
    print(prefix+' '+nonce,flush=True)
''')
            runner.chmod(0o700)
            report=ipc._run_once_v2(str(runner),b'owned-test-probe',10)
            self.assertEqual(report['state'],'owned_win64_v2_protocol_verified')
            self.assertIsNotNone(report['launcher_spawn_ms'])
            self.assertIsNotNone(report['wine_ready_wait_ms'])
            self.assertGreaterEqual(report['post_ready_session_ms'],0)
            self.assertLess(report['wine_ready_wait_ms'],report['startup_elapsed_ms']+50)
            self.assertFalse(report['detached_wine_helpers_reaped_verified'])

    def test_noconsent_does_not_invoke_launcher(self):
        with patch('gameweld.ipc._run_once_v2',side_effect=AssertionError('unconsented launch')):
            self.assertEqual(ipc.run_probe(consent=False)['state'],'consent_required')

    def test_benchmark_retains_timing_series_without_game_access(self):
        mock_result={'state':'owned_win64_v2_protocol_verified','startup_elapsed_ms':9000,
                     'launcher_spawn_ms':2.4,'wine_ready_wait_ms':8998,
                     'roundtrip_ms':{'ping':.01,'status':.02,'stop':.03}}
        with patch.object(ipc,'run_probe',return_value=mock_result):
            report=ipc.run_benchmark(consent=True,runs=1)
        self.assertEqual(report['launcher_spawn_ms'],[2.4])
        self.assertEqual(report['wine_ready_wait_ms'],[8998])
        self.assertFalse(report['game_memory_accessed'])


class StartupCLITests(unittest.TestCase):
    def invoke(self,*args):
        env=os.environ.copy()
        with tempfile.TemporaryDirectory() as state:
            env['XDG_STATE_HOME']=state
            cp=subprocess.run([sys.executable,'-m','gameweld',*args],cwd=ROOT,
                              capture_output=True,text=True,timeout=12,env=env)
        return cp.returncode,json.loads(cp.stdout)

    def test_cli_compare_reports_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=Path(tmp)/'old.json';new=Path(tmp)/'new.json'
            old.write_text(json.dumps(verified([9025,6824])))
            new.write_text(json.dumps(verified([35247])))
            code,report=self.invoke('--startup-compare',str(old),str(new))
            self.assertEqual(code,0)
            self.assertEqual(report['state'],'single_new_session_inconclusive')
            self.assertEqual(report['ratio'],4.448)
            self.assertFalse(report['cause_verified'])

    def test_cli_history_trend_does_not_write(self):
        code,report=self.invoke('--startup-trend')
        self.assertEqual(code,0)
        self.assertEqual(report['successful_session_count'],0)

    def test_cli_forged_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/'bad.json';bad.write_text('{not json')
            code,result=self.invoke('--startup-compare',str(bad),str(bad))
            self.assertEqual(code,1)
            self.assertEqual(result['state'],'invalid_or_unreadable_report')

if __name__=='__main__':unittest.main()
