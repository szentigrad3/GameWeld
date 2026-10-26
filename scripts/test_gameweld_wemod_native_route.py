#!/usr/bin/env python3
"""Offline tests: GameWeld's no-Steam-Bridge route is a read-only check."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-wemod-native-route.py")
spec = importlib.util.spec_from_file_location("gameweld_native_route", SOURCE)
assert spec and spec.loader
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


class NativeRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-native-route-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_steam_without_bridge_requires_real_attachment_validation(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        prefix = self.root / "steamapps/compatdata/123456/pfx"
        prefix.mkdir(parents=True)
        before = sorted(x.relative_to(self.root).as_posix() for x in self.root.rglob("*"))
        result = route.native_route_report("steam", "123456", install_dir=str(install))
        self.assertEqual(result["provider"], "steam")
        self.assertTrue(result["evidence"]["steam_manifest_present"])
        self.assertTrue(result["evidence"]["game_prefix_present"])
        self.assertFalse(result["legacy_bridge_required"])
        self.assertFalse(result["game_runtime_attached"])
        self.assertIn("NOT READY", result["state"])
        self.assertEqual(
            sorted(x.relative_to(self.root).as_posix() for x in self.root.rglob("*")),
            before
        )

    def test_heroic_and_lutris_support_without_steam_id(self):
        runner = self.root / "wine"
        runner.write_text("#! /bin/sh\n")
        prefix = self.root / "prefix"
        prefix.mkdir()
        for provider, game in (("heroic", "gog_abcdef"), ("lutris", "lutris:my-game")):
            result = route.native_route_report(
                provider, game, prefix=str(prefix), runner=str(runner)
            )
            self.assertEqual(result["provider"], provider)
            self.assertTrue(result["evidence"]["game_prefix_present"])
            self.assertTrue(result["evidence"]["runner_file_present"])
            self.assertFalse(result["legacy_bridge_required"])
            self.assertFalse(result["game_runtime_attached"])

    def test_steam_user_report_marks_runner_not_required_and_attachment_unverified(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        (self.root / "steamapps/compatdata/123456/pfx").mkdir(parents=True)
        result = route.native_route_report("steam", "123456", install_dir=str(install))
        text = route.human_readable_report(result)
        self.assertIn("Steam AppID manifest: FOUND", text)
        self.assertIn("Steam Proton prefix: FOUND", text)
        self.assertIn("Separate Wine runner: NOT REQUIRED", text)
        self.assertIn("Trainer attachment to this game: NOT VERIFIED", text)
        self.assertIn("no GameWeld Steam Bridge needed", text)

    def test_heroic_lutris_human_report_explains_runner_and_safe_next_action(self):
        for provider, game_id in (("heroic", "gog_abcdef"), ("lutris", "lutris:my-game")):
            with self.subTest(provider=provider):
                prefix = self.root / (provider + "-pfx")
                prefix.mkdir()
                result = route.native_route_report(provider, game_id, prefix=str(prefix))
                output = route.human_readable_report(result)
                self.assertIn(f"{provider.title()} game prefix: FOUND", output)
                self.assertIn(f"{provider.title()} configured Wine/Proton runner: NOT VERIFIED", output)
                self.assertIn("original-platform integration", output)
                self.assertIn("Safety: READ-ONLY", output)

    def test_cli_text_format_keeps_machine_json_default(self):
        import contextlib
        from io import StringIO
        report = route.native_route_report("steam", "123456")
        with patch.object(route, "native_route_report", return_value=report):
            stdout = StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(route.main([
                    "--provider", "steam", "--game-id", "123456", "--format", "text"
                ]), 0)
            self.assertIn("GAMEWELD — WEMOD GAME CONNECTION", stdout.getvalue())
            self.assertIn("NOT VERIFIED", stdout.getvalue())
            stdout = StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(route.main([
                    "--provider", "steam", "--game-id", "123456"
                ]), 0)
            self.assertFalse(json.loads(stdout.getvalue())["game_runtime_attached"])
            stdout = StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(route.main([
                    "--provider", "steam", "--game-id", "123456", "--format", "summary"
                ]), 0)
            self.assertIn("WeMod connection", stdout.getvalue())
            self.assertIn("Install: BLOCKED", stdout.getvalue())
            self.assertLessEqual(len(stdout.getvalue().splitlines()), 7)

    def test_steam_gui_report_surfaces_active_proton_session_without_leaking_tokens(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        prefix = self.root / "steamapps/compatdata/123456/pfx"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        pid = proc / "54321"
        pid.mkdir(parents=True)
        (pid / "environ").write_bytes(
            (f"STEAM_COMPAT_DATA_PATH={prefix.parent}\0"
             "SteamAppId=123456\0WEMOD_ACCOUNT_TOKEN=NEVER_EXPOSE").encode()
        )
        result = route.native_route_report(
            "steam", "123456", install_dir=str(install), proc_root=proc
        )
        self.assertEqual(result["process_activity"]["state"], "ACTIVE")
        self.assertFalse(result["process_activity"]["installer_authorized"])
        self.assertFalse(result["process_activity"]["game_runtime_idle_verified"])
        self.assertIn("NOT READY", result["state"])
        rendered = route.human_readable_report(result)
        self.assertIn("Game activity: ACTIVE", rendered)
        self.assertIn("Install permission: BLOCKED", rendered)
        self.assertNotIn("NEVER_EXPOSE", json.dumps(result))
        self.assertNotIn("NEVER_EXPOSE", rendered)

    def test_heroic_gui_reports_no_match_but_never_authorizes_install(self):
        prefix = self.root / "heroic/prefix"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        proc.mkdir()
        result = route.native_route_report(
            "heroic", "gog-abc", prefix=str(prefix), proc_root=proc
        )
        self.assertEqual(result["process_activity"]["state"], "IDLE_CANDIDATE")
        self.assertFalse(result["process_activity"]["installer_authorized"])
        rendered = route.human_readable_report(result)
        self.assertIn("game closure is still unverified", rendered)
        self.assertIn("Trainer attachment to this game: NOT VERIFIED", rendered)

    def test_missing_prefix_fails_closed_without_attempting_runtime_scan(self):
        with patch.object(route, "runtime_activity", wraps=route.runtime_activity) as scanner:
            result = route.native_route_report("lutris", "game-abc")
            self.assertEqual(result["process_activity"]["state"], "UNKNOWN")
            self.assertFalse(result["process_activity"]["installer_authorized"])
            scanner.assert_called_once()
        self.assertIn("Game activity: UNKNOWN", route.human_readable_report(result))

    def test_steam_uses_discovered_matching_appid_prefix_not_arbitrary_hint(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        discovered = self.root / "steamapps/compatdata/123456/pfx"
        discovered.mkdir(parents=True)
        misleading = self.root / "other/pfx"
        misleading.mkdir(parents=True)
        with patch.object(route, "runtime_activity", return_value={
            "state": "UNKNOWN", "installer_authorized": False
        }) as scanner:
            route.native_route_report(
                "steam", "123456", install_dir=str(install),
                prefix=str(misleading)
            )
            self.assertEqual(scanner.call_args.args[2], discovered)

    def test_dev_appdir_symlinked_helper_finds_real_runtime_inspector(self):
        prefix = self.root / "heroic/prefix"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        proc.mkdir()
        symlink_path = self.root / "dev-AppDir/usr/libexec/gameweld-wemod-native-route.py"
        symlink_path.parent.mkdir(parents=True)
        symlink_path.symlink_to(SOURCE)
        with patch.object(route, "__file__", str(symlink_path)):
            activity = route.runtime_activity("heroic", "gog-a", prefix, proc_root=proc)
        self.assertEqual(activity["state"], "IDLE_CANDIDATE")
        self.assertFalse(activity["installer_authorized"])


    def test_game_summary_does_not_confuse_visible_wemod_with_attachment(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        prefix = self.root / "steamapps/compatdata/123456/pfx"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        pid = proc / "1500"
        pid.mkdir(parents=True)
        (pid / "environ").write_bytes(
            (f"STEAM_COMPAT_DATA_PATH={prefix.parent}\0SteamAppId=123456\0").encode()
        )
        (pid / "cmdline").write_bytes(
            b"wine\x00C:\\Program Files\\WeMod\\WeMod.exe\x00"
        )
        report = route.native_route_report(
            "steam", "123456", install_dir=str(install), proc_root=proc
        )
        self.assertEqual(report["process_activity"]["wemod_process_candidates"], 1)
        self.assertFalse(report["process_activity"]["trainer_attached"])
        self.assertFalse(report["game_runtime_attached"])
        summary = route.gui_summary(report)
        self.assertIn("Process visible in selected prefix", summary)
        self.assertIn("Trainer: NOT VERIFIED", summary)
        self.assertIn("Install: BLOCKED", summary)
        self.assertLessEqual(len(summary.splitlines()), 7)

    def test_no_active_process_does_not_claim_trainer_absent(self):
        prefix = self.root / "heroic/prefix"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        proc.mkdir()
        report = route.native_route_report(
            "heroic", "gog-a", prefix=str(prefix), proc_root=proc
        )
        summary = route.gui_summary(report)
        self.assertIn("WeMod process: Not verified", summary)
        self.assertIn("Trainer: NOT VERIFIED", summary)

    def test_live_game_unknown_wemod_explains_unreadable_matching_names(self):
        install = self.root / "steamapps/common/Test Game"
        install.mkdir(parents=True)
        (self.root / "steamapps/appmanifest_123456.acf").write_text("fixture")
        prefix = self.root / "steamapps/compatdata/123456/pfx"
        prefix.mkdir(parents=True)
        proc = self.root / "proc"
        pid = proc / "2000"
        pid.mkdir(parents=True)
        (pid / "environ").write_bytes(
            (f"STEAM_COMPAT_DATA_PATH={prefix.parent}\0SteamAppId=123456\0").encode()
        )
        result = route.native_route_report(
            "steam", "123456", install_dir=str(install), proc_root=proc
        )
        self.assertEqual(result["process_activity"]["state"], "ACTIVE")
        self.assertEqual(result["process_activity"]["matching_process_count"], 1)
        self.assertEqual(result["process_activity"]["wemod_process_name_unreadable"], 1)
        summary = route.gui_summary(result)
        self.assertIn("ACTIVE — matching game session detected", summary)
        self.assertIn("1/1 process names unreadable", summary)
        self.assertIn("Trainer: NOT VERIFIED", summary)
        self.assertIn("Install: BLOCKED", summary)

    def test_unknown_game_and_provider_fail_closed(self):
        for provider, game_id in [
            ("steam", "invalid"), ("steam", "0"), ("heroic", "../../foo"),
            ("lutris", "bad name / id"), ("unknown", "123456"),
        ]:
            with self.subTest(provider=provider, game_id=game_id):
                with self.assertRaises(route.NativeRouteBlocked):
                    route.native_route_report(provider, game_id)

    def test_cli_is_game_specific_and_does_not_launch(self):
        with patch.object(route, "native_route_report", return_value={
            "provider": "steam", "game_id": "123456", "game_runtime_attached": False
        }) as check:
            import contextlib
            from io import StringIO
            out = StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(route.main([
                    "--provider", "steam", "--game-id", "123456"
                ]), 0)
            self.assertEqual(json.loads(out.getvalue())["game_runtime_attached"], False)
            check.assert_called_once()

if __name__ == "__main__":
    unittest.main()
