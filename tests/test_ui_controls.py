"""Static GUI regression checks; a GTK4 host is required for render validation."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "gameweld" / "ui.py"

class LibraryControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_python_compilation(self):
        compile(self.tree, str(SOURCE), "exec")

    def test_sort_dropdown(self):
        self.assertIn("Gtk.DropDown.new_from_strings", self.source)
        self.assertIn("Steam App ID", self.source)
        self.assertIn("self.on_sort", self.source)

    def test_sort_is_local_only(self):
        self.assertIn('visible.sort(key=lambda game: game["appid"])', self.source)
        self.assertNotIn("subprocess.", self.source)

    def test_copy_id_uses_clipboard(self):
        self.assertIn("self.get_clipboard().set_text", self.source)
        self.assertIn("self.copy_id_button.set_sensitive(game is not None)", self.source)

    def test_favourite_count_visible(self):
        self.assertIn('len(favourite_ids)', self.source)
        self.assertIn("favourites", self.source)

if __name__ == "__main__":
    unittest.main()
