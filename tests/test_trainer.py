"""Offline end-to-end trainer launcher tests with harmless fake runtimes.

Never execute any commercial trainer, game, real Proton or Wine in CI.
"""
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from gameweld import trainer


def stub_pe(path, machine=0x8664):
    blob = bytearray(1024)
    blob[:2] = b'MZ'
    blob[0x3c:0x40] = (128).to_bytes(4, 'little')
    blob[128:132] = b'PE\x00\x00'
    blob[132:134] = machine.to_bytes(2, 'little')
    blob[152:154] = (0x20b if machine == 0x8664 else 0x10b).to_bytes(2, 'little')
    path.write_bytes(blob)


class TrainerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = self.root / 'Trainer Test.exe'
        stub_pe(self.exe)
        self.steamapps = self.root / 'Steam' / 'steamapps'
        self.steamapps.mkdir(parents=True)
        (self.steamapps / 'appmanifest_3008130.acf').write_text(
            '"AppState" { "appid" "3008130" "name" "Game Under Test" "installdir" "Test" }')
        self.runtime = self.root / 'wine'
        self.runtime.write_text('#!/bin/sh\ntest -r "$1" || exit 45\nsleep 0.15\nexit 0\n')
        self.runtime.chmod(0o700)
        self.staging = self.root / 'private-staging'
        self.staging.mkdir(mode=0o700)
        self.patchers = [
            mock.patch.object(trainer, '_find_wine', return_value=self.runtime),
            mock.patch.object(trainer, '_staging_base', return_value=self.staging),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sha = trainer.inspect_trainer(self.exe)['sha256']

    def test_inspect_pe_x64(self):
        report = trainer.inspect_trainer(self.exe)
        self.assertEqual(report['state'], 'windows_pe_inspected')
        self.assertEqual(report['size_bytes'], 1024)
        self.assertEqual(report['machine'], 'x64')
        self.assertFalse(report['reputation_verified'])

    def test_inspect_pe_x86(self):
        stub_pe(self.exe, 0x14c)
        self.assertEqual(trainer.inspect_trainer(self.exe)['machine'], 'x86')

    def test_refuse_invalid_pe(self):
        self.exe.write_bytes(b'x' * 1024)
        with self.assertRaises(ValueError):
            trainer.inspect_trainer(self.exe)

    def test_refuse_nonexe_extension(self):
        bad = self.root / 'trainer.bin'
        bad.write_bytes(self.exe.read_bytes())
        with self.assertRaises(ValueError):
            trainer.inspect_trainer(bad)

    def test_refuse_symlink(self):
        link = self.root / 'trainer.exe'
        link.symlink_to(self.exe)
        with self.assertRaises(ValueError):
            trainer.inspect_trainer(link)

    def test_preflight_selected_installed_game(self):
        result = trainer.prepare_trainer(self.exe, appid=3008130, steamapps=self.steamapps)
        self.assertEqual(result['state'], 'ready_for_explicit_consent')
        self.assertEqual(result['trainer_sha256'], self.sha)

    def test_preflight_rejects_uninstalled_game(self):
        with self.assertRaises(ValueError):
            trainer.prepare_trainer(self.exe, appid=123, steamapps=self.steamapps)

    def test_launch_requires_explicit_consent(self):
        result = self.run_session(consent=False)
        self.assertEqual(result['state'], 'explicit_consent_required')
        self.assertFalse(result['trainer_process_started'])

    def test_sha256_mismatch_refused(self):
        result = self.run_session(expected_sha256='0' * 64)
        self.assertEqual(result['state'], 'trainer_changed_since_review')
        self.assertFalse(result['trainer_process_started'])

    def test_inspection_launch_is_no_malware_claim(self):
        result = self.run_session()
        self.assertEqual(result['state'], 'trainer_process_exited')
        self.assertTrue(result['trainer_process_started'])
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['owned_launcher_reaped'])
        self.assertFalse(result['trainer_functional_verified'])
        self.assertFalse(result['game_attachment_verified'])
        self.assertFalse(result['steam_modified'])
        self.assertFalse(result['raw_paths_disclosed'])
        self.assertEqual(list(self.staging.iterdir()), [])

    def test_staged_file_matches_prior_hash(self):
        self.exe.write_bytes(self.exe.read_bytes() + b'changed')
        result = self.run_session()
        self.assertEqual(result['state'], 'trainer_changed_since_review')

    def test_rejected_if_original_changes_during_staging(self):
        self.exe.write_bytes(self.exe.read_bytes() + b'modified')
        with self.assertRaises(ValueError):
            trainer._stage_pinned_exe(self.exe, self.root / 'staged.exe', self.sha)

    def test_cancel_before_start(self):
        stop = threading.Event()
        stop.set()
        result = self.run_session(cancel_event=stop)
        self.assertEqual(result['state'], 'cancelled_before_launch')
        self.assertFalse(result['trainer_process_started'])

    def test_proton_prefix_requires_explicit_consent(self):
        result = self.run_session(mode='proton', consent_game_prefix=False)
        self.assertEqual(result['state'], 'game_prefix_consent_required')

    def test_proton_prefix_missing(self):
        with self.assertRaises((ValueError, OSError)):
            trainer.prepare_trainer(self.exe, appid=3008130, mode='proton',
                                    proton=self.root / 'missing-proton', steamapps=self.steamapps)

    def _create_proton(self):
        compat = self.steamapps / 'compatdata' / '3008130'
        (compat / 'pfx' / 'drive_c').mkdir(parents=True)
        proton = self.root / 'proton'
        proton.write_text('#!/bin/sh\n'
                          'test "$1" = run || exit 66\n'
                          'test -r "$2" || exit 65\n'
                          'test -d "$STEAM_COMPAT_DATA_PATH/pfx/drive_c" || exit 67\n'
                          'test "$STEAM_COMPAT_APP_ID" = 3008130 || exit 68\n'
                          'sleep 0.1\nexit 0\n')
        proton.chmod(0o700)
        return proton

    def test_proton_selected_prefix_with_consent(self):
        proton = self._create_proton()
        result = self.run_session(mode='proton', proton=proton, consent_game_prefix=True)
        self.assertEqual(result['state'], 'trainer_process_exited')
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['existing_game_prefix_used'])
        self.assertTrue(result['wine_prefix_may_have_changed'])
        self.assertTrue((self.steamapps / 'compatdata/3008130/pfx/drive_c').is_dir())
        self.assertFalse(result['game_attachment_verified'])

    def test_proton_prefix_symlink_blocked(self):
        proton = self._create_proton()
        c = self.steamapps / 'compatdata' / '3008130'
        c.rename(self.steamapps / 'actual')
        c.symlink_to(self.steamapps / 'actual', target_is_directory=True)
        with self.assertRaises(ValueError):
            trainer.prepare_trainer(self.exe, appid=3008130, mode='proton',
                                    proton=proton, steamapps=self.steamapps)

    def test_timeout_limits_validated(self):
        for timeout in (1, 1801, True, '15'):
            self.assertEqual(self.run_session(timeout=timeout)['state'], 'invalid_timeout')

    def test_launch_does_not_modify_original_exe(self):
        before = self.exe.read_bytes()
        self.run_session()
        self.assertEqual(self.exe.read_bytes(), before)

    def run_session(self, **kwargs):
        arguments = {'appid': 3008130, 'expected_sha256': self.sha,
                     'consent': True, 'steamapps': self.steamapps,
                     'timeout': 10, 'wine_executable': self.runtime}
        arguments.update(kwargs)
        return trainer.run_trainer(self.exe, **arguments)


if __name__ == '__main__':
    unittest.main()
