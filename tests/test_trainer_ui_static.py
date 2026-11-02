"""Without a GTK graphical runtime, validate GUI safety wiring statically."""
import ast
import unittest
from pathlib import Path


class TrainerUIStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / 'gameweld' / 'ui.py'
        cls.source = cls.path.read_text()
        cls.tree = ast.parse(cls.source)

    def test_gui_compiles(self):
        compile(self.tree, str(self.path), 'exec')

    def test_trainer_lab_tab_created(self):
        self.assertIn("'trainers', 'Trainer Lab'", self.source)
        self.assertIn('self.make_trainer_lab()', self.source)

    def test_checksum_review_required(self):
        self.assertIn("self.trainer_review_sha = result['trainer_sha256']", self.source)
        self.assertIn('expected_sha256=hash_pin', self.source)

    def test_both_consent_gates(self):
        self.assertIn('self.trainer_consent.get_active()', self.source)
        self.assertIn('self.trainer_prefix_consent.get_active()', self.source)

    def test_trainer_cleanup_on_close(self):
        self.assertIn('self.on_trainer_stop(None)', self.source)
        self.assertIn('self.trainer_cancel_event.set()', self.source)

    def test_no_game_memory_access(self):
        self.assertNotIn('process_vm_writev', self.source)
        self.assertNotIn('ptrace', self.source)


if __name__ == '__main__':
    unittest.main()
