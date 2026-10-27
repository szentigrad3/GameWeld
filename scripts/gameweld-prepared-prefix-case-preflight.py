#!/usr/bin/env python3
"""Assess retained ZIP case variants and optional local host filesystem behavior.

Default: read-only ZIP index and metadata examination, no archive extraction.
--test-host-filesystem: uses only small, synthetic temporary names under the
private GameWeld cache, immediately removes them, and never invokes Wine/Proton.
Neither mode authorizes promoting a rejected ZIP into downloads or staging.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import errno
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unicodedata
import zipfile

MAX_REJECTED = 2


class CasePreflightRefused(ValueError):
    pass


def cache_root_ok(root: Path) -> None:
    if (not root.is_absolute() or root.name != "prepared-wemod" or
            root.parent.name != "gameweld" or
            any(x.casefold() in {"steamapps", "compatdata", "pfx"} for x in root.parts) or
            any(x.is_symlink() for x in (root, *root.parents)) or
            not root.is_dir() or
            stat.S_IMODE(root.stat().st_mode) & 0o077):
        raise CasePreflightRefused("Private GameWeld prepared-wemod cache is unavailable or unsafe")


def load_audit():
    script = Path(__file__).resolve().with_name("gameweld-prepared-prefix-audit.py")
    if script.is_symlink() or not script.is_file():
        raise CasePreflightRefused("Shared ZIP index validator unavailable")
    spec = importlib.util.spec_from_file_location("gameweld_case_preflight_audit", script)
    if spec is None or spec.loader is None:
        raise CasePreflightRefused("Could not load ZIP index validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_rejected(root: Path) -> Path:
    cache_root_ok(root)
    rejected = root / "rejected"
    if (rejected.is_symlink() or not rejected.is_dir() or
            stat.S_IMODE(rejected.stat().st_mode) & 0o077):
        raise CasePreflightRefused("Rejected cache folder missing or unsafe")
    files = list(rejected.glob("*.zip"))
    if len(files) != 1 or len(files) > MAX_REJECTED:
        raise CasePreflightRefused("Exactly one rejected ZIP is required")
    path = files[0]
    digest = path.stem
    if (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or
            path.is_symlink() or not path.is_file()):
        raise CasePreflightRefused("Rejected ZIP is not a managed regular file")
    receipt = rejected / (digest + ".rejected.json")
    if (receipt.is_symlink() or not receipt.is_file() or
            receipt.stat().st_size > 4096):
        raise CasePreflightRefused("Rejected ZIP source receipt missing or unsafe")
    try:
        metadata = json.loads(receipt.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise CasePreflightRefused("Rejected ZIP receipt is unreadable") from exc
    if (not isinstance(metadata, dict) or metadata.get("sha256") != digest or
            metadata.get("status") != "REJECTED_NOT_STAGEABLE" or
            metadata.get("source") != "DeckCheatz/BuiltPrefixes-dev" or
            type(metadata.get("bytes")) is not int or
            metadata["bytes"] != path.stat().st_size):
        raise CasePreflightRefused("Rejected ZIP source receipt is inconsistent")
    return path


def classify_ambiguous_entries(members: list[zipfile.ZipInfo]) -> tuple[list[dict], int]:
    groups: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    for member in members:
        groups[unicodedata.normalize("NFC", member.filename.rstrip("/")).casefold()].append(member)
    collisions = []
    for group in groups.values():
        if len(group) <= 1:
            continue
        names = [entry.filename.rstrip("/") for entry in group]
        sizes = [entry.file_size for entry in group]
        collisions.append({
            "names": names, "sizes": sizes,
            "distinct_names": len(set(names)) == len(names),
            "sizes_differ": len(set(sizes)) > 1,
            "all_files": all(not e.is_dir() for e in group),
        })
    return collisions, len(members)


def test_private_host_case_preservation(root: Path) -> tuple[bool, bool]:
    """Synthetic file+folder probe only. No archive bytes ever written."""
    cache_root_ok(root)
    with tempfile.TemporaryDirectory(prefix=".case-probe-", dir=root) as folder:
        base = Path(folder)
        a, b = base / "InstallUtil.exe", base / "installutil.exe"
        a.write_bytes(b"CASE-A")
        try:
            fd = os.open(b, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as target:
                target.write(b"CASE-B")
        except FileExistsError:
            file_ok = False
        else:
            file_ok = (a.read_bytes() == b"CASE-A" and
                       b.read_bytes() == b"CASE-B" and
                       a.stat().st_ino != b.stat().st_ino)
        a_dir, b_dir = base / "CONFIG", base / "Config"
        a_dir.mkdir()
        try:
            b_dir.mkdir()
        except FileExistsError:
            directory_ok = False
        else:
            directory_ok = (a_dir.stat().st_ino != b_dir.stat().st_ino)
    return file_ok, directory_ok


def report(root: Path, *, test_host: bool = False) -> str:
    archive_path = select_rejected(root)
    audit = load_audit()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            categories, _ = audit.classify_zip_collisions(archive)
            collisions, total = classify_ambiguous_entries(members)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError,
            audit.UnsafePreparedPrefix) as exc:
        raise CasePreflightRefused("Rejected ZIP directory cannot be inspected safely") from exc
    lines = [
        "GAMEWELD — QUARANTINED ZIP CASE COMPATIBILITY PREFLIGHT",
        "Mode: archive filename inspection only; no extraction or Wine/Proton process",
        f"Archive SHA-256 filename prefix: {archive_path.stem[:12]}",
        f"ZIP members: {total}",
        f"Distinct case-ambiguous path groups: {len(collisions)}",
        f"Case-collision member pairs: {categories['case_collision']}",
        f"Groups with different sizes: {sum(x['sizes_differ'] for x in collisions)}",
    ]
    for group in collisions[:8]:
        lines.append("Ambiguous Windows-style name group: " +
                     " | ".join(f"{ascii(name)[:180]} ({size} bytes)"
                              for name, size in zip(group["names"], group["sizes"])))
    if test_host:
        file_ok, directory_ok = test_private_host_case_preservation(root)
        lines.append("Host file case-preservation: " + ("PASS" if file_ok else "FAIL"))
        lines.append("Host directory case-preservation: " + ("PASS" if directory_ok else "FAIL"))
        lines.append("Synthetic temporary files removed; no archive contents were extracted.")
        if not (file_ok and directory_ok):
            lines.append("Host result: NOT SUITABLE for case-preserving sandbox rehearsal")
        else:
            lines.append("Host result: CAN PRESERVE CASE on this cache filesystem; "
                         "Wine/Proton lookup behavior is still UNVERIFIED")
    else:
        lines.append("Host filesystem not tested (use --test-host-filesystem for a synthetic probe).")
    lines += [
        "Windows/Wine ambiguous name resolution and .NET compatibility: UNVERIFIED",
        "Full local SHA-256/CRC verified only by the separate integrity command.",
        "Case-colliding ZIP: STILL REJECTED. Do not normalize, stage, install or run it.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_cache = Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache"))
    parser.add_argument("--cache-root", type=Path,
                        default=default_cache / "gameweld/prepared-wemod")
    parser.add_argument("--test-host-filesystem", action="store_true",
                        help="Create and immediately delete only tiny synthetic case test files")
    args = parser.parse_args()
    try:
        print(report(args.cache_root, test_host=args.test_host_filesystem))
    except (CasePreflightRefused, OSError) as exc:
        parser.exit(2, f"GameWeld case compatibility preflight: BLOCKED — {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
