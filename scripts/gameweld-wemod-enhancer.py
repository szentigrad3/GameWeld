#!/usr/bin/env python3
"""GameWeld PC2 launcher for e-gleba/wemod_enhancer's upstream CLI.

All WeMod file edits are delegated to the upstream patch/restore commands
after an explicit GameWeld confirmation. This adapter only installs the
pinned upstream artifact into a private per-user directory and launches it.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

VERSION = "v1.0.7"
URL_ROOT = f"https://github.com/e-gleba/wemod_enhancer/releases/download/{VERSION}"
ASSETS = {
    "x86_64": (
        "wemod_enhancer-linux-amd64.tar.xz",
        "7a4d7d9687f9e86a0971a9b894ba9fe26a5fd02b1426564b44475a7d0eb15a30",
    ),
    "aarch64": (
        "wemod_enhancer-linux-arm64.tar.xz",
        "bf43ce14dc7a9760ff74882e7a535f542eb26b71ac60a2a37f9f2bdef78893f6",
    ),
}
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_UNPACKED = 220 * 1024 * 1024
PATCH_SCRIPT = Path("bin/wemod_enhancer.py")
PATCH_DLL = Path("bin/version.dll")


def data_root() -> Path:
    home = Path.home()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and not Path(xdg).is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute path")
    base = Path(xdg) if xdg else home / ".local/share"
    return base / "gameweld" / "tools" / "wemod-enhancer"


def installed_helper_dir() -> Path:
    manual = os.environ.get("GAMEWELD_WEMOD_ENHANCER_DIR")
    if manual:
        if not Path(manual).is_absolute():
            raise ValueError("GAMEWELD_WEMOD_ENHANCER_DIR must be absolute")
        return Path(manual).resolve()
    return data_root() / VERSION


def valid_patcher(root: Path) -> bool:
    return (
        (root / PATCH_SCRIPT).is_file()
        and (root / PATCH_DLL).is_file()
        and not (root / PATCH_SCRIPT).is_symlink()
        and not (root / PATCH_DLL).is_symlink()
    )


def detect_wemod(explicit: str | None = None) -> Path | None:
    home = Path.home()
    options = (
        [Path(explicit)] if explicit else [
            Path(os.environ["GAMEWELD_WEMOD_INSTALL_DIR"])
            if os.environ.get("GAMEWELD_WEMOD_INSTALL_DIR") else None,
            home / "wemod-launcher/wemod_data/wemod_bin",
            home / "Games/wemod-launcher/wemod_data/wemod_bin",
            home / ".local/share/wemod-launcher/wemod_data/wemod_bin",
        ]
    )
    for candidate in options:
        if candidate is None:
            continue
        # Do not search, patch or download anything outside known locations.
        path = candidate.expanduser().resolve()
        if (path / "WeMod.exe").is_file() and (path / "resources/app.asar").is_file():
            return path
    return None


def download_package(url: str, expected_sha: str, destination: Path) -> None:
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(url, timeout=45) as response, destination.open("wb") as output:
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > MAX_DOWNLOAD:
                raise ValueError("Upstream archive exceeds the size limit")
            digest.update(block)
            output.write(block)
    if digest.hexdigest() != expected_sha:
        raise ValueError("Upstream archive SHA256 mismatch; no installation performed")


def safe_unpack(archive: Path, destination: Path) -> None:
    total = 0
    with tarfile.open(archive, "r:xz") as src:
        members = src.getmembers()
        for member in members:
            # Standard tar archives may include a harmless "." root directory.
            if member.isdir() and member.name in (".", "./"):
                continue
            name = PurePosixPath(member.name)
            if (
                name.is_absolute() or not name.parts
                or any(part in ("", ".", "..") for part in name.parts)
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError("Unsafe upstream package entry; refusing extraction")
            if member.isfile():
                total += member.size
                if member.size > MAX_UNPACKED or total > MAX_UNPACKED:
                    raise ValueError("Upstream archive exceeds extracted size limit")
        for member in members:
            if member.isdir() and member.name in (".", "./"):
                continue
            name = PurePosixPath(member.name)
            target = destination.joinpath(*name.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = src.extractfile(member)
            if source is None:
                raise ValueError("Could not read upstream package entry")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            # Never preserve untrusted SUID or directory modes.
            target.chmod(0o644)
    if not valid_patcher(destination):
        # CPack tarballs can contain a single top-level package directory
        # (e.g. wemod_enhancer/bin/...) rather than a flat bin/ layout.
        # Do not guess between multiple candidates or follow archive links.
        candidates = []
        for script in destination.rglob("wemod_enhancer.py"):
            root = script.parent.parent
            if (
                root != destination
                and root.is_relative_to(destination)
                and valid_patcher(root)
            ):
                candidates.append(root)
        if len(candidates) == 1:
            nested = candidates[0]
            items = list(nested.iterdir())
            if any((destination / item.name).exists() for item in items):
                raise ValueError("Upstream nested package conflicts with destination")
            for item in items:
                item.rename(destination / item.name)
    if not valid_patcher(destination):
        seen = sorted(
            str(path.relative_to(destination))
            for path in destination.rglob("*")
            if path.is_file() and (
                "wemod_enhancer" in path.name or path.name == "version.dll"
            )
        )[:12]
        raise ValueError(
            "Upstream Linux package lacks the required patcher/DLL layout; "
            "observed: " + (", ".join(seen) if seen else "(no expected files)")
        )


def install_helper() -> Path:
    if os.environ.get("GAMEWELD_WEMOD_ENHANCER_DIR"):
        raise ValueError("Custom enhancer directory set; managed installation is disabled")
    dest = installed_helper_dir()
    if valid_patcher(dest):
        print("WeMod Enhancer already installed; leaving existing files unchanged.")
        return dest
    import platform
    arch = platform.machine().lower()
    if arch == "amd64":
        arch = "x86_64"
    if arch == "arm64":
        arch = "aarch64"
    if arch not in ASSETS:
        raise ValueError(f"No pinned Linux WeMod Enhancer archive for architecture {arch}")
    name, expected_sha = ASSETS[arch]
    base = data_root()
    base.mkdir(parents=True, exist_ok=True)
    # Keep an unverified/existing destination intact; never delete or overwrite.
    if dest.exists():
        raise ValueError("Destination exists but is not a valid helper; manual inspection required")
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=base) as temp:
        work = Path(temp)
        archive = work / "upstream.tar.xz"
        package = work / "package"
        package.mkdir()
        print("Downloading pinned upstream WeMod Enhancer Linux package...", flush=True)
        download_package(f"{URL_ROOT}/{name}", expected_sha, archive)
        safe_unpack(archive, package)
        package.rename(dest)
    print(f"WeMod Enhancer {VERSION} installed in GameWeld's private tools directory.")
    return dest


def run_upstream(action: str, install: Path, helper: Path) -> int:
    if not valid_patcher(helper):
        raise ValueError("WeMod Enhancer patcher not installed or invalid")
    command = [
        sys.executable, str(helper / PATCH_SCRIPT),
        action, "--install-dir", str(install),
    ]
    print(f"Running upstream WeMod Enhancer '{action}' on the selected WeMod installation.", flush=True)
    completed = subprocess.run(
        command, cwd=str(helper), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=180, check=False,
    )
    print(completed.stdout[-6000:] if completed.stdout else "(No upstream output)")
    if completed.returncode != 0:
        raise RuntimeError(f"Upstream WeMod Enhancer '{action}' failed ({completed.returncode}); see above")
    print(f"Upstream WeMod Enhancer '{action}' completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "install", "patch", "restore"))
    parser.add_argument("--install-dir", help="Folder containing WeMod.exe and resources/app.asar")
    parser.add_argument("--confirm", action="store_true", help="Required for download/patch/restore")
    args = parser.parse_args()
    folder = detect_wemod(args.install_dir)
    if args.action == "status":
        print(f"Upstream: https://github.com/e-gleba/wemod_enhancer ({VERSION})")
        print("WeMod installation: " + ("FOUND" if folder else "NOT FOUND (select its folder in Settings)"))
        print("WeMod Enhancer CLI: " + ("READY" if valid_patcher(installed_helper_dir()) else "NOT INSTALLED"))
        if folder:
            print("WeMod backup: " + ("AVAILABLE" if
                (folder / "resources/app.asar.backup").exists() else "NOT PRESENT"))
        print("Status is read-only; no WeMod files have been changed.")
        return 0
    if not args.confirm:
        raise ValueError(f"'{args.action}' requires explicit --confirm")
    if args.action == "install":
        install_helper()
        return 0
    if folder is None:
        raise ValueError("WeMod.exe and resources/app.asar not found; choose the WeMod install folder")
    # Restore never downloads additional components without confirmation.
    helper = installed_helper_dir() if args.action == "restore" else (
        installed_helper_dir() if valid_patcher(installed_helper_dir()) else install_helper())
    if args.action == "restore" and not (folder / "resources/app.asar.backup").is_file():
        raise ValueError("No original app.asar backup is present; refusing restore")
    return run_upstream(args.action, folder, helper)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"WeMod Enhancer integration: {exc}", file=sys.stderr)
        sys.exit(1)
