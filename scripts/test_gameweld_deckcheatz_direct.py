#!/usr/bin/env python3
"""PC2 DeckCheatz 1.x provider: synthetic read-only/direct-run safety tests."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-direct.py")
spec = importlib.util.spec_from_file_location("gameweld_deckcheatz_direct", SOURCE)
backend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend
spec.loader.exec_module(backend)


class DeckCheatzDirectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gw-deckcheatz-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        checkout = self.root / "deckcheatz"
        src = checkout / "src"
        src.mkdir(parents=True)
        (src / "wemod.py").write_text("# source fixture\n")
        (checkout / "wemod").symlink_to(Path("src/wemod.py"))
        (checkout / "README.md").write_text("WeMod Launcher testing\n")
        (checkout / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE\n")
        self.checkout = checkout
        self.launcher = checkout / "wemod"

        root = self.root / "Steam"
        lib = self.root / "Library"
        steamapps = lib / "steamapps"
        gamedir = steamapps / "common" / "Astrometica"
        gamedir.mkdir(parents=True)
        exe = gamedir / "Astrometica.exe"
        exe.write_bytes(b"MZ-game")
        (steamapps / "appmanifest_2353250.acf").write_text('"appid" "2353250"')
        compat = steamapps / "compatdata/2353250"
        (compat / "pfx").mkdir(parents=True)
        proton = root / "compatibilitytools.d/GE-Proton/proton"
        proton.parent.mkdir(parents=True)
        proton.write_text("#!/bin/sh\nexit 0\n")
        proton.chmod(0o755)
        (root / "steamapps").mkdir(exist_ok=True)
        self.exe = exe
        self.game = gamedir
        self.compat = compat
        self.proton = proton
        self.steam = root

        self.flags = [
            "--appid", "2353250",
            "--launcher", str(self.launcher),
            "--proton", str(proton),
            "--game-exe", str(exe),
            "--install-dir", str(gamedir),
            "--compatdata", str(compat),
            "--steam-root", str(root),
        ]

    def test_discovery_is_readonly_and_confirms_1x_layout(self):
        with patch.object(backend, "installed_candidates", return_value=[self.launcher]):
            with patch.object(backend.subprocess, "run") as process:
                with redirect_stdout(io.StringIO()) as result:
                    self.assertEqual(backend.main(["--discover"]), 0)
                process.assert_not_called()
        report = json.loads(result.getvalue())
        self.assertEqual(report["available_count"], 1)
        self.assertEqual(report["checkouts"][0]["license"], "AGPL-3.0")

    def test_preview_does_not_write_steam_options_or_spawn(self):
        with patch.object(backend.subprocess, "run") as process:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(backend.main(["--preview", *self.flags]), 0)
            process.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertFalse(result["steam_launch_options_modified"])
        self.assertFalse(result["will_invoke_steam_client"])
        self.assertEqual(result["argv"], [
            sys.executable, str(self.launcher), str(self.proton),
            "waitforexitandrun", str(self.exe),
        ])
        self.assertEqual(result["env_overrides"]["STEAM_COMPAT_TOOL_PATHS"],
                         str(self.proton.parent))
        self.assertEqual(result["env_overrides"]["SteamAppId"], "2353250")
        self.assertEqual(result["readiness"], "preview_only_unverified")

    def test_launch_requires_both_explicit_consents(self):
        for extra in ([], ["--confirm-prefix-changes"], ["--experimental-direct-launch"]):
            with self.subTest(extra=extra):
                with patch.object(backend.subprocess, "run") as process:
                    with self.assertRaisesRegex(backend.Blocked, "requires BOTH"):
                        backend.main(["--launch", *self.flags, *extra])
                    process.assert_not_called()

    def test_full_consent_spawns_only_external_launcher_not_steam(self):
        result = SimpleNamespace(returncode=0)
        with patch.object(backend, "active_game_process", return_value=False):
            with patch.object(backend.subprocess, "run", return_value=result) as process:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(backend.main([
                        "--launch", *self.flags,
                        "--game-arg=--windowed",
                        "--confirm-prefix-changes", "--experimental-direct-launch",
                    ]), 0)
        args, kwargs = process.call_args
        self.assertEqual(args[0][0], sys.executable)
        self.assertEqual(args[0][1], str(self.launcher))
        self.assertEqual(args[0][-1], "--windowed")
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["cwd"], str(self.exe.parent))
        self.assertEqual(kwargs["env"]["STEAM_COMPAT_DATA_PATH"], str(self.compat))
        self.assertEqual(kwargs["env"]["SELF_UPDATE"], "False")
        self.assertNotIn("steam", [Path(x).name for x in args[0]])
        self.assertNotIn("shell", kwargs)

    def test_active_game_refuses_duplicate_launch(self):
        with patch.object(backend, "active_game_process", return_value=True):
            with patch.object(backend.subprocess, "run") as process:
                with self.assertRaisesRegex(backend.Blocked, "already has an active process"):
                    backend.main(["--launch", *self.flags,
                                  "--confirm-prefix-changes",
                                  "--experimental-direct-launch"])
                process.assert_not_called()


    def test_process_scan_refuses_unreadable_same_user_environment(self):
        pid = self.root / "proc" / "12345"
        pid.mkdir(parents=True)
        (pid / "environ").write_bytes(b"SteamAppId=2353250\\0")
        with patch.object(backend.os, "getuid", return_value=os.getuid()):
            with patch.object(Path, "open", autospec=True, side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(backend.Blocked, "Cannot verify"):
                    backend.active_game_process("2353250", pid.parent)

    def test_process_scan_ignores_recognized_kde_and_overlay_tasks(self):
        root = self.root / "proc"
        for i, name in enumerate(("systemd", "(sd-pam)", "kwin_wayland",
                                  "gameoverlayui", "gameoverlayui")):
            pid = root / str(2001 + i)
            pid.mkdir(parents=True)
            (pid / "environ").write_bytes(b"protected")
            (pid / "comm").write_text(name + "\n")
            (pid / "cmdline").write_bytes(name.encode() + b"\x00")
        original = Path.open

        def protected(path, *args, **kwargs):
            if path.name == "environ" and path.parent.parent == root:
                raise PermissionError("protected host environment")
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", autospec=True, side_effect=protected):
            self.assertFalse(backend.active_game_process("2353250", root))

    def test_process_scan_unknown_wine_and_spoofed_overlay_still_block(self):
        root = self.root / "proc"
        cases = (("wineserver", "wineserver"),
                 ("gameoverlayui", "/other/WeMod.exe"),
                 ("unknown", "other"))
        original = Path.open
        for name, argv in cases:
            with self.subTest(name=name, argv=argv):
                pid = root / "2001"
                pid.mkdir(parents=True, exist_ok=True)
                (pid / "environ").write_bytes(b"protected")
                (pid / "comm").write_text(name + "\n")
                (pid / "cmdline").write_bytes(argv.encode() + b"\x00")

                def protected(path, *args, **kwargs):
                    if path.name == "environ" and path.parent == pid:
                        raise PermissionError("cannot inspect")
                    return original(path, *args, **kwargs)

                with patch.object(Path, "open", autospec=True, side_effect=protected):
                    with self.assertRaisesRegex(backend.Blocked, "Cannot verify"):
                        backend.active_game_process("2353250", root)

    def test_process_scan_refuses_oversized_environment(self):
        pid = self.root / "proc" / "12345"
        pid.mkdir(parents=True)
        (pid / "environ").write_bytes(b"FILL=" + b"x" * (128 * 1024))
        with self.assertRaisesRegex(backend.Blocked, "exceeds safe inspection limit"):
            backend.active_game_process("2353250", pid.parent)

    def test_process_scan_ignores_vanished_pid(self):
        pid = self.root / "proc" / "12345"
        pid.mkdir(parents=True)
        with patch.object(Path, "stat", autospec=True, side_effect=FileNotFoundError()):
            self.assertFalse(backend.active_game_process("2353250", pid.parent))

    def test_no_arbitrary_executable_or_prefix(self):
        outside = self.root / "outside.exe"
        outside.write_bytes(b"MZ")
        replacement = list(self.flags)
        i = replacement.index("--game-exe") + 1
        replacement[i] = str(outside)
        with self.assertRaisesRegex(backend.Blocked, "inside its explicit Steam install"):
            backend.main(["--preview", *replacement])
        other = list(self.flags)
        i = other.index("--compatdata") + 1
        other[i] = str(self.root)
        with self.assertRaisesRegex(backend.Blocked, "game-specific Steam compatdata"):
            backend.main(["--preview", *other])

    def test_unrelated_checkout_rejected(self):
        fake = self.root / "malicious"
        fake.mkdir()
        (fake / "wemod").write_text("echo trainer")
        with self.assertRaisesRegex(backend.Blocked, "source layout absent"):
            backend.inspect_launcher(fake / "wemod")

    def test_source_checkout_and_steam_options_remain_unchanged(self):
        target = self.root / "Steam/userdata/config/localconfig.vdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"Steam LaunchOptions = untouched")
        before = target.read_bytes()
        backend.build_plan(backend.argparse.Namespace(
            appid="2353250", launcher=self.launcher, proton=self.proton,
            game_exe=self.exe, install_dir=self.game,
            compatdata=self.compat, steam_root=self.steam, game_arg=[],
        ))
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual((self.checkout / "src/wemod.py").read_text(),
                         "# source fixture\n")


if __name__ == "__main__":
    unittest.main()
