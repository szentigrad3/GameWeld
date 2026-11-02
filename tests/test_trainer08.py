"""0.8.0 trainer integration checks. All runtime executables here are local harmless scripts."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from gameweld import trainer


def write_pe(path):
    data = bytearray(1024)
    data[:2] = b'MZ'
    data[0x3c:0x40] = (128).to_bytes(4, 'little')
    data[128:132] = b'PE\0\0'
    data[132:134] = (0x8664).to_bytes(2, 'little')
    data[152:154] = (0x20b).to_bytes(2, 'little')
    path.write_bytes(data)


class UsableTrainerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.exe = self.root/'Trusted.exe'
        write_pe(self.exe)
        self.sha = trainer.inspect_trainer(self.exe)['sha256']
        self.steamapps = self.root/'Steam'/'steamapps'
        self.steamapps.mkdir(parents=True)
        (self.steamapps/'appmanifest_123456.acf').write_text(
            '"AppState" { "appid" "123456" "name" "Safe Offline Game" "installdir" "Game" }')
        self.runtime = self.root/'wine'
        self.private = self.root/'staging'
        self.private.mkdir(mode=0o700)
        for name, value in [('_find_wine', lambda: self.runtime),
                            ('_staging_base', lambda: self.private)]:
            p = mock.patch.object(trainer, name, value)
            p.start()
            self.addCleanup(p.stop)

    def runtime_script(self, body):
        self.runtime.write_text('#!/bin/sh\n' + body + '\n')
        self.runtime.chmod(0o700)

    def run_test(self, **kw):
        args = dict(appid=123456, expected_sha256=self.sha, consent=True,
                    wine_executable=self.runtime, steamapps=self.steamapps, timeout=10)
        args.update(kw)
        return trainer.run_trainer(self.exe, **args)

    def test_stdout_stderr_counted_no_content(self):
        self.runtime_script('echo "Hello private name and path"; echo "err:module:import_dll missing" >&2; exit 3')
        report = self.run_test()
        self.assertEqual(report['state'], 'trainer_process_failed')
        self.assertEqual(report['exit_code'], 3)
        self.assertGreater(report['stderr_bytes_observed'], 0)
        self.assertGreater(report['stdout_bytes_observed'], 0)
        self.assertIn('missing_dll_hint', report['diagnostic_hints'])
        self.assertNotIn('private name', str(report))
        self.assertFalse(report['windows_trainer_process_verified'])
        self.assertEqual(list(self.private.iterdir()), [])

    def test_output_spam_stops_own_launcher(self):
        self.runtime_script('yes WARNING')
        report = self.run_test()
        self.assertEqual(report['state'], 'output_limit_stopped')
        self.assertTrue(report['output_limit_reached'])
        self.assertTrue(report['owned_launcher_reaped'])

    def test_stop_running_trainer(self):
        self.runtime_script('sleep 8')
        cancel = threading.Event()
        threading.Timer(0.2, cancel.set).start()
        report = self.run_test(cancel_event=cancel)
        self.assertEqual(report['state'], 'cancelled')
        self.assertTrue(report['owned_launcher_reaped'])
        self.assertLess(report['elapsed_ms'], 5000)

    def test_rejected_binary_never_spawns(self):
        self.runtime_script('echo never')
        result = self.run_test(expected_sha256='0'*64)
        self.assertEqual(result['state'], 'trainer_changed_since_review')
        self.assertFalse(result['trainer_process_started'])

    def test_companion_warning_not_staged(self):
        (self.root/'plugins.dll').write_bytes(b'dummy')
        (self.root/'preferences.json').write_text('{}')
        plan = trainer.prepare_trainer(self.exe, appid=123456, steamapps=self.steamapps)
        self.assertEqual(plan['companion_resources_detected'], 2)
        self.assertFalse(plan['companion_resources_staged'])
        self.assertFalse(plan['companion_resources_integrity_verified'])

    def test_doctor_readonly_no_execution(self):
        report = trainer.trainer_doctor(appid=123456, steamapps=self.steamapps)
        self.assertEqual(report['state'], 'readonly_diagnostics_complete')
        self.assertTrue(report['game_installed'])
        self.assertTrue(report['system_wine_available'])
        self.assertFalse(report['trainer_launched'])
        self.assertFalse(report['game_runtime_match_verified'])

    def test_consent_gate_still_first(self):
        self.runtime_script('echo never')
        report = self.run_test(consent=False)
        self.assertEqual(report['state'], 'explicit_consent_required')
        self.assertEqual(list(self.private.iterdir()), [])

    def test_classification_whitelist(self):
        hints = trainer._classify_output(b'hello /home/bob/private.exe\nerr:module:import_dll')
        self.assertEqual(hints, ['missing_dll_hint'])


class UIContractTests(unittest.TestCase):
    def test_scrolled_controls_and_export(self):
        text=(Path(__file__).resolve().parents[1]/'gameweld/ui.py').read_text()
        for required in ('trainer_scroll.set_vexpand(True)',
                         "self.tabs.add_titled(trainer_scroll, 'trainers', 'Trainer Lab')",
                         'Gtk.FileChooserNative.new', 'self.trainer_proton_options',
                         'self.trainer_last_report = result', 'on_trainer_copy_report',
                         'self.trainer_prefix_consent.set_active(False)'):
            self.assertIn(required, text)

if __name__ == '__main__':
    unittest.main()
