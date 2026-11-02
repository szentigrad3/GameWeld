import ast
import unittest
from pathlib import Path

class UIStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file=Path(__file__).resolve().parents[1]/'gameweld'/'ui.py'
        cls.text=cls.file.read_text()
        cls.tree=ast.parse(cls.text)

    def test_compile(self):compile(self.tree,str(self.file),'exec')
    def test_library_scrolls(self):self.assertIn('scroll.set_vexpand(True)',self.text)
    def test_no_paned(self):self.assertNotIn('Gtk.Paned(',self.text)
    def test_ipc_requires_consent(self):
        self.assertIn('self.ipc_consent.get_active()',self.text)
        self.assertIn('run_probe(consent=True',self.text)
    def test_notes(self):self.assertIn('on_save_note',self.text)
    def test_readonly_inspect(self):self.assertIn('game_report(game)',self.text)
    def test_no_external_trainer(self):
        self.assertNotIn('Gtk.FileChooser',self.text)
        self.assertNotIn('process_vm_writev',self.text)
    def test_idle_delivery(self):self.assertIn('GLib.idle_add(deliver)',self.text)

if __name__=='__main__':unittest.main()
