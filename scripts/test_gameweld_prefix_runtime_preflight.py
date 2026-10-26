#!/usr/bin/env python3
"""Offline procfs fixtures: report active game runtime without modifying prefixes."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-prefix-runtime-preflight.py")
spec = importlib.util.spec_from_file_location("gameweld_prefix_runtime_preflight", SOURCE)
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class PrefixRuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-procfs-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.prefixes = {
            "steam": self.root / "steamapps/compatdata/361420/pfx",
            "heroic": self.root / "heroic/game-a/prefix",
            "lutris": self.root / "lutris/game-b/prefix",
        }
        for prefix in self.prefixes.values():
            prefix.mkdir(parents=True)
            (prefix / "system.reg").write_bytes(b"ORIGINAL")
        self.before = [p.joinpath("system.reg").read_bytes()
                       for p in self.prefixes.values()]

    def fake(self, pid, env):
        p = self.proc / str(pid)
        p.mkdir()
        (p / "environ").write_bytes(
            b"\x00".join(a.encode() for a in env) + b"\x00")

    def report(self, provider="steam", game_id="361420"):
        return check.procfs_report(
            provider, game_id, self.prefixes[provider],
            proc_root=self.proc, current_uid=os.getuid()
        )

    def unchanged(self):
        self.assertEqual(
            [p.joinpath("system.reg").read_bytes() for p in self.prefixes.values()],
            self.before
        )

    def test_active_exact_wineprefix_detected_for_all_three_providers(self):
        game_ids = {"steam": "361420", "heroic": "gog-a", "lutris": "lutris:b"}
        for i, (provider, game_id) in enumerate(game_ids.items()):
            prefix = self.prefixes[provider]
            self.fake(200 + i, [f"WINEPREFIX={prefix}",
                                "PRIVATE_TOKEN=NEVER_LOG_ME"])
            result = self.report(provider, game_id)
            self.assertEqual(result["state"], "ACTIVE")
            self.assertIn(200+i, result["matching_processes"])
            self.assertFalse(result["installer_authorized"])
            self.assertFalse(result["game_runtime_idle_verified"])
            self.assertNotIn("NEVER_LOG_ME", str(result))
        self.unchanged()

    def test_steam_compat_data_and_exact_appid_detected(self):
        prefix = self.prefixes["steam"]
        self.fake(335, [f"STEAM_COMPAT_DATA_PATH={prefix.parent}",
                        "SteamAppId=361420"])
        self.assertEqual(self.report()["state"], "ACTIVE")
        self.unchanged()

    def test_mismatched_appid_not_reported_active(self):
        prefix = self.prefixes["steam"]
        self.fake(335, [f"STEAM_COMPAT_DATA_PATH={prefix.parent}",
                        "SteamAppId=99999"])
        result = self.report()
        self.assertEqual(result["state"], "IDLE_CANDIDATE")
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["game_runtime_idle_verified"])
        self.unchanged()

    def test_unreadable_process_fails_closed_as_unknown(self):
        self.fake(335, ["WINEPREFIX=/unrelated"])
        previous = Path.read_bytes
        def refuse(path):
            if path.name == "environ" and path.parent.name == "335":
                raise PermissionError("Access denied")
            return previous(path)
        with patch.object(Path, "read_bytes", refuse):
            result = self.report()
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["unreadable_same_user_processes"], 1)
        self.assertFalse(result["installer_authorized"])
        self.unchanged()

    def test_positive_active_beats_unreadable_process(self):
        self.fake(335, [f"WINEPREFIX={self.prefixes['steam']}"])
        self.fake(336, ["WINEPREFIX=/unrelated"])
        previous = Path.read_bytes
        def refuse(path):
            if path.name == "environ" and path.parent.name == "336":
                raise PermissionError()
            return previous(path)
        with patch.object(Path, "read_bytes", refuse):
            result = self.report()
        self.assertEqual(result["state"], "ACTIVE")
        self.assertEqual(result["unreadable_same_user_processes"], 1)
        self.unchanged()

    def test_no_processes_is_never_authorization_to_install(self):
        outcome = self.report()
        self.assertEqual(outcome["state"], "IDLE_CANDIDATE")
        self.assertFalse(outcome["installer_authorized"])
        self.assertFalse(outcome["provider_specific_lock_verified"])
        self.assertFalse(outcome["game_runtime_idle_verified"])
        self.unchanged()

    def test_symlinked_prefix_cannot_be_checked(self):
        alias = self.root / "alias"
        alias.symlink_to(self.prefixes["steam"], target_is_directory=True)
        with self.assertRaisesRegex(check.RuntimePreflightRefused, "non-symlinked"):
            check.procfs_report("steam", "361420", alias,
                                proc_root=self.proc)
        self.unchanged()

    def test_invalid_provider_or_game_id_refused(self):
        for provider, gameid in (("steam", "bad"), ("heroic", "../../unsafe"),
                                  ("notreal", "12345")):
            with self.assertRaises(check.RuntimePreflightRefused):
                check.procfs_report(provider, gameid,
                                    self.prefixes["steam"], proc_root=self.proc)
        self.unchanged()

    def test_limited_process_enumeration_yields_unknown(self):
        self.fake(335, [f"WINEPREFIX={self.prefixes['steam']}"])
        with patch.object(check, "MAX_PIDS", 0):
            outcome = self.report()
        self.assertEqual(outcome["state"], "UNKNOWN")
        self.assertFalse(outcome["installer_authorized"])
        self.unchanged()


if __name__ == "__main__":
    unittest.main()
