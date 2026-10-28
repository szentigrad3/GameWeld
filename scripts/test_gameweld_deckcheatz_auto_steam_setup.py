#!/usr/bin/env python3
"""Safety tests for zero-paste, Steam-managed one-shot DeckCheatz setup."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-auto-steam-setup.py")
spec = importlib.util.spec_from_file_location("gw_auto_steam_setup_tests", SOURCE)
assert spec and spec.loader
auto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto)

class Options:
    @staticmethod
    def tokens(text):
        return iter([text[1:-1] if text.startswith('"') else text])
    @staticmethod
    def parse_vdf(s):
        out = {}
        # This fixture parser checks values but the real parser is tested
        # below using the installed source file's parser.
        raise AssertionError("Use the actual GameWeld VDF parser")

def real_options():
    spec = importlib.util.spec_from_file_location(
        "gw_auto_steam_real_options",
        SOURCE.with_name("gameweld-steam-launch-options-preserve.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class AutoSteamTests(unittest.TestCase):
    APPID = "3008130"
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.opts = real_options()
        self.config = self.root / "localconfig.vdf"
        self.raw = (b'// preserve this comment\n'
                    b'"UserLocalConfigStore" { "Software" { "Valve" { "Steam" {'
                    b' "apps" { "3008130" { "LaunchOptions" ""'
                    b' "LastPlayed" "42" } "999999" {'
                    b' "LaunchOptions" "-safe" } } } } } }\n')
        self.config.write_bytes(self.raw)
        self.config.chmod(0o600)

    def test_change_only_exact_appid_launch_option_token(self):
        recipe = '/usr/bin/python3 "/home/a space/steam-session.py" run --appid 3008130 -- %command%'
        changed = auto.replace_launch_option(
            self.raw, self.APPID, "", recipe, self.opts)
        self.assertIn(b"steam-session.py", changed)
        self.assertIn(b'"LaunchOptions" "-safe"', changed)
        self.assertIn(b'// preserve this comment', changed)
        self.assertEqual(self.raw, self.config.read_bytes())
        restored = auto.replace_launch_option(
            changed, self.APPID, recipe, "", self.opts)
        self.assertEqual(restored, self.raw)

    def test_duplicate_launch_options_fail_closed(self):
        duplicate = self.raw.replace(
            b'"LaunchOptions" ""', b'"LaunchOptions" "" "LaunchOptions" ""', 1)
        with self.assertRaises(self.opts.Blocked):
            auto.replace_launch_option(duplicate, self.APPID, "", "abc", self.opts)
        self.assertEqual(self.config.read_bytes(), self.raw)

    def test_missing_value_and_changed_original_fail_closed(self):
        with self.assertRaises((auto.SetupBlocked, self.opts.Blocked)):
            auto.replace_launch_option(self.raw, self.APPID, "MANGOHUD=1", "abc", self.opts)
        # No live-client inference: a missing field is distinct from an
        # explicitly saved empty value and must not use the wrong baseline.
        missing = self.raw.replace(b'"LaunchOptions" ""', b'"Other" ""', 1)
        self.assertIsNone(auto.saved_option_value(missing, self.APPID, self.opts))
        with self.assertRaises((auto.SetupBlocked, self.opts.Blocked)):
            auto.replace_launch_option(missing, self.APPID, "", "abc", self.opts)
        self.assertEqual(self.config.read_bytes(), self.raw)

    def test_absent_saved_option_in_existing_game_is_inserted_once(self):
        missing = self.raw.replace(b'"LaunchOptions" ""', b'"Other" ""', 1)
        command = "/usr/bin/python3 /private/steam-session.py run --appid 3008130 -- %command%"
        changed = auto.replace_launch_option(missing, self.APPID, None, command, self.opts)
        self.assertEqual(auto.saved_option_value(changed, self.APPID, self.opts), command)
        self.assertIn(b'"Other" ""', changed)
        self.assertIn(b'"LaunchOptions" "-safe"', changed)
        self.assertIn(b'// preserve this comment', changed)
        with self.assertRaises((auto.SetupBlocked, self.opts.Blocked)):
            auto.replace_launch_option(changed, self.APPID, None, command, self.opts)
        self.assertEqual(auto.saved_option_value(missing, self.APPID, self.opts), None)
        self.assertEqual(self.config.read_bytes(), self.raw)

    def test_absent_app_entry_and_duplicate_app_entries_are_blocked(self):
        missing_app = self.raw.replace(b'"3008130"', b'"1234567"', 1)
        with self.assertRaises((auto.SetupBlocked, self.opts.Blocked)):
            auto.replace_launch_option(missing_app, self.APPID, None, "abc", self.opts)
        duplicate_app = self.raw.replace(
            b'"999999" {', b'"3008130" {', 1)
        with self.assertRaises((auto.SetupBlocked, self.opts.Blocked)):
            auto.replace_launch_option(duplicate_app, self.APPID, None, "abc", self.opts)

    def test_absent_option_registration_is_offline_and_backed_up(self):
        from types import SimpleNamespace
        cfg, account = self.config, "4548901"
        missing = self.raw.replace(b'"LaunchOptions" ""', b'"Other" ""', 1)
        cfg.write_bytes(missing)
        wrapper = self.root / "steam-session.py"
        wrapper.write_text("#!/usr/bin/python3")
        wrapper.chmod(0o700)
        saved_baselines = []
        opts = SimpleNamespace(
            find_config=lambda appid, root, user: (cfg, account),
            parse_vdf=self.opts.parse_vdf,
            only=self.opts.only,
            tokens=self.opts.tokens,
            save_backup=lambda appid, user, old, **kw: saved_baselines.append((old, kw)),
        )
        session = SimpleNamespace(
            install_wrapper=lambda: None,
            installed_wrapper_path=lambda: wrapper,
            compose=lambda old, dest, aid: (
                "/usr/bin/python3 " + str(dest) +
                " run --appid " + aid + " -- %command%", "SAFE_EMPTY"),
        )
        with patch.object(auto, "peer",
                          side_effect=lambda name, label: opts if name.endswith("preserve.py") else session), \
             patch.object(auto, "steam_is_running", return_value=False):
            report = auto.register_steam_shim(self.APPID, state_root=self.root / "state")
        self.assertEqual(report["result"], "automatic_steam_wrapper_installed")
        self.assertEqual(saved_baselines, [("", {"verified_empty": True})])
        backup = (self.root / "state/gameweld/automatic-steam-setup" /
                  account / (self.APPID + ".original-localconfig.vdf"))
        self.assertEqual(backup.read_bytes(), missing)
        self.assertIsNotNone(auto.saved_option_value(cfg.read_bytes(), self.APPID, self.opts))
        self.assertEqual(cfg.stat().st_mode & 0o777, 0o600)

    def test_atomic_write_preserves_permissions_and_blocks_stale_config(self):
        other = self.raw.replace(b'"LastPlayed" "42"', b'"LastPlayed" "43"')
        import hashlib
        with patch.object(auto, "steam_is_running", return_value=False):
            auto.atomic_replace(self.config, other, hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(other, self.config.read_bytes())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        with patch.object(auto, "steam_is_running", return_value=False):
            with self.assertRaisesRegex(auto.SetupBlocked, "changed since snapshot"):
                auto.atomic_replace(self.config, self.raw, hashlib.sha256(self.raw).hexdigest())

    def test_never_write_running_steam(self):
        with patch.object(auto, "steam_is_running", return_value=True):
            with self.assertRaisesRegex(auto.SetupBlocked, "Steam must be closed"):
                auto.register_steam_shim(self.APPID)
        self.assertEqual(self.config.read_bytes(), self.raw)

    def test_end_to_end_registration_uses_test_localconfig_no_live_steam(self):
        from types import SimpleNamespace
        import shutil
        cfg = self.config
        opts = self.opts
        account = "4548901"
        wrapper = self.root / "steam-session.py"
        wrapper.write_text("#!/usr/bin/python3")
        wrapper.chmod(0o700)
        backup_calls = []
        def make_options():
            return SimpleNamespace(
                find_config=lambda appid, root, user: (cfg, account),
                launch_option=opts.launch_option,
                parse_vdf=opts.parse_vdf, only=opts.only, tokens=opts.tokens,
                save_backup=lambda appid, user, old, **kw: backup_calls.append(
                    (appid, user, old, kw)),
            )
        def make_session():
            return SimpleNamespace(
                install_wrapper=lambda: None,
                installed_wrapper_path=lambda: wrapper,
                compose=lambda old, dest, aid: (
                    "/usr/bin/python3 " + str(dest) +
                    " run --appid " + aid + " -- %command%", "SAFE_EMPTY"),
            )
        def peer(name, label):
            return make_options() if name.endswith("preserve.py") else make_session()
        state = self.root / "state"
        with patch.object(auto, "peer", side_effect=peer), \
             patch.object(auto, "steam_is_running", return_value=False):
            result = auto.register_steam_shim(self.APPID, state_root=state)
        self.assertEqual(result["result"], "automatic_steam_wrapper_installed")
        self.assertTrue(result["original_user_options_preserved"])
        self.assertEqual(len(backup_calls), 1)
        self.assertTrue(backup_calls[0][3]["verified_empty"])
        original_saved = (state / "gameweld/automatic-steam-setup"
                          / account / (self.APPID + ".original-localconfig.vdf"))
        self.assertEqual(original_saved.read_bytes(), self.raw)
        self.assertEqual(original_saved.stat().st_mode & 0o777, 0o600)
        installed = opts.launch_option(cfg, self.APPID)
        self.assertIn("steam-session.py", installed)
        self.assertIn("-- %command%", installed)
        self.assertIn(b'"LastPlayed" "42"', cfg.read_bytes())

    def test_full_config_backup_never_overwritten(self):
        folder = self.root / "private" / "account"
        folder.parent.mkdir(mode=0o700)
        auto.secure_dir(folder)
        saved = folder / "original"
        self.assertTrue(auto.save_exclusive(saved, self.raw))
        self.assertFalse(auto.save_exclusive(saved, self.raw))
        with self.assertRaisesRegex(auto.SetupBlocked, "conflicts"):
            auto.save_exclusive(saved, b"malicious second backup")
        self.assertEqual(saved.read_bytes(), self.raw)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)

    def test_graceful_shutdown_is_required_no_kill(self):
        from types import SimpleNamespace
        with patch.object(auto, "steam_is_running", side_effect=[True,False,False]), \
             patch.object(auto.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(auto.stop_steam_gracefully("/usr/bin/steam"))
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["/usr/bin/steam", "-shutdown"])

    def test_steam_launch_is_requested_not_claimed_success(self):
        class Session:
            @staticmethod
            def arm(_id, _launcher):
                return {"result": "SINGLE_SESSION_ARMED"}
        with patch.object(auto, "peer", return_value=Session), \
             patch.object(auto.subprocess, "Popen") as popen:
            result = auto.auto_launch(self.APPID, self.root / "wemod", "/usr/bin/steam")
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["/usr/bin/steam", "-applaunch", self.APPID])
        self.assertFalse(result["game_window_verified"])
        self.assertFalse(result["wemod_attachment_verified"])

if __name__ == "__main__":
    unittest.main()
