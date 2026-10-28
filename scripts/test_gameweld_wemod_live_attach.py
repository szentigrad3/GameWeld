#!/usr/bin/env python3
"""Synthetic Steam live WeMod no-options client handoff tests. Never launch Proton."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-wemod-live-attach.py")
SPEC = importlib.util.spec_from_file_location("gameweld_wemod_live_attach", SOURCE)
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class LiveAttachTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gameweld-live-attach-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.id = "2353250"
        self.steam_root = self.base / "Steam"
        self.steamapps = self.steam_root / "steamapps"
        self.game = self.steamapps / "common" / "Example Astrometica"
        self.compat = self.steamapps / "compatdata" / self.id
        self.game.mkdir(parents=True)
        (self.steamapps / f"appmanifest_{self.id}.acf").write_text("fake manifest")
        (self.compat / "pfx").mkdir(parents=True)
        (self.compat / "pfx/system.reg").write_bytes(b"PRESERVE ORIGINAL PREFIX")
        self.client = self.base / "client"
        (self.client / "resources").mkdir(parents=True)
        (self.client / "WeMod.exe").write_bytes(b"fake wemod executable")
        (self.client / "resources/app.asar").write_bytes(b"fake app")
        self.proton_dir = self.base / "GE-Proton"
        self.proton_dir.mkdir()
        self.proton = self.proton_dir / "proton"
        self.proton.write_text("#!/bin/sh\nexit 98\n")
        self.proton.chmod(0o700)
        (self.proton_dir / "toolmanifest.vdf").write_text("fixture")
        self.proc = self.base / "proc"
        self.proc.mkdir()
        self.pid = self.proc / "1000"
        self.pid.mkdir()
        self.make_proc()
        self.saved = (self.compat / "pfx/system.reg").read_bytes()
        self.root_state = self.base / "state/gameweld/wemod-live"

    def make_proc(self, *, root=None, paths=None, appid=None, client=False):
        entries = {
            "STEAM_COMPAT_DATA_PATH": str(self.compat),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(root or self.steam_root),
            "STEAM_COMPAT_TOOL_PATHS": str(paths or self.proton_dir),
            "SteamAppId": str(appid or self.id),
            "SECRET_TOKEN": "DO_NOT_LEAK",
            "WEMOD_USER": "HIDDEN",
        }
        (self.pid / "environ").write_bytes(
            b"\x00".join((k + "=" + v).encode() for k, v in entries.items()) + b"\x00"
        )
        (self.pid / "cmdline").write_bytes(b"WeMod.exe\x00" if client else b"Astrometica.exe\x00")
        (self.pid / "comm").write_bytes(b"WeMod.exe\n" if client else b"Astrometica.exe\n")

    def plan(self):
        return helper.plan(self.id, self.game, self.client, proc_root=self.proc,
                           uid=os.getuid())

    def unchanged(self):
        self.assertEqual((self.compat / "pfx/system.reg").read_bytes(), self.saved)
        self.assertEqual(list(self.game.iterdir()), [])

    def test_default_preview_only_identifies_exact_live_context(self):
        report, private = self.plan()
        self.assertEqual(report["matching_prefix_processes"], 1)
        self.assertTrue(report["unique_proton_context"])
        self.assertTrue(report["managed_client_present"])
        self.assertTrue(report["can_attempt_with_explicit_consent"])
        self.assertEqual(report["mode"], "live_client_handoff_preview")
        self.assertFalse(report["steam_launch_options_changed"])
        self.assertFalse(report["new_game_launched"])
        self.assertFalse(report["trainer_attachment_verified"])
        self.assertEqual(private["context"]["proton"], self.proton)
        self.assertNotIn("DO_NOT_LEAK", str(report))
        self.assertNotIn(str(self.client), json.dumps(report))
        self.assertFalse(self.root_state.exists())
        self.unchanged()

    def test_explicit_approved_handoff_spawns_only_wemod_not_game(self):
        report, private = self.plan()
        called = []
        class Child:
            pid = 43210
        def capture(argv, **kwargs):
            called.append((argv, kwargs))
            return Child()
        with patch.object(helper.subprocess, "Popen", capture):
            result = helper.launch(report, private, approved=True, state_root=self.root_state,
                                   proc_root=self.proc, uid=os.getuid())
        self.assertEqual(result["pid"], 43210)
        self.assertEqual(len(called), 1)
        args, options = called[0]
        self.assertEqual(args, [str(self.proton), "runinprefix",
                                 str(self.client / "WeMod.exe")])
        self.assertNotIn("waitforexitandrun", args)
        self.assertEqual(options["env"]["WINEDLLOVERRIDES"], "version=n,b")
        self.assertEqual(options["env"]["SteamAppId"], self.id)
        self.assertEqual(options["env"]["STEAM_COMPAT_DATA_PATH"], str(self.compat))
        self.assertEqual(options["env"]["WEMOD_LOG"], result["log"])
        self.assertNotIn("SECRET_TOKEN", str(options["env"]))
        self.assertNotIn("DO_NOT_LEAK", json.dumps(result))
        self.assertFalse(result["trainer_attachment_verified"])
        self.assertFalse(result["steam_launch_options_changed"])
        self.assertEqual(os.stat(result["log"]).st_mode & 0o777, 0o600)
        self.unchanged()

    def test_electron_gpu_fallback_changes_only_wemod_argv(self):
        report, private = self.plan()
        captured = []
        class Child:
            pid = 43211
        def capture(argv, **kwargs):
            captured.append((argv, kwargs))
            return Child()
        with patch.object(helper.subprocess, "Popen", capture):
            result = helper.launch(
                report, private, approved=True, state_root=self.root_state,
                proc_root=self.proc, uid=os.getuid(), disable_gpu=True)
        self.assertEqual(len(captured), 1)
        args, opts = captured[0]
        self.assertEqual(args, [str(self.proton), "runinprefix",
                               str(self.client / "WeMod.exe"), "--disable-gpu"])
        self.assertEqual(opts["cwd"], self.client)
        self.assertFalse(result["steam_bridge_used"])
        self.assertFalse(result["new_game_launched"])
        self.assertFalse(result["steam_launch_options_changed"])
        self.assertTrue(result["wemod_gpu_disabled"])
        self.assertFalse(result["trainer_attachment_verified"])
        self.unchanged()

    def test_default_client_handoff_leaves_gpu_enabled(self):
        report, private = self.plan()
        class Child:
            pid = 43212
        with patch.object(helper.subprocess, "Popen", return_value=Child()) as launch:
            result = helper.launch(
                report, private, approved=True, state_root=self.root_state,
                proc_root=self.proc, uid=os.getuid())
        self.assertFalse(result["wemod_gpu_disabled"])
        self.assertNotIn("--disable-gpu", launch.call_args.args[0])
        self.unchanged()

    def test_missing_approval_never_spawns(self):
        report, private = self.plan()
        with patch.object(helper.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(helper.AttachBlocked, "approval"):
                helper.launch(report, private, approved=False, state_root=self.root_state)
            popen.assert_not_called()
        self.assertFalse(self.root_state.exists())
        self.unchanged()

    def test_duplicate_wemod_process_blocks_second_instance(self):
        self.make_proc(client=True)
        report, private = self.plan()
        self.assertTrue(report["wemod_already_visible"])
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        with self.assertRaisesRegex(helper.AttachBlocked, "clean live-session"):
            helper.launch(report, private, approved=True)
        self.unchanged()

    def test_wrong_appid_or_prefix_blocks_session(self):
        self.make_proc(appid="999999")
        report, _ = self.plan()
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.assertEqual(report["matching_prefix_processes"], 0)
        self.unchanged()

    def test_ambiguous_proton_tool_path_blocks(self):
        second = self.base / "Second-Proton"
        second.mkdir()
        (second / "proton").write_text("#!/bin/sh\nexit 98\n")
        (second / "proton").chmod(0o700)
        (second / "toolmanifest.vdf").write_text("fixture")
        self.make_proc(paths=f"{self.proton_dir}:{second}")
        report, _ = self.plan()
        self.assertFalse(report["unique_proton_context"])
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.unchanged()

    def test_missing_client_blocks_and_does_not_touch_prefix(self):
        (self.client / "resources/app.asar").unlink()
        report, _ = self.plan()
        self.assertFalse(report["managed_client_present"])
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.unchanged()

    def test_missing_game_manifest_blocks(self):
        (self.steamapps / f"appmanifest_{self.id}.acf").unlink()
        with self.assertRaisesRegex(helper.AttachBlocked, "manifest"):
            self.plan()
        self.unchanged()

    def test_unreadable_process_environment_fails_closed(self):
        original = helper.read_env
        def deny(proc):
            if proc.name == "1000":
                raise PermissionError("simulated privacy restriction")
            return original(proc)
        with patch.object(helper, "read_env", side_effect=deny):
            report, _ = self.plan()
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.assertEqual(report["matching_prefix_processes"], 0)
        self.unchanged()

    def test_acknowledged_unknowns_only_allow_matching_game_context(self):
        # Original game's exact Steam environment remains readable; unrelated
        # processes cannot be inspected, as on the user's CachyOS desktop.
        for i in range(4):
            p = self.proc / str(2001 + i)
            p.mkdir()
            (p / "environ").write_bytes(b"unreadable-fixture")
        original = helper.read_env
        def inaccessible(proc):
            if int(proc.name) >= 2001:
                raise PermissionError("fixture unreadable")
            return original(proc)
        with patch.object(helper, "read_env", side_effect=inaccessible):
            preview, _ = self.plan()
            self.assertFalse(preview["can_attempt_with_explicit_consent"])
            accepted, priv = helper.plan(
                self.id, self.game, self.client, proc_root=self.proc, uid=os.getuid(),
                accept_unreadable_risk=True)
            self.assertEqual(accepted["unreadable_same_user_processes"], 4)
            self.assertTrue(accepted["unreadable_process_risk_accepted"])
            self.assertTrue(accepted["can_attempt_with_explicit_consent"])
            with patch.object(helper.subprocess, "Popen") as spawn:
                spawn.return_value.pid = 45678
                result = helper.launch(
                    accepted, priv, approved=True, state_root=self.root_state,
                    proc_root=self.proc, uid=os.getuid(),
                    accept_unreadable_risk=True)
                self.assertEqual(result["pid"], 45678)
                spawn.assert_called_once()
            with patch.object(helper.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(helper.AttachBlocked, "session changed"):
                    helper.launch(
                        accepted, priv, approved=True,
                        proc_root=self.proc, uid=os.getuid(),
                        accept_unreadable_risk=False)
                spawn.assert_not_called()
        self.unchanged()

    def test_protected_host_and_overlay_processes_do_not_block_we_mod(self):
        # Models the observed KDE/CachyOS /proc audit: unreadable desktop
        # services and Steam overlay tasks are not Wine or WeMod clients.
        names = [
            "systemd", "(sd-pam)", "polkit-kde-auth", "arch-update",
            "kwin_wayland", "gameoverlayui", "gameoverlayui",
            "gameoverlayui", "gameoverlayui", "gameoverlayui",
        ]
        for i, name in enumerate(names):
            p = self.proc / str(2001 + i)
            p.mkdir()
            (p / "environ").write_bytes(b"hidden-environment")
            (p / "comm").write_text(name + "\n")
            (p / "cmdline").write_bytes(name.encode() + b"\x00")
        original = helper.read_env

        def protect(proc):
            if int(proc.name) >= 2001:
                raise PermissionError("simulated protected desktop environment")
            return original(proc)

        with patch.object(helper, "read_env", side_effect=protect):
            report, private = self.plan()
            self.assertTrue(report["can_attempt_with_explicit_consent"])
            self.assertEqual(report["unreadable_same_user_processes"], 0)
            self.assertEqual(report["unreadable_recognized_host_processes"], 10)
            self.assertEqual(report["matching_prefix_processes"], 1)
            with patch.object(helper.subprocess, "Popen") as spawned:
                spawned.return_value.pid = 54321
                result = helper.launch(
                    report, private, approved=True, state_root=self.root_state,
                    proc_root=self.proc, uid=os.getuid())
                self.assertEqual(result["pid"], 54321)
                spawned.assert_called_once()
        self.unchanged()

    def test_host_name_cannot_hide_a_wemod_executable(self):
        p = self.proc / "2001"
        p.mkdir()
        (p / "environ").write_bytes(b"hidden-environment")
        (p / "comm").write_text("gameoverlayui\n")
        (p / "cmdline").write_bytes(b"/any/WeMod.exe\x00")
        original = helper.read_env

        def protect(proc):
            if proc.name == "2001":
                raise PermissionError("cannot inspect matching Steam game overlay")
            return original(proc)

        with patch.object(helper, "read_env", side_effect=protect):
            report, private = self.plan()
            self.assertEqual(report["unreadable_same_user_processes"], 1)
            self.assertEqual(report["unreadable_recognized_host_processes"], 0)
            self.assertFalse(report["can_attempt_with_explicit_consent"])
            with patch.object(helper.subprocess, "Popen") as spawned:
                with self.assertRaisesRegex(helper.AttachBlocked, "clean live-session"):
                    helper.launch(report, private, approved=True)
                spawned.assert_not_called()
        self.unchanged()

    def test_unreadable_wine_process_still_blocks_handoff(self):
        p = self.proc / "2001"
        p.mkdir()
        (p / "environ").write_bytes(b"hidden-environment")
        (p / "comm").write_text("wineserver\n")
        (p / "cmdline").write_bytes(b"wineserver\x00")
        original = helper.read_env

        def protect(proc):
            if proc.name == "2001":
                raise PermissionError("Wine environment inaccessible")
            return original(proc)

        with patch.object(helper, "read_env", side_effect=protect):
            report, _ = self.plan()
            self.assertEqual(report["unreadable_same_user_processes"], 1)
            self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.unchanged()

    def test_unreadable_override_cannot_create_missing_game_session(self):
        self.make_proc(appid="999999")
        report, _ = helper.plan(
            self.id, self.game, self.client, proc_root=self.proc,
            uid=os.getuid(), accept_unreadable_risk=True)
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.assertEqual(report["matching_prefix_processes"], 0)
        self.unchanged()

    def test_more_than_eight_unreadable_processes_always_block(self):
        for i in range(9):
            p = self.proc / str(2001 + i)
            p.mkdir()
            (p / "environ").write_bytes(b"inaccessible-fixture")
        original = helper.read_env
        def unreadable(proc):
            if int(proc.name) >= 2001:
                raise PermissionError("fixture only")
            return original(proc)
        with patch.object(helper, "read_env", side_effect=unreadable):
            report, _ = helper.plan(
                self.id, self.game, self.client, proc_root=self.proc,
                uid=os.getuid(), accept_unreadable_risk=True)
            self.assertFalse(report["unreadable_process_risk_accepted"])
            self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.unchanged()

    def test_tool_must_be_from_live_process_evidence(self):
        self.make_proc(paths="/nonexistent/GE-Proton")
        report, _ = self.plan()
        self.assertFalse(report["unique_proton_context"])
        self.assertFalse(report["can_attempt_with_explicit_consent"])
        self.unchanged()

    def test_session_closes_between_preview_and_launch(self):
        report, private = self.plan()
        (self.pid / "environ").unlink()
        with patch.object(helper.subprocess, "Popen") as spawned:
            with self.assertRaisesRegex(helper.AttachBlocked, "session changed"):
                helper.launch(report, private, approved=True, state_root=self.root_state,
                              proc_root=self.proc, uid=os.getuid())
            spawned.assert_not_called()
        self.assertFalse(self.root_state.exists())
        self.unchanged()

    def test_wemod_starts_between_preview_and_launch(self):
        report, private = self.plan()
        self.make_proc(client=True)
        with patch.object(helper.subprocess, "Popen") as spawned:
            with self.assertRaisesRegex(helper.AttachBlocked, "session changed"):
                helper.launch(report, private, approved=True, state_root=self.root_state,
                              proc_root=self.proc, uid=os.getuid())
            spawned.assert_not_called()
        self.assertFalse(self.root_state.exists())
        self.unchanged()

    def test_no_risky_steam_config_files_created(self):
        report, _ = self.plan()
        self.assertFalse(report["steam_launch_options_changed"])
        self.assertFalse((self.steam_root / "userdata").exists())
        self.assertFalse((self.steam_root / "config").exists())
        self.unchanged()


if __name__ == "__main__":
    unittest.main()
