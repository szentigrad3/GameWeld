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
import time
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
            'dll=directory/"version.dll"\n'
            'helper_dll=Path(__file__).parent/"version.dll"\n'
            'if operation=="patch":\n'
            '    if not backup.exists():backup.write_bytes(asar.read_bytes())\n'
            '    asar.write_bytes(b"PATCHED-FIXTURE")\n'
            '    dll.write_bytes(helper_dll.read_bytes())\n'
            'elif operation=="restore":\n'
            '    asar.write_bytes(backup.read_bytes())\n'
            '    if dll.exists():dll.unlink()\n'
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
        self.assertIn("Wand/WeMod client: FOUND", response.stdout)
        self.assertIn("WeMod Enhancer CLI: READY", response.stdout)
        self.assertEqual(before, (self.client / "resources/app.asar").read_bytes())

    def test_discover_managed_deckcheatz_client(self):
        from unittest.mock import patch
        managed = self.home / ".local/share/gameweld/deckcheatz/wemod_data/wemod_bin"
        (managed / "resources").mkdir(parents=True)
        (managed / "WeMod.exe").write_bytes(b"MZ-FIXTURE")
        (managed / "resources/app.asar").write_bytes(b"TEST-ASAR")
        with patch.dict(os.environ, self.environment):
            with patch.object(bridge, "discover_existing_clients", return_value=[]):
                clients = bridge.available_clients()
        self.assertEqual(clients, [managed.resolve()])

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

    def test_verify_patch_file_evidence_is_read_only(self):
        kwargs = ("--install-dir", str(self.client))
        before = self.cmd("verify", *kwargs)
        self.assertEqual(before.returncode, 2, before.stdout)
        self.assertIn("Client patch file check: NOT VERIFIED", before.stdout)
        self.assertEqual((self.client / "resources/app.asar").read_bytes(), b"ORIGINAL-FIXTURE")
        self.assertEqual(self.cmd("patch", *kwargs, "--confirm").returncode, 0)
        verified = self.cmd("verify", *kwargs)
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("Client patch file check: PASS", verified.stdout)
        self.assertIn("Enhancer DLL proxy: MATCHES", verified.stdout)
        self.assertIn("version=n,b", verified.stdout)
        self.assertEqual(self.cmd("restore", *kwargs, "--confirm").returncode, 0)
        restored = self.cmd("verify", *kwargs)
        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("Client patch file check: NOT VERIFIED", restored.stdout)

    def test_game_test_native_linux_vs_windows_evidence(self):
        kwargs = ("--install-dir", str(self.client))
        patched = self.cmd("patch", *kwargs, "--confirm")
        self.assertEqual(patched.returncode, 0, patched.stdout)
        game = self.root / "steamapp"
        game.mkdir()
        base = ("game-test", *kwargs,
                "--appid", "346900", "--game-name", "AdVenture Capitalist",
                "--game-provider", "steam", "--game-dir", str(game))
        native = self.cmd(*base, "--runtime-hint", "native")
        self.assertEqual(native.returncode, 0, native.stdout)
        self.assertIn("NATIVE LINUX ELF observed", native.stdout)
        self.assertIn("Windows Wand trainer not ready", native.stdout)
        self.assertIn("Trainer available for this specific game: NOT VERIFIED", native.stdout)
        self.assertEqual((self.client / "resources/app.asar").read_bytes(), b"PATCHED-FIXTURE")
        windows = self.cmd(*base, "--runtime-hint", "windows-associated")
        self.assertEqual(windows.returncode, 0, windows.stdout)
        self.assertIn("Windows-process name ASSOCIATED", windows.stdout)
        self.assertIn("live in-game trainer not yet proven", windows.stdout)
        invalid = self.cmd("game-test", *kwargs, "--appid", "346900;sh",
            "--game-provider", "steam")
        self.assertNotEqual(invalid.returncode, 0)

    def test_wand_smoke_launch_uses_existing_prefix_and_native_override(self):
        kwargs = ("--install-dir", str(self.client))
        patched = self.cmd("patch", *kwargs, "--confirm")
        self.assertEqual(patched.returncode, 0, patched.stdout)
        fake_prefix = self.root / "existing-prefix"
        (fake_prefix / "drive_c").mkdir(parents=True)
        commands = self.root / "bin"
        commands.mkdir()
        capture = self.root / "wine-env.txt"
        wine = commands / "wine"
        wine.write_text('#!/bin/sh\nprintf "%s\\n" "$WINEDLLOVERRIDES" > "$GAMEWELD_TEST_CAPTURE"\n', encoding="utf-8")
        wine.chmod(0o755)
        env = self.environment.copy()
        env["PATH"] = str(commands) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
        env["GAMEWELD_TEST_CAPTURE"] = str(capture)
        command = [sys.executable, str(HELPER), "launch-test", *kwargs,
                   "--wine-prefix", str(fake_prefix)]
        blocked = subprocess.run(command,env=env,text=True,capture_output=True,timeout=20)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertFalse(capture.exists())
        permitted = subprocess.run(command+["--confirm"],env=env,text=True,capture_output=True,timeout=20)
        self.assertEqual(permitted.returncode, 0, permitted.stdout+permitted.stderr)
        self.assertIn("Wand Wine smoke-test launch requested", permitted.stdout)
        self.assertIn("Client UI appeared / DLL loaded / login / trainer attach: NOT VERIFIED",permitted.stdout)
        for _ in range(100):
            if capture.exists():
                break
            time.sleep(0.01)
        self.assertTrue(capture.exists(), "Fake Wine helper not invoked")
        self.assertEqual(capture.read_text(encoding="utf-8").strip(), "version=n,b")

    def test_overview_read_only_auto_resolves_unique_patched_client(self):
        from unittest.mock import patch
        second = self.root / "app-1.2.3"
        (second / "resources").mkdir(parents=True)
        (second / "resources/app.asar").write_bytes(b"UNPATCHED VERSION")
        clients = [self.client, second]
        with patch.object(bridge, "discover_existing_clients", return_value=clients):
            self.assertIsNone(bridge.detect_wemod())
            response = self.cmd("game-test", "--game-provider", "steam",
                "--appid", "2533250", "--game-name", "Astrometica")
            # In the subprocess the real scanner sees no test fixtures.
            self.assertNotEqual(response.returncode, 0)
        self.assertEqual(self.cmd("patch", "--install-dir", str(self.client), "--confirm").returncode, 0)
        resolved, why = bridge.resolve_read_only_client(clients, self.helper)
        self.assertEqual(resolved, self.client.resolve())
        self.assertIn("only client", why)
        untouched = (second / "resources/app.asar").read_bytes()
        self.assertEqual(untouched, b"UNPATCHED VERSION")
        # Read-only auto-resolution must never authorize patch/restore on
        # multiple installations without the user's explicit selection.
        with patch.object(bridge, "discover_existing_clients", return_value=clients):
            self.assertIsNone(bridge.detect_wemod())

    def test_auto_resolve_refuses_two_patched_clients(self):
        one = self.client
        two = self.root / "app-5.6.7"
        (two / "resources").mkdir(parents=True)
        (two / "resources/app.asar").write_bytes(b"FIRST")
        (two / "resources/app.asar.backup").write_bytes(b"ORIGINAL")
        (two / "version.dll").write_bytes((self.helper / "bin/version.dll").read_bytes())
        (one / "resources/app.asar.backup").write_bytes(b"ORIGINAL")
        (one / "resources/app.asar").write_bytes(b"FIRST")
        (one / "version.dll").write_bytes((self.helper / "bin/version.dll").read_bytes())
        resolved, reason = bridge.resolve_read_only_client([one, two], self.helper)
        self.assertIsNone(resolved)
        self.assertIn("more than one patched", reason)

    def test_auto_resolve_refuses_multiple_unpatched_clients(self):
        other = self.root / "app-0.1.2"
        (other / "resources").mkdir(parents=True)
        (other / "resources/app.asar").write_bytes(b"VANILLA")
        resolved, reason = bridge.resolve_read_only_client([self.client, other], self.helper)
        self.assertIsNone(resolved)
        self.assertIn("none uniquely verified", reason)

    def test_missing_wemod_folder_is_not_patched(self):
        response = self.cmd("patch", "--install-dir", str(self.root / "not-found"), "--confirm")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("no unique wand/wemod client", response.stdout.lower())

    def test_wand_executable_and_app_version_discovery(self):
        original = self.client / "WeMod.exe"
        original.rename(self.client / "Wand.exe")
        self.assertEqual(bridge.client_root(self.client), self.client.resolve())
        response = self.cmd("status", "--install-dir", str(self.client))
        self.assertEqual(response.returncode, 0, response.stdout)
        self.assertIn("Wand/WeMod client: FOUND", response.stdout)

        # PC1's scanner reports app-versions whose WeMod.exe is in a parent.
        version = self.root / "app-11.12.13"
        (version / "resources").mkdir(parents=True)
        (version / "resources/app.asar").write_bytes(b"FIXTURE")
        self.assertEqual(bridge.client_root(version), version.resolve())

    def test_ambiguous_existing_clients_are_not_selected(self):
        from unittest.mock import patch
        second = self.root / "app-3.4.5"
        (second / "resources").mkdir(parents=True)
        (second / "resources/app.asar").write_bytes(b"FIXTURE")
        # Run discovery against the test HOME, never a developer's real
        # managed DeckCheatz installation or explicit client override.
        with patch.dict(os.environ, {"HOME": str(self.home),
                                     "GAMEWELD_WEMOD_INSTALL_DIR": ""}):
            with patch.object(bridge, "discover_existing_clients", return_value=[self.client, second]):
                self.assertIsNone(bridge.detect_wemod())
                self.assertEqual(len(bridge.available_clients()), 2)
                # Explicit selection still works even when multiple clients
                # exist, without altering any installed WeMod files.
                self.assertEqual(bridge.detect_wemod(str(second)), second.resolve())

    def test_unrelated_proton_tool_is_not_a_wemod_client(self):
        tool = self.root / "GE-Proton-Wand-SHA256"
        (tool / "resources").mkdir(parents=True)
        (tool / "resources/app.asar").write_bytes(b"FAKE")
        self.assertIsNone(bridge.client_root(tool))

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

    def make_live_proton_fixture(self, appid="2353250", comm="Astrometica.exe"):
        from pathlib import Path
        proc = self.root / "proc-fixture"
        prefix = self.root / "compat" / appid
        (prefix / "pfx" / "drive_c").mkdir(parents=True, exist_ok=True)
        steamroot = self.root / "steam-root"
        steamroot.mkdir(exist_ok=True)
        runtime = self.root / "Proton"
        runtime.mkdir(exist_ok=True)
        proton = runtime / "proton"
        proton.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        proton.chmod(0o755)
        wine_bin = runtime / "files" / "bin"
        wine_bin.mkdir(parents=True)
        wine = wine_bin / "wine"
        wine.write_text('#!/bin/sh\n'
                        'printf "%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n" "$WINEDLLOVERRIDES" "$WINEPREFIX" '
                        '"$WINE_GRAPHICS_DRIVER" "$PROTON_USE_X11_EXCLUSIVE" "$WINELOADER" '+
                       '"$WINESERVER" "$WINEFSYNC" > "$GAMEWELD_TEST_CAPTURE"\n',
                        encoding="utf-8")
        wine.chmod(0o755)
        wine_server = wine_bin / "wineserver"
        wine_server.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        wine_server.chmod(0o755)
        for pid, process in ((701, comm), (702, "reaper")):
            directory = proc / str(pid)
            directory.mkdir(parents=True, exist_ok=True)
            environment = {
                "SteamAppId": appid,
                "STEAM_COMPAT_APP_ID": appid,
                "STEAM_COMPAT_DATA_PATH": str(prefix),
                "STEAM_COMPAT_TOOL_PATHS": str(runtime),
                "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steamroot),
                "WINEFSYNC": "1",
            }
            (directory / "environ").write_bytes(b"\0".join(
                (key + "=" + value).encode() for key, value in environment.items()) + b"\0")
            (directory / "comm").write_text(process + "\n", encoding="utf-8")
        return proc, prefix, proton

    def test_live_proton_requires_running_windows_game_not_steam_helper(self):
        proc, prefix, proton = self.make_live_proton_fixture()
        session = bridge.live_steam_proton_session("2353250", proc)
        self.assertEqual(session["game_pid"], 701)
        self.assertEqual(session["compat"], prefix.resolve())
        self.assertEqual(session["proton"], proton.resolve())
        self.assertEqual(session["process_count"], 2)
        with self.assertRaisesRegex(ValueError, "No same-user live Proton session"):
            bridge.live_steam_proton_session("2353251", proc)
        (proc / "701" / "comm").write_text("steamwebhelper\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Only Steam helpers"):
            bridge.live_steam_proton_session("2353250", proc)

    def test_live_proton_rejects_ambiguous_game_prefixes(self):
        proc, prefix, proton = self.make_live_proton_fixture()
        other = self.root / "other-compat"
        (other / "pfx" / "drive_c").mkdir(parents=True)
        env_file = proc / "703" / "environ"
        env_file.parent.mkdir()
        raw = (proc / "701" / "environ").read_bytes()
        env_file.write_bytes(raw.replace(str(prefix).encode(), str(other).encode()))
        (env_file.parent / "comm").write_text("Another.exe\n")
        with self.assertRaisesRegex(ValueError, "Multiple live Proton prefixes"):
            bridge.live_steam_proton_session("2353250", proc)

    def test_live_launch_joins_active_proton_wineserver_with_wand_only_x11(self):
        from unittest.mock import patch
        proc, prefix, proton = self.make_live_proton_fixture()
        capture = self.root / "proton-capture.txt"
        proton.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n%s\\n%s\\n" "$WINEDLLOVERRIDES" '
            '"$STEAM_COMPAT_DATA_PATH" "$STEAM_COMPAT_APP_ID" > "$GAMEWELD_TEST_CAPTURE"\n',
            encoding="utf-8",
        )
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        self.assertEqual(self.cmd("patch", "--install-dir", str(self.client),
                                  "--confirm").returncode, 0)
        with patch.dict(os.environ, {"GAMEWELD_TEST_CAPTURE": str(capture),
                                    "XDG_STATE_HOME": str(self.root / "state"),
                                    "DISPLAY": ":0"}):
            with self.assertRaisesRegex(ValueError, "Steam game installation directory"):
                bridge.launch_wand_in_live_game(
                    self.client, self.helper, "2353250", "", proc)
            bridge.launch_wand_in_live_game(
                self.client, self.helper, "2353250", str(game_dir), proc)
        self.assertTrue(capture.exists(), "Exact fake Proton was not invoked")
        self.assertEqual(capture.read_text().splitlines(), [
            "version=n,b", str(prefix.resolve() / "pfx"), "x11", "WeMod.exe",
            str(proton.parent / "files" / "bin" / "wine"),
            str(proton.parent / "files" / "bin" / "wineserver"), "1",
        ])
        # Nothing about the request certifies a trainer is attached.
        self.assertEqual((self.client / "resources/app.asar").read_bytes(),
                         b"PATCHED-FIXTURE")

    def test_live_x11_join_fails_closed_when_proton_wine_is_missing(self):
        from unittest.mock import patch
        proc, _prefix, proton = self.make_live_proton_fixture()
        (proton.parent / "files" / "bin" / "wine").unlink()
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        self.assertEqual(self.cmd("patch", "--install-dir",
                                  str(self.client), "--confirm").returncode, 0)
        with patch.dict(os.environ, {"DISPLAY": ":0",
                                    "XDG_STATE_HOME": str(self.root / "state")}):
            with self.assertRaisesRegex(ValueError, "files/bin/wine"):
                bridge.launch_wand_in_live_game(
                    self.client, self.helper, "2353250", str(game_dir), proc)

    def test_live_gpu_off_retry_passes_chromium_flags_and_captures_proton_log(self):
        from unittest.mock import patch
        import stat
        proc, prefix, proton = self.make_live_proton_fixture()
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        capture = self.root / "software-render-args.txt"
        wine = proton.parent / "files" / "bin" / "wine"
        wine.write_text(
            '#!/bin/sh\n'
            'printf "overrides=%s\\nprefix=%s\\n" "$WINEDLLOVERRIDES" '
            '"$WINEPREFIX" > "$GAMEWELD_TEST_CAPTURE"\n'
            'printf "arg=%s\\n" "$@" >> "$GAMEWELD_TEST_CAPTURE"\n'
            'echo "fake Wine stderr: renderer unavailable" >&2\n',
            encoding="utf-8"
        )
        # The selected game's prior DLL overrides must survive in the WeMod
        # child; the existing version rule must be replaced, not duplicated.
        envfile = proc / "701" / "environ"
        envfile.write_bytes(envfile.read_bytes() +
                            b"WINEDLLOVERRIDES=crypt32=b;version=b\0")
        self.assertEqual(
            self.cmd("patch", "--install-dir", str(self.client),
                     "--confirm").returncode, 0
        )
        state = self.root / "private-state"
        with patch.dict(os.environ, {
            "XDG_STATE_HOME": str(state),
            "GAMEWELD_TEST_CAPTURE": str(capture),
            "DISPLAY": ":0",
        }):
            bridge.launch_wand_in_live_game(
                self.client, self.helper, "2353250", str(game_dir),
                proc, software_render=True)
        argv = capture.read_text().splitlines()
        self.assertEqual(argv[0], "overrides=crypt32=b;version=n,b")
        self.assertEqual(argv[1], "prefix=" + str(prefix.resolve() / "pfx"))
        self.assertIn("arg=" + str(self.client / "WeMod.exe"), argv)
        self.assertIn("arg=--disable-gpu", argv)
        self.assertIn("arg=--disable-gpu-compositing", argv)
        self.assertIn("arg=--enable-logging=stderr", argv)
        self.assertNotIn("arg=runinprefix", argv)
        logs = list((state / "gameweld").glob("wand-live-2353250-*.log"))
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertTrue(log.is_file())
        self.assertIn("direct X11 wineserver join + software rendering", log.read_text())
        self.assertIn("Client executable: " + str(self.client / "WeMod.exe"), log.read_text())
        self.assertIn("fake Wine stderr: renderer unavailable", log.read_text())
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)

    def test_in_process_gpu_experiment_and_wemod_only_dll_trace(self):
        from unittest.mock import patch
        proc, prefix, proton = self.make_live_proton_fixture()
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        capture = self.root / "inprocess-gpu-args.txt"
        wine = proton.parent / "files" / "bin" / "wine"
        wine.write_text(
            '#!/bin/sh\n'
            'printf "winedebug=%s\\n" "$WINEDEBUG" > "$GAMEWELD_TEST_CAPTURE"\n'
            'printf "arg=%s\\n" "$@" >> "$GAMEWELD_TEST_CAPTURE"\n',
            encoding="utf-8"
        )
        self.assertEqual(
            self.cmd("patch", "--install-dir", str(self.client),
                     "--confirm").returncode, 0
        )
        with patch.dict(os.environ, {
            "XDG_STATE_HOME": str(self.root / "private-state"),
            "GAMEWELD_TEST_CAPTURE": str(capture),
            "DISPLAY": ":0",
        }):
            with self.assertRaisesRegex(ValueError, "requires --software-render"):
                bridge.launch_wand_in_live_game(
                    self.client, self.helper, "2353250", str(game_dir), proc,
                    in_process_gpu=True)
            bridge.launch_wand_in_live_game(
                self.client, self.helper, "2353250", str(game_dir), proc,
                software_render=True, in_process_gpu=True, trace_dll_load=True)
        argv = capture.read_text().splitlines()
        self.assertEqual(argv[0], "winedebug=-all,+loaddll")
        self.assertIn("arg=--in-process-gpu", argv)
        self.assertIn("arg=--disable-gpu", argv)
        self.assertNotIn("arg=runinprefix", argv)
        logs = list((self.root / "private-state/gameweld").glob("wand-live-2353250-*.log"))
        self.assertEqual(len(logs), 1)
        log = logs[0].read_text()
        self.assertIn("In-process GPU experiment: True", log)
        self.assertIn("WeMod-only DLL load trace: True", log)

    def test_repeated_handoffs_keep_independent_logs(self):
        from unittest.mock import patch
        proc, prefix, proton = self.make_live_proton_fixture()
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        wine = proton.parent / "files" / "bin" / "wine"
        wine.write_text('#!/bin/sh\necho fake WeMod child\n', encoding="utf-8")
        self.assertEqual(
            self.cmd("patch", "--install-dir", str(self.client),
                     "--confirm").returncode, 0
        )
        state = self.root / "private-state"
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(state), "DISPLAY": ":0"}):
            bridge.launch_wand_in_live_game(
                self.client, self.helper, "2353250", str(game_dir), proc)
            logs = list((state / "gameweld").glob("wand-live-2353250-*.log"))
            self.assertEqual(len(logs), 1)
            first = logs[0]
            original = first.read_bytes()
            bridge.launch_wand_in_live_game(
                self.client, self.helper, "2353250", str(game_dir), proc,
                software_render=True)
        logs = list((state / "gameweld").glob("wand-live-2353250-*.log"))
        self.assertEqual(len(logs), 2)
        self.assertEqual(first.read_bytes(), original)
        other = next(path for path in logs if path != first)
        self.assertIn(b"software rendering requested", other.read_bytes())
        self.assertNotIn(b"\x00", other.read_bytes())

    def test_isolated_official_legacy_baseline_without_enhancer(self):
        from unittest.mock import patch
        import json
        proc, prefix, proton = self.make_live_proton_fixture()
        baseline = self.data / "gameweld/wemod-compat/11.6.0"
        (baseline / "resources").mkdir(parents=True)
        (baseline / "WeMod.exe").write_bytes(b"MZ-BASELINE")
        (baseline / "resources/app.asar").write_bytes(b"BASELINE-ASAR")
        data = {
            "tool": "gameweld-isolated-wemod-baseline",
            "version": "11.6.0",
            "package_sha256": "5b94ae5592e698b13cbc06fae4c096fe2438cbd362daac3f842e13190bf836ba",
            "exe_sha256": hashlib.sha256((baseline / "WeMod.exe").read_bytes()).hexdigest(),
            "asar_sha256": hashlib.sha256((baseline / "resources/app.asar").read_bytes()).hexdigest(),
        }
        (baseline / ".gameweld-baseline.json").write_text(json.dumps(data))
        capture = self.root / "baseline-env.txt"
        wine = proton.parent / "files" / "bin" / "wine"
        wine.write_text(
            '#!/bin/sh\\n'
            'printf "dll=%s\\n" "$WINEDLLOVERRIDES" > "$GAMEWELD_TEST_CAPTURE"\\n',
            encoding="utf-8"
        )
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        env = dict(self.environment, XDG_STATE_HOME=str(self.root / "state"),
                   DISPLAY=":0", GAMEWELD_TEST_CAPTURE=str(capture))
        with patch.dict(os.environ, env):
            bridge.verify_legacy_baseline(baseline)
            bridge.launch_wand_in_live_game(
                baseline, self.helper, "2353250", str(game_dir), proc,
                software_render=True, legacy_baseline=True)
            self.assertEqual(capture.read_text().strip(), "dll=")
            # Patching even one DLL removes the client from the clean baseline.
            (baseline / "version.dll").write_bytes(b"MZ-PATCHED")
            with self.assertRaisesRegex(ValueError, "contains version.dll"):
                bridge.verify_legacy_baseline(baseline)
            (baseline / "version.dll").unlink()
            (baseline / "resources/app.asar").write_bytes(b"MODIFIED")
            with self.assertRaisesRegex(ValueError, "file hash mismatch"):
                bridge.verify_legacy_baseline(baseline)

    def test_legacy_baseline_cli_must_use_explicit_directory(self):
        response = self.cmd("live-launch", "--confirm", "--legacy-baseline",
                            "--game-provider", "steam", "--appid", "2353250")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("requires an explicit --install-dir", response.stdout)

    def test_software_render_only_allowed_for_confirmed_live_launch(self):
        status = self.cmd("status", "--software-render", "--appid", "2353250")
        self.assertNotEqual(status.returncode, 0)
        self.assertIn("--software-render is only supported", status.stdout)
        game_dir = self.root / "Astrometica"
        game_dir.mkdir()
        denied = self.cmd("live-launch", "--software-render",
                          "--game-provider", "steam", "--appid", "2353250",
                          "--game-dir", str(game_dir), "--install-dir", str(self.client))
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("requires explicit --confirm", denied.stdout)

    def test_gpu_in_process_cli_requires_software_and_live_launch(self):
        response = self.cmd("status", "--in-process-gpu")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("confirmed live Wand launch", response.stdout)
        response = self.cmd("live-launch", "--in-process-gpu",
                            "--appid", "2353250", "--confirm")
        self.assertNotEqual(response.returncode, 0)
        self.assertIn("requires --software-render", response.stdout)

    def test_live_launch_cli_fails_closed_without_confirmation_or_process(self):
        game = self.root / "Astrometica"
        game.mkdir()
        self.assertEqual(self.cmd("patch", "--install-dir",
                                  str(self.client), "--confirm").returncode, 0)
        options = ("live-launch", "--install-dir", str(self.client),
                   "--game-provider", "steam", "--appid", "2353250",
                   "--game-dir", str(game))
        before = self.cmd(*options)
        self.assertNotEqual(before.returncode, 0, before.stdout)
        self.assertIn("requires explicit --confirm", before.stdout)
        # Normal developer/CI machines must not claim an Astrometica session.
        bad_id = self.cmd("live-launch", "--install-dir", str(self.client),
                          "--game-provider", "steam", "--appid", "2353250;echo x",
                          "--game-dir", str(game), "--confirm")
        self.assertNotEqual(bad_id.returncode, 0, bad_id.stdout)


    def test_live_launch_reuses_only_uniquely_patched_client_among_three(self):
        """Regression: game-test resolves app-12.55.0, live-launch must too.

        This is entirely mocked: no real Steam, Wine, Wand or game is started.
        Patch/restore still never infer a writable target from multiple clients.
        """
        import contextlib
        from unittest.mock import patch
        other_clients = []
        for version in ("app-11.0.0", "app-13.0.0"):
            folder = self.root / version
            (folder / "resources").mkdir(parents=True)
            (folder / "resources/app.asar").write_bytes(b"UNPATCHED")
            other_clients.append(folder)
        result = self.cmd("patch", "--install-dir", str(self.client), "--confirm")
        self.assertEqual(result.returncode, 0, result.stdout)
        candidates = [other_clients[0], self.client, other_clients[1]]
        app_dir = self.root / "Astrometica"
        app_dir.mkdir()
        arguments = [
            "gameweld-wemod-enhancer.py", "live-launch", "--confirm",
            "--game-provider", "steam", "--appid", "2353250",
            "--game-dir", str(app_dir),
        ]
        output = io.StringIO()
        with patch.dict(os.environ, self.environment):
            with patch.object(bridge, "available_clients", return_value=candidates):
                with patch.object(bridge, "launch_wand_in_live_game") as launch:
                    with patch.object(sys, "argv", arguments):
                        with contextlib.redirect_stdout(output):
                            self.assertEqual(bridge.main(), 0)
                    launch.assert_called_once_with(
                        self.client, self.helper, "2353250", str(app_dir))
                    self.assertIn("only client with matching, verified", output.getvalue())
                    # A GUI click without consent never gets as far as launching.
                    with patch.object(sys, "argv",
                                      [x for x in arguments if x != "--confirm"]):
                        with self.assertRaisesRegex(ValueError, "explicit --confirm"):
                            bridge.main()
                    self.assertEqual(launch.call_count, 1)
                    # Two genuinely patched clients must fail closed.
                    second = other_clients[1]
                    (second / "resources/app.asar.backup").write_bytes(b"ORIGINAL")
                    (second / "version.dll").write_bytes(
                        (self.helper / "bin/version.dll").read_bytes())
                    with patch.object(sys, "argv", arguments):
                        with self.assertRaisesRegex(ValueError, "more than one patched"):
                            bridge.main()
                    self.assertEqual(launch.call_count, 1)
                    # Patch and Restore may not silently select a target.
                    with patch.object(sys, "argv",
                                      ["gameweld-wemod-enhancer.py", "restore", "--confirm"]):
                        with self.assertRaisesRegex(ValueError, "No unique"):
                            bridge.main()
                    self.assertEqual(launch.call_count, 1)
        self.assertEqual((other_clients[0] / "resources/app.asar").read_bytes(), b"UNPATCHED")


if __name__ == "__main__":
    unittest.main()
