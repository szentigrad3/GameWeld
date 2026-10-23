#!/usr/bin/env python3
"""Fixtures for the read-only PC1 AppDir policy check."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('release_audit', HERE / 'audit-appimage-files.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AppDirAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ('usr/bin/gameweld', 'usr/bin/gameforge', 'usr/bin/wand-native'):
            self.put(rel, b'\x7fELFok')
        self.put('usr/libexec/wand-native-backend', b'\x7fELFok')
        self.put('usr/libexec/gameweld-elevate.exe', b'MZok')

    def put(self, rel, payload):
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)

    def test_expected_components(self):
        result = module.audit(self.root)
        self.assertEqual('PACKAGING_PASS_ONLY', result['status'])
        self.assertEqual(5, len(result['native_executables']))

    def test_reference_art_fails(self):
        self.put('usr/share/gameweld/resonance-cover-reference.png', b'image')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_game_id_art_fails(self):
        self.put('usr/share/gameweld/assets/games/2713000-cover.jpg', b'image')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_unreviewed_executable_fails(self):
        self.put('usr/libexec/resonance-native-trainer.exe', b'MZother')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_unexpected_elf_fails(self):
        self.put('usr/bin/extraneous-native', b'\x7fELFunknown')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_mismatched_gtk_launcher_fails(self):
        self.put('usr/bin/gameforge', b'\x7fELFchanged')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_missing_gtk_alias_fails(self):
        (self.root / 'usr/bin/wand-native').unlink()
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_bundled_dll_fails(self):
        self.put('usr/libexec/crypt32.dll', b'MZother')
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])

    def test_missing_backend_fails(self):
        (self.root / 'usr/libexec/wand-native-backend').unlink()
        self.assertEqual('PACKAGING_FAIL', module.audit(self.root)['status'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
