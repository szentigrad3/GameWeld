#!/usr/bin/env python3
"""Check private license approvals against Ubuntu evidence; never grant approval.

Default operation rejects incomplete/unknown approvals and reports blockers.
No libraries are copied, packaged, signed or published.
"""
import argparse
import json
from pathlib import Path
import sys

def validate(review, inventory, evidence, approvals):
    by_key = {(d["soname"], d["sha256"]): d for d in review["dependencies"]}
    evidence_names = {s for pkg in evidence["packages"] for s in pkg["sonames"]}
    failures = []
    checked = 0
    for item in approvals.get("approved_libraries", []):
        checked += 1
        name = item.get("soname", "")
        digest = item.get("sha256", "")
        dep = by_key.get((name, digest))
        if not dep:
            failures.append(f"{name}: not found in hash-pinned review")
            continue
        if dep["classification"] != "review":
            failures.append(f"{name}: system/driver library cannot be bundled")
        if name not in evidence_names:
            failures.append(f"{name}: no Ubuntu package provenance hint")
        if not item.get("redistribution_approved") or not item.get("license_verified"):
            failures.append(f"{name}: explicit license and redistribution approvals absent")
        for field in ("source_path", "license_spdx", "notice_path", "notice_sha256"):
            if not item.get(field):
                failures.append(f"{name}: {field} missing")
    if not approvals.get("approved_libraries"):
        failures.append("No approved libraries supplied (expected private fail-closed default)")
    return {"approvals_checked": checked, "ready_for_private_staging": not failures,
            "public_distribution_approved": False, "blockers": sorted(set(failures))}

def main():
    p = argparse.ArgumentParser()
    for key in ("review", "inventory", "evidence", "approvals", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    result = validate(json.loads(a.review.read_text()), json.loads(a.inventory.read_text()),
                      json.loads(a.evidence.read_text()), json.loads(a.approvals.read_text()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Reviewed approvals: {result['approvals_checked']}")
    print(f"Outstanding blockers: {len(result['blockers'])}")
    for issue in result["blockers"]:
        print("BLOCKED: " + issue)
    return 0 if result["ready_for_private_staging"] else 2

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(3)
