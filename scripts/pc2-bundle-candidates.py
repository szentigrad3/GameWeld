#!/usr/bin/env python3
"""Produce private, explicitly UNAPPROVED library-bundle candidates from CI evidence."""
import argparse
import json
from pathlib import Path

def candidates(inventory, review, evidence, closure):
    listed = {}
    for record in inventory["records"]:
        for dep in record["dependencies"]:
            if dep.get("resolved"):
                listed[(dep["soname"], dep["sha256"])] = dep
    ownership = {}
    for package in evidence["packages"]:
        for name in package["sonames"]:
            ownership.setdefault(name, []).append(package["package"])
    wanted = set(closure["unbundled_dependencies"])
    rows = []
    for dep in review["dependencies"]:
        name = dep["soname"]
        if name not in wanted or dep["classification"] != "review":
            continue
        raw = listed.get((name, dep["sha256"]))
        rows.append({
            "soname": name,
            "sha256": dep["sha256"],
            "source_path": raw["host_path"] if raw else None,
            "ubuntu_package_candidates": sorted(ownership.get(name, [])),
            "license_spdx": None,
            "notice_path": None,
            "notice_sha256": None,
            "license_verified": False,
            "redistribution_approved": False,
            "approved_for_private_staging": False
        })
    names = {row["soname"] for row in rows}
    return {
        "purpose": "manual review candidates; NOT a staging approval manifest",
        "approved_libraries": [],
        "candidate_libraries": sorted(rows, key=lambda x: x["soname"]),
        "missing_evidence": sorted(wanted - names),
        "portable": False,
        "public_release_approved": False,
        "warnings": [
            "These are only direct ELF dependencies; transitives and dlopen modules not assessed.",
            "License and redistribution clearance require individual review.",
            "Do not copy candidates into a release AppDir."
        ]
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("inventory", "review", "evidence", "closure", "out"):
        p.add_argument("--"+name, type=Path, required=True)
    a=p.parse_args()
    result=candidates(*(json.loads(getattr(a,name).read_text())
                         for name in ("inventory","review","evidence","closure")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2)+"\n")
    print(f"Private library candidates: {len(result['candidate_libraries'])}")
    print(f"Candidates missing exact evidence: {len(result['missing_evidence'])}")
    print("Approved libraries: 0. This is NOT a portable build.")
if __name__=="__main__":
    main()
