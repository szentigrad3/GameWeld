import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from gameweld import ipc

ACTUAL=Path(os.environ.get('GAMEWELD_TEST_FIXTURE', str(ipc.fixture_default_path())))

class IpcTests(unittest.TestCase):
    def test_pinned_constants(self):
        self.assertEqual(ipc.PROBE_BYTES,4096)
        self.assertEqual(len(ipc.PROBE_SHA256),64)
        self.assertEqual(ipc.frame('PING','0123456789abcdef'),b'PING 0123456789abcdef\n')

    def test_invalid_command(self):
        with self.assertRaises(ValueError):ipc.frame('WRITE','0123456789abcdef')

    def test_no_consent(self):
        self.assertEqual(ipc.run_probe(consent=False)['state'],'consent_required')

    def test_missing_fixture(self):
        self.assertFalse(ipc.preflight('/tmp/missing/gameweld_sidecar_probe_v2.exe')['pinned_fixture_verified'])
        self.assertEqual(ipc.run_probe(consent=True,fixture='/tmp/missing/gameweld_sidecar_probe_v2.exe')['state'],
                         'fixture_integrity_failed')

    def test_hash_reject(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/ipc.PROBE_NAME
            f.write_bytes(b'MZ'+b'\0'*4094)
            self.assertFalse(ipc.preflight(f)['pinned_fixture_verified'])

    def test_symlink_reject(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/ipc.PROBE_NAME
            f.symlink_to(ACTUAL)
            self.assertFalse(ipc.preflight(f)['pinned_fixture_verified'])

    @unittest.skipUnless(ACTUAL.exists(),'historical Batch77 binary only used for local verification')
    def test_known_batch77_binary(self):
        self.assertEqual(hashlib.sha256(ACTUAL.read_bytes()).hexdigest(),ipc.PROBE_SHA256)
        self.assertTrue(ipc.preflight(ACTUAL)['pinned_fixture_verified'])

    def test_no_forbidden_system_calls_in_source(self):
        src=(Path(ipc.__file__)).read_text()
        for bad in ('process_vm_writev','ptrace(', 'SteamAppId=3008130', 'PROTON_REMOTE_DEBUG_CMD'):
            self.assertNotIn(bad,src)

if __name__=='__main__':unittest.main()

class ProtocolRuntimeTests(unittest.TestCase):
    def _runner(self, root, good=True):
        import sys
        path=Path(root)/'owned-fake-wine'
        sent = 'prefix' if good else '(prefix if command != "PING" else "BROKEN ")'
        code=(f'#!{sys.executable}\n'
              'import sys\n'
              'sys.stdout.write("GW77_READY\\n");sys.stdout.flush()\n'
              'for command,prefix in (("PING","GW77_PONG "),("STATUS","GW77_STATUS OK "),("STOP","GW77_STOPPED ")):\n'
              '    line=sys.stdin.readline().strip()\n'
              '    if not line.startswith(command+" "):sys.exit(2)\n'
              '    nonce=line.split(" ",1)[1]\n'
              f'    sys.stdout.write(({sent})+nonce+"\\n");sys.stdout.flush()\n')
        path.write_text(code)
        path.chmod(0o700)
        return str(path)

    def test_owned_four_stage_ipc(self):
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root)
            result=ipc._run_once_v2(runner,b'not-real-windows-binary',15)
            self.assertEqual(result['state'],'owned_win64_v2_protocol_verified',result)
            self.assertEqual(result['protocol_stages_completed'],4)
            self.assertTrue(result['owned_launcher_reaped'])
            self.assertFalse(result['detached_wine_helpers_reaped_verified'])
            self.assertFalse(result['raw_paths_disclosed'])

    def test_malformed_response_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            runner=self._runner(root,good=False)
            result=ipc._run_once_v2(runner,b'not-real-windows-binary',15)
            self.assertEqual(result['state'],'owned_win64_v2_protocol_failed')
            self.assertFalse(result['ping_pong_verified'])
            self.assertFalse(result['detached_wine_helpers_reaped_verified'])
