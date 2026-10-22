#!/usr/bin/env python3
from __future__ import annotations
import argparse, re
from pathlib import Path

P107 = re.compile(r"CertGetCertificateContextProperty \([^\n]*, 107,")
WIN_OK = re.compile(r"WinVerifyTrust returning 00000000|WINTRUST_DefaultVerify returning 00000000")
RET0 = re.compile(r"CertGetCertificateContextProperty returning 0")
BRIDGE = re.compile(r"Plugin signature verification failed.*reason=verification_error", re.I)

def main() -> int:
    ap = argparse.ArgumentParser(description="Correlate Wand/Tophat plugin signature failure with Wine CERT_SHA256_HASH_PROP_ID behavior.")
    ap.add_argument("files", nargs="+", help="Wine debug trace, fingerprint summary, or Tophat telemetry text")
    ns = ap.parse_args()
    found = {"wintrust_ok": False, "prop107": False, "prop107_fail": False, "bridge_error": False}
    for name in ns.files:
        p = Path(name)
        if not p.is_file():
            continue
        lines = p.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines):
            if WIN_OK.search(line): found["wintrust_ok"] = True
            if P107.search(line):
                found["prop107"] = True
                if any(RET0.search(x) for x in lines[i:i+8]): found["prop107_fail"] = True
            if BRIDGE.search(line): found["bridge_error"] = True
    print("Wand Native plugin-signature correlation")
    for k, v in found.items(): print(f"{k}={str(v).lower()}")
    if found["wintrust_ok"] and found["prop107_fail"] and found["bridge_error"]:
        print("classification=wine-cert-sha256-property-gap")
        print("evidence=WinTrust succeeded; CERT_SHA256_HASH_PROP_ID failed; Tophat reported verification_error")
        return 0
    if found["prop107_fail"]:
        print("classification=wine-cert-sha256-property-gap-suspected")
        return 0
    print("classification=incomplete-evidence")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
