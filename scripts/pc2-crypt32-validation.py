#!/usr/bin/env python3
"""GameWeld PC2 Test 22: validate NEW crypt32 candidates, never install them.

--audit: read-only cross-architecture PE/export and known-certificate checks.
--compile-probes --confirm: build two tiny Windows API probes inside build/.
--runtime-probes --confirm --proton /abs/path/proton: run the probes inside a
FRESH, disposable Proton prefix, with candidate DLLs copied only into that
prefix. Never touch Steam's actual Proton files or any game's compatdata.

A passing test establishes CERT_SHA256_HASH_PROP_ID behavior for the compiled
candidate in that sandbox, NOT that Wand renders or attaches to games.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build/pc2-source/crypt32-source-rebuild"
TESTROOT = ROOT / "build/pc2-source/crypt32-validation"
PROBE = ROOT / "scripts/pc2-crypt32-sha256-probe.c"
ARCHS = {
    "x86_64-windows": ("x86_64-w64-mingw32-gcc", "x86_64-w64-mingw32-objdump", "x86_64"),
    "i386-windows": ("i686-w64-mingw32-gcc", "i686-w64-mingw32-objdump", "i386"),
}
EXPORTS = (
    "CertCreateCertificateContext", "CertGetCertificateContextProperty",
    "CertSetCertificateContextProperty", "CertFreeCertificateContext",
)


class ValidationBlocked(ValueError):
    pass


def safe_workdir():
    if any(x.is_symlink() for x in (TESTROOT, TESTROOT / "probes", TESTROOT / "runtime")):
        raise ValidationBlocked("Symlinked validation output directory is not allowed")


def candidate(arch: str) -> Path:
    return BUILD / "candidate" / arch / "crypt32.dll"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for part in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def check_fixture():
    """Fixture expected digests are computed independently of crypt32 itself."""
    if not PROBE.is_file() or PROBE.is_symlink():
        raise ValidationBlocked("Missing/unsafe offline SHA256 certificate probe source")
    data = PROBE.read_text(encoding="utf-8")
    block = re.search(r"static const char der_hex\[\]\s*=\s*(.*?);", data, re.S)
    hashes = dict(re.findall(
        r"static const char (expected_sha256|expected_sha1)\[\]\s*=\s*\"([a-f0-9]+)\";", data))
    if not block or set(hashes) != {"expected_sha256", "expected_sha1"}:
        raise ValidationBlocked("Test certificate/expected digests missing")
    chunks = re.findall(r'"([0-9a-fA-F]+)"', block.group(1))
    if not chunks:
        raise ValidationBlocked("Offline certificate DER hex missing")
    raw = bytes.fromhex("".join(chunks))
    if len(raw) < 200 or len(raw) > 4096 or not raw.startswith(b"\x30\x82"):
        raise ValidationBlocked("Invalid embedded DER fixture length/encoding")
    if hashlib.sha256(raw).hexdigest() != hashes["expected_sha256"]:
        raise ValidationBlocked("Probe SHA256 expectation does NOT match independently computed DER digest")
    if hashlib.sha1(raw).hexdigest() != hashes["expected_sha1"]:
        raise ValidationBlocked("Probe SHA1 control expectation does NOT match DER digest")
    return len(raw), hashes


def audit() -> int:
    safe_workdir()
    print("GameWeld PC2 Test 22 — offline crypt32 candidate ABI and certificate fixture")
    print("Mode: READ ONLY; no Wine, Proton, games, builds or patchers launched")
    rebuild = ROOT / "scripts/pc2-wand-crypt32-rebuild.py"
    spec = importlib.util.spec_from_file_location("gameweld_crypt32_rebuild", rebuild)
    if spec is None or spec.loader is None:
        raise ValidationBlocked("Cannot load existing Test21 read-only candidate verifier")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    if mod.status_candidates(BUILD) != 0:
        raise ValidationBlocked("Test21 candidate status incomplete. Do not try to run them.")
    length, hashes = check_fixture()
    print(f"Certificate DER fixture: {length} bytes, SHA256={hashes['expected_sha256']}")
    for arch, (_, objdump, _) in ARCHS.items():
        binary = candidate(arch)
        if not binary.is_file() or binary.is_symlink():
            raise ValidationBlocked(arch + " candidate crypt32 DLL missing")
        if not shutil.which(objdump):
            raise ValidationBlocked("Required MinGW import/export inspector missing: " + objdump)
        result = subprocess.run(
            [objdump, "-p", str(binary)], text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise ValidationBlocked(arch + " objdump PE export inspection failed: " +
                                    result.stderr[:500])
        missing = [name for name in EXPORTS if not re.search(
            r"\b" + re.escape(name) + r"\b", result.stdout)]
        if missing:
            raise ValidationBlocked(arch + " crypt32 is missing required PE exports: " +
                                    ", ".join(missing))
        print(arch + ": required Wincrypt API exports FOUND; SHA256=" + sha256(binary))
    print("STATIC AUDIT: PASS (file integrity, PE exports and independent fixture only).")
    print("Functional certificate-property behavior and Wand trainer integration: NOT YET VERIFIED")
    return 0


def probe_path(arch: str) -> Path:
    return TESTROOT / "probes" / (ARCHS[arch][2] + "-crypt32-property.exe")


def compile_probes() -> int:
    audit()
    safe_workdir()
    directory = TESTROOT / "probes"
    if directory.exists():
        raise ValidationBlocked("Probe output folder exists; preserve previously compiled tests. "
                                "Use existing probes rather than overwriting them.")
    for arch, (gcc, _, _) in ARCHS.items():
        if not shutil.which(gcc):
            raise ValidationBlocked("Required Windows compiler not available: " + gcc)
    directory.mkdir(parents=True, exist_ok=False)
    for arch, (gcc, _, _) in ARCHS.items():
        output = probe_path(arch)
        command = [gcc, "-O2", "-Wall", "-Wextra", "-o", str(output),
                   str(PROBE), "-lcrypt32"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            raise ValidationBlocked("Failed to cross-compile " + arch + " probe:\n" +
                                    result.stderr[-2500:])
        if not output.is_file() or output.stat().st_size < 1024:
            raise ValidationBlocked(arch + " compiler produced no executable")
        print(arch + " probe compiled: " + str(output) + " SHA256=" + sha256(output))
    print("PROBE BUILD: PASS — only disposable GameWeld project files created.")
    print("Next: opt-in functional test in a NEW disposable Proton prefix, not a game prefix.")
    return 0


def find_steam():
    home = Path.home()
    options = [
        home / ".steam/root", home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
    ]
    return next((p.resolve() for p in options if p.is_dir()), None)


def run_proton(proton: Path, exe: Path, data: Path, steam: Path,
               env_overrides: dict[str, str], logfile: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env.update({
        "STEAM_COMPAT_DATA_PATH": str(data),
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam),
        "STEAM_COMPAT_APP_ID": "0",
        "SteamAppId": "0",
        "SteamGameId": "0",
        "WINEPREFIX": str(data / "pfx"),
        "WINEDEBUG": "-all,+loaddll",
    })
    env.update(env_overrides)
    # Noninteractive execution: a crash or missing Proton runtime will fail
    # without running a game or trainer, and never uses an existing game prefix.
    try:
        p = subprocess.run(
            [str(proton), "waitforexitandrun", str(exe)],
            env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False,
        )
        result = p.stdout[-250_000:]
        rc = p.returncode
    except subprocess.TimeoutExpired as exc:
        result = str(exc)
        rc = 124
    logfile.write_text(result, encoding="utf-8")
    return rc, result


def _safe_replace_prefix_dll(pfx: Path, arch: str, binary: Path) -> Path:
    sysdir = pfx / "drive_c/windows" / (
        "system32" if arch == "x86_64-windows" else "syswow64")
    if not sysdir.is_dir() or sysdir.is_symlink() or not sysdir.resolve().is_relative_to(pfx.resolve()):
        raise ValidationBlocked("Disposable Wine prefix system directory missing or points outside sandbox")
    target = sysdir / "crypt32.dll"
    if target.exists() or target.is_symlink():
        previous = sysdir / "crypt32.gameweld-original.dll"
        if previous.exists() or previous.is_symlink():
            raise ValidationBlocked("Scratch prefix already has crypt32 backup; refusing overwrite")
        target.rename(previous)  # Rename link/file in SCRATCH prefix only, never write its target.
    shutil.copyfile(binary, target)  # Never follow original symlink: it was renamed above.
    if sha256(target) != sha256(binary):
        raise ValidationBlocked("Copied scratch prefix crypt32 DLL checksum mismatch")
    return target


def runtime_probes(proton: Path) -> int:
    audit()
    safe_workdir()
    if not proton.is_absolute() or not proton.is_file() or not os.access(proton, os.X_OK):
        raise ValidationBlocked("--proton must identify an existing absolute executable Proton launcher")
    proton = proton.resolve(strict=True)
    if proton.is_relative_to(TESTROOT.resolve(strict=False)):
        raise ValidationBlocked("Proton executable cannot reside inside test output")
    for arch in ARCHS:
        binary = probe_path(arch)
        if not binary.is_file() or binary.is_symlink():
            raise ValidationBlocked("No compiled " + arch + " Windows test EXE. Run --compile-probes first.")
    steam = find_steam()
    if not steam:
        raise ValidationBlocked("Steam client root not found. No runtime session was started.")
    runtime_root = TESTROOT / "runtime"
    if runtime_root.exists() and (not runtime_root.is_dir() or runtime_root.is_symlink()):
        raise ValidationBlocked("Unsafe runtime directory")
    runtime_root.mkdir(parents=True, exist_ok=True)
    session = runtime_root / ("isolated-" + uuid.uuid4().hex[:12])
    session.mkdir(parents=False, exist_ok=False)
    print("DISPOSABLE Proton prefix: " + str(session))
    print("Existing Proton launcher READ ONLY: " + str(proton))
    print("No existing Steam game prefix, game, Wand process or trainer is used.")
    # First run bootstraps this NEW prefix. The probe may fail here because
    # candidate DLLs are NOT installed yet; only prefix creation matters.
    rc0, out0 = run_proton(
        proton, probe_path("x86_64-windows"), session, steam,
        {"WINEDLLOVERRIDES": "crypt32=b"}, session / "bootstrap.log")
    pfx = session / "pfx"
    if not (pfx / "drive_c/windows/system32").is_dir():
        raise ValidationBlocked("Proton did not create a valid disposable prefix. "
                                "Bootstrap rc=" + str(rc0) + "; inspect " +
                                str(session / "bootstrap.log"))
    for arch in ARCHS:
        _safe_replace_prefix_dll(pfx, arch, candidate(arch))
    checked = {}
    for arch in ARCHS:
        rc, output = run_proton(
            proton, probe_path(arch), session, steam,
            {"WINEDLLOVERRIDES": "crypt32=n"}, session / (ARCHS[arch][2] + ".log"))
        markers = ["GW_SHA256_OK", "GW_SHA1_OK",
                   "GW_SHA256_AFTER_SET_OK", "GW_CRYPT32_CERT_SHA256_RESULT=PASS"]
        print(arch + ": exit=" + str(rc) +
              ", API markers=" + str(sum(x in output for x in markers)) + "/" + str(len(markers)))
        # Require native-only crypt32 loading, never native-then-builtin
        # fallback. The probe names the actual DLL module it imported.
        module = re.search(r"(?m)^GW_CRYPT32_MODULE=([^\r\n]+)", output)
        expected_subdir = ("system32" if arch == "x86_64-windows" else "syswow64")
        located_in_sandbox = bool(
            module and
            ("\\windows\\" + expected_subdir + "\\crypt32.dll") in
            module.group(1).replace("/", "\\").lower()
        )
        checked[arch] = rc == 0 and all(x in output for x in markers) and located_in_sandbox
        print(arch + " native-only DLL module path: " +
              (module.group(1) if module else "MISSING"))
        print(arch + (" CERTIFICATE API: PASS" if checked[arch] else
                       " CERTIFICATE API: FAILED/UNVERIFIED (see sandbox log)"))
    passed = all(checked.values())
    report = [
        "GameWeld PC2 Test 22 — isolated Proton crypt32 certificate SHA256 smoke",
        "Proton launcher: " + str(proton),
        "Disposable compatibility data: " + str(session),
        "Candidate x86_64 SHA256: " + sha256(candidate("x86_64-windows")),
        "Candidate i386 SHA256: " + sha256(candidate("i386-windows")),
        "CertGet/Set ID 107 x86_64: " + ("PASS" if checked["x86_64-windows"] else "FAIL"),
        "CertGet/Set ID 107 i386: " + ("PASS" if checked["i386-windows"] else "FAIL"),
        "RESULT: " + ("API FUNCTIONAL PASS" if passed else "BLOCKED"),
        "No Steam game or Wand launched. Real trainer/renderer NOT verified.",
    ]
    (session / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    if not passed:
        raise ValidationBlocked("One or more sandboxed property probes failed; DO NOT install candidate DLLs")
    print("Candidate API behaviour passed only in disposable prefix. "
          "Do not change the installed GameWeld Proton hash gate yet.")
    return 0



def diagnose_runtime_logs() -> int:
    """Inspect the most recent sandbox output only; never start Proton.

    A nonzero Windows process exit code without GW_CRYPT32_MODULE proves
    neither an API failure nor a bad DLL. Show the bootstrap and architecture
    logs to distinguish loader/probe/environment failures.
    """
    safe_workdir()
    root = TESTROOT / "runtime"
    if not root.is_dir() or root.is_symlink():
        print("No previous Test22 runtime logs found under " + str(root))
        return 2
    sessions = [
        p for p in root.iterdir()
        if p.is_dir() and not p.is_symlink()
        and re.fullmatch(r"isolated-[0-9a-f]{12}", p.name)
    ]
    if not sessions:
        print("No previous Test22 disposable runtime session found")
        return 2
    session = max(sessions, key=lambda p: p.stat().st_mtime_ns)
    print("GameWeld PC2 Test 22 — existing isolated Proton runtime diagnostics")
    print("Mode: READ ONLY; does not launch Steam, Proton, Wand or a game")
    print("Session: " + str(session))
    pattern = re.compile(
        r"(?i)(err:|error:|fatal|failed|failure|not found|not load|"
        r"cannot|can't|module|c0000135|c000007b|status_dll|"
        r"GW_|steam[_ ]compat|proton:|wine:)"
    )
    for name in ("bootstrap.log", "x86_64.log", "i386.log", "report.txt"):
        path = session / name
        print("\n========== " + name + " ==========")
        if path.is_symlink() or not path.is_file():
            print("MISSING or unsafe file")
            continue
        if path.stat().st_size > 12 * 1024 * 1024:
            print("Large log: displaying last 2 MiB only")
        with path.open("rb") as inp:
            inp.seek(0, os.SEEK_END)
            inp.seek(max(0, inp.tell() - 2 * 1024 * 1024))
            content = inp.read().decode("utf-8", errors="replace")
        lines = content.splitlines()
        print("Read lines:", len(lines))
        selected = [line for line in lines if pattern.search(line)]
        if selected:
            print("--- Diagnostic matches (last 40) ---")
            for line in selected[-40:]:
                print(line[:900])
        if name != "report.txt":
            print("--- Last 25 lines ---")
            for line in lines[-25:]:
                print(line[:900])
        elif not selected:
            print(content[-3000:])
    print("\nSTATUS: No new tests were run. Exit code 53 + no GW_ markers "
          "cannot identify a crypt32 API defect without loader diagnostics.")
    print("Do not install the staged DLLs into the existing GE Proton Wand tool.")
    return 0

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--audit", action="store_true", help="default: read-only binary/export inspection")
    mode.add_argument("--compile-probes", action="store_true")
    mode.add_argument("--runtime-probes", action="store_true")
    mode.add_argument("--diagnose-runtime", action="store_true", help="read previous sandbox Proton logs without running any tests")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--proton", type=Path, help="explicit absolute Proton launcher for disposable runtime tests")
    args = p.parse_args(argv)
    if args.diagnose_runtime:
        if args.confirm or args.proton:
            raise ValidationBlocked("--diagnose-runtime is read-only and accepts no --confirm or --proton")
        return diagnose_runtime_logs()
    if args.audit or (not args.compile_probes and not args.runtime_probes):
        if args.confirm or args.proton:
            raise ValidationBlocked("--audit is read only; --confirm/--proton not used")
        return audit()
    if not args.confirm:
        raise ValidationBlocked("Opt-in build/runtime tests require explicit --confirm")
    if args.compile_probes:
        if args.proton:
            raise ValidationBlocked("--proton is only valid for --runtime-probes")
        return compile_probes()
    if not args.proton:
        raise ValidationBlocked("--runtime-probes requires --proton /absolute/path/proton")
    return runtime_probes(args.proton)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationBlocked as exc:
        print("GameWeld Test 22 BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
