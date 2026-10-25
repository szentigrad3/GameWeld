#!/usr/bin/env python3
"""Inspect private AppDir ELF dependencies on Linux; inventory only, no bundling."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appdir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    root = ns.appdir.resolve()
    binaries = [root / "usr/bin/gameweld", root / "usr/bin/wand-native-backend"]
    records = []
    failed = False
    for binary in binaries:
        if not binary.is_file():
            print(f"Missing binary: {binary}", file=sys.stderr)
            failed = True
            continue
        proc = run("ldd", str(binary))
        if proc.returncode:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            failed = True
            continue
        deps = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if "not found" in line:
                failed = True
                deps.append({"raw": line, "resolved": False})
                continue
            match = re.search(r"=>\s+(/[^\s]+)", line)
            if not match:
                match = re.search(r"^(/[^\s]+)", line)
            if not match:
                continue
            path = Path(match.group(1))
            if not path.is_file():
                failed = True
                deps.append({"raw": line, "resolved": False})
                continue
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            package = run("dpkg-query", "-S", str(path)) if shutil_which("dpkg-query") else None
            package_text = (package.stdout.strip().splitlines() or [""])[0] if package and package.returncode == 0 else ""
            deps.append({
                "soname": line.split("=>")[0].strip() if "=>" in line else path.name,
                "host_path": str(path),
                "sha256": sha,
                "debian_package_hint": package_text,
                "resolved": True,
                "bundle_approved": False,
            })
        records.append({"binary": str(binary.relative_to(root)), "dependencies": deps})
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps({
        "purpose": "private dependency inventory only; no libraries copied",
        "redistribution_approved": False,
        "portable": False,
        "records": records,
    }, indent=2) + "\n")
    print(f"Dependency inventory: {ns.out}")
    print("No system libraries were copied; all dependency redistribution remains unapproved.")
    if failed:
        print("FAIL: missing dependency or binary", file=sys.stderr)
        return 1
    return 0

def shutil_which(command):
    from shutil import which
    return which(command)

if __name__ == "__main__":
    raise SystemExit(main())
