#!/usr/bin/env python3
"""Inspect private AppDir ELF DT_NEEDED dependency closure without executing binaries.

Conservative audit: reports unbundled runtime dependencies and fails --require-closure.
A closed direct ELF dependency graph does NOT establish portability, licensing,
GTK module availability, launcher correctness, or runtime compatibility.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

HOST_ONLY = {"libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2",
             "librt.so.1", "libresolv.so.2", "libutil.so.1"}
HOST_PREFIX = ("ld-linux", "libnss_", "libGL.so.", "libEGL.so.",
               "libGLX.so.", "libvulkan.so.", "libdrm.so.")
NEEDED = re.compile(r"\(NEEDED\).*?\[(.*?)\]")

def dependencies(path):
    result = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"readelf failed on {path}: {result.stderr.strip()}")
    return sorted(set(NEEDED.findall(result.stdout)))

def inspect(appdir):
    root = appdir.resolve()
    executables = [root / "usr/bin/gameweld", root / "usr/bin/wand-native-backend"]
    missing = [str(p) for p in executables if not p.is_file()]
    libraries = [p for folder in ("usr/lib", "usr/lib64") for p in (root / folder).rglob("*")
                 if p.is_file()] 
    bundled = {p.name: p for p in libraries}
    queue = [p for p in executables if p.is_file()] + libraries
    seen = set()
    records = []
    gaps = set()
    while queue:
        elf = queue.pop()
        if elf in seen:
            continue
        seen.add(elf)
        required = dependencies(elf)
        row = {"file": str(elf.relative_to(root)), "needed": []}
        for name in required:
            if name in bundled:
                state = "bundled"
            elif name in HOST_ONLY or any(name.startswith(prefix) for prefix in HOST_PREFIX):
                state = "host"
            else:
                state = "unbundled"
                gaps.add(name)
            row["needed"].append({"soname": name, "resolution": state})
        records.append(row)
    return {"scope": "private static ELF DT_NEEDED inspection",
            "portable": False, "redistribution_approved": False,
            "direct_elf_closure_satisfied": not gaps and not missing,
            "unbundled_dependencies": sorted(gaps), "missing_executables": missing,
            "objects": sorted(records, key=lambda row: row["file"]),
            "limitations": ["does not inspect dlopen/GTK modules", "does not launch the GUI",
                            "does not prove cross-distribution compatibility",
                            "does not grant redistribution rights"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--appdir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-closure", action="store_true")
    args = parser.parse_args()
    data = inspect(args.appdir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Static runtime report: {args.report}")
    print(f"Unbundled SONAMEs: {len(data['unbundled_dependencies'])}")
    for item in data["unbundled_dependencies"]:
        print(f"  REVIEW: {item}")
    print("Publication remains BLOCKED irrespective of closure.")
    if args.require_closure and not data["direct_elf_closure_satisfied"]:
        return 2
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print(f"Audit error: {error}", file=sys.stderr)
        sys.exit(3)
