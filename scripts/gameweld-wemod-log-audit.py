#!/usr/bin/env python3
"""Read-only, binary-safe summary of one GameWeld WeMod live-launch log."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

MAX_READ = 64 * 1024 * 1024
CRASH_COUNTER = re.compile(r"The GPU process has crashed (\d+) time\(s\)", re.I)


def newest_log(appid: str, state: Path) -> Path:
    files = [p for p in state.glob(f"wand-live-{appid}*.log")
             if p.is_file() and not p.is_symlink()]
    if not files:
        raise FileNotFoundError(f"No Wand/WeMod live log for Steam AppID {appid} in {state}")
    return max(files, key=lambda p: (p.stat().st_mtime_ns, p.name))


def audit(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Log must be an existing regular file, not a symlink")
    size = path.stat().st_size
    with path.open("rb") as handle:
        raw = handle.read(MAX_READ + 1)
    partial = len(raw) > MAX_READ
    raw = raw[:MAX_READ]
    nul_count = raw.count(b"\0")
    # A previous client can keep writing at its original file offset after
    # O_TRUNC, leaving sparse NUL holes. Treat this as evidence to investigate,
    # NOT proof of an active process or any specific renderer failure.
    rows = raw.replace(b"\0", b"").decode("utf-8", "replace").splitlines()
    gpu = [line for line in rows if "GPU process launch failed" in line]
    counters = [int(m.group(1)) for line in rows
                if (m := CRASH_COUNTER.search(line))]
    dll = [line for line in rows if "version.dll" in line.lower()]
    native = [line for line in dll if "loaded" in line.lower()
              and re.search(r"\bnative\b", line, re.I)]
    builtin = [line for line in dll if "loaded" in line.lower()
               and re.search(r"\bbuiltin\b", line, re.I)]
    header = [
        f"Log: {path}",
        f"Log size: {size} bytes",
        f"Scanned bytes: {len(raw)}" + (" (PARTIAL)" if partial else ""),
        f"Embedded NUL bytes: {nul_count}",
        f"GPU launch failure lines scanned: {len(gpu)}",
        "Last reported Chromium crash counter: " +
            (str(counters[-1]) if counters else "not present"),
        f"version.dll matching trace lines: {len(dll)}",
        f"version.dll native loads: {len(native)}",
        f"version.dll builtin loads: {len(builtin)}",
    ]
    if nul_count:
        header.append("Warning: NUL bytes may indicate overlapping/truncated log writers.")
    if counters and counters[-1] > len(gpu):
        header.append("Warning: Chromium's crash counter exceeds the log's observed failures; history may be incomplete.")
    header.append("DLL trace excerpts (up to 12):")
    header.extend("  " + line[:360] for line in dll[:12])
    if not dll:
        header.append("  No version.dll trace found; loading remains unverified.")
    return "\n".join(header)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", default="2353250")
    parser.add_argument("--log", type=Path, help="Inspect an explicit log path")
    args = parser.parse_args()
    if not args.appid.isascii() or not args.appid.isdecimal():
        parser.error("--appid must be decimal digits")
    home = os.environ.get("XDG_STATE_HOME")
    if home and not Path(home).is_absolute():
        parser.error("XDG_STATE_HOME must be an absolute path")
    state = (Path(home) if home else Path.home() / ".local/state") / "gameweld"
    try:
        log = args.log or newest_log(args.appid, state)
        print(audit(log))
        return 0
    except (OSError, ValueError) as exc:
        print(f"GameWeld WeMod log audit: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
