#!/usr/bin/env python3
"""Offline synthetic ASAR fixtures; never downloads or runs WeMod or Proton."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("gameweld-wemod-client-audit.py")
spec = importlib.util.spec_from_file_location("gw_wemod_version_audit", SOURCE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def make_asar(path: Path, data: dict, *, offset="0", bad_size=False) -> None:
    package = json.dumps(data).encode("utf-8")
    tree = {"files": {"package.json": {"size": len(package), "offset": offset}}}
    header_json = json.dumps(tree).encode("utf-8")
    pad = b"\0" * ((-len(header_json)) % 4)
    header = struct.pack("<II", len(header_json) + 4, len(header_json)) + header_json + pad
    # Chromium's pickle header can contain padding following the string.
    with path.open("wb") as fh:
        fh.write(struct.pack("<II", 4, len(header)))
        fh.write(header)
        fh.write(package[:-1] if bad_size else package)


class ClientAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gameweld-client-audit-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.resources = self.root / "resources"
        self.resources.mkdir()
        self.exe = self.root / "WeMod.exe"
        self.exe.write_bytes(b"MZ" + bytes(128))
        self.asar = self.resources / "app.asar"

    def test_read_bounded_asar_metadata(self):
        make_asar(self.asar, {"name": "wemod", "version": "12.3.4"})
        result = mod.inspect(self.root)
        self.assertTrue(result["resources_app_asar_found"])
        self.assertEqual(result["reported_versions"][0]["version"], "12.3.4")
        self.assertEqual(result["reported_versions"][0]["source"],
                         "electron_app_asar_package_json")
        self.assertFalse(result["release_version_verified"])
        self.assertEqual(result["mode"], "read_only")

    def test_old_client_is_not_automatically_changed(self):
        make_asar(self.asar, {"name": "wemod", "version": "11.6.0"})
        before_exe = self.exe.read_bytes()
        before_asar = self.asar.read_bytes()
        result = mod.inspect(self.root)
        self.assertEqual(result["reported_versions"][0]["version"], "11.6.0")
        self.assertEqual(self.exe.read_bytes(), before_exe)
        self.assertEqual(self.asar.read_bytes(), before_asar)
        self.assertEqual(result["actions_performed"], "none")

    def test_no_version_is_not_guessed(self):
        make_asar(self.asar, {"name": "application"})
        report = mod.inspect(self.root)
        self.assertEqual(report["reported_versions"], [])
        self.assertFalse(report["release_version_verified"])

    def test_out_of_bounds_offset_rejected(self):
        make_asar(self.asar, {"version": "12.9.0"}, offset="99999999999")
        self.assertIsNone(mod.asar_package_json(self.asar))

    def test_truncated_asar_rejected(self):
        make_asar(self.asar, {"version": "12.9.0"}, bad_size=True)
        self.assertIsNone(mod.asar_package_json(self.asar))

    def test_invalid_non_windows_binary_rejected(self):
        self.exe.write_text("not an executable")
        with self.assertRaisesRegex(ValueError, "no Windows PE signature"):
            mod.inspect(self.root)

    def test_no_prefix_or_steam_changes(self):
        make_asar(self.asar, {"version": "12.3.4"})
        self.assertFalse((self.root / "pfx").exists())
        report = mod.inspect(self.root)
        self.assertFalse((self.root / "pfx").exists())
        self.assertEqual(report["actions_performed"], "none")

    def test_symlinked_asar_is_not_read(self):
        target = self.root / "actual.asar"
        make_asar(target, {"version": "12.1.0"})
        self.asar.symlink_to(target)
        report = mod.inspect(self.root)
        self.assertFalse(report["resources_app_asar_found"])
        self.assertEqual(report["reported_versions"], [])


if __name__ == "__main__":
    unittest.main()
