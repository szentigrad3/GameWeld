#!/usr/bin/env python3
"""Compare discovery/functional AppDir binaries without invoking Steam or games."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(discovery, functional):
    problems=[]
    outputs={}
    for label, root in (("discovery", discovery), ("functional", functional)):
        marker=root/"NOT-FOR-DISTRIBUTION.txt"
        gui=root/"usr/bin/gameweld"
        backend=root/"usr/bin/wand-native-backend"
        if not marker.is_file() or not gui.is_file() or not backend.is_file():
            problems.append(label+": incomplete private AppDir")
            continue
        text=marker.read_text()
        if f"Build mode: {label}" not in text or "NOT APPROVED FOR DISTRIBUTION" not in text:
            problems.append(label+": mode/publication marker absent")
        outputs[label]={"gui_sha256":sha256(gui),"backend_sha256":sha256(backend)}
    if len(outputs)==2:
        if outputs["discovery"]["gui_sha256"]==outputs["functional"]["gui_sha256"]:
            problems.append("functional and discovery GUI binaries are identical")
        if outputs["discovery"]["backend_sha256"]!=outputs["functional"]["backend_sha256"]:
            problems.append("backend differs between variants")
    return {"passed":not problems,"issues":problems,"binaries":outputs,
            "note":"Binary difference is not evidence of launch/setup correctness or portable packaging."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--discovery",type=Path,required=True)
    p.add_argument("--functional",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    data=check(a.discovery,a.functional)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,indent=2)+"\n")
    for issue in data["issues"]: print("FAIL: "+issue,file=sys.stderr)
    print("PASS: private variants confirmed distinct" if data["passed"] else "FAIL: variant mismatch")
    return 0 if data["passed"] else 2

if __name__=="__main__": sys.exit(main())
