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
import re
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
    required = ("git", "make", "file", "sha256sum", "autoreconf", "sh")
    optional = ("clang", "gcc", "x86_64-w64-mingw32-gcc",
                "i686-w64-mingw32-gcc", "bison", "flex", "pkg-config")
    for name in required:
        print("REQUIRED " + name + ": " + ("FOUND" if shutil.which(name) else "MISSING"))
    for name in optional:
        print("BUILD-DEPENDENCY " + name + ": " +
              ("FOUND" if shutil.which(name) else "NOT FOUND (configure may require it)"))
    print("This builder does not use sudo, pacman, make install, Proton managers or DLL injection.")
    print("Actual full Wine builds can be resource-intensive and require development packages.")
    print("An interrupted source build can be resumed with the SAME --build --confirm command.")
    print("The pinned Wine Git checkout requires autogen.sh to generate configure.")
    print("To opt in: python3 scripts/pc2-wand-crypt32-rebuild.py --build --confirm")
    print("New hashes MUST NOT be treated as approved replacements without ABI/behavioral testing.")
    return 0


def run_log(command: list[str], log, *, cwd: Path | None = None) -> None:
    print("Running: " + " ".join(command[:4]), flush=True)
    subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)


def ensure_pinned_source(source: Path, log) -> None:
    """Clone once, or reuse only the exact pinned Wine checkout safely.

    Re-enter after failed bootstrap/configure/make. Never clean/reset any
    existing source tree and never apply the SHA256 patch twice.
    """
    if not source.exists():
        run_log(["git", "clone", "--filter=blob:none", "--no-checkout",
                 UPSTREAM, str(source)], log)
        run_log(["git", "-C", str(source), "fetch", "--depth=1",
                 "origin", REV], log)
        run_log(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], log)
    elif not (source / ".git").is_dir():
        blocked("Existing Wine source is not a Git checkout; refusing to overwrite it")

    head = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != REV:
        blocked("Existing Wine checkout revision " + head +
                " differs from pinned revision " + REV + "; refusing to reset")

    # An interrupted first run has already applied the patch. 'git apply
    # --reverse --check' is a read-only proof of its exact presence.
    reverse = subprocess.run(
        ["git", "-C", str(source), "apply", "--reverse", "--check", str(PATCH)],
        stdout=log, stderr=subprocess.STDOUT, check=False,
    )
    if reverse.returncode == 0:
        print("Pinned Wine SHA256 patch: already applied; preserving checkout", flush=True)
    else:
        run_log(["git", "-C", str(source), "apply", "--check",
                 str(PATCH)], log)
        run_log(["git", "-C", str(source), "apply", str(PATCH)], log)

    cert = (source / "dlls/crypt32/cert.c").read_text(encoding="utf-8")
    if ("case CERT_SHA256_HASH_PROP_ID:" not in cert or
            "CALG_SHA_256" not in cert):
        blocked("Patched Wine cert.c does not contain CERT_SHA256_HASH_PROP_ID/CALG_SHA_256")


def ensure_configure(source: Path, log) -> None:
    """Wine Git checkouts ship autogen.sh + configure.ac, not configure.

    Run ONLY the checked-out project's documented ./autogen.sh script.
    All generated files remain in the isolated Wine source checkout.
    """
    configure = source / "configure"
    if configure.is_file():
        print("Wine configure: already generated; reusing it", flush=True)
        return
    if not (source / "autogen.sh").is_file() or not (source / "configure.ac").is_file():
        blocked("Pinned Wine Git checkout is missing autogen.sh/configure.ac")
    if not shutil.which("autoreconf"):
        blocked("Wine bootstrap needs autoreconf (autoconf); install its build dependency first")
    print("Wine configure absent: running source autogen.sh (bootstrap only)", flush=True)
    run_log(["sh", "./autogen.sh"], log, cwd=source)
    if not configure.is_file():
        blocked("Wine autogen.sh finished without producing configure; inspect build-output.log")



