#!/usr/bin/env python3
"""Offline tests of one-shot Steam wrapper, never launches real Steam/games."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("gameweld-deckcheatz-session.py")
SPEC = importlib.util.spec_from_file_location("gw_steam_one_shot", SCRIPT)
assert SPEC and SPEC.loader
session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session)


class SingleSessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gameweld-oneshot-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.states = self.root / "state"
        self.launcher = self.root / "installed-deckcheatz/wemod"
        self.launcher.parent.mkdir()
        self.launcher.write_text("#!/usr/bin/env python3\n")
        self.launcher.chmod(0o755)
        self.appid = "3008130"

    def test_arm_consume_passthrough_and_one_shot_cleanup(self):
        before = dict(os.environ)
        launched, normal = [], []
        armed = session.arm(self.appid, self.launcher,
                            state_root=self.states, now=1000)
        self.assertEqual(armed["result"], "SINGLE_SESSION_ARMED")
        self.assertFalse(armed["steam_launch_options_changed"])
        self.assertTrue(session.status(self.appid, state_root=self.states,
                                       now=1001)["session_armed"])
        with self.assertRaisesRegex(session.SessionBlocked, "already armed"):
            session.arm(self.appid, self.launcher,
                        state_root=self.states, now=1002)

        def spawn(argv, *, env):
            launched.append((argv, env.copy()))
            return 0

        def passthrough(command, argv, env):
            normal.append((command, argv, env.copy()))
            return 0

        command = ["/usr/bin/steam-runtime", "waitforexitandrun", "game.exe", "-dx11"]
        status = session.invoke(self.appid, command, state_root=self.states,
                                now=1004, spawn=spawn, passthrough=passthrough)
        self.assertEqual(status, 0)
        self.assertEqual(launched[0][0], [str(self.launcher), *command])
        self.assertEqual(launched[0][1]["WINEDLLOVERRIDES"], "version=n,b")
        self.assertEqual(launched[0][1]["WEMOD_LOG"],
                         str(self.launcher.parent / "wemod.log"))
        self.assertEqual(normal, [])
        self.assertFalse(session.status(self.appid, state_root=self.states,
                                        now=1005)["session_armed"])
        self.assertEqual(before, dict(os.environ))

        # Subsequent launches pass through unchanged, including original env.
        status = session.invoke(self.appid, command, state_root=self.states,
                                now=1006, spawn=spawn, passthrough=passthrough)
        self.assertEqual(status, 0)
        self.assertEqual(len(launched), 1)
        self.assertEqual(normal[0][:2], (command[0], command))
        self.assertEqual(normal[0][2], before)

    def test_failing_or_crashing_trainer_cannot_leave_session_armed(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        def failure(argv, *, env):
            raise RuntimeError("simulated trainer startup crash")
        with self.assertRaisesRegex(RuntimeError, "crash"):
            session.invoke(self.appid, ["/game"], state_root=self.states,
                           now=1003, spawn=failure)
        self.assertFalse(session.status(self.appid, state_root=self.states,
                                        now=1004)["session_armed"])

    def test_game_crash_exit_status_is_returned_and_session_cleared(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        actual = session.invoke(
            self.appid, ["/game"], state_root=self.states, now=1002,
            spawn=lambda args, *, env: 23)
        self.assertEqual(actual, 23)
        self.assertFalse(session.status(self.appid, state_root=self.states,
                                        now=1003)["session_armed"])

    def test_expired_token_does_not_enable_deckcheatz(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        seen = []
        session.invoke(
            self.appid, ["/game"], state_root=self.states, now=1700,
            passthrough=lambda cmd, args, env: seen.append(args),
            spawn=lambda *args, **kwargs: self.fail("expired token launched trainer"))
        self.assertEqual(seen, [["/game"]])
        self.assertFalse(session.status(self.appid, state_root=self.states,
                                        now=1701)["session_armed"])

    def test_disarm_prevents_a_pending_game_from_launching_with_trainer(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        self.assertTrue(session.disarm(self.appid, state_root=self.states)
                        ["pending_session_cancelled"])
        self.assertFalse(session.disarm(self.appid, state_root=self.states)
                         ["pending_session_cancelled"])
        self.assertIsNone(session.consume(self.appid, state_root=self.states, now=1001))

    def test_bad_launcher_symlink_and_nonexecutables_refused(self):
        self.launcher.chmod(0o600)
        with self.assertRaisesRegex(session.SessionBlocked, "not executable"):
            session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        self.launcher.chmod(0o755)
        src = self.launcher.parent / "src"
        src.mkdir()
        target = src / "wemod.py"
        target.write_text("#!/usr/bin/env python3\n")
        target.chmod(0o755)
        self.launcher.unlink()
        self.launcher.symlink_to("src/wemod.py")
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        self.assertEqual(session.consume(self.appid, state_root=self.states,
                                         now=1001), self.launcher)
        self.launcher.unlink()
        outside = self.root / "outside-script"
        outside.write_text("#!/usr/bin/env python3\n")
        outside.chmod(0o755)
        self.launcher.symlink_to(outside)
        with self.assertRaisesRegex(session.SessionBlocked, "symlink"):
            session.arm(self.appid, self.launcher, state_root=self.states, now=1002)

    def test_private_root_token_file_and_no_symlink_acceptance(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        token, lock = session.paths(self.appid, session.private_root(self.states))
        self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(token.parent.stat().st_mode), 0o700)
        self.assertFalse(lock.is_symlink())
        self.assertEqual(session.read_token(token)["appid"], self.appid)
        token.unlink()
        target = self.root / "private"
        target.write_text("do not modify")
        token.symlink_to(target)
        with self.assertRaisesRegex(session.SessionBlocked, "Unsafe"):
            session.consume(self.appid, state_root=self.states, now=1001)
        self.assertEqual(target.read_text(), "do not modify")

    def test_default_pass_through_without_armed_token(self):
        calls = []
        rc = session.invoke(self.appid, ["/usr/bin/true", "foo"],
                            state_root=self.states, now=1000,
                            passthrough=lambda *a: calls.append(a),
                            spawn=lambda *a, **kw: self.fail("trainer called"))
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][0], "/usr/bin/true")
        self.assertEqual(calls[0][1], ["/usr/bin/true", "foo"])

    def test_other_appid_cannot_consume_selected_session(self):
        session.arm(self.appid, self.launcher, state_root=self.states, now=1000)
        self.assertIsNone(session.consume("2353250", state_root=self.states, now=1001))
        self.assertTrue(session.status(self.appid, state_root=self.states,
                                       now=1001)["session_armed"])

    def test_safe_one_time_launch_string_and_complex_wrappers_refused(self):
        output, state = session.compose("", SCRIPT, self.appid)
        self.assertEqual(state, "SAFE_EMPTY")
        self.assertIn(f"run --appid {self.appid} -- %command%", output)
        self.assertIn(str(SCRIPT), output)
        self.assertIn("python3", output)
        original = "PROTON_LOG=1  %command% -dx11"
        output, state = session.compose(original, SCRIPT, self.appid)
        self.assertEqual(state, "SAFE_ENV_AND_ARGUMENTS")
        self.assertTrue(output.startswith("PROTON_LOG=1 "))
        self.assertTrue(output.endswith("%command% -dx11"))
        for original in ("mangohud %command%", "gamescope -f -- %command%",
                         "bash -c 'echo hi; %command%'"):
            with self.subTest(original=original):
                value, state = session.compose(original, SCRIPT, self.appid)
                self.assertIsNone(value)
                self.assertTrue(state.startswith("MANUAL_"))

    def test_installer_creates_stable_launcher_once_without_editing_steam(self):
        installed = self.root / "managed/steam-session.py"
        result = session.install_wrapper(destination=installed, source=SCRIPT)
        self.assertEqual(result["result"], "SESSION_WRAPPER_INSTALLED")
        self.assertEqual(result["wrapper"], str(installed))
        self.assertEqual(stat.S_IMODE(installed.stat().st_mode), 0o700)
        again = session.install_wrapper(destination=installed, source=SCRIPT)
        self.assertEqual(again["result"], "SESSION_WRAPPER_ALREADY_INSTALLED")
        self.assertEqual(installed.read_bytes(), SCRIPT.read_bytes())
        installed.write_text("user-edited file")
        with self.assertRaisesRegex(session.SessionBlocked, "different session wrapper"):
            session.install_wrapper(destination=installed, source=SCRIPT)
        self.assertEqual(installed.read_text(), "user-edited file")

    def test_read_only_exact_game_installed_session_verification(self):
        root = self.root / "Steam"
        cfg = root / "userdata/12345/config/localconfig.vdf"
        cfg.parent.mkdir(parents=True)
        launcher = self.root / "managed/steam-session.py"
        launcher.parent.mkdir()
        launcher.write_bytes(b"stub")
        option, state = session.compose("PROTON_LOG=1 %command% -dx11",
                                        launcher, self.appid)
        self.assertEqual(state, "SAFE_ENV_AND_ARGUMENTS")
        escaped = option.replace("\\", "\\\\").replace('"', '\\"')
        cfg.write_text('"UserLocalConfigStore" { "Software" { "Valve" {'
                       '"Steam" { "apps" { "' + self.appid +
                       '" { "LaunchOptions" "' + escaped +
                       '" } } } } } }', encoding="utf-8")
        original = cfg.read_bytes()
        with self.assertRaisesRegex(ValueError, "Need one Steam account"):
            session.verify_steam_option(
                self.appid, wrapper=launcher,
                steam_root=self.root / "no-such-steam")
        details = session.verify_steam_option(
            self.appid, wrapper=launcher, steam_root=root)
        self.assertTrue(details["session_wrapper_installed_in_saved_options"])
        self.assertFalse(details["live_steam_ui_verified"])
        self.assertEqual(cfg.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "no "):
            session.verify_steam_option(
                "2353250", wrapper=launcher, steam_root=root)

    def test_invalid_appid_never_arms(self):
        for appid in ("0", "-1", "1;id", "4294967296", "", "000010"):
            with self.subTest(appid=appid):
                with self.assertRaises(session.SessionBlocked):
                    session.arm(appid, self.launcher, state_root=self.states)

if __name__ == "__main__":
    unittest.main()
