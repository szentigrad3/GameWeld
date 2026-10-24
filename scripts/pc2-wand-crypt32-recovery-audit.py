#!/usr/bin/env python3
"""Read-only local search for the exact Wand Native 0.1.41 crypt32 binaries.

Search likely old-build locations and source archives; never unpack, patch,
copy, delete or alter installed Proton, Steam, Wand, or Wine files. The only
write is the user-visible TXT audit report under build/pc2-source.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import re
import tarfile
import zipfile

EXPECTED = {
    "x86_64-windows": "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775",
    "i386-windows": "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da",
}
ARCHIVE_RE = re.compile(
    r"(?:wand-native|wand-crypt32|ge-proton-wand|wand-ge-proton).*"
    r"(?:\.zip|\.tar\.gz|\.tgz)$", re.I,
)
CRYPT_RE = re.compile(r"(?:^|/)(x86_64-windows|i386-windows)/crypt32\.dll$", re.I)
SKIP_DIRS = frozenset({".git", "node_modules", ".cache", ".venv", "__pycache__",
                       "steamapps", "games", "shadercache", "depotcache"})
MAX_ARCHIVE_MEMBER = 48 * 1024 * 1024  # no zip bombs / huge test artefacts
MAX_TREE_FILES = 150_000


def sha_stream(fileobj) -> str:
    h = hashlib.sha256()
    for block in iter(lambda: fileobj.read(1024 * 1024), b""):
        h.update(block)
    return h.hexdigest()


def default_roots() -> list[Path]:
    home = Path.home()
    return [
        home / "Desktop",
        home / "Downloads",
        home / "src/wand-ge-proton",
        home / ".local/share/wand-native",
        home / ".local/share/Steam/compatibilitytools.d",
        home / ".steam/root/compatibilitytools.d",
        Path("/mnt/other/JASON/DOWNLOADS/Compressed"),
        Path("/mnt/other/github/GameWeld/payload"),
        Path("/mnt/games/Steam/compatibilitytools.d/GE-Proton-Wand-SHA256"),
    ]


def find_files(roots: list[Path]):
    seen: set[str] = set()
    visited = 0
    for base in roots:
        if not base.is_dir() or base.is_symlink():
            continue
        for directory, dirs, files in os.walk(base, followlinks=False):
            root = Path(directory)
            level = len(root.relative_to(base).parts)
            dirs[:] = sorted(
                d for d in dirs if not (root / d).is_symlink()
                and d not in SKIP_DIRS and level < 9
            )
            for filename in sorted(files):
                visited += 1
                if visited > MAX_TREE_FILES:
                    raise RuntimeError("Stopped after 150000 inspected names; narrow --root")
                p = root / filename
                if p.is_symlink() or not p.is_file():
                    continue
                key = str(p.resolve())
                if key in seen:
                    continue
                name = str(p).replace("\\", "/")
                if CRYPT_RE.search(name) or ARCHIVE_RE.fullmatch(filename):
                    seen.add(key)
                    yield p


def scan_archive(path: Path, lines: list[str], matches: dict[str, list[str]]) -> None:
    found: dict[str, str] = {}
    saw_patch = False
    count = 0

    def examine(member: str, size: int, open_member) -> None:
        nonlocal saw_patch, count
        if member.endswith("wine-crypt32-cert-sha256-prop.patch"):
            saw_patch = True
        m = CRYPT_RE.search(member)
        if not m or not (0 < size <= MAX_ARCHIVE_MEMBER):
            return
        arch = m.group(1).lower()
        with open_member() as stream:
            digest = sha_stream(stream)
        count += 1
        found[arch] = digest
        if digest == EXPECTED[arch]:
            matches[arch].append(str(path) + " : " + member)

    try:
        if path.name.lower().endswith(".zip"):
            with zipfile.ZipFile(path, "r") as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    examine(member.filename, member.file_size,
                            lambda item=member: archive.open(item, "r"))
        elif path.name.lower().endswith((".tar.gz", ".tgz")):
            with tarfile.open(path, "r:gz") as archive:
                for member in archive:
                    if not member.isfile():
                        continue
                    examine(member.name, member.size,
                            lambda item=member: archive.extractfile(item))
    except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
        lines.append("ARCHIVE UNREADABLE: " + str(path) + " (" + type(exc).__name__ + ")")
        return

    if not count and saw_patch:
        lines.append("SOURCE PATCH ONLY: " + str(path))
    elif not count:
        lines.append("NO CRYPT32 PAYLOAD: " + str(path))
    else:
        lines.append("ARCHIVE DLLS: " + str(path) + " (" + str(count) + " entries)")
        for arch, digest in sorted(found.items()):
            lines.append("  " + arch + " " + ("PROVEN" if digest == EXPECTED[arch]
                                                  else "DIFFERENT") + " SHA256=" + digest)


def audit(roots: list[Path]) -> str:
    lines = ["GameWeld PC2 — Wand Native 0.1.41 crypt32 recovery audit",
             "Mode: READ ONLY, no extraction, no Proton changes",
             "Release hashes verified against original tested 0.1.41 records"]
    matches = {arch: [] for arch in EXPECTED}
    count = 0
    for path in find_files(roots):
        count += 1
        if CRYPT_RE.search(str(path).replace("\\", "/")):
            arch = CRYPT_RE.search(str(path).replace("\\", "/")).group(1).lower()
            try:
                with path.open("rb") as f:
                    digest = sha_stream(f)
                is_match = digest == EXPECTED[arch]
                lines.append(("PROVEN DLL: " if is_match else "DIFFERENT DLL: ") +
                             str(path) + " [" + arch + " SHA256=" + digest + "]")
                if is_match:
                    matches[arch].append(str(path))
            except OSError as exc:
                lines.append("DLL UNREADABLE: " + str(path) +
                             " (" + type(exc).__name__ + ")")
        else:
            scan_archive(path, lines, matches)

    lines.append("Candidate files/archives examined: " + str(count))
    for arch in EXPECTED:
        lines.append("Verified " + arch + " candidates: " + str(len(matches[arch])))
        for path in matches[arch][:8]:
            lines.append("  " + path)
    if all(matches[arch] for arch in EXPECTED):
        lines.append("RESULT: BOTH HISTORICALLY PROVEN DLLS LOCATED; review sources before any manual restore")
    else:
        missing = ", ".join(arch for arch in EXPECTED if not matches[arch])
        lines.append("RESULT: NO COMPLETE PROVEN COMPILED DLL PAIR FOUND (missing " + missing + ")")
        lines.append("NEXT: Rebuild missing Wine crypt32 payload against the original GE-Proton11-7/Wine baseline, "
                     "or recover the final non-source 0.1.41 release package. "
                     "Do NOT rename, overwrite or bypass mismatched installed DLLs.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path,
                        help="Restrict search to directory (repeatable); useful for tests")
    parser.add_argument("--report", type=Path,
                        default=Path("build/pc2-source/pc2-crypt32-recovery-report.txt"))
    args = parser.parse_args()
    report = audit(args.root or default_roots())
    if not args.report.parent.exists():
        args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.report.is_symlink():
        raise ValueError("Refusing to write report through a symlink")
    args.report.write_text(report, encoding="utf-8")
    print(report, end="")
    print("Report: " + str(args.report.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
