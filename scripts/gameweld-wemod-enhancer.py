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


def client_root(candidate: Path) -> Path | None:
    """Resolve a real Wand/WeMod Electron app version, never a Proton provider."""
    try:
        folder = candidate.expanduser().resolve(strict=True)
        asar = folder / "resources" / "app.asar"
        if (
            not folder.is_dir() or asar.is_symlink()
            or not asar.is_file() or not os.access(asar, os.R_OK)
        ):
            return None
        # GameWeld's existing scanner can find an app-N.N.N subdirectory
        # containing the resources, without a WeMod.exe in that subdirectory.
        known = any((folder / executable).is_file() for executable in
                    ("WeMod.exe", "Wand.exe", "wemod.exe", "wand.exe"))
        if not known and not folder.name.startswith("app-"):
            return None
        return folder
    except (OSError, RuntimeError, ValueError):
        return None


def discover_existing_clients() -> list[Path]:
    """Reuse GameWeld's existing bounded Steam/Heroic/Lutris/Wine scanner."""
    discovery = Path(__file__).resolve().with_name("gameweld-wand-discovery.py")
    if not discovery.is_file():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(discovery), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=45, check=False, text=True,
        )
        if result.returncode != 0 or len(result.stdout) > (256 * 1024):
            return []
        import json
        data = json.loads(result.stdout)
        if data.get("ok") is not True:
            return []
        output: list[Path] = []
        seen: set[Path] = set()
        for item in data.get("installations", [])[:200]:
            path = item.get("install", "")
            if not isinstance(path, str) or not path:
                continue
            valid = client_root(Path(path))
            if valid and valid not in seen:
                output.append(valid)
                seen.add(valid)
        return output
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def available_clients(explicit: str | None = None) -> list[Path]:
    if explicit:
        valid = client_root(Path(explicit))
        return [valid] if valid else []
    home = Path.home()
    known = [
        Path(os.environ["GAMEWELD_WEMOD_INSTALL_DIR"])
        if os.environ.get("GAMEWELD_WEMOD_INSTALL_DIR") else None,
        home / "wemod-launcher/wemod_data/wemod_bin",
        home / "Games/wemod-launcher/wemod_data/wemod_bin",
        home / ".local/share/wemod-launcher/wemod_data/wemod_bin",
    ]
    found: list[Path] = []
    seen: set[Path] = set()
    for candidate in known:
        if candidate is None:
            continue
        valid = client_root(candidate)
        if valid and valid not in seen:
            found.append(valid)
            seen.add(valid)
    for valid in discover_existing_clients():
        if valid not in seen:
            found.append(valid)
            seen.add(valid)
    return found


def detect_wemod(explicit: str | None = None) -> Path | None:
    found = available_clients(explicit)
    # Never choose an arbitrary Wine prefix when more than one client exists.
    return found[0] if len(found) == 1 else None


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



