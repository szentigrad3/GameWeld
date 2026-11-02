"""CLI integration: the trainer doctor never executes anything."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from gameweld.__main__ import main


class DoctorCLITests(unittest.TestCase):
    def test_doctor_readonly_without_game(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rc = main(['--trainer-doctor'])
        result = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(result['operation'], 'trainer-doctor')
        self.assertFalse(result['trainer_launched'])
        self.assertFalse(result['game_process_accessed'])
        self.assertFalse(result['raw_paths_disclosed'])

    def test_doctor_installed_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            steam = Path(tmp)
            (steam/'appmanifest_3008130.acf').write_text(
                '"AppState" { "appid" "3008130" "name" "Offline Example" "installdir" "Game" }')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = main(['--trainer-doctor', '--trainer-appid', '3008130',
                           '--steamapps', str(steam)])
            result = json.loads(output.getvalue())
            self.assertEqual(rc, 0)
            self.assertTrue(result['game_installed'])
            self.assertFalse(result['trainer_launched'])

    def test_doctor_does_not_select_arbitrary_proton(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rc = main(['--trainer-doctor', '--trainer-mode', 'proton'])
        result = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertFalse(result['game_runtime_match_verified'])

if __name__ == '__main__': unittest.main()
