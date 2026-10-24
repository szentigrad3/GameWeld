#!/usr/bin/env python3
"""Fixture-only tests for the old Wand Native 0.1.41 managed-session bridge."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).with_name("gameweld-wand-native-bridge.py")

class NativeManagedBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-native-bridge-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / "installed" / "Astrometica"
        self.game.mkdir(parents=True)
        self.runtime = self.root / "Wand app-12.55.0" / "WeMod.exe"
        self.runtime.parent.mkdir()
        self.runtime.write_bytes(b"MZ-TEST")
        self.record = self.root / "command-record.txt"
        self.cli = self.root / "wandctl"
        self.cli.write_text(
            "#!/usr/bin/env python3\n"
            "import os,sys,json\n"
            "from pathlib import Path\n"
            "args=sys.argv[1:]\n"
            "with Path(os.environ['GAMEWELD_TEST_RECORD']).open('a') as f:f.write(' '.join(args)+'\\n')\n"
            "if args==['--version']:print('wandctl '+os.environ.get('GW_MOCK_VERSION','0.1.41'))\n"
            "elif args==['ping']:print('{}')\n"
            "elif args==['proton','verify']:print('Result: healthy')\n"
            "elif args and args[0]=='inspect':\n"
            "  print(json.dumps({'game':{'app_id':int(args[1]),'install_dir':os.environ['GW_TEST_GAME']},'proton':{'display_name':'GE Proton Wand SHA256'}}))\n"
            "elif args and args[0]=='provider-health':\n"
            "  print(json.dumps([{'id':'wemod','available':True,'status':'ready','details':[\n"
            "    'WeMod runtime 12.55.0 at '+os.environ['GW_TEST_RUNTIME'],\n"
            "    ('DWriteCore compatibility: installed beside runtime' if os.environ.get('GW_NO_DWRITE')!='1' else 'DWriteCore compatibility: missing')]}]))\n"
            "elif args and args[0]=='processes':\n"
            "  print(json.dumps({'best_candidate_pid':701 if os.environ.get('GW_MOCK_RUNNING')=='1' else None,'candidates':[]}))\n"
            "elif args and args[0]=='begin-session':\n"
            "  print(json.dumps({'id':'00000000-0000-0000-0000-000000000001','state':'Preparing'}))\n"
            "else:print('Unexpected arguments:',args,file=sys.stderr);sys.exit(2)\n",
            encoding="utf-8"
        )
        self.cli.chmod(0o755)
        self.env = dict(os.environ,
            GAMEWELD_WAND_NATIVE_CLI=str(self.cli),
            GAMEWELD_TEST_RECORD=str(self.record),
            GW_TEST_GAME=str(self.game),
            GW_TEST_RUNTIME=str(self.runtime),
            HOME=str(self.root),
        )

    def invoke(self, *args: str, env=None):
        return subprocess.run(
            [sys.executable, str(HELPER), *args],
            env=env or self.env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=20
        )

    def base(self):
        return ("--appid", "2353250", "--game-provider", "steam",
                "--game-dir", str(self.game))

    def test_readonly_check_does_not_start_game_or_wand(self):
        result = self.invoke("check", *self.base())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Wand Native 0.1.41: VERIFIED", result.stdout)
        self.assertIn("DWriteCore beside runtime: VERIFIED", result.stdout)
        self.assertIn("Read-only readiness: PASS", result.stdout)
        self.assertNotIn("begin-session", self.record.read_text())
        self.assertEqual(self.runtime.read_bytes(), b"MZ-TEST")

    def test_managed_launch_requires_explicit_confirmation(self):
        denied = self.invoke("play", *self.base())
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("explicit --confirm", denied.stdout)
        self.assertFalse(self.record.exists(), "No CLI action without consent")
        allowed = self.invoke("play", *self.base(), "--confirm")
        self.assertEqual(allowed.returncode, 0, allowed.stdout)
        self.assertIn("begin-session request: ACCEPTED", allowed.stdout)
        record = self.record.read_text()
        self.assertIn("begin-session 2353250", record)
        self.assertIn("--provider wemod --proton GE Proton Wand SHA256", record)

    def test_existing_game_process_fails_closed(self):
        env = dict(self.env, GW_MOCK_RUNNING="1")
        denied = self.invoke("play", *self.base(), "--confirm", env=env)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("CLOSE the game", denied.stdout)
        self.assertNotIn("begin-session", self.record.read_text())

    def test_missing_dwrite_and_unverified_cli_fail_closed(self):
        for settings, reason in [
            ({"GW_NO_DWRITE": "1"}, "DWriteCore is not installed"),
            ({"GW_MOCK_VERSION": "0.1.40"}, "not tested 0.1.41"),
        ]:
            with self.subTest(settings=settings):
                self.record.unlink(missing_ok=True)
                response = self.invoke("play", *self.base(), "--confirm",
                                       env=dict(self.env, **settings))
                self.assertNotEqual(response.returncode, 0)
                self.assertIn(reason, response.stdout)
                if self.record.exists():
                    self.assertNotIn("begin-session", self.record.read_text())

    def test_different_game_path_and_wrong_provider_blocked(self):
        mismatch = self.invoke("check", "--appid", "2353250", "--game-dir",
                               str(self.root), "--game-provider", "steam")
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("disagree", mismatch.stdout)
        wrong = self.invoke("play", "--confirm", "--appid", "2353250",
                            "--game-provider", "heroic")
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("standard Steam games", wrong.stdout)
        malformed = self.invoke("play", "--confirm", "--appid", "2353250;exit")
        self.assertNotEqual(malformed.returncode, 0)

if __name__ == "__main__":
    unittest.main()