def sha256_file(path: Path, max_bytes: int = 400 * 1024 * 1024) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    if path.stat().st_size > max_bytes:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_patch_files(folder: Path, helper: Path) -> tuple[bool, list[str]]:
    """Evidence that a specific existing Wand client has the Enhancer's files.

    This does NOT prove runtime DLL selection, login or game trainer support.
    """
    messages = ["Wand/WeMod selected client: FOUND"]
    asar = folder / "resources" / "app.asar"
    backup = folder / "resources" / "app.asar.backup"
    installed_proxy = folder / "version.dll"
    trusted_proxy = helper / PATCH_DLL
    original_hash = sha256_file(backup)
    active_hash = sha256_file(asar)
    proxy_hash = sha256_file(installed_proxy, max_bytes=8 * 1024 * 1024)
    reference_hash = sha256_file(trusted_proxy, max_bytes=8 * 1024 * 1024)
    if not original_hash:
        messages.append("Original ASAR backup: MISSING or unreadable")
    else:
        messages.append("Original ASAR backup: PRESENT")
    if not active_hash:
        messages.append("Active ASAR: MISSING or unreadable")
    elif original_hash and active_hash != original_hash:
        messages.append("Active ASAR: MODIFIED compared with original backup")
    elif original_hash:
        messages.append("Active ASAR: SAME as original backup (not patched)")
    else:
        messages.append("Active ASAR: readable; patch difference unknown")
    if proxy_hash and reference_hash and proxy_hash == reference_hash:
        messages.append("Enhancer DLL proxy: MATCHES pinned upstream helper")
    elif not reference_hash:
        messages.append("Enhancer DLL proxy: reference helper unavailable")
    else:
        messages.append("Enhancer DLL proxy: MISSING or DOES NOT MATCH pinned helper")
    good = bool(
        original_hash and active_hash and original_hash != active_hash
        and proxy_hash and reference_hash and proxy_hash == reference_hash
    )
    messages.append("Client patch file check: " + (
        "PASS (files only; runtime not verified)" if good else "NOT VERIFIED"
    ))
    messages.append("Wine native DLL override: REQUIRED (version=n,b); actual loading not verified")
    return good, messages


def validate_appid(appid: str) -> str:
    if not appid.isascii() or not appid.isdecimal() or str(int(appid)) != appid or not (0 < int(appid) < 2**32):
        raise ValueError("A valid decimal Steam app ID is required for the selected game check")
    return appid


def check_selected_game(args: argparse.Namespace, patched: bool) -> list[str]:
    """Per-game explanation without asserting unsupported trainer functionality."""
    output = ["Selected game: " + (args.game_name or "(unnamed)")]
    output.append("Game provider: " + (args.game_provider or "unknown"))
    if args.game_provider != "steam":
        output.append("Game compatibility: UNKNOWN — PC2 has not validated Wand on this provider")
    else:
        validate_appid(args.appid)
        output.append("Selected Steam App ID: " + args.appid)
        folder = Path(args.game_dir) if args.game_dir else None
        if folder and folder.is_dir():
            output.append("Selected game installed directory: PRESENT")
        else:
            output.append("Selected game installed directory: NOT VERIFIED")
        if args.runtime_hint == "native":
            output.append("Game runtime: NATIVE LINUX ELF observed")
            output.append("Wand Windows trainer with this Linux build: NOT SUPPORTED")
        elif args.runtime_hint == "windows-associated":
            output.append("Game runtime: Windows-process name ASSOCIATED (not executable-verified)")
        else:
            output.append("Game runtime: UNKNOWN — run game and rerun this check")
    selected_prefix = Path(args.wine_prefix).resolve() if args.wine_prefix else None
    game_prefix = Path(args.game_prefix).resolve() if args.game_prefix else None
    if selected_prefix and game_prefix:
        output.append("Wand and game prefix: " + (
            "SAME DIRECTORY (ownership not verified)" if selected_prefix == game_prefix
            else "DIFFERENT — trainer must join the game's actual runtime"
        ))
    else:
        output.append("Wand and game prefix: NOT VERIFIED")
    output.append("Trainer available for this specific game: NOT VERIFIED")
    output.append("WeMod login/Pro entitlement and runtime DLL load: NOT VERIFIED")
    if not patched:
        output.append("Game test result: BLOCKED — selected client patch files not verified")
    elif args.runtime_hint == "native":
        output.append("Game test result: NATIVE LINUX GAME — Windows Wand trainer not ready")
    else:
        output.append("Game test result: PATCH FILES READY — live in-game trainer not yet proven")
    return output


