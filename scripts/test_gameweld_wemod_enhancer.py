#!/usr/bin/env python3
"""Safe fixtures for the GameWeld PC2 WeMod Enhancer GUI bridge."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

HELPER = Path(__file__).resolve().parent / "gameweld-wemod-enhancer.py"
spec = importlib.util.spec_from_file_location("gameweld_wemod_bridge", HELPER)
assert spec and spec.loader
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class WeModEnhancerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-wemod-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data = self.root / "data"
        self.data.mkdir()
        self.client = self.root / "client"
        (self.client / "resources").mkdir(parents=True)
        (self.client / "WeMod.exe").write_bytes(b"MZ-FIXTURE")
        (self.client / "resources/app.asar").write_bytes(b"ORIGINAL-FIXTURE")
        self.helper = self.root / "helper"
        (self.helper / "bin").mkdir(parents=True)
        (self.helper / "bin/version.dll").write_bytes(b"MZ-FIXTURE")
        (self.helper / "bin/wemod_enhancer.py").write_text(
            'import sys\n'
            'from pathlib import Path\n'
            'operation=sys.argv[1]\n'
            'directory=Path(sys.argv[sys.argv.index("--install-dir")+1])\n'
            'asar=directory/"resources/app.asar"\n'
            'backup=directory/"resources/app.asar.backup"\n'
            'if operation=="patch":\n'
            '    if not backup.exists():backup.write_bytes(asar.read_bytes())\n'
            '    asar.write_bytes(b"PATCHED-FIXTURE")\n'
            'elif operation=="restore":\n'
            '    asar.write_bytes(backup.read_bytes())\n'
            'else:raise SystemExit(8)\n'
            'print("fake fixture operation:", operation)\n',
            encoding="utf-8",
        )
        self.environment = dict(os.environ,
            HOME=str(self.home), XDG_DATA_HOME=str(self.data),
            GAMEWELD_WEMOD_ENHANCER_DIR=str(self.helper))

    def cmd(self, *args):
        return subprocess.run(
            [sys.executable, str(HELPER), *args],
            env=self.environment, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=20,
        )

    def test_status_is_read_only_and_detects_explicit_wemod(self):
        before = (self.client / "resources/app.asar").read_bytes()
        response = self.cmd("status", "--install-dir", str(self.client))
        self.assertEqual(response.returncode, 0, response.stdout)
        self.assertIn("WeMod installation: FOUND", response.stdout)
        self.assertIn("WeMod Enhancer CLI: READY", response.stdout)
        self.assertEqual(before, (self.client / "resources/app.asar").read_bytes())

    def test_patch_then_restore_both_require_confirmation(self):
        source = self.client / "resources/app.asar"
        for action in ("patch", "restore"):
            response = self.cmd(action, "--install-dir", str(self.client))
            self.assertNotEqual(response.returncode, 0, response.stdout)
            self.assertEqual(source.read_bytes(), b"ORIGINAL-FIXTURE")
        patched = self.cmd("patch", "--install-dir", str(self.client), "--confirm")
        self.assertEqual(patched.returncode, 0, patched.stdout)
        self.assertEqual(source.read_bytes(), b"PATCHED-FIXTURE")
        self.assertEqual((self.client / "resources/app.asar.backup").read_bytes(),b"ORIGINAL-FIXTURE")
        restored = self.cmd("restore", "--install-dir", str(self.client), "--confirm")
        self.assertEqual(restored.returncode, 0, restored.stdout)
        self.assertEqual(source.read_bytes(), b"ORIGINAL-FIXTURE")

    def test_missing_wemod_folder_is_not_patched(self):
        response = self.cmd("patch", "--install-dir", str(self.root / "not-found"), "--confirm")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("not found", response.stdout.lower())

    def test_restore_requires_original_backup(self):
        response = self.cmd("restore", "--install-dir", str(self.client), "--confirm")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("backup", response.stdout.lower())

    def test_source_package_check_detects_bad_hash(self):
        candidate = self.root / "tiny-package"
        candidate.write_bytes(b"not a package")
        out = self.root / "downloaded"
        expected = hashlib.sha256(b"not a package").hexdigest()
        bridge.download_package(candidate.as_uri(), expected, out)
        self.assertEqual(out.read_bytes(), b"not a package")
        with self.assertRaises(ValueError):
            bridge.download_package(candidate.as_uri(), "f"*64, out)

    def test_safe_unpack_requires_upstream_script_and_dll(self):
        archive = self.root / "valid.tar.xz"
        with tarfile.open(archive, "w:xz") as tar:
            for path, data in [
                ("bin/wemod_enhancer.py", b"print('fixture')"),
                ("bin/version.dll", b"MZ\x00\x00fixture"),
            ]:
                info = tarfile.TarInfo(path)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        folder = self.root / "unpacked"
        folder.mkdir()
        bridge.safe_unpack(archive, folder)
        self.assertTrue(bridge.valid_patcher(folder))

    def test_safe_unpack_handles_cpack_nested_root(self):
        archive = self.root / "cpack.tar.xz"
        with tarfile.open(archive, "w:xz") as tar:
            for path, data in [
                ("wemod_enhancer/bin/wemod_enhancer.py", b"print('fixture')"),
                ("wemod_enhancer/bin/version.dll", b"MZ\x00\x00fixture"),
            ]:
                info = tarfile.TarInfo(path)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        folder = self.root / "cpack-unpacked"
        folder.mkdir()
        bridge.safe_unpack(archive, folder)
        self.assertTrue(bridge.valid_patcher(folder))

    def test_safe_unpack_rejects_symlinks_and_traversal(self):
        for index, name in enumerate(("../outside", "bin/alias")):
            archive = self.root / f"unsafe-{index}.tar.xz"
            with tarfile.open(archive, "w:xz") as tar:
                info = tarfile.TarInfo(name)
                if index:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "/outside"
                else:
                    info.size = 3
                tar.addfile(info, None if index else io.BytesIO(b"bad"))
            folder = self.root / f"extract-{index}"
            folder.mkdir()
            with self.assertRaises(ValueError):
                bridge.safe_unpack(archive, folder)

if __name__ == "__main__":
    unittest.main()
