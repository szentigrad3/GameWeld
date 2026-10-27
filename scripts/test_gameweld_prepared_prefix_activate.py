#!/usr/bin/env python3
"""Synthetic real-prefix promotion and rollback tests. No actual games touched."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent


def load(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


promote = load("gameweld-prepared-prefix-activate.py", "gw_activate_test")
importer = load("gameweld-prepared-prefix-import.py", "gw_import_test")


class PrefixActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-prepared-activate-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.appid = "2353250"
        self.install = self.root / "steamapps/common/Astrometica"
        self.compat = self.root / "steamapps/compatdata/2353250"
        self.install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_2353250.acf").write_text("fixture")
        (self.compat / "pfx/drive_c/users/steamuser").mkdir(parents=True)
        (self.compat / "pfx/drive_c/users/steamuser/save.dat").write_bytes(b"SAVE")
        (self.compat / "pfx/system.reg").write_bytes(b"GAME ORIGINAL")
        (self.compat / "version").write_text("GE-Proton10-1")
        (self.compat / "pfx/dosdevices").mkdir()
        (self.compat / "pfx/dosdevices/z:").symlink_to("/")
        self.state = self.root / "state/gameweld/prefix-imports"
        self.state.mkdir(parents=True)
        self.state.chmod(0o700)
        self.candidate_dir = self.state / "2353250-aaaaaaaaaaaaaaaa"
        self.candidate = self.candidate_dir / "compatdata"
        shutil.copytree(self.compat, self.candidate, symlinks=True)
        (self.candidate / "pfx/system.reg").write_bytes(b"PREPARED DOTNET")
        (self.candidate / "pfx/.wemod_installer").write_text("true")
        info = {
            "appid": self.appid, "mode": "ISOLATED_CANDIDATE_PREPARED",
            "live_game_modified": False,
            "original_game_snapshot_sha256": importer.fingerprint(self.compat)
        }
        (self.candidate_dir / "candidate.json").write_text(json.dumps(info))
        self.processes = self.root / "proc"
        self.processes.mkdir()

    def do_activate(self, **kwargs):
        with patch.dict(os.environ, {
            "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
        }), patch.object(promote.shutil, "disk_usage", return_value=type(
            "Disk", (), {"free": 100 * 1024**3
        })()):
            return promote.activate(
                self.appid, self.install, self.candidate_dir,
                state_root=self.state, proc_root=self.processes,
                approved=kwargs.get("approved", True),
                game_closed=kwargs.get("closed", True),
                accepted_risk=kwargs.get("risk", True)
            )

    def do_rollback(self, txid, **kwargs):
        with patch.dict(os.environ, {
            "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
        }):
            return promote.rollback(
                self.appid, self.install, txid,
                state_root=self.state, proc_root=self.processes,
                approved=kwargs.get("approved", True),
                game_closed=kwargs.get("closed", True),
                accepted_risk=kwargs.get("risk", True)
            )

    def original(self):
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(),
                         b"GAME ORIGINAL")
        self.assertEqual((self.compat / "pfx/drive_c/users/steamuser/save.dat").read_bytes(),
                         b"SAVE")
        self.assertTrue((self.compat / "pfx/dosdevices/z:").is_symlink())

    def test_apply_reversible_and_original_preserved(self):
        result = self.do_activate()
        self.assertTrue(result["backup_preserved"])
        self.assertFalse(result["steam_options_changed"])
        self.assertFalse(result["trainer_verified"])
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(),
                         b"PREPARED DOTNET")
        backup = Path(result["backup_path"])
        self.assertEqual((backup / "pfx/system.reg").read_bytes(), b"GAME ORIGINAL")
        self.assertEqual((self.compat / "pfx/drive_c/users/steamuser/save.dat").read_bytes(),
                         b"SAVE")
        result2 = self.do_rollback(result["txid"])
        self.assertTrue(result2["original_game_restored"])
        self.assertTrue(Path(result2["postimport_path"]).exists())
        self.original()
        self.assertFalse((self.root / "steamapps/config").exists())

    def test_missing_user_or_environment_approval_never_writes(self):
        with self.assertRaisesRegex(promote.ActivationBlocked, "opt-in"):
            promote.activate(self.appid, self.install, self.candidate_dir,
                             state_root=self.state, approved=True,
                             game_closed=True, accepted_risk=True,
                             proc_root=self.processes)
        with self.assertRaisesRegex(promote.ActivationBlocked, "approvals"):
            self.do_activate(approved=False)
        self.original()

    def test_changed_game_prefix_aborts_before_staging(self):
        (self.compat / "pfx/system.reg").write_bytes(b"CHANGED AFTER PREVIEW")
        with self.assertRaisesRegex(promote.ActivationBlocked, "changed"):
            self.do_activate()
        self.assertFalse(list(self.compat.parent.glob(".gameweld-*")))
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(),
                         b"CHANGED AFTER PREVIEW")

    def test_matching_active_wine_process_blocks(self):
        pid = self.processes / "710"
        pid.mkdir()
        (pid / "environ").write_bytes(
            f"WINEPREFIX={self.compat / 'pfx'}\0".encode()
        )
        with self.assertRaisesRegex(promote.ActivationBlocked, "may still"):
            self.do_activate()
        self.assertFalse(list(self.compat.parent.glob(".gameweld-*")))
        self.original()

    def test_second_rename_fails_and_old_prefix_restored(self):
        real_rename = promote.os.rename
        def fail_staged(src, dst):
            if Path(src).name.startswith(".gameweld-import-"):
                raise OSError("simulated interrupted promotion")
            return real_rename(src, dst)
        with patch.object(promote.os, "rename", side_effect=fail_staged):
            with self.assertRaisesRegex(OSError, "interrupted promotion"):
                self.do_activate()
        self.original()
        self.assertFalse(list(self.compat.parent.glob(".gameweld-import-*")))
        self.assertFalse(list(self.compat.parent.glob(".gameweld-original-*")))

    def test_unmanaged_candidate_folder_rejected(self):
        unmanaged = self.root / "unmanaged"
        unmanaged.mkdir()
        with self.assertRaisesRegex(promote.ActivationBlocked, "not in GameWeld"):
            with patch.dict(os.environ, {
                "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
            }):
                promote.activate(self.appid, self.install, unmanaged,
                    state_root=self.state, approved=True, game_closed=True,
                    accepted_risk=True, proc_root=self.processes)
        self.original()


    def test_recovery_with_missing_live_prefix_refuses_active_process(self):
        txid = "d" * 32
        backup = self.compat.parent / f".gameweld-original-{self.appid}-{txid}"
        staging = self.compat.parent / f".gameweld-import-{self.appid}-{txid}"
        shutil.copytree(self.candidate, staging, symlinks=True)
        promote.write_new_journal(self.state, txid, {
            "txid": txid, "appid": self.appid, "state": "PREPARED",
            "compat_path": str(self.compat), "backup_path": str(backup),
            "staging_path": str(staging),
            "original_sha256": importer.fingerprint(self.compat),
        })
        os.rename(self.compat, backup)
        pid = self.processes / "712"
        pid.mkdir()
        (pid / "environ").write_bytes(
            f"WINEPREFIX={self.compat / 'pfx'}\\0".encode()
        )
        with patch.dict(os.environ, {
            "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
        }):
            with self.assertRaisesRegex(promote.ActivationBlocked, "may still"):
                promote.recover_interrupted(
                    self.appid, self.install, txid, state_root=self.state,
                    approved=True, game_closed=True, accepted_risk=True,
                    proc_root=self.processes)
        self.assertFalse(self.compat.exists())
        self.assertTrue(backup.is_dir())
        self.assertTrue(staging.is_dir())
        self.assertEqual(promote.read_journal(self.state, txid)["state"], "PREPARED")

    def test_recover_interrupted_swap_with_game_prefix_temporarily_missing(self):
        txid = "f" * 32
        original = self.compat.parent / f".gameweld-original-{self.appid}-{txid}"
        staging = self.compat.parent / f".gameweld-import-{self.appid}-{txid}"
        shutil.copytree(self.candidate, staging, symlinks=True)
        data = {
            "txid": txid, "appid": self.appid, "state": "PREPARED",
            "compat_path": str(self.compat), "backup_path": str(original),
            "staging_path": str(staging),
            "original_sha256": importer.fingerprint(self.compat)
        }
        promote.write_new_journal(self.state, txid, data)
        os.rename(self.compat, original)
        self.assertFalse(self.compat.exists())
        with patch.dict(os.environ, {
            "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
        }):
            result = promote.recover_interrupted(
                self.appid, self.install, txid, state_root=self.state,
                approved=True, game_closed=True, accepted_risk=True,
                proc_root=self.processes)
        self.assertEqual(result["state"], "ROLLED_BACK")
        self.original()
        self.assertTrue(Path(str(staging) + ".aborted").exists())
        self.assertEqual(promote.read_journal(self.state, txid)["state"], "ROLLED_BACK")

    def test_recover_interrupted_journal_after_candidate_switch(self):
        txid = "e" * 32
        backup = self.compat.parent / f".gameweld-original-{self.appid}-{txid}"
        staging = self.compat.parent / f".gameweld-import-{self.appid}-{txid}"
        shutil.copytree(self.candidate, staging, symlinks=True)
        data = {
            "txid": txid, "appid": self.appid, "state": "PREPARED",
            "compat_path": str(self.compat), "backup_path": str(backup),
            "staging_path": str(staging),
            "original_sha256": importer.fingerprint(self.compat)
        }
        promote.write_new_journal(self.state, txid, data)
        os.rename(self.compat, backup)
        os.rename(staging, self.compat)
        with patch.dict(os.environ, {
            "GAMEWELD_PREFIX_IMPORT_EXPERIMENT": promote.EXPERIMENT
        }):
            result = promote.recover_interrupted(
                self.appid, self.install, txid, state_root=self.state,
                approved=True, game_closed=True, accepted_risk=True,
                proc_root=self.processes)
        self.assertEqual(result["state"], "ROLLED_BACK")
        self.original()
        retired = self.compat.parent / f".gameweld-recovered-test-{self.appid}-{txid}"
        self.assertTrue(retired.is_dir())
        self.assertEqual((retired / "pfx/system.reg").read_bytes(), b"PREPARED DOTNET")

    def test_rollback_requires_original_backup(self):
        data = self.do_activate()
        shutil.rmtree(Path(data["backup_path"]))
        with self.assertRaisesRegex(promote.ActivationBlocked, "invalid"):
            self.do_rollback(data["txid"])
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(),
                         b"PREPARED DOTNET")

    def test_rollback_cannot_run_during_active_game(self):
        data = self.do_activate()
        pid = self.processes / "800"
        pid.mkdir()
        (pid / "environ").write_bytes(
            f"WINEPREFIX={self.compat / 'pfx'}\0".encode()
        )
        with self.assertRaisesRegex(promote.ActivationBlocked, "may still"):
            self.do_rollback(data["txid"])
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(),
                         b"PREPARED DOTNET")
        (pid / "environ").unlink()
        self.do_rollback(data["txid"])
        self.original()


if __name__ == "__main__":
    unittest.main()
