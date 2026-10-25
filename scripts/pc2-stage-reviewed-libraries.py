#!/usr/bin/env python3
"""Private, explicitly approved ELF copy staging. Never edits the source AppDir."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--review", type=Path, required=True)
    p.add_argument("--approved", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    a = p.parse_args()
    review = json.loads(a.review.read_text())
    approvals = json.loads(a.approved.read_text())
    if review.get("public_release_approved") or review.get("bundle_enabled"):
        raise ValueError("Review is an inventory only; unexpected approval flags")
    entries = approvals.get("approved_libraries", [])
    indexed = {(x["soname"], x["sha256"]): x for x in review["dependencies"]}
    if a.destination.exists():
        raise ValueError("Destination already exists: refusing overwrite")
    if not entries:
        print("BLOCKED: no approved libraries; no files copied")
        return 0
    staging = a.destination.with_name(a.destination.name + ".staging")
    if staging.exists():
        raise ValueError("Previous staging directory exists")
    try:
        staging.mkdir(parents=True)
        seen = set()
        for entry in entries:
            name = entry["soname"]
            expected = entry["sha256"]
            key = (name, expected)
            if key in seen or key not in indexed:
                raise ValueError("Duplicate or unlisted dependency")
            seen.add(key)
            if indexed[key]["classification"] != "review":
                raise ValueError(f"Host dependency cannot be bundled: {name}")
            if not entry.get("redistribution_approved") or not entry.get("license_verified"):
                raise ValueError(f"Missing legal approval: {name}")
            if not entry.get("license_spdx") or not entry.get("notice_path"):
                raise ValueError(f"Missing license notice details: {name}")
            source = Path(entry["source_path"])
            if not source.is_file() or source.is_symlink() or digest(source) != expected:
                raise ValueError(f"Source missing, linked or hash mismatch: {name}")
            if Path(name).name != name or "/" in name:
                raise ValueError("Unsafe SONAME")
            target = staging / name
            shutil.copy2(source, target)
            if digest(target) != expected:
                raise ValueError("Staged checksum mismatch")
        staging.rename(a.destination)
        print(f"PRIVATE staging complete: {len(entries)} libraries")
        print("Not approved for public distribution; validate loader paths and licensing separately.")
        return 0
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        sys.exit(2)
