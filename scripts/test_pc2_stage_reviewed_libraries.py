#!/usr/bin/env python3
"""Isolated tests of private ELF staging. No host libraries or game files touched."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("pc2-stage-reviewed-libraries.py")

class ReviewedLibraryStagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "libexample.so"
        self.src.write_bytes(b"isolated-fixture-not-a-real-ELF")
        self.digest = hashlib.sha256(self.src.read_bytes()).hexdigest()
        self.notice = self.root / "fixture-LICENSE.txt"
        self.notice.write_text("MIT fixture text")
        self.notice_digest = hashlib.sha256(self.notice.read_bytes()).hexdigest()
        self.review = self.root / "review.json"
        self.approved = self.root / "approved.json"
        self.dest = self.root / "libs"
        self.write_review()
    def write_review(self, classification="review"):
        self.review.write_text(json.dumps({
            "public_release_approved": False, "bundle_enabled": False,
            "dependencies": [{"soname": "libexample.so", "sha256": self.digest,
                              "classification": classification}]
        }))
    def write_approval(self, **changes):
        entry = {
            "soname": "libexample.so", "sha256": self.digest,
            "source_path": str(self.src), "redistribution_approved": True,
            "license_verified": True, "license_spdx": "MIT",
            "notice_path": str(self.notice), "notice_sha256": self.notice_digest,
        }
        entry.update(changes)
        self.approved.write_text(json.dumps({"approved_libraries": [entry]}))
    def invoke(self):
        return subprocess.run([sys.executable, str(SCRIPT), "--review", str(self.review),
                               "--approved", str(self.approved), "--destination", str(self.dest)],
                              text=True, capture_output=True)
    def test_empty_approval_list_does_not_create_destination(self):
        self.approved.write_text('{"approved_libraries":[]}')
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.dest.exists())
    def test_exact_reviewed_fixture_can_be_staged_privately(self):
        self.write_approval()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dest / "libexample.so").read_bytes(), self.src.read_bytes())
    def test_digest_mismatch_rejected_without_destination(self):
        self.write_approval(sha256="0" * 64)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
    def test_missing_license_approval_rejected(self):
        self.write_approval(license_verified=False)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
    def test_license_notice_hash_mismatch_rejected(self):
        self.write_approval(notice_sha256="0" * 64)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
    def test_missing_license_notice_rejected(self):
        self.write_approval(notice_path=str(self.root / "missing-license"))
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
    def test_host_dependency_never_staged(self):
        self.write_review(classification="host")
        self.write_approval()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
    def test_existing_destination_never_overwritten(self):
        self.dest.mkdir()
        sentinel = self.dest / "sentinel"
        sentinel.write_text("keep")
        self.write_approval()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(sentinel.read_text(), "keep")
    def test_failed_second_entry_cleans_partial_staging(self):
        self.write_approval()
        approval = json.loads(self.approved.read_text())
        second = dict(approval["approved_libraries"][0])
        second["soname"] = "libmissing.so"
        second["sha256"] = "1" * 64
        approval["approved_libraries"].append(second)
        self.approved.write_text(json.dumps(approval))
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.dest.with_name(self.dest.name + ".staging").exists())

if __name__ == "__main__":
    unittest.main()
