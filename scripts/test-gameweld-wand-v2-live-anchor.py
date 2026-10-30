#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for bounded read-only Proton PID liveness validation."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name('gameweld-wand-v2-live-anchor.py')
spec = importlib.util.spec_from_file_location('gameweld_live_anchor', SCRIPT)
assert spec and spec.loader
anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)


def observation(**kw):
    d = dict(appid=3008130, state='linux_game_process_candidate_correlated',
             game_process_candidate_pids=[58638],
             candidate_linux_pid=58638, candidate_start_time_ticks=3641164,
             exact_prefix_identity_crosschecked=True,
             wine_server_pids=[58556], exact_runtime_verified=False,
             game_process_verified=False, monitor_attached=False,
             trainer_attachment_verified=False)
    d.update(kw)
    return d


class AnchorTests(unittest.TestCase):
    def check(self, observations, *, pid=58638, ticks=3641164, samples=None):
        seq = iter(observations)
        self.sleep_count = 0
        def sleep(_seconds):
            self.sleep_count += 1
        return anchor.verify_anchor(3008130, Path('/not/used'), Path('/not/used.exe'),
                                    pid=pid, start_ticks=ticks,
                                    samples=samples or len(observations), interval_ms=0,
                                    inspector=lambda *_: next(seq), sleeper=sleep)

    def test_three_sample_stable_game_candidate(self):
        d = self.check([observation(), observation(), observation()])
        self.assertEqual(d['state'], 'linux_runtime_anchor_stable')
        self.assertEqual(d['samples_completed'], 3)
        self.assertEqual(self.sleep_count, 2)
        self.assertTrue(d['same_prefix_wineserver_observed'])
        self.assertFalse(d['win32_pid_verified'])
        self.assertFalse(d['exact_runtime_verified'])
        self.assertFalse(d['trainer_attachment_verified'])
        self.assertEqual(d['processes_signalled'], 0)

    def test_inspection_appid_mismatch(self):
        d = self.check([observation(appid=20)])
        self.assertEqual(d['reason'], 'inspection_appid_mismatch')

    def test_candidate_set_not_exactly_anchor(self):
        d = self.check([observation(game_process_candidate_pids=[58638, 100])])
        self.assertEqual(d['reason'], 'candidate_set_not_exactly_anchor')

    def test_boolean_pid_rejected(self):
        d = self.check([], pid=True, samples=1)
        self.assertEqual(d['reason'], 'invalid_anchor_or_sampling_parameters')

    def test_linux_pid_switch_fails_closed(self):
        d = self.check([observation(), observation(candidate_linux_pid=12345)])
        self.assertEqual(d['reason'], 'anchored_linux_pid_changed')
        self.assertEqual(d['samples_completed'], 1)

    def test_pid_reuse_fails_closed(self):
        d = self.check([observation(), observation(candidate_start_time_ticks=999)])
        self.assertEqual(d['reason'], 'anchored_linux_process_replaced_or_restarted')

    def test_game_exit_fails_closed(self):
        d = self.check([observation(), observation(state='steam_session_not_verified')])
        self.assertEqual(d['reason'], 'unique_linux_game_candidate_not_present')

    def test_second_game_instance_fails_closed(self):
        d = self.check([observation(state='ambiguous_game_process_candidates')])
        self.assertEqual(d['reason'], 'unique_linux_game_candidate_not_present')

    def test_prefix_not_crosschecked_fails_closed(self):
        d = self.check([observation(exact_prefix_identity_crosschecked=False)])
        self.assertEqual(d['reason'], 'exact_prefix_identity_not_crosschecked')

    def test_missing_wineserver_fails_closed(self):
        d = self.check([observation(wine_server_pids=[])])
        self.assertEqual(d['reason'], 'same_prefix_wineserver_not_observed')

    def test_malformed_wineserver_fails_closed(self):
        d = self.check([observation(wine_server_pids=['hello'])])
        self.assertEqual(d['reason'], 'same_prefix_wineserver_not_observed')

    def test_unexpected_attachment_claim_rejected(self):
        d = self.check([observation(monitor_attached=True)])
        self.assertEqual(d['reason'], 'inspection_crossed_unverified_trust_boundary')

    def test_unexpected_runtime_claim_rejected(self):
        d = self.check([observation(exact_runtime_verified=True)])
        self.assertEqual(d['reason'], 'inspection_crossed_unverified_trust_boundary')

    def test_invalid_pid_fails_closed(self):
        d = self.check([], pid=0, samples=1)
        self.assertEqual(d['reason'], 'invalid_anchor_or_sampling_parameters')

    def test_invalid_start_time_fails_closed(self):
        d = self.check([], ticks=0, samples=1)
        self.assertEqual(d['reason'], 'invalid_anchor_or_sampling_parameters')

    def test_invalid_sample_count_fails_closed(self):
        d = self.check([], samples=31)
        self.assertEqual(d['reason'], 'invalid_anchor_or_sampling_parameters')

    def test_inspector_exception_fails_closed(self):
        def error(*_):
            raise OSError('test only')
        d = anchor.verify_anchor(3008130, Path('/not/used'), Path('/not/used.exe'),
                                 pid=58638, start_ticks=3641164, inspector=error)
        self.assertEqual(d['reason'], 'read_only_process_inspection_failed')

    def test_wrong_response_type_fails_closed(self):
        d = self.check(['not-a-dict'])
        self.assertEqual(d['reason'], 'invalid_inspection_response')

    def test_no_trainer_or_steam_writes_claimed(self):
        d = self.check([observation()])
        self.assertFalse(d['trainer_launched'])
        self.assertFalse(d['steam_configuration_written'])
        self.assertFalse(d['game_prefix_modified'])
        self.assertFalse(d['monitor_attached'])


if __name__ == '__main__':
    unittest.main()
