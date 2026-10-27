#!/usr/bin/env python3
"""Offline checks for read-only bounded prepared ZIP directory probe."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

SOURCE = Path(__file__).with_name("gameweld-remote-zip-directory.py")
spec = importlib.util.spec_from_file_location("gameweld_range_probe", SOURCE)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
URL = "https://github.com/DeckCheatz/BuiltPrefixes-dev/releases/download/PfxVer10.1/GE-Proton10.1.zip"


class FakeReply:
    def __init__(self, archive, requested, status=206, malformed=False):
        self.blob = archive
        self.status = status
        if requested.startswith("bytes=-"):
            size = int(requested[7:])
            self.start, self.end = max(0, len(archive) - size), len(archive) - 1
        else:
            self.start, self.end = map(int, requested[6:].split("-"))
        self.headers = {"Content-Range": (
            "garbage" if malformed else
            f"bytes {self.start}-{self.end}/{len(archive)}")}
    def geturl(self):
        return "https://release-assets.githubusercontent.com/safe"
    def read(self, n):
        return self.blob[self.start:self.end + 1][:n]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class RemoteZipDirectoryTests(unittest.TestCase):
    def makezip(self, names, pad=0):
        out = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as z:
                for name in names:
                    z.writestr(name, b"x" * pad)
        return out.getvalue()

    def opener(self, blob, calls, *, status=206, malformed=False):
        def get(req, timeout):
            calls.append(req.get_header("Range"))
            return FakeReply(blob, calls[-1], status=status, malformed=malformed)
        return get

    def test_reports_exact_file_duplicate_and_case_variation(self):
        z = self.makezip(["pfx/Alpha/", "pfx/alpha/", "pfx/a.txt", "pfx/a.txt"])
        calls = []
        counts, examples = probe.inspect_directory(URL, opener=self.opener(z, calls))
        self.assertEqual(counts["case/Unicode name collision"], 1)
        self.assertEqual(counts["exact duplicate file"], 1)
        self.assertEqual(calls, ["bytes=-65557"])
        self.assertIn("case/Unicode", examples[0])

    def test_second_range_for_large_metadata(self):
        z = self.makezip([f"pfx/file_{i:04d}.txt" for i in range(2200)])
        calls = []
        counts, _ = probe.inspect_directory(URL, opener=self.opener(z, calls))
        self.assertEqual(counts["total entries"], 2200)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith("bytes="))

    def test_rejects_server_that_ignores_range_or_lies(self):
        z = self.makezip(["pfx/ok.txt"])
        for opts in ({"status": 200}, {"malformed": True}):
            with self.subTest(opts=opts), self.assertRaises(probe.ProbeRefused):
                probe.inspect_directory(URL, opener=self.opener(z, [], **opts))

    def test_rejects_untrusted_initial_asset_url_and_bad_zip(self):
        with self.assertRaises(probe.ProbeRefused):
            probe.inspect_directory("https://example.com/not.zip", opener=lambda *a, **k: None)
        with self.assertRaises(probe.ProbeRefused):
            probe.inspect_directory(URL, opener=self.opener(b"not a zip", []))

    def test_no_file_writes_or_extraction(self):
        blob = self.makezip(["pfx/test.exe"])
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            before = list(parent.iterdir())
            probe.inspect_directory(URL, opener=self.opener(blob, []))
            self.assertEqual(list(parent.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
