"""Headless UI layout contract tests; actual GTK rendering requires CachyOS."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "gameweld" / "ui.py"

class UILayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_ui_is_valid_python(self):
        compile(self.tree, str(SOURCE), "exec")

    def test_list_is_scrolled_and_expands(self):
        self.assertIn("Gtk.ScrolledWindow(", self.source)
        self.assertIn("self.scroller.set_vexpand(True)", self.source)
        self.assertIn("columns.set_vexpand(True)", self.source)

    def test_regression_non_expanding_paned_removed(self):
        self.assertNotIn("Gtk.Paned(", self.source)

    def test_library_total_is_visible(self):
        self.assertIn("Steam games discovered", self.source)

    def test_trainer_execution_not_exposed_in_ui(self):
        self.assertNotIn("subprocess.", self.source)
        self.assertNotIn("process_vm_writev", self.source)
        self.assertNotIn("Gtk.FileChooser", self.source)

if __name__ == "__main__":
    unittest.main()
