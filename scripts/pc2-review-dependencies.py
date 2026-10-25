#!/usr/bin/env python3
"""Fail-closed review of Ubuntu AppDir dependency inventory. No bundling."""
import argparse
import json
from pathlib import Path
import sys

# Runtime/loader and graphics drivers must be supplied by the target host.
HOST_PREFIXES = ("ld-linux", "libc.so.", "libm.so.", "libpthread.so.",
                 "libdl.so.", "libresolv.so.", "libnss_", "libGL.so.",
                 "libEGL.so.", "libGLX.so.", "libdrm.so.", "libvulkan.so.")

def classify(name):
    return "host" if name.startswith(HOST_PREFIXES) else "review"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.inventory.read_text())
    dependencies = {}
    errors = []
    for record in source.get("records", []):
        for dep in record.get("dependencies", []):
            if not dep.get("resolved"):
                errors.append(f"unresolved: {dep.get('raw', '?')}")
                continue
            name = dep.get("soname", "")
            digest = dep.get("sha256", "")
            if not name or len(digest) != 64:
                errors.append(f"incomplete dependency: {name}")
                continue
            key = (name, digest)
            dependencies[key] = {
                "soname": name, "sha256": digest,
                "ubuntu_package_hint": dep.get("debian_package_hint", ""),
                "classification": classify(name),
                "license_verified": False,
                "redistribution_approved": False,
                "bundle": False,
            }
    items = sorted(dependencies.values(), key=lambda x: (x["soname"], x["sha256"]))
    report = {
        "scope": "Private GameWeld RC1 Ubuntu dependency review",
        "bundle_enabled": False,
        "public_release_approved": False,
        "dependencies": items,
        "errors": errors,
        "review_required": sum(x["classification"] == "review" for x in items),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Dependencies inventoried: {len(items)}")
    print(f"Require manual policy/licence review: {report['review_required']}")
    print(f"Report: {args.report}")
    print("No libraries bundled or approved for redistribution.")
    if errors:
        for error in errors: print(error, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
