#!/usr/bin/env python3
"""Preview transitive ELF dependency closure from local Ubuntu libraries.

Read-only analysis: never copies libraries, asserts license approval or
makes claims of portability. Uses ldd only on libraries originating from the
trusted CI build machine; do not supply third-party untrusted ELF files.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

def preview(candidates, inventory):
    paths = {}
    for record in inventory["records"]:
        for dep in record["dependencies"]:
            if dep.get("resolved") and dep.get("host_path"):
                paths.setdefault(dep["soname"], dep["host_path"])
    queue = [x["soname"] for x in candidates["candidate_libraries"]]
    seen, rows, missing = set(), [], set()
    while queue:
        soname = queue.pop(0)
        if soname in seen:
            continue
        seen.add(soname)
        path = paths.get(soname)
        if not path or not Path(path).is_file():
            missing.add(soname)
            continue
        proc = subprocess.run(["readelf", "-d", path], text=True, capture_output=True)
        if proc.returncode:
            missing.add(soname)
            continue
        import re
        needed = sorted(set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", proc.stdout)))
        rows.append({"soname": soname, "host_path": path, "needed": needed})
        for dep in needed:
            if dep not in seen:
                queue.append(dep)
    return {"type": "read-only-transitive-ELF-preview", "libraries_scanned": len(rows),
            "missing_host_evidence": sorted(missing),
            "dependencies": sorted(rows, key=lambda x: x["soname"]),
            "approved_libraries": [], "portable": False,
            "limitations": ["No dlopen or GTK module enumeration",
                            "Host-provided libraries are not separated into a final policy",
                            "No licensing approval or runtime launch verification"]}

def main():
    p = argparse.ArgumentParser()
    for name in ("candidates", "inventory", "out"):
        p.add_argument("--"+name, type=Path, required=True)
    a=p.parse_args()
    report=preview(json.loads(a.candidates.read_text()),json.loads(a.inventory.read_text()))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(f"Transitive libraries scanned: {report['libraries_scanned']}")
    print(f"Missing host evidence: {len(report['missing_host_evidence'])}")
    print("Read-only investigation; no portable AppImage generated.")
if __name__=="__main__":
    try: main()
    except (OSError, ValueError, KeyError) as e:
        print(f"Audit failed: {e}",file=sys.stderr)
        sys.exit(2)