def run_wand_smoke_test(folder: Path, helper: Path, prefix_arg: str | None) -> None:
    patched, proof = verify_patch_files(folder, helper)
    for line in proof:
        print(line)
    if not patched:
        raise ValueError("Wand launch blocked: selected installation's patch files are not verified")
    if not prefix_arg:
        raise ValueError("Wand launch needs the selected existing Wine prefix (no new prefix created)")
    prefix = Path(prefix_arg).expanduser().resolve(strict=True)
    if not prefix.is_dir() or not (prefix / "drive_c").is_dir():
        raise ValueError("Wand launch requires a real, already-existing Wine prefix")
    # Only launch a known client EXE from the selected installation. Never
    # run Update.exe or create/repair/reconfigure a Proton compatibility tool.
    executable = next(
        (folder / name for name in ("Wand.exe", "WeMod.exe", "wand.exe", "wemod.exe")
         if (folder / name).is_file()), None
    )
    if executable is None:
        raise ValueError("No Wand.exe/WeMod.exe in selected app version; launch it via its existing launcher")
    import shutil as sh
    wine = sh.which("wine")
    if not wine:
        raise ValueError("Wine is not on PATH; no launcher was started")
    environment = os.environ.copy()
    environment["WINEPREFIX"] = str(prefix)
    # Upstream requires native version.dll before Wine built-in to avoid
    # Electron integrity rejection. This affects this ONE child only.
    environment["WINEDLLOVERRIDES"] = "version=n,b"
    child = subprocess.Popen(
        [wine, str(executable)], cwd=str(folder), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True
    )
    print(f"Wand Wine smoke-test launch requested (PID {child.pid}).", flush=True)
    print("Native-first DLL loading requested: version=n,b", flush=True)
    print("Client UI appeared / DLL loaded / login / trainer attach: NOT VERIFIED", flush=True)
    print("This Wine client test is separate from a game's Steam Proton session.", flush=True)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "install", "patch", "restore", "verify", "game-test", "launch-test"))
    parser.add_argument("--install-dir", help="Folder containing WeMod.exe and resources/app.asar")
    parser.add_argument("--confirm", action="store_true", help="Required for download/patch/restore")
    parser.add_argument("--game-provider", choices=("steam", "heroic", "lutris", "other"))
    parser.add_argument("--appid", default="")
    parser.add_argument("--game-name", default="")
    parser.add_argument("--game-dir", default="")
    parser.add_argument("--game-prefix", default="")
    parser.add_argument("--wine-prefix", default="")
    parser.add_argument("--runtime-hint", choices=("native", "windows-associated", "unknown"), default="unknown")
    args = parser.parse_args()
    candidates = available_clients(args.install_dir) if args.action != "install" else []
    folder = candidates[0] if len(candidates) == 1 else None
    if args.action == "status":
        print(f"Upstream: https://github.com/e-gleba/wemod_enhancer ({VERSION})")
        print("Wand/WeMod client: " + ("FOUND" if folder else "MULTIPLE FOUND (select an exact installation)" if len(candidates) > 1 else "NOT FOUND (select the app-version folder in Settings)"))
        print("WeMod Enhancer CLI: " + ("READY" if valid_patcher(installed_helper_dir()) else "NOT INSTALLED"))
        if folder:
            print("WeMod backup: " + ("AVAILABLE" if
                (folder / "resources/app.asar.backup").exists() else "NOT PRESENT"))
        print("Status is read-only; no WeMod files have been changed.")
        return 0
    if args.action in ("verify", "game-test"):
        if folder is None:
            raise ValueError("Choose exactly one existing Wand/WeMod app-version folder")
        healthy, result = verify_patch_files(folder, installed_helper_dir())
        for line in result:
            print(line)
        if args.action == "game-test":
            for line in check_selected_game(args, healthy):
                print(line)
        return 0 if healthy else 2
    if args.action in ("install", "patch", "restore", "launch-test") and not args.confirm:
        raise ValueError(f"'{args.action}' requires explicit --confirm")
    if args.action == "install":
        install_helper()
        return 0
    if folder is None:
        raise ValueError("No unique Wand/WeMod client selected. Choose the app-version folder with resources/app.asar; this is distinct from the Proton compatibility tool.")
    if args.action == "launch-test":
        run_wand_smoke_test(folder, installed_helper_dir(), args.wine_prefix)
        return 0
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
