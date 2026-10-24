#!/usr/bin/env python3
"""Stage a new, UNVERIFIED Wine crypt32 pair; never touch installed Proton.

Default --preflight is strictly read-only. --build --confirm explicitly clones
pinned ValveSoftware/wine 46b29104, applies the original 0.1.41 SHA256 patch,
then builds Wine's x86_64/i386 Windows PE DLLs in a private project directory.
The new DLLs are NOT the proven 0.1.41 binaries unless BOTH release hashes match.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

REV = "46b29104e3741fe23bf5e2547196a253aab88c89"
UPSTREAM = "https://github.com/ValveSoftware/wine.git"
HISTORIC = {
    "x86_64-windows": "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775",
    "i386-windows": "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da",
}
ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / "patches/wine-crypt32-cert-sha256-prop.patch"
WORK = ROOT / "build/pc2-source/crypt32-source-rebuild"


def blocked(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_dirs(base: Path) -> None:
    if base.exists() and not base.is_dir():
        blocked("Build root exists but is not a directory")
    for path in (base, base / "wine-source", base / "wine-build", base / "candidate"):
        if path.is_symlink():
            blocked("Symlinked rebuild directory refused: " + str(path))


def preflight() -> int:
    print("GameWeld PC2 Test 21 — pinned Wine crypt32 rebuild preflight")
    print("Mode: READ ONLY; no downloads, changes or game launch")
    print("GE-Proton baseline: GE-Proton11-7 (source revision checked below)")
    print("ValveSoftware/wine source revision: " + REV)
    print("Original patch: " + str(PATCH))
    print("Build outputs ONLY in: " + str(WORK))
    if not PATCH.is_file():
        blocked("The original Wine SHA256 patch is missing")
    safe_dirs(WORK)
    required = ("git", "make", "file", "sha256sum")
    optional = ("clang", "gcc", "x86_64-w64-mingw32-gcc",
                "i686-w64-mingw32-gcc", "bison", "flex", "pkg-config")
    for name in required:
        print("REQUIRED " + name + ": " + ("FOUND" if shutil.which(name) else "MISSING"))
    for name in optional:
        print("BUILD-DEPENDENCY " + name + ": " +
              ("FOUND" if shutil.which(name) else "NOT FOUND (configure may require it)"))
    print("This builder does not use sudo, pacman, make install, Proton managers or DLL injection.")
    print("Actual full Wine builds can be resource-intensive and require development packages.")
    print("To opt in: python3 scripts/pc2-wand-crypt32-rebuild.py --build --confirm")
    print("New hashes MUST NOT be treated as approved replacements without ABI/behavioral testing.")
    return 0


def run_log(command: list[str], log, *, cwd: Path | None = None) -> None:
    print("Running: " + " ".join(command[:4]), flush=True)
    subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)


def compile_only(work: Path) -> int:
    source = work / "wine-source"
    build = work / "wine-build"
    output = work / "candidate"
    log_path = work / "build-output.log"
    if not PATCH.is_file():
        blocked("Historical crypt32 patch source missing")
    if not all(shutil.which(name) for name in ("git", "make", "file")):
        blocked("git, make and file are required before a Wine source build")
    safe_dirs(work)
    if (output / "SHA256SUMS").exists():
        blocked("Candidate binaries already exist; won't overwrite an unvalidated build.")
    if build.exists():
        blocked("Build directory already exists; preserve prior work instead of overwriting.")
    if source.exists():
        blocked("Source directory already exists; preserve prior work instead of patching over it.")
    work.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            run_log(["git", "clone", "--filter=blob:none", "--no-checkout",
                     UPSTREAM, str(source)], log)
            run_log(["git", "-C", str(source), "checkout", "--detach", REV], log)
            head = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                text=True).strip()
            if head != REV:
                blocked("Wine source commit is not pinned revision " + REV)
            run_log(["git", "-C", str(source), "apply", "--check",
                     str(PATCH)], log)
            run_log(["git", "-C", str(source), "apply", str(PATCH)], log)
            cert = (source / "dlls/crypt32/cert.c").read_text(encoding="utf-8")
            if "case CERT_SHA256_HASH_PROP_ID:" not in cert or "CALG_SHA_256" not in cert:
                blocked("The applied Wine patch did not add the intended certificate SHA256 behavior")
            build.mkdir()
            run_log([str(source / "configure"), "--enable-archs=i386,x86_64"],
                    log, cwd=build)
            jobs = max(1, min(os.cpu_count() or 4, 12))
            run_log(["make", "-j" + str(jobs)], log, cwd=build)
    except (OSError, subprocess.CalledProcessError) as exc:
        blocked("Isolated Wine build failed (" + type(exc).__name__ +
                "). See " + str(log_path) +
                ". No installed Proton binaries were touched.")

    outputs = {}
    for arch, expected in HISTORIC.items():
        candidate = build / "dlls/crypt32" / arch / "crypt32.dll"
        if not candidate.is_file() or candidate.is_symlink():
            blocked("Wine build didn't produce a Windows PE crypt32.dll for " + arch)
        description = subprocess.check_output(["file", "-b", str(candidate)],
                                               text=True).strip()
        if "PE32" not in description or "DLL" not in description:
            blocked("Built artifact is not Windows PE DLL for " + arch +
                    ": " + description)
        digest = sha256(candidate)
        outputs[arch] = (candidate, digest)
        print(arch + " SHA256=" + digest +
              (" (historical EXACT MATCH)" if digest == expected
               else " (DIFFERENT from 0.1.41 tested binary; NOT VERIFIED)"))

    output.mkdir()
    for arch, (candidate, _) in outputs.items():
        target_dir = output / arch
        target_dir.mkdir()
        shutil.copyfile(candidate, target_dir / "crypt32.dll")
    manifest = output / "SHA256SUMS"
    manifest.write_text(
        "".join(outputs[arch][1] + "  " + arch +
                "/crypt32.dll\n" for arch in HISTORIC), encoding="utf-8")
    print("Candidate artifacts: " + str(output))
    print("Compile log: " + str(log_path))
    print("No Steam, Wand, game or installed Proton files were modified.")
    print("STOP: Do not install newly compiled binaries before runtime/ABI validation.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--build", action="store_true")
    p.add_argument("--confirm", action="store_true")
    args = p.parse_args(argv)
    if args.build:
        if not args.confirm:
            blocked("--build requires explicit --confirm; only --preflight is read-only")
        return compile_only(WORK)
    if args.confirm:
        blocked("--confirm is only valid with --build")
    return preflight()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print("GameWeld Wine rebuild: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
