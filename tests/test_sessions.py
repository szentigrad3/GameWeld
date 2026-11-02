"""Batch 0.3.0: conservative benchmark and helper identity safety tests."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from gameweld import helpers, ipc


class HelperReviewTests(unittest.TestCase):
    def test_invalid_prefix_and_identity_are_rejected(self):
        with self.assertRaises(ValueError):
            helpers.snapshot_active('relative-prefix', owned_pgid=10)
        with self.assertRaises(ValueError):
            helpers.snapshot_active('/tmp/owned', owned_pgid=0)
        with self.assertRaises(ValueError):
            helpers.identity_states([(1, 2)])

    def test_review_no_snapshot_never_proves_cleanup(self):
        result = helpers.review(None)
        self.assertFalse(result['all_detached_helpers_reaped_verified'])
        self.assertFalse(result['observed_identities_absent_twice'])

    def test_review_absent_identity_not_global_reaping(self):
        active = {'ids': {(999999999, 1)}, 'unreadable': 2,
                  'truncated': False, 'available': True}
        with patch.object(helpers, 'identity_states', return_value={
            'gone': 1, 'live': 0, 'zombie': 0, 'unknown': 0}), \
             patch.object(helpers.time, 'sleep', return_value=None):
            result = helpers.review(active)
        self.assertTrue(result['observed_identities_absent_twice'])
        self.assertFalse(result['all_detached_helpers_reaped_verified'])
        self.assertEqual(result['active_census_env_unreadable'], 2)
        self.assertNotIn('ids', result)

    def test_proc_identity_missing_is_unknown(self):
        with patch.object(helpers, '_proc_identity', side_effect=PermissionError):
            self.assertEqual(helpers.identity_states({(12, 900)})['unknown'], 1)

    def test_proc_identity_recycled_is_gone(self):
        with patch.object(helpers, '_proc_identity', return_value=(12, 901, b'S')):
            self.assertEqual(helpers.identity_states({(12, 900)})['gone'], 1)


class BenchmarkTests(unittest.TestCase):
    def test_no_consent_never_calls_runner(self):
        with patch.object(ipc, 'run_probe', side_effect=AssertionError('must not run')):
            result = ipc.run_benchmark(consent=False, runs=3)
        self.assertEqual(result['state'], 'consent_required')
        self.assertEqual(result['runs_completed'], 0)

    def test_invalid_run_counts(self):
        for value in (True, 0, 4, -1, 2.1, '2'):
            with self.assertRaises(ValueError):
                ipc.run_benchmark(consent=True, runs=value)

    def test_success_three_runs_and_aggregate(self):
        times = iter([20722, 6696, 7529])
        def success(**_):
            startup = next(times)
            return {'state':'owned_win64_v2_protocol_verified',
                    'startup_elapsed_ms':startup,
                    'roundtrip_ms':{'ping': 0.3, 'status':0.4, 'stop':0.2},
                    'detached_wine_helpers_reaped_verified':False}
        with patch.object(ipc, 'run_probe', side_effect=success) as runner:
            report = ipc.run_benchmark(consent=True, runs=3)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(report['state'], 'isolated_ipc_benchmark_verified')
        self.assertEqual(report['startup_min_ms'], 6696)
        self.assertEqual(report['startup_max_ms'], 20722)
        self.assertEqual(report['startup_mean_ms'], 11649.0)
        self.assertFalse(report['detached_wine_helpers_reaped_verified'])

    def test_cancel_without_launch(self):
        event=threading.Event()
        event.set()
        with patch.object(ipc, 'run_probe', side_effect=AssertionError('not launched')):
            report=ipc.run_benchmark(consent=True,runs=2,cancel_event=event)
        self.assertEqual(report['state'],'isolated_ipc_benchmark_cancelled')
        self.assertEqual(report['runs_completed'],0)

    def test_cancel_owned_fixture_reaps_it(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            runner=Path(tmp)/'owned-fake-wine'
            runner.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(20)\n")
            runner.chmod(0o700)
            event=threading.Event()
            event.set()
            result=ipc._run_once_v2(str(runner),b'no-windows-image',5,cancel_event=event)
        self.assertEqual(result['error_category'],'cancelled')
        self.assertTrue(result['owned_launcher_reaped'])
        self.assertTrue(result['temporary_prefix_cleanup_verified'])
        self.assertFalse(result['detached_wine_helpers_reaped_verified'])

    def test_fails_closed_after_first_failure(self):
        success = {'state':'owned_win64_v2_protocol_verified','startup_elapsed_ms':7000,
                   'roundtrip_ms':{}}
        failed = {'state':'owned_win64_v2_protocol_failed','startup_elapsed_ms':None,
                  'roundtrip_ms':{},'error_category':'timeout'}
        with patch.object(ipc, 'run_probe', side_effect=[success,failed,AssertionError('3rd not called')]) as runner:
            report=ipc.run_benchmark(consent=True,runs=3)
        self.assertEqual(runner.call_count, 2)
        self.assertFalse(report['all_protocols_verified'])
        self.assertEqual(report['runs_completed'], 2)

    def test_simulated_real_session_retains_no_private_data(self):
        # Test the existing owned, byte-bounded protocol supervisor with a
        # simulated Wine child. This is not a real Windows fixture test.
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            runner=Path(tmp)/'owned-fake-wine'
            runner.write_text(f'''#!{sys.executable}
import sys
print('GW77_READY', flush=True)
for name,prefix in [('PING','GW77_PONG'),('STATUS','GW77_STATUS OK'),('STOP','GW77_STOPPED')]:
    command,nonce=sys.stdin.readline().strip().split()
    if command!=name:sys.exit(2)
    print(prefix+' '+nonce, flush=True)
''')
            runner.chmod(0o700)
            result=ipc._run_once_v2(str(runner),b'not-a-real-fixture',12)
        self.assertEqual(result['state'],'owned_win64_v2_protocol_verified',result)
        self.assertGreaterEqual(result['startup_elapsed_ms'],0)
        self.assertGreaterEqual(result['session_elapsed_ms'],result['startup_elapsed_ms'])
        self.assertIn('observed_helper_review',result)
        self.assertFalse(result['detached_wine_helpers_reaped_verified'])
        self.assertNotIn('WINEPREFIX=',repr(result))

if __name__=='__main__':unittest.main()
