"""Trainer CLI never launches an unapproved executable."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from gameweld.__main__ import main
from test_trainer import stub_pe


class TrainerCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exe = Path(self.temp.name) / 'Trainer.exe'
        stub_pe(self.exe)

    def invoke(self, *args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc = main(list(args))
        return rc, json.loads(stream.getvalue())

    def test_cli_inspection(self):
        rc, report = self.invoke('--trainer-inspect', str(self.exe))
        self.assertEqual(rc, 0)
        self.assertEqual(report['state'], 'windows_pe_inspected')
        self.assertFalse(report['reputation_verified'])

    def test_cli_no_launch_without_consent(self):
        rc, report = self.invoke('--trainer-launch', str(self.exe), '--trainer-appid', '3008130')
        self.assertEqual(rc, 1)
        self.assertEqual(report['state'], 'explicit_consent_required')
        self.assertFalse(report['trainer_process_started'])

    def test_cli_invalid_trainer(self):
        rc, report = self.invoke('--trainer-inspect', str(self.exe) + '.missing')
        self.assertEqual(rc, 1)
        self.assertFalse(report['trainer_process_started'])

    def test_cli_hash_required(self):
        rc, report = self.invoke('--trainer-launch', str(self.exe), '--trainer-appid', '3008130',
                                  '--consent-trainer-launch')
        self.assertEqual(rc, 1)
        self.assertEqual(report['state'], 'invalid_expected_sha256')


if __name__ == '__main__':
    unittest.main()
