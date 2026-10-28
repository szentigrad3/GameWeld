#!/usr/bin/env python3
"""Offline Steam per-game launch-options preservation tests; NEVER edits Steam."""
from __future__ import annotations
import importlib.util
import io
import contextlib
import json
from unittest.mock import patch
from pathlib import Path
import stat
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-steam-launch-options-preserve.py")
SPEC = importlib.util.spec_from_file_location("gw_steam_options_preserve", SOURCE)
assert SPEC and SPEC.loader
options = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(options)

APPID = "3008130"
ACCOUNT = "123456789"
RECIPE = 'WINEDLLOVERRIDES="version=n,b" WEMOD_LOG=/home/u/wemod.log /home/u/wemod %command%'

class PreserveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="gw-steam-preservation-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.steam = self.root / "Steam"
        self.file = self.steam / "userdata" / ACCOUNT / "config/localconfig.vdf"
        self.file.parent.mkdir(parents=True)
        self.backups = self.root / "private"
        self.make_config("")

    def make_config(self, raw):
        value = raw.replace("\\", "\\\\").replace('"', '\\"')
        self.file.write_text(
            '"UserLocalConfigStore" { "friends" { "dummy" "1" } '
            '"Software" { "Valve" { "Steam" { '
            '"apps" { "' + APPID + '" { "LaunchOptions" "' + value + '" } }'
            ' } } } }', encoding="utf-8")
        self.file.chmod(0o600)
        self.saved = self.file.read_bytes()

    def unchanged(self):
        self.assertEqual(self.file.read_bytes(), self.saved)

    def test_empty_game_option_matches_known_working_wrapper(self):
        config, account = options.find_config(APPID, self.steam, None)
        self.assertEqual(account, ACCOUNT)
        self.assertEqual(config, self.file)
        self.assertEqual(options.launch_option(config, APPID), "")
        self.assertEqual(options.merge("", RECIPE), (RECIPE, "SAFE_EMPTY"))
        self.unchanged()

    def test_missing_app_entry_is_unknown_not_an_empty_original(self):
        # Previous code silently returned "", risking backup of a wrong
        # original after the user successfully used a live Steam wrapper.
        self.file.write_text(
            '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" {'
            '"apps" { "333" { "LaunchOptions" "unrelated" } } } } } }',
            encoding="utf-8")
        self.saved = self.file.read_bytes()
        with self.assertRaisesRegex(options.Blocked, "cannot verify original"):
            options.launch_option(self.file, APPID)
        self.unchanged()

    def test_missing_launch_options_field_is_unknown_not_empty(self):
        self.file.write_text(
            '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" {'
            '"apps" { "' + APPID + '" { "LastPlayed" "123" } } } } } }',
            encoding="utf-8")
        self.saved = self.file.read_bytes()
        with self.assertRaisesRegex(options.Blocked, "NOT proof"):
            options.launch_option(self.file, APPID)
        self.unchanged()

    def run_main_with_fixture(self, *flags):
        output = io.StringIO()
        error = io.StringIO()
        with patch.object(options, "recipe_for", return_value=RECIPE), \
             patch.dict("os.environ", {"XDG_STATE_HOME": str(self.backups)}), \
             contextlib.redirect_stdout(output), \
             contextlib.redirect_stderr(error):
            try:
                returncode = options.main(
                    [*flags, "--appid", APPID, "--steam-root", str(self.steam)])
            except SystemExit as exc:
                returncode = exc.code
        return returncode, output.getvalue(), error.getvalue()

    def test_explicit_empty_disk_requires_live_steam_ui_confirmation(self):
        # The exact failure from real GUI testing: disk shows blank despite
        # user's working Steam Launch Options in their live client.
        rc, result, error = self.run_main_with_fixture("--preview")
        self.assertEqual(rc, 0, error)
        parsed = json.loads(result)
        self.assertEqual(parsed["original_launch_option"], "")
        self.assertIsNone(parsed["proposed_launch_option"])
        self.assertEqual(parsed["merge_status"], "NEEDS_STEAM_UI_EMPTY_CHECK")
        self.assertTrue(parsed["requires_manual_review"])
        self.assertFalse(options.backup_file(APPID, ACCOUNT, self.backups).exists())
        self.unchanged()

        rc, result, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(rc, 2)
        self.assertIn("Verify the CURRENT game's field", error)
        self.assertFalse(options.backup_file(APPID, ACCOUNT, self.backups).exists())
        self.unchanged()

        # Only separate user confirmation can allow that EMPTY original.
        rc, result, error = self.run_main_with_fixture(
            "--preview", "--verified-empty-in-steam")
        self.assertEqual(rc, 0, error)
        parsed = json.loads(result)
        self.assertEqual(parsed["merge_status"], "SAFE_EMPTY")
        self.assertEqual(parsed["proposed_launch_option"], RECIPE)

        rc, result, error = self.run_main_with_fixture(
            "--save-original", "--verified-empty-in-steam")
        self.assertEqual(rc, 0, error)
        parsed = json.loads(result)
        self.assertEqual(parsed["result"], "ORIGINAL_BACKUP_SAVED")
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups), "")
        self.unchanged()

    def test_missing_field_refuses_even_with_manual_empty_confirmation(self):
        self.file.write_text(
            '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" {'
            '"apps" { "' + APPID + '" { "LastPlayed" "1" } } } } } }',
            encoding="utf-8")
        self.saved = self.file.read_bytes()
        rc, _, error = self.run_main_with_fixture(
            "--save-original", "--verified-empty-in-steam")
        self.assertEqual(rc, 2)
        self.assertIn("NOT proof", error)
        self.assertFalse(options.backup_file(APPID, ACCOUNT, self.backups).exists())
        self.unchanged()

    def test_env_only_plus_arguments_preserves_existing_exact_text(self):
        original = "PROTON_LOG=1 DXVK_HUD=fps  %command% -dx11"
        self.make_config(original)
        self.assertEqual(options.launch_option(self.file, APPID), original)
        merged, status = options.merge(original, RECIPE)
        self.assertEqual(status, "SAFE_ENV_AND_ARGUMENTS")
        self.assertEqual(merged,
                         "PROTON_LOG=1 DXVK_HUD=fps " + RECIPE + " -dx11")
        self.unchanged()

    def test_existing_working_quoted_steam_wrapper_is_not_replaced(self):
        quoted = ('WINEDLLOVERRIDES="version=n,b" '
                  'WEMOD_LOG="/home/u/wemod.log" '
                  '"/home/u/wemod" %command%')
        self.assertEqual(options.merge(quoted, RECIPE),
                         (quoted, "ALREADY_CONFIGURED"))
        self.make_config(quoted)
        self.assertEqual(options.launch_option(self.file, APPID), quoted)
        self.unchanged()

    def test_only_game_flags_can_be_appended(self):
        self.assertEqual(options.merge("-vulkan -novid", RECIPE),
                         (RECIPE + " -vulkan -novid", "SAFE_GAME_FLAGS"))
        self.assertEqual(options.merge(RECIPE, RECIPE),
                         (RECIPE, "ALREADY_CONFIGURED"))

    def test_gamescope_mangohud_and_custom_scripts_are_never_reordered(self):
        bad = [
            "mangohud %command%",
            "gamemoderun %command%",
            "gamescope -f -- %command%",
            "MANGOHUD=1 gamescope -f -- %command%",
            "bash -c 'echo hello && %command%'",
            "LD_PRELOAD=/tmp/x.so %command% ; echo injected",
            "DXVK_HUD=fps | sh -c %command%",
            "PROTON_LOG=1 %command% && echo goodbye",
            "WINEDLLOVERRIDES=version=n,b /home/u/wemod %command% -vulkan",
            "%command% %command%",
            "PROTON_LOG=1 $(touch /tmp/not-written) %command%",
            "PROTON_LOG=1 /tmp/custom %command%",
            "WINEDLLOVERRIDES=foo %command%",
            "WEMOD_LOG=/tmp/old %command%",
        ]
        for original in bad:
            with self.subTest(original=original):
                proposed, state = options.merge(original, RECIPE)
                self.assertIsNone(proposed)
                self.assertTrue(state.startswith("MANUAL_"))
        self.unchanged()

    def test_parses_steam_vdf_comments_escapes_and_other_games(self):
        source = (
            '// Steam configuration\n'
            '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" {'
            '"apps" { "333" { "LaunchOptions" "do nothing" }'
            '"' + APPID + '" { /* comment */ "LaunchOptions" "PROTON_LOG=1 %command%" } }'
            ' } } } }')
        self.file.write_text(source, encoding="utf-8")
        self.saved = self.file.read_bytes()
        self.assertEqual(options.launch_option(self.file, APPID),
                         "PROTON_LOG=1 %command%")
        self.unchanged()

    def test_duplicate_game_field_and_malformed_vdf_refused(self):
        self.make_config("")
        before = self.file.read_text()
        self.file.write_text(before.replace(
            '"LaunchOptions" ""', '"LaunchOptions" "a" "LaunchOptions" "b"'))
        self.saved = self.file.read_bytes()
        with self.assertRaisesRegex(options.Blocked, "Duplicate"):
            options.launch_option(self.file, APPID)
        self.file.write_text(' "UserLocalConfigStore" { "oops" "value"')
        self.saved = self.file.read_bytes()
        with self.assertRaisesRegex(options.Blocked, "Missing"):
            options.launch_option(self.file, APPID)
        self.unchanged()

    def test_working_steam_symlink_integration_no_silent_replacement(self):
        # Integration regression for a real working Steam DeckCheatz 1.x
        # checkout, whose wemod entry is a symlink to src/wemod.py.
        checkout = self.root / "GameWeld DeckCheatz"
        src = checkout / "src"
        src.mkdir(parents=True)
        target = src / "wemod.py"
        target.write_text("#!/usr/bin/env python3\n")
        target.chmod(0o755)
        wrapper = checkout / "wemod"
        wrapper.symlink_to("src/wemod.py")
        known = ('WINEDLLOVERRIDES="version=n,b" '
                 'WEMOD_LOG="' + str(checkout / "wemod.log") + '" '
                 '"' + str(wrapper) + '" %command%')
        self.make_config(known)
        original = options.launch_option(self.file, APPID)
        proposed, state = options.merge(original, options.recipe_for(wrapper))
        self.assertEqual(state, "ALREADY_CONFIGURED")
        self.assertEqual(proposed, known)
        self.assertEqual(self.file.read_bytes(), self.saved)
        self.assertFalse((checkout / "wemod.log").exists())

    def test_one_time_session_recipe_requires_stable_installed_shim(self):
        import importlib.util
        script = Path(__file__).with_name("gameweld-deckcheatz-session.py")
        spec = importlib.util.spec_from_file_location("gw_session_for_test", script)
        one_shot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(one_shot)
        data = self.root / "xdg-data"
        data.mkdir()
        with patch.dict("os.environ", {"XDG_DATA_HOME": str(data)}):
            with self.assertRaisesRegex(options.Blocked, "Install or update"):
                options.recipe_for(None, session_appid=APPID)
            dest = one_shot.installed_wrapper_path()
            one_shot.install_wrapper(destination=dest, source=script)
            proposed = options.recipe_for(None, session_appid=APPID)
            self.assertIn(f"run --appid {APPID} -- %command%", proposed)
            self.assertIn(str(dest), proposed)
            self.assertIn("/usr/bin/python3", proposed)
            self.assertEqual(options.merge("", proposed),
                             (proposed, "SAFE_EMPTY"))
            original = "PROTON_LOG=1  %command% -dx11"
            combined, status = options.merge(original, proposed)
            self.assertEqual(status, "SAFE_ENV_AND_ARGUMENTS")
            self.assertIn("PROTON_LOG=1", combined)
            self.assertTrue(combined.endswith("%command% -dx11"))
            self.assertIsNone(options.merge("mangohud %command%", proposed)[0])
        self.unchanged()

    def test_multiple_accounts_never_guess_and_selector_is_explicit(self):
        second = self.steam / "userdata" / "24680/config/localconfig.vdf"
        second.parent.mkdir(parents=True)
        second.write_text(self.file.read_text())
        with self.assertRaisesRegex(options.Blocked, "Need one Steam account"):
            options.find_config(APPID, self.steam, None)
        selected, account = options.find_config(APPID, self.steam, ACCOUNT)
        self.assertEqual(selected, self.file)
        self.assertEqual(account, ACCOUNT)
        self.unchanged()

    def test_unverified_legacy_empty_original_backup_cannot_clear_steam_options(self):
        path = options.backup_file(APPID, ACCOUNT, self.backups)
        path.parent.mkdir(parents=True, mode=0o700)
        path.write_text(json.dumps(
            {"version": 1, "appid": APPID, "account": ACCOUNT, "original": ""}
        ))
        path.chmod(0o600)
        with self.assertRaisesRegex(options.Blocked, "unverified EMPTY original"):
            options.load_backup(APPID, ACCOUNT, self.backups)
        self.assertEqual(self.file.read_bytes(), self.saved)

    def test_legacy_empty_backup_migrates_to_separate_verified_current_snapshot(self):
        legacy = options.backup_file(APPID, ACCOUNT, self.backups)
        legacy.parent.parent.mkdir(parents=True, mode=0o700)
        legacy.parent.mkdir(mode=0o700)
        legacy.write_text(json.dumps({
            "version": 1, "appid": APPID, "account": ACCOUNT, "original": ""
        }), encoding="utf-8")
        legacy.chmod(0o600)
        old_bytes = legacy.read_bytes()
        old_mtime = legacy.stat().st_mtime_ns
        self.make_config("")
        rc, _, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(rc, 2, error)
        current = options.verified_baseline_file(APPID, ACCOUNT, self.backups)
        self.assertFalse(current.exists())
        with self.assertRaisesRegex(options.Blocked, "unverified EMPTY original"):
            options.load_backup(APPID, ACCOUNT, self.backups)
        rc, output, error = self.run_main_with_fixture(
            "--save-original", "--verified-empty-in-steam")
        self.assertEqual(rc, 0, error)
        parsed = json.loads(output)
        self.assertEqual(parsed["result"], "VERIFIED_CURRENT_BASELINE_SAVED")
        self.assertTrue(parsed["legacy_historical_original_unverified"])
        self.assertEqual(current.stat().st_mode & 0o777, 0o600)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups), "")
        self.assertEqual(legacy.read_bytes(), old_bytes)
        self.assertEqual(legacy.stat().st_mtime_ns, old_mtime)
        rc, output, error = self.run_main_with_fixture(
            "--save-original", "--verified-empty-in-steam")
        self.assertEqual(rc, 0, error)
        self.assertEqual(json.loads(output)["result"], "VERIFIED_CURRENT_BASELINE_REUSED")
        self.assertEqual(legacy.read_bytes(), old_bytes)
        self.unchanged()

    def test_legacy_backup_nonempty_current_options_must_not_be_relabelled(self):
        legacy = options.backup_file(APPID, ACCOUNT, self.backups)
        legacy.parent.parent.mkdir(parents=True, mode=0o700)
        legacy.parent.mkdir(mode=0o700)
        legacy.write_text(json.dumps({
            "version": 1, "appid": APPID, "account": ACCOUNT, "original": ""
        }), encoding="utf-8")
        legacy.chmod(0o600)
        original = legacy.read_bytes()
        self.make_config("MANGOHUD=1 %command%")
        rc, output, error = self.run_main_with_fixture(
            "--save-original", "--verified-empty-in-steam")
        self.assertEqual(rc, 2)
        self.assertEqual(output, "")
        self.assertIn("cannot be reconciled", error)
        self.assertFalse(options.verified_baseline_file(
            APPID, ACCOUNT, self.backups).exists())
        self.assertEqual(legacy.read_bytes(), original)
        self.unchanged()

    def test_verified_baseline_refuses_legacy_tampering_or_symlink(self):
        legacy = options.backup_file(APPID, ACCOUNT, self.backups)
        legacy.parent.parent.mkdir(parents=True, mode=0o700)
        legacy.parent.mkdir(mode=0o700)
        legacy.write_text(json.dumps({
            "version": 1, "appid": APPID, "account": ACCOUNT, "original": ""
        }), encoding="utf-8")
        legacy.chmod(0o600)
        self.make_config("")
        path = options.save_backup(APPID, ACCOUNT, "", self.backups,
                                   verified_empty=True)
        self.assertEqual(path, options.verified_baseline_file(
            APPID, ACCOUNT, self.backups))
        baseline_bytes = path.read_bytes()
        legacy.write_text(json.dumps({
            "version": 1, "appid": APPID, "account": ACCOUNT,
            "original": "", "note": "modified"
        }), encoding="utf-8")
        with self.assertRaisesRegex(options.Blocked, "Legacy original changed"):
            options.load_backup(APPID, ACCOUNT, self.backups)
        self.assertEqual(path.read_bytes(), baseline_bytes)
        path.unlink()
        path.symlink_to(legacy)
        with self.assertRaisesRegex(options.Blocked, "unsafe"):
            options.load_backup(APPID, ACCOUNT, self.backups)
        self.unchanged()

    def test_empty_backup_is_only_written_after_explicit_live_ui_check(self):
        with self.assertRaisesRegex(options.Blocked, "verified in the live Steam UI"):
            options.save_backup(APPID, ACCOUNT, "", self.backups)
        self.assertFalse(options.backup_file(APPID, ACCOUNT, self.backups).exists())
        path = options.save_backup(APPID, ACCOUNT, "", self.backups,
                                   verified_empty=True)
        self.assertEqual(json.loads(path.read_text())["live_empty_confirmed"], True)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups), "")
        self.unchanged()

    def test_private_original_backup_is_exclusive_and_nonoverwriting(self):
        old = "PROTON_LOG=1 %command% -dx11"
        self.make_config(old)
        original = self.file.read_bytes()
        backup = options.save_backup(APPID, ACCOUNT, old, self.backups)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups), old)
        reused_path, reused = options.save_backup(
            APPID, ACCOUNT, old, self.backups, return_status=True)
        self.assertEqual(reused_path, backup)
        self.assertTrue(reused)
        with self.assertRaisesRegex(options.Blocked, "differs from Steam"):
            options.save_backup(APPID, ACCOUNT, RECIPE, self.backups)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups), old)
        self.assertEqual(self.file.read_bytes(), original)

    def test_setup_retry_is_idempotent(self):
        original = "PROTON_LOG=1 %command% -dx11"
        self.make_config(original)
        code, output, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["result"], "ORIGINAL_BACKUP_SAVED")
        backup = options.backup_file(APPID, ACCOUNT, self.backups)
        initial = backup.read_bytes()
        modified = backup.stat().st_mtime_ns
        code, output, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["result"], "ORIGINAL_BACKUP_REUSED")
        self.assertTrue(result["backup_reused"])
        self.assertEqual(backup.read_bytes(), initial)
        self.assertEqual(backup.stat().st_mtime_ns, modified)
        self.unchanged()

    def test_existing_original_conflict_never_overwrites_backup(self):
        self.make_config("PROTON_LOG=1 %command% -dx11")
        rc, _, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(rc, 0, error)
        path = options.backup_file(APPID, ACCOUNT, self.backups)
        backup_bytes = path.read_bytes()
        self.make_config("MANGOHUD=1 %command% -dx11")
        rc, result, error = self.run_main_with_fixture("--save-original")
        self.assertEqual(rc, 2)
        self.assertEqual(result, "")
        self.assertIn("differs from Steam", error)
        self.assertEqual(path.read_bytes(), backup_bytes)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, self.backups),
                         "PROTON_LOG=1 %command% -dx11")
        self.unchanged()

    def test_preexisting_gameweld_state_can_be_public_but_backups_are_private(self):
        state = self.root / "preexisting-state"
        gw = state / "gameweld"
        gw.mkdir(parents=True, mode=0o755)
        gw.chmod(0o755)
        result = options.save_backup(APPID, ACCOUNT, "ORIGINAL",
                                     state)
        self.assertEqual(options.load_backup(APPID, ACCOUNT, state), "ORIGINAL")
        self.assertEqual(stat.S_IMODE(gw.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(result.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(result.parent.parent.stat().st_mode), 0o700)
        self.unchanged()

    def test_symlinked_config_and_backup_refused(self):
        self.file.unlink()
        target = self.root / "sensitive.vdf"
        target.write_text("private")
        self.file.symlink_to(target)
        with self.assertRaisesRegex(options.Blocked, "Unsafe"):
            options.launch_option(self.file, APPID)
        self.assertEqual(target.read_text(), "private")
        path = options.backup_file(APPID, ACCOUNT, self.backups)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        with self.assertRaisesRegex(options.Blocked, "Symlinked"):
            options.save_backup(APPID, ACCOUNT, "orig", self.backups)

    def test_duplicate_steam_root_symlink_is_deduplicated(self):
        other = self.root / "alias"
        other.symlink_to(self.steam, target_is_directory=True)
        root, selected = options.find_config(APPID, other, ACCOUNT)
        self.assertEqual((root, selected), (self.file, ACCOUNT))
        self.unchanged()

if __name__ == "__main__":
    unittest.main()
