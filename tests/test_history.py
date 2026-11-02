"""History has an explicit persist gate and a privacy-preserving allowlist."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gameweld import history


SOURCE = Path('/mnt/data/gameweld-desktop-030-benchmark.json')


def fixture_report():
    return {
        'operation': 'gameweld-ipc-benchmark', 'schema_version': 1,
        'state': 'isolated_ipc_benchmark_verified', 'runs_requested': 2,
        'runs_completed': 2, 'secret': '/home/test/private/file',
        'attempts': [
            {'state': 'owned_win64_v2_protocol_verified', 'ready_verified': True,
             'ping_pong_verified': True, 'status_verified': True, 'stop_ack_verified': True,
             'launcher_exit_zero': True, 'owned_launcher_reaped': True,
             'temporary_prefix_cleanup_verified': True,
             'startup_elapsed_ms': 9000, 'session_elapsed_ms': 13000,
             'roundtrip_ms': {'ping': .02, 'status': .03, 'stop': .01},
             'observed_helper_review': {'observed_identities': 1,
                                        'observed_identities_absent_twice': True,
                                        'untrusted': '/tmp/prefix'},
             'raw_env': 'SENSITIVE=secret', 'error_category': 'none'},
            {'state': 'owned_win64_v2_protocol_verified', 'ready_verified': True,
             'ping_pong_verified': True, 'status_verified': True, 'stop_ack_verified': True,
             'launcher_exit_zero': True, 'owned_launcher_reaped': True,
             'temporary_prefix_cleanup_verified': True,
             'startup_elapsed_ms': 6800, 'session_elapsed_ms': 11000,
             'roundtrip_ms': {'ping': .025, 'status': .02, 'stop': .015},
             'observed_helper_review': {'observed_identities': 1,
                                        'observed_identities_absent_twice': True},
             'error_category': 'none'}]
    }


class HistoryTests(unittest.TestCase):
    def test_sanitise_and_aggregate(self):
        clean=history.sanitise_benchmark(fixture_report())
        self.assertEqual(clean['startup_mean_ms'],7900)
        self.assertEqual(clean['startup_min_ms'],6800)
        self.assertEqual(clean['startup_max_ms'],9000)
        self.assertEqual(clean['successful_runs'],2)
        self.assertFalse(clean['detached_helpers_fully_verified'])
        self.assertNotIn('SENSITIVE',repr(clean))
        self.assertNotIn('/tmp/prefix',repr(clean))
        self.assertNotIn('/home/test',repr(clean))

    def test_history_file_permissions_and_dedup(self):
        summary=history.sanitise_benchmark(fixture_report())
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'state'/'benchmarks.json'
            one=history.record_summary(summary,path=path)
            two=history.record_summary(summary,path=path)
            self.assertEqual(one['state'],'summary_recorded')
            self.assertEqual(two['state'],'already_recorded')
            self.assertEqual(len(history.load_history(path)),1)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
            stored=path.read_text()
            self.assertNotIn('SENSITIVE',stored)
            self.assertNotIn('/tmp/prefix',stored)
            self.assertNotIn('secret',stored)
            rep=history.history_report(path=path)
            self.assertEqual(rep['record_count'],1)
            self.assertEqual(rep['success_count'],1)

    def test_refuses_unknown_nested_data(self):
        summary=history.sanitise_benchmark(fixture_report())
        bad=copy.deepcopy(summary)
        bad['attempts'][0]['wine_environment']='secret'
        with self.assertRaises(ValueError):history.record_summary(bad)

    def test_rejects_summary_forged_hash(self):
        summary=history.sanitise_benchmark(fixture_report())
        summary['id']='0'*20
        with self.assertRaises(ValueError):history.record_summary(summary)

    def test_bad_json_unreadable(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'broken.json'
            path.write_text('{oops')
            with self.assertRaises(ValueError):history.read_report(path)

    def test_benchmark_file_cannot_be_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            real=Path(root)/'report.json'
            real.write_text(json.dumps(fixture_report()))
            link=Path(root)/'link.json';link.symlink_to(real)
            with self.assertRaises(ValueError):history.read_report(link)

    def test_history_destination_cannot_be_symlink(self):
        summary=history.sanitise_benchmark(fixture_report())
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'existing.json';target.write_text('keep')
            link=Path(root)/'benchmarks.json';link.symlink_to(target)
            with self.assertRaises(ValueError):history.record_summary(summary,path=link)
            self.assertEqual(target.read_text(),'keep')

    def test_history_corruption_does_not_overwrite(self):
        summary=history.sanitise_benchmark(fixture_report())
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'benchmarks.json';path.write_text('bad json')
            with self.assertRaises(ValueError):history.record_summary(summary,path=path)
            self.assertEqual(path.read_text(),'bad json')

    def test_success_claim_requires_evidence(self):
        broken=fixture_report()
        broken['attempts'][0]['stop_ack_verified']=False
        with self.assertRaises(ValueError):history.sanitise_benchmark(broken)

    def test_report_count_is_consistent(self):
        broken=fixture_report()
        broken['runs_completed']=3
        with self.assertRaises(ValueError):history.sanitise_benchmark(broken)

    def test_invalid_types_are_rejected(self):
        for state in ([], {}, 1, None):
            payload=fixture_report();payload['state']=state
            with self.assertRaises(ValueError):history.sanitise_benchmark(payload)
        payload=fixture_report();payload['attempts'][0]['state']=[]
        with self.assertRaises(ValueError):history.sanitise_benchmark(payload)

    def test_comparison_is_not_causal(self):
        a=history.sanitise_benchmark(fixture_report())
        b=copy.deepcopy(a);b['startup_mean_ms']=6000.0
        comp=history.compare_summaries(a,b)
        self.assertEqual(comp['change_ms'],-1900)
        self.assertTrue(comp['faster'])
        self.assertTrue(comp['comparison_is_not_causal'])

    @unittest.skipUnless(SOURCE.exists(),'prior host report not mounted')
    def test_prior_actual_host_report(self):
        source=history.read_report(SOURCE)
        self.assertEqual(source['startup_mean_ms'],7924.5)
        self.assertEqual(source['successful_runs'],2)
        self.assertFalse(source['detached_helpers_fully_verified'])
        self.assertTrue(all(x['observed_absent_twice'] for x in source['attempts']))

    def test_does_not_touch_wine_without_command(self):
        with patch('gameweld.ipc.run_benchmark',side_effect=AssertionError('wine invoked')):
            with tempfile.TemporaryDirectory() as root:
                path=Path(root)/'benchmarks.json'
                report=history.history_report(path=path)
                self.assertEqual(report['record_count'],0)

if __name__=='__main__':unittest.main()
