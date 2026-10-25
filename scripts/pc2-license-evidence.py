#!/usr/bin/env python3
"""Prepare non-authoritative Debian license evidence for AppDir dependencies.

Reads the existing dependency inventory and the Ubuntu host's installed package
copyright files. Does not approve licenses, copy libraries, or distribute binaries.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

def owner(path):
    candidate = Path(path)
    paths = [candidate]
    if str(candidate).startswith("/lib/"):
        paths.append(Path("/usr" + str(candidate)))
    paths.append(candidate.resolve())
    seen = set()
    for probe in paths:
        key = str(probe)
        if key in seen:
            continue
        seen.add(key)
        result = subprocess.run(["dpkg-query", "-S", key], capture_output=True, text=True)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            if ": " in line:
                return line.split(": ", 1)[0].split(",")[0]
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.inventory.read_text())
    packages = {}
    missing = []
    host_runtime = []
    for record in source.get("records", []):
        for dep in record.get("dependencies", []):
            if not dep.get("resolved"):
                missing.append(dep.get("raw", "unresolved"))
                continue
            name = dep.get("soname", "")
            if name.startswith(("ld-linux-", "ld-musl-")):
                host_runtime.append(name)
                continue
            path = Path(dep.get("host_path", ""))
            pkg = owner(path)
            if not pkg:
                missing.append(name + ": package ownership unverified")
                continue
            normalized = pkg.split(":")[0]
            copyright_path = Path("/usr/share/doc") / normalized / "copyright"
            exists = copyright_path.is_file()
            key = normalized
            row = packages.setdefault(key, {
                "package": normalized,
                "copyright_file": str(copyright_path) if exists else None,
                "copyright_sha256": None,
                "sonames": [],
                "redistribution_approved": False,
                "license_review_required": True,
            })
            if name not in row["sonames"]:
                row["sonames"].append(name)
            if exists:
                import hashlib
                row["copyright_sha256"] = hashlib.sha256(copyright_path.read_bytes()).hexdigest()
            else:
                missing.append(name + ": copyright file unavailable")
    for row in packages.values():
        row["sonames"].sort()
    data = {
        "purpose": "Ubuntu package copyright provenance hints; legal review still required",
        "redistribution_approved": False,
        "licenses_verified": False,
        "packages": sorted(packages.values(), key=lambda x: x["package"]),
        "host_provided_dynamic_loaders": sorted(set(host_runtime)),
        "gaps": sorted(set(missing)),
        "notes": [
            "A package copyright file does not establish compatibility of all subcomponents.",
            "License obligations, build provenance and third-party rights require human review.",
            "No libraries or copyright material are copied into this report."
        ]
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Packages with provenance hints: {len(packages)}")
    print(f"Copyright/provenance gaps: {len(data['gaps'])}")
    print("No redistribution approvals inferred.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        sys.exit(2)
