#!/usr/bin/env python3
"""Safe v2 external-source bridge tests; no Steam, WeMod or Proton is launched."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

SOURCE = Path(__file__).with_name("gameweld-wand-v2-proxy.py")
spec = importlib.util.spec_from_file_location("gameweld_v2_proxy_tests", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class V2ProxyTests(unittest.TestCase):
    def test_uninstalled_v2_blocks_without_fallback(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"XDG_DATA_HOME": home}):
                with self.assertRaisesRegex(module.ProxyBlocked, "v2_not_installed"):
                    module.source_path()

    def test_user_owned_tree_and_sanitized_result(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home) / "gameweld/wand-v2/src/wand_launcher"
            root.mkdir(parents=True)
            (root / "__init__.py").write_text("safe")
            (root / "entrypoint.py").write_text("safe")
            with patch.dict(os.environ, {"XDG_DATA_HOME": home}):
                self.assertEqual(module.source_path(), root.parent)
                class Process:
                    returncode=0
                    stdout=json.dumps({"state":"live_preview",
                        "can_attempt_with_explicit_consent": True,
                        "steam_launch_options_changed": False})
                with patch.object(module.subprocess, "run", return_value=Process()) as call:
                    output=module.invoke("3008130", Path("/tmp/game"), launch=False)
                self.assertTrue(output["v2_integration"])
                self.assertFalse(output["steam_settings_changed_by_proxy"])
                argv=call.call_args.args[0]
                self.assertEqual(argv[1:4], ["-m","wand_launcher","attach"])
                self.assertNotIn("--approve-existing-prefix-change",argv)
                with patch.object(module.subprocess, "run", return_value=Process()) as call:
                    module.invoke("3008130", Path("/tmp/game"), launch=True)
                self.assertIn("--approve-existing-prefix-change",call.call_args.args[0])

    def test_invalid_identity_or_symlink_fails_closed(self):
        with self.assertRaisesRegex(module.ProxyBlocked,"invalid_appid"):
            module.invoke("not-a-number",Path("/tmp/game"),launch=False)
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)/"gameweld/wand-v2/src/wand_launcher"
            root.mkdir(parents=True)
            (root/"__init__.py").write_text("safe")
            (root/"entrypoint.py").symlink_to(root/"__init__.py")
            with patch.dict(os.environ,{"XDG_DATA_HOME":home}):
                with self.assertRaisesRegex(module.ProxyBlocked,"symlinked"):
                    module.source_path()

if __name__ == "__main__":
    unittest.main()
