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