def diagnose_build_log(work: Path, *, max_errors: int = 16) -> int:
    """Read only the latest build attempt; do not retry make or alter the tree.

    Wine's parallel make logs can interleave error lines. Preserve source
    excerpts plus the final output so no guessed dependency fix is applied.
    """
    log_path = work / "build-output.log"
    if not log_path.is_file():
        print("No build-output.log found at " + str(log_path))
        return 2
    if log_path.is_symlink():
        blocked("Refusing symlinked build log")
    # Read a bounded suffix; the log itself can be large after a Wine build.
    with log_path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 4 * 1024 * 1024))
        log = stream.read().decode("utf-8", errors="replace")
    section = "\n=== GameWeld Wine pinned source build/resume ===\n"
    if section in log:
        log = log.rsplit(section, 1)[-1]
    lines = log.splitlines()
    pattern = re.compile(
        r"(?i)(?:\berror:|\bfatal error:|undefined reference|"
        r"no rule to make target|make(?:\[\d+\])?: \*\*\*|"
        r"collect2:|ld: cannot find|killed signal|out of memory|"
        r"cannot find -l|linker command failed|cannot execute)"
    )
    matches = [i for i, line in enumerate(lines) if pattern.search(line)]
    print("GameWeld PC2 Test 21 — failed Wine build diagnostics")
    print("Mode: READ ONLY; no Wine/Proton/make processes started")
    print("Source log: " + str(log_path))
    print("Latest attempt lines: " + str(len(lines)) +
          ", likely error lines: " + str(len(matches)))
    for index in matches[-max_errors:]:
        lo, hi = max(0, index - 2), min(len(lines), index + 3)
        print("--- Possible failure at build line " + str(index + 1) + " ---")
        for offset in range(lo, hi):
            print(f"{offset+1}: {lines[offset][:700]}")
    print("--- Last 45 lines of latest attempt ---")
    for line in lines[-45:]:
        print(line[:700])
    if not matches:
        print("No standard compiler/linker errors matched; see last lines above.")
    print("Nothing was rebuilt or installed. Share these diagnostics to identify "
          "the actual missing dependency or compilation failure.")
    return 0


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
    if output.exists():
        blocked("Candidate output directory already exists; preserve it instead of overwriting")
    if source.exists() and not (source / ".git").is_dir():
        blocked("Source directory exists without Git metadata; refusing overwrite")
    if build.exists() and not build.is_dir():
        blocked("Build output path is not a directory")
    work.mkdir(parents=True, exist_ok=True)
    # Append to the original source checkout/build log on retries. Never
    # truncate failed-build diagnostics; no rm/reset is performed.
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n=== GameWeld Wine pinned source build/resume ===\n")
            log.flush()
            ensure_pinned_source(source, log)
            ensure_configure(source, log)
            if not build.exists():
                build.mkdir()
            if not (build / "Makefile").is_file():
                run_log([str(source / "configure"), "--enable-archs=i386,x86_64"],
                        log, cwd=build)
                if not (build / "Makefile").is_file():
                    blocked("Wine configure finished without Makefile; inspect build-output.log")
            else:
                print("Wine build Makefile already exists; resuming compilation", flush=True)
            jobs = max(1, min(os.cpu_count() or 4, 12))
            run_log(["make", "-j" + str(jobs)], log, cwd=build)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("Isolated Wine build exited (" + type(exc).__name__ + ").", file=sys.stderr)
        try:
            diagnose_build_log(work)
        except (OSError, ValueError) as diagnostic_exc:
            print("Log inspection failed: " + str(diagnostic_exc), file=sys.stderr)
        blocked("Wine build failed. Preserve the existing source/build tree. "
                "No installed Proton binaries were touched. "
                "Run --diagnose to redisplay the compiler errors.")

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
    group.add_argument("--diagnose", action="store_true", help="read only the existing latest build error log")
    p.add_argument("--confirm", action="store_true")
    args = p.parse_args(argv)
    if args.diagnose:
        if args.confirm:
            blocked("--diagnose does not accept --confirm")
        return diagnose_build_log(WORK)
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
