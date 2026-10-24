#!/usr/bin/env python3
"""Compatibility entrypoint for GameWeld PC2's integrated one-Proton-session engine.

The former Test 19 implementation required an external wandctl 0.1.41 daemon
that was absent on the user's system. The actual managed-launch architecture
is now provided by GameWeld's own gameweld-managed-wand.py source, with an
optional existing verified isolated Proton tool. No standalone daemon needed.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys

def main() -> int:
    target = Path(__file__).resolve().with_name("gameweld-managed-wand.py")
    if not target.is_file():
        print("GameWeld managed Wand: integrated launcher source is missing", file=sys.stderr)
        return 1
    spec = importlib.util.spec_from_file_location("gameweld_managed_wand", target)
    if spec is None or spec.loader is None:
        print("GameWeld managed Wand: cannot load integrated launcher", file=sys.stderr)
        return 1
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return int(module.main())

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("GameWeld managed Wand: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
