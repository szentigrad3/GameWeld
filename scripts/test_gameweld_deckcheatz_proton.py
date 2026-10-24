#!/usr/bin/env python3
"""Synthetic read-only DeckCheatz Proton location checks (no Steam or Proton execution)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-deckcheatz-proton.py")
spec = importlib.util.spec_from_file_location("gw_deckcheatz_proton_tested", SOURCE)
backend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend
spec.loader.exec_module(backend)


class FakeSteamResolver:
    def steam_library_roots(self, root):
        return [root]

    def _tool_dirs(self, root, libraries):
        return [root / "compatibilitytools.d", root / "steamapps/common"]

    def _resolve_tool_path(self, root, libraries, name):
        return str(root / "compatibilitytools.d" / name)

    def _compatdata_runtime_hint(self, path):
        return "", ""

    def _compat_tool_mapping(self, root, userdir, appid):
        return "", "", "", "", ""


class ProtonLocatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gw-deckcheatz-proton-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "steamroot"
        game = root / "steamapps/common/FakeGame"
        game.mkdir(parents=True)
        (root / "steamapps/appmanifest_2353250.acf").write_text('"appid" "2353250"')
        compat = root / "steamapps/compatdata/2353250"
        (compat / "pfx").mkdir(parents=True)
        self.root = root
        self.install = game
        self.compat = compat

    def args(self, **changes):
        values = dict(appid="2353250", steam_root=str(self.root),
                      install_dir=str(self.install), compatdata=str(self.compat),
                      preferred_name="", preferred_path="")
        values.update(changes)
        return SimpleNamespace(**values)

    def proton(self, name):
        path = self.root / "compatibilitytools.d" / name / "proton"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
        return path

    def resolve(self, **changes):
        with patch.object(backend, "load_steam_resolver", return_value=FakeSteamResolver()):
            return backend.resolve(self.args(**changes))

    def test_one_installed_launcher_resolves_without_running_it(self):
        proton = self.proton("GE-Proton-Test")
        result = self.resolve()
        self.assertEqual(result["selected"], str(proton))
        self.assertFalse(result["game_launched"])
        self.assertFalse(result["steam_launch_options_modified"])

    def test_ambiguous_versions_fail_closed(self):
        self.proton("GE-Proton-TestA")
        self.proton("GE-Proton-TestB")
        result = self.resolve()
        self.assertEqual(result["selected"], "")
        self.assertEqual(result["candidate_count"], 2)

    def test_selected_game_compat_tool_wins(self):
        self.proton("GE-Proton-TestA")
        right = self.proton("GE-Proton-TestB")
        result = self.resolve(preferred_name="GE-Proton-TestB")
        self.assertEqual(result["selected"], str(right))
        self.assertEqual(result["reason"], "Resolved game-discovery-tool-name")

    def test_unrelated_executable_rejected(self):
        wrong = self.root / "wrong.sh"
        wrong.write_text("#!/bin/sh\nexit 0\n")
        wrong.chmod(0o755)
        self.assertEqual(backend.verified_proton(wrong), "")

    def test_game_manifest_required(self):
        (self.root / "steamapps/appmanifest_2353250.acf").unlink()
        with self.assertRaisesRegex(ValueError, "matching Steam manifest"):
            self.resolve()


if __name__ == "__main__":
    unittest.main()
