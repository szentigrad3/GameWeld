#!/usr/bin/env python3
"""Regression: RC1 audit honors exact image arguments and both filename types.

Only temporary dummy files are created. No AppImage, game, Steam, Wine or
trainer is launched. An intentionally missing checksum stops before extraction.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name("pc2-rc1-package-audit.sh")


class AppImageAuditSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gameweld-audit-selection-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        scripts = root / "scripts"
        scripts.mkdir()
        self.script = scripts / SOURCE.name
        shutil.copyfile(SOURCE, self.script)
        self.out = root / "build" / "pc2-source" / "local-appimages"
        self.out.mkdir(parents=True)

    def add_image(self, kind: str, stamp: str) -> Path:
        image = self.out / f"GameWeld-PC2-RC1-{kind}-{stamp}-x86_64.AppImage"
        image.write_bytes(b"not-an-appimage")
        return image

    def audit(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.script), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def test_explicit_candidate_is_used_unchanged(self):
        target = self.add_image("CANDIDATE", "20261025-093051")
        res = self.audit(target)
        self.assertEqual(res.returncode, 2)
        self.assertIn(f"Missing adjacent checksum: {target}.sha256", res.stderr)
        self.assertNotIn("No local PC2 AppImage", res.stderr)

    def test_explicit_path_does_not_switch_to_newer_local_image(self):
        target = self.add_image("CANDIDATE", "20261025-093051")
        old = self.add_image("LOCAL", "20261025-094200")
        os.utime(old, (2_000_000_000, 2_000_000_000))
        res = self.audit(target)
        self.assertIn(str(target) + ".sha256", res.stderr)
        self.assertNotIn(str(old) + ".sha256", res.stderr)

    def test_no_argument_detects_candidate_only(self):
        target = self.add_image("CANDIDATE", "20261025-093051")
        res = self.audit()
        self.assertEqual(res.returncode, 2)
        self.assertIn(str(target) + ".sha256", res.stderr)

    def test_no_argument_picks_newest_local_or_candidate(self):
        old = self.add_image("LOCAL", "20261024-205535")
        new = self.add_image("CANDIDATE", "20261025-093051")
        os.utime(old, (1_600_000_000, 1_600_000_000))
        os.utime(new, (1_800_000_000, 1_800_000_000))
        res = self.audit()
        self.assertEqual(res.returncode, 2)
        self.assertIn(str(new) + ".sha256", res.stderr)

    def test_no_image_rejects_cleanly(self):
        res = self.audit()
        self.assertEqual(res.returncode, 2)
        self.assertIn("No PC2 local/candidate AppImage found", res.stderr)


if __name__ == "__main__":
    unittest.main()
