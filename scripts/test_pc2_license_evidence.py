#!/usr/bin/env python3
"""Package owner lookup regression tests; no real packaging writes."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

script=Path(__file__).with_name("pc2-license-evidence.py")
spec=importlib.util.spec_from_file_location("pc2_license_evidence",script)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PackageOwnerTests(unittest.TestCase):
    def test_merged_usr_fallback(self):
        queried=[]
        def fake_run(args, **kwargs):
            queried.append(args[-1])
            if args[-1] == "/usr/lib/x86_64-linux-gnu/libgtk-3.so.0":
                return SimpleNamespace(returncode=0,stdout="libgtk-3-0:amd64: /usr/lib/x86_64-linux-gnu/libgtk-3.so.0\n")
            return SimpleNamespace(returncode=1,stdout="")
        with patch.object(module.subprocess,"run",side_effect=fake_run):
            self.assertEqual(module.owner("/lib/x86_64-linux-gnu/libgtk-3.so.0"),"libgtk-3-0:amd64")
        self.assertIn("/usr/lib/x86_64-linux-gnu/libgtk-3.so.0",queried)
    def test_unknown_owner_remains_unverified(self):
        with patch.object(module.subprocess,"run",return_value=SimpleNamespace(returncode=1,stdout="")):
            self.assertIsNone(module.owner("/lib/example/libunknown.so.0"))

if __name__ == "__main__":
    unittest.main()
