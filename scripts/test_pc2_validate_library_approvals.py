#!/usr/bin/env python3
"""Offline release-gate tests. No third-party binaries accessed."""
import importlib.util
from pathlib import Path
import unittest

source=Path(__file__).with_name("pc2-validate-library-approvals.py")
spec=importlib.util.spec_from_file_location("private_approval_gate",source)
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class Approvals(unittest.TestCase):
    def setUp(self):
        self.review={"dependencies":[{"soname":"libfixture.so.1","sha256":"a"*64,"classification":"review"}]}
        self.inventory={"records":[]}
        self.evidence={"packages":[{"package":"fixture","sonames":["libfixture.so.1"]}]}
        self.approved={"approved_libraries":[{
            "soname":"libfixture.so.1","sha256":"a"*64,"redistribution_approved":True,
            "license_verified":True,"source_path":"/fixture/libfixture.so.1",
            "license_spdx":"MIT","notice_path":"/fixture/NOTICE","notice_sha256":"b"*64
        }]}
    def check(self):
        return gate.validate(self.review,self.inventory,self.evidence,self.approved)
    def test_valid_evidence_is_only_private_staging_ready(self):
        r=self.check()
        self.assertTrue(r["ready_for_private_staging"])
        self.assertFalse(r["public_distribution_approved"])
    def test_empty_approvals_blocked(self):
        self.approved={"approved_libraries":[]}
        self.assertFalse(self.check()["ready_for_private_staging"])
    def test_no_provenance_blocks(self):
        self.evidence={"packages":[]}
        self.assertFalse(self.check()["ready_for_private_staging"])
    def test_hash_mismatch_blocks(self):
        self.approved["approved_libraries"][0]["sha256"]="c"*64
        self.assertFalse(self.check()["ready_for_private_staging"])
    def test_host_library_blocks(self):
        self.review["dependencies"][0]["classification"]="host"
        self.assertFalse(self.check()["ready_for_private_staging"])
    def test_missing_license_notice_digest_blocks(self):
        self.approved["approved_libraries"][0]["notice_sha256"]=""
        self.assertFalse(self.check()["ready_for_private_staging"])

if __name__=="__main__":
    unittest.main()
