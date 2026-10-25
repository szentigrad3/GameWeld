#!/usr/bin/env python3
"""GameWeld PC2 launcher for e-gleba/wemod_enhancer's upstream CLI.

All WeMod file edits are delegated to the upstream patch/restore commands
after an explicit GameWeld confirmation. This adapter only installs the
pinned upstream artifact into a private per-user directory and launches it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
        home / ".local/share/gameweld/deckcheatz/wemod_data/wemod_bin",
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


def verify_legacy_baseline(folder: Path) -> None:
    """Only allow the deliberately isolated, hash-pinned official 11.6.0.

    Never bypass Enhancer validation for an arbitrary Windows executable.
    This is a renderer-only comparison and never patches or installs .NET.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and not Path(xdg).is_absolute():
        raise ValueError("XDG_DATA_HOME must be absolute")
    base = Path(xdg) if xdg else Path.home() / ".local/share"
    expected = base / "gameweld/wemod-compat/11.6.0"
    if folder.resolve() != expected.resolve():
        raise ValueError("Legacy baseline is limited to GameWeld's isolated 11.6.0 directory")
    marker = folder / ".gameweld-baseline.json"
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Missing verified compatibility-build manifest; use gameweld-wemod-compat.py")
    try:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Legacy baseline manifest is unreadable") from exc
    if (metadata.get("tool") != "gameweld-isolated-wemod-baseline"
            or metadata.get("version") != "11.6.0"
            or metadata.get("package_sha256") != "5b94ae5592e698b13cbc06fae4c096fe2438cbd362daac3f842e13190bf836ba"):
        raise ValueError("Legacy baseline manifest does not match pinned official package")
    for relpath, key in (("WeMod.exe", "exe_sha256"),
                         ("resources/app.asar", "asar_sha256")):
        target = folder / relpath
        if target.is_symlink() or sha256_file(target) != metadata.get(key):
            raise ValueError(f"Legacy baseline file hash mismatch: {relpath}")
    if (folder / "version.dll").exists():
        raise ValueError("Legacy baseline is patched or contains version.dll; refusing comparison")


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


def resolve_read_only_client(candidates: list[Path], helper: Path) -> tuple[Path | None, str]:
    """Select an unambiguous client for inspection or confirmed live launch.

    Auto-inference is ONLY for verify, game-test, and an explicitly confirmed
    live-launch. Patch and Restore remain strictly selection-only. Inference
    requires original ASAR backup plus exactly matching pinned DLL proxy.
    """
    if len(candidates) == 1:
        return candidates[0], "one existing client installation"
    if not candidates:
        return None, "no existing Wand/WeMod client detected"
    if not valid_patcher(helper):
        return None, "multiple client installations and upstream patch reference unavailable"
    verified = []
    for candidate in candidates[:200]:
        # Cheap prefilter before hashing potentially large ASAR files.
        if not (candidate / "resources/app.asar.backup").is_file():
            continue
        if not (candidate / "version.dll").is_file():
            continue
        if verify_patch_files(candidate, helper)[0]:
            verified.append(candidate)
            if len(verified) > 1:
                break
    if len(verified) == 1:
        return verified[0], "only client with matching, verified Enhancer patch files"
    if len(verified) > 1:
        return None, "more than one patched Wand/WeMod client; manual selection required"
    return None, "multiple clients, none uniquely verified as patched; select one manually"


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


# PC2 Test 16: one-click live Steam/Proton Wand handoff. This deliberately
# requests a client launch, NOT a trainer attach or entitlement verification.
# Read live same-user /proc evidence; never infer a Proton prefix from the
# installed game's path or select a Proton build from an unrelated Steam game.
def live_steam_proton_session(appid: str, proc_root: Path = Path("/proc")) -> dict[str, object]:
    validate_appid(appid)
    matching = []
    examined = 0
    try:
        entries = os.scandir(proc_root)
    except OSError as exc:
        raise ValueError("Unable to inspect running Steam processes") from exc
    with entries:
        for entry in entries:
            if not entry.name.isascii() or not entry.name.isdecimal():
                continue
            examined += 1
            if examined > 8192:
                break
            proc = Path(entry.path)
            try:
                if proc.stat().st_uid != os.getuid():
                    continue
                raw = (proc / "environ").open("rb")
                with raw:
                    data = raw.read(262145)
                if len(data) > 262144:
                    continue
                env: dict[str, str] = {}
                for token in data.split(b"\0"):
                    if b"=" not in token:
                        continue
                    key, value = token.split(b"=", 1)
                    if key in (b"SteamAppId", b"SteamGameId", b"STEAM_COMPAT_APP_ID",
                               b"STEAM_COMPAT_DATA_PATH", b"STEAM_COMPAT_TOOL_PATHS",
                               b"STEAM_COMPAT_CLIENT_INSTALL_PATH"):
                        env[key.decode("ascii")] = value.decode("utf-8", "replace")
                if not any(env.get(key) == appid for key in (
                        "SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")):
                    continue
                compat = env.get("STEAM_COMPAT_DATA_PATH", "")
                if not compat or not Path(compat).is_absolute():
                    continue
                prefix = Path(compat).resolve(strict=True)
                if not prefix.is_dir() or not (prefix / "pfx" / "drive_c").is_dir():
                    continue
                comm = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip().lower()
                # Windows .exe process evidence, not just a Steam helper, is
                # required; even this is not proof of trainer compatibility.
                excluded = {
                    "services.exe", "explorer.exe", "wineserver", "wineboot.exe",
                    "svchost.exe", "rpcss.exe", "plugplay.exe",
                    "steam.exe", "crashpad.exe", "crashreport.exe",
                    "wand.exe", "wemod.exe", "update.exe",
                }
                game_candidate = comm.endswith(".exe") and comm not in excluded
                tool = None
                for tool_dir in env.get("STEAM_COMPAT_TOOL_PATHS", "").split(":")[:16]:
                    if not tool_dir or not Path(tool_dir).is_absolute():
                        continue
                    p = Path(tool_dir)
                    p = p if p.name == "proton" else p / "proton"
                    try:
                        if p.is_file() and os.access(p, os.X_OK):
                            tool = p.resolve(strict=True)
                            break
                    except (OSError, ValueError):
                        continue
                steamroot = env.get("STEAM_COMPAT_CLIENT_INSTALL_PATH", "")
                matching.append((int(entry.name), prefix, game_candidate, tool, steamroot, env.get("STEAM_COMPAT_TOOL_PATHS", "")))
            except (OSError, UnicodeError, ValueError):
                continue
    if not matching:
        raise ValueError("No same-user live Proton session found for the selected Steam App ID; start the game first")
    prefixes = {str(row[1]) for row in matching}
    if len(prefixes) != 1:
        raise ValueError("Multiple live Proton prefixes claim this Steam App ID; refusing ambiguous handoff")
    candidates = [row for row in matching if row[2]]
    if not candidates:
        raise ValueError("Only Steam helpers were found; a Windows .exe game process is not yet observed")
    tools = {str(row[3]) for row in matching if row[3] is not None}
    if len(tools) != 1:
        raise ValueError("Cannot identify ONE exact Proton executable from the live game's environment")
    roots = {row[4] for row in matching if row[4]}
    live_tools = {row[5] for row in matching if row[5]}
    if len(live_tools) != 1:
        raise ValueError("Conflicting live Steam runtime tool environment; refusing handoff")
    if len(roots) != 1 or not Path(next(iter(roots))).is_dir():
        raise ValueError("Cannot identify the live Steam client root; no Wand handoff attempted")
    result: dict[str, object] = {
        "compat": candidates[0][1],
        "game_pid": candidates[0][0],
        "proton": Path(next(iter(tools))),
        "steamroot": Path(next(iter(roots))),
        "tool_paths": next(iter(live_tools)),
        "process_count": len(matching),
    }
    return result


def live_steam_container_launch_client(session: dict, appid: str) -> Path:
    """Require a pre-existing per-game D-Bus launcher, never create another game container.

    A fresh _v2-entry-point creates its own container; it is NOT guaranteed to
    share the running game's Wine server. Refuse that misleading fallback.
    """
    validate_appid(appid)
    manifest = Path(session["proton"]).parent / "toolmanifest.vdf"
    if not manifest.is_file():
        raise ValueError("Exact Proton runtime toolmanifest.vdf missing")
    text = re.sub(r"//[^\n]*", "", manifest.read_text(encoding="utf-8", errors="replace"))
    match = re.search(r'"require_tool_appid"\s+"(\d+)"', text)
    runtimes = {
        "4183110": "SteamLinuxRuntime_4",
        "1628350": "SteamLinuxRuntime_sniper",
        "1391110": "SteamLinuxRuntime_soldier",
    }
    name = runtimes.get(match.group(1)) if match else None
    if not name:
        raise ValueError("Unsupported or unverified live Proton container runtime")
    client = (Path(session["steamroot"]) / "steamapps/common" / name /
              "pressure-vessel/bin/steam-runtime-launch-client")
    if not client.is_file() or not os.access(client, os.X_OK):
        raise ValueError("The selected game's Steam runtime launch-client is missing")
    gdbus = shutil.which("gdbus")
    if not gdbus:
        raise ValueError("Cannot verify existing game container launcher: gdbus not installed")
    try:
        probe = subprocess.run([
            gdbus, "call", "--session", "--dest", "org.freedesktop.DBus",
            "--object-path", "/org/freedesktop/DBus",
            "--method", "org.freedesktop.DBus.NameHasOwner",
            "com.steampowered.App" + appid,
        ], text=True, capture_output=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Cannot verify the running game's D-Bus launcher service") from exc
    if probe.returncode != 0 or probe.stdout.strip().lower() != "(true,)":
        raise ValueError(
            "No active per-game Steam container launcher service; refusing a second "
            "container or host-Wine fallback. GameWeld did not modify Steam launch options."
        )
    return client


def launch_wand_in_live_game(folder: Path, helper: Path,
                             appid: str, game_dir: str,
                             proc_root: Path = Path("/proc"),
                             *, software_render: bool = False,
                             in_process_gpu: bool = False,
                             trace_dll_load: bool = False,
                             legacy_baseline: bool = False,
                             join_steam_container: bool = False) -> None:
    """Opt-in external client launch using the running game's exact Proton.

    Never runs a random Wine binary against an active Steam Proton prefix.
    Does not install or patch Wand, change Steam settings, or attach a trainer.
    """
    validate_appid(appid)
    if in_process_gpu and not software_render:
        raise ValueError("--in-process-gpu requires --software-render")
    if not game_dir or not Path(game_dir).is_dir():
        raise ValueError("The selected Steam game installation directory is not verified")
    if legacy_baseline:
        verify_legacy_baseline(folder)
        print("Verified official WeMod 11.6.0 BASELINE: unpatched, renderer-only comparison", flush=True)
        print("No Enhancer proxy is used and no .NET installer is run.", flush=True)
    else:
        patched, report = verify_patch_files(folder, helper)
        for line in report:
            print(line, flush=True)
        if not patched:
            raise ValueError("Live launch blocked: the chosen Wand app-version patch is not verified")
    executable = next((folder / name for name in
                      ("Wand.exe", "WeMod.exe", "wand.exe", "wemod.exe")
                      if (folder / name).is_file() and not (folder / name).is_symlink()), None)
    if executable is None:
        raise ValueError(
            "Selected app-version contains patch files but no direct Wand.exe/WeMod.exe; "
            "use its existing launcher. No Steam/Proton settings were changed."
        )
    session = live_steam_proton_session(appid, proc_root)
    print("Exact Steam App ID association: FOUND", flush=True)
    print("Windows executable candidate: OBSERVED (not authenticated)", flush=True)
    print("Live Proton executable: FOUND", flush=True)
    print("Live Proton prefix: FOUND (shared with running game)", flush=True)
    # A request is allowed only while the observed Windows process still exists.
    if not (proc_root / str(session["game_pid"])).is_dir():
        raise ValueError("The observed game process exited before Wand could start")
    environment = os.environ.copy()
    environment.pop("WINEPREFIX", None)  # Proton owns the exact game prefix.
    environment["STEAM_COMPAT_TOOL_PATHS"] = str(session["tool_paths"])
    environment["STEAM_COMPAT_DATA_PATH"] = str(session["compat"])
    environment["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(session["steamroot"])
    environment["SteamAppId"] = appid
    environment["SteamGameId"] = appid
    environment["STEAM_COMPAT_APP_ID"] = appid
    # Both rendering modes join the live game's Wine server. The old software
    # fallback launched a second Proton bootstrap and introduced another
    # failure path on CachyOS.
    # Port of crates/wand-runtime's historic active-Wineserver join.
    # A second 'proton runinprefix' introduced a new Proton bootstrap and
    # previously caused Wand startup/window failures on CachyOS. Run Wine
    # from the game's OWN selected Proton tool and join its active server.
    proton_root = Path(session["proton"]).parent
    # Mirror crates/wand-runtime::proton_wine_binary / wineserver_binary.
    wine = next((p for p in (
        proton_root / "files/bin/wine",
        proton_root / "files/bin/wine64",
        proton_root / "files/lib/wine/x86_64-unix/wine",
    ) if p.is_file() and os.access(p, os.X_OK)), None)
    wine_server = next((p for p in (
        proton_root / "files/bin/wineserver",
        proton_root / "files/lib/wine/x86_64-unix/wineserver",
    ) if p.is_file() and os.access(p, os.X_OK)), None)
    if wine is None:
        raise ValueError("Live Proton tool exposes no executable Wine binary (files/bin/wine or old equivalents); X11 join blocked")
    if wine_server is None:
        raise ValueError("Live Proton tool exposes no executable wineserver binary; X11 join blocked")
    if not environment.get("DISPLAY"):
        raise ValueError("An X11/XWayland DISPLAY is required for the proven Wand X11 launch; none found")

    # Recover only relevant environment from the EXACT observed live game
    # candidate, not Steam's global or another game's Proton session.
    pid_env = proc_root / str(session["game_pid"]) / "environ"
    try:
        with pid_env.open("rb") as handle:
            raw_env = handle.read(262145)
        if len(raw_env) > 262144:
            raise ValueError("Live game environment too large for safe join")
        keep = {
            "WINEPREFIX", "WINELOADER", "WINESERVER", "WINEDEBUG",
            "WINEDLLOVERRIDES", "WINEESYNC", "WINEFSYNC", "WINEARCH",
            "WINE_DISABLE_VULKAN_OPWR", "LD_LIBRARY_PATH",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH", "STEAM_COMPAT_DATA_PATH",
            "STEAM_COMPAT_APP_ID", "STEAM_COMPAT_INSTALL_PATH",
            "STEAM_COMPAT_LIBRARY_PATHS", "SteamAppId", "SteamGameId",
        }
        for token in raw_env.split(b"\0"):
            if b"=" not in token:
                continue
            key, value = token.split(b"=", 1)
            try:
                name = key.decode("ascii")
                val = value.decode("utf-8")
            except (UnicodeError, ValueError):
                continue
            if name in keep or name.startswith(("PROTON_", "DXVK_", "VKD3D_")):
                if name not in {"PROTON_USE_X11_EXCLUSIVE", "WAND_ELECTRON_RENDERER",
                                "WAND_WINDOW_BACKEND"}:
                    environment[name] = val
    except OSError as exc:
        raise ValueError("Cannot recover exact game's live Wine environment") from exc

    environment["WINEPREFIX"] = str(Path(session["compat"]) / "pfx")
    environment["WINELOADER"] = str(wine)
    environment["WINESERVER"] = str(wine_server)
    environment["STEAM_COMPAT_TOOL_PATHS"] = str(session["tool_paths"])
    environment["STEAM_COMPAT_DATA_PATH"] = str(session["compat"])
    environment["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(session["steamroot"])
    environment["SteamAppId"] = appid
    environment["SteamGameId"] = appid
    environment["STEAM_COMPAT_APP_ID"] = appid
    # Preserve other inherited DLL overrides for this WeMod child, while
    # forcing the patched version.dll native-first. The game stays untouched.
    overrides = [part for part in environment.get("WINEDLLOVERRIDES", "").split(";")
                 if part.strip() and part.split("=", 1)[0].strip().lower() != "version"]
    environment["WINEDLLOVERRIDES"] = (";".join(overrides) if legacy_baseline
                                        else ";".join(overrides + ["version=n,b"]))
    if trace_dll_load:
        # Diagnostic only: trace DLL selection for THIS WeMod child, never
        # enable Wine tracing on the live game or modify the shared prefix.
        environment["WINEDEBUG"] = "-all,+loaddll"
    environment["WINE_GRAPHICS_DRIVER"] = "x11"
    environment["PROTON_USE_X11_EXCLUSIVE"] = executable.name
    environment.pop("MANGOHUD", None)
    environment.pop("LD_PRELOAD", None)
    command = [str(wine), str(executable)]
    if software_render:
        # These Electron flags affect only the WeMod child and do not prove
        # window rendering or trainer attachment.
        command.extend(("--disable-gpu", "--disable-gpu-compositing",
                        "--enable-logging=stderr"))
    if in_process_gpu:
        # Electron can still spawn a GPU child under --disable-gpu. This
        # opt-in Chromium diagnostic keeps it in-process instead, at the cost
        # of reduced GPU-process isolation; never enable for the game.
        command.append("--in-process-gpu")
    launch_mode = "direct active Proton wineserver join + Wand-only X11"
    if join_steam_container:
        client = live_steam_container_launch_client(session, appid)
        # The per-game Steam launcher provides the game's own mount namespace
        # and runtime libraries. /usr/bin/env applies our WeMod-only overrides
        # inside that container without changing the game's process env.
        inner_env = [
            "WINEPREFIX=" + str(Path(session["compat"]) / "pfx"),
            "WINELOADER=" + str(wine),
            "WINESERVER=" + str(wine_server),
            "WINEDLLOVERRIDES=" + environment["WINEDLLOVERRIDES"],
            "WINE_GRAPHICS_DRIVER=x11",
        ]
        if trace_dll_load:
            inner_env.append("WINEDEBUG=-all,+loaddll")
        command = [
            str(client), "--bus-name=com.steampowered.App" + appid,
            "--directory=" + str(folder), "--",
            "/usr/bin/env", *inner_env, *command,
        ]
        launch_mode = "existing Steam per-game container service + Wand-only X11"
    if software_render:
        launch_mode += " (software rendering requested)"
    if in_process_gpu:
        launch_mode += " (in-process GPU experiment)"
    if trace_dll_load:
        launch_mode += " (DLL load trace)"
    if legacy_baseline:
        launch_mode += " (official unpatched 11.6.0 baseline)"
    # Capture only the explicitly confirmed client session. Do not change
    # Steam's launch options, Wine registry, caches, or existing game prefixes.
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home and not Path(state_home).is_absolute():
        raise ValueError("XDG_STATE_HOME must be an absolute path")
    state = (Path(state_home) if state_home else Path.home() / ".local/state") / "gameweld"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A previous WeMod child may keep writing to its log after our launcher
    # returns. NEVER truncate a reused filename: its old open descriptor may
    # append beyond the new EOF and fill the file with NUL holes, mixing logs
    # and creating misleading crash counts. Isolate every live handoff.
    import time
    log = state / ("wand-live-" + appid + "-" + str(os.getpid()) + "-"
                   + str(time.time_ns()) + ".log")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(
                ("GameWeld PC2 Wand live handoff: App ID " + appid + "\n"
                 + "Mode: direct X11 wineserver join" + (" + software rendering requested" if software_render else "") + "\n"
                 + "Client executable: " + str(executable) + "\n"
                 + "Legacy unpatched client baseline: " + str(legacy_baseline) + "\n"
                 + "In-process GPU experiment: " + str(in_process_gpu) + "\n"
                 + "WeMod-only DLL load trace: " + str(trace_dll_load) + "\n"
                 + "Steam game container join: " + str(join_steam_container) + "\n"
                 + "Renderer and login status: NOT VERIFIED\n"
                 + "==== Proton/Wand child output ====\n").encode("utf-8"))
            stream.flush()
            child = subprocess.Popen(
                command, cwd=str(folder), env=environment,
                stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True
            )
    except OSError as exc:
        raise RuntimeError(
            "Could not start the verified Proton/Wand child: " + type(exc).__name__
        ) from exc
    print("Wand startup mode: " + launch_mode, flush=True)
    print("Wand startup diagnostic log: " + str(log), flush=True)
    print("Wand launch child PID: " + str(child.pid), flush=True)
    # A Proton launcher can exit after handing off to another process; exit 0
    # still does not attest to a visible Wand window or trainer attachment.
    import time
    time.sleep(1)
    code = child.poll()
    if code is not None and code != 0:
        raise RuntimeError(f"Live Proton handoff command exited with status {code}")
    print("Live Wand verified runtime handoff: SENT (window contents not verified)", flush=True)
    print("Same running-game Proton/prefix used; no Steam launch options modified.", flush=True)
    print("Wand window, version.dll actual load, login and game trainer attachment: NOT VERIFIED", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "install", "patch", "restore", "verify", "game-test", "launch-test", "live-launch"))
    parser.add_argument("--install-dir", help="Folder containing WeMod.exe and resources/app.asar")
    parser.add_argument("--confirm", action="store_true", help="Required for install/patch/restore and launch actions")
    parser.add_argument("--software-render", action="store_true", help="Retry live Wand with Electron GPU acceleration disabled")
    parser.add_argument("--in-process-gpu", action="store_true",
                        help="EXPERIMENTAL: keep Chromium GPU work in WeMod's main process (requires --software-render)")
    parser.add_argument("--trace-dll-load", action="store_true",
                        help="Trace Wine DLL loading for this confirmed WeMod launch only")
    parser.add_argument("--legacy-baseline", action="store_true",
                        help="EXPERIMENTAL: compare the separately staged, verified official unpatched WeMod 11.6.0")
    parser.add_argument("--join-steam-container", action="store_true",
                        help="EXPERIMENTAL: use an existing per-game Steam container launcher; never change launch options")
    parser.add_argument("--game-provider", choices=("steam", "heroic", "lutris", "other"))
    parser.add_argument("--appid", default="")
    parser.add_argument("--game-name", default="")
    parser.add_argument("--game-dir", default="")
    parser.add_argument("--game-prefix", default="")
    parser.add_argument("--wine-prefix", default="")
    parser.add_argument("--runtime-hint", choices=("native", "windows-associated", "unknown"), default="unknown")
    args = parser.parse_args()
    if args.software_render and args.action != "live-launch":
        raise ValueError("--software-render is only supported for a confirmed live Wand launch")
    if (args.in_process_gpu or args.trace_dll_load) and args.action != "live-launch":
        raise ValueError("GPU and DLL trace options require a confirmed live Wand launch")
    if args.in_process_gpu and not args.software_render:
        raise ValueError("--in-process-gpu requires --software-render")
    if args.legacy_baseline and args.action != "live-launch":
        raise ValueError("--legacy-baseline only supports confirmed live-launch")
    if args.join_steam_container and args.action != "live-launch":
        raise ValueError("--join-steam-container only supports confirmed live-launch")
    if args.legacy_baseline and not args.install_dir:
        raise ValueError("--legacy-baseline requires an explicit --install-dir")
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
        folder, reason = resolve_read_only_client(candidates, installed_helper_dir())
        if folder is None:
            raise ValueError(
                "Cannot identify the patched client: " + reason +
                ". Open Settings → WeMod Enhancer, select the correct app-version, then retry."
            )
        print("Selected Wand client: " + folder.name + " (" + reason + ")")
        healthy, result = verify_patch_files(folder, installed_helper_dir())
        for line in result:
            print(line)
        if args.action == "game-test":
            for line in check_selected_game(args, healthy):
                print(line)
        return 0 if healthy else 2
    if args.action in ("install", "patch", "restore", "launch-test", "live-launch") and not args.confirm:
        raise ValueError(f"'{args.action}' requires explicit --confirm")
    if args.action == "install":
        install_helper()
        return 0
    if args.action == "live-launch":
        if args.legacy_baseline:
            # Clean renderer-only baseline is explicitly chosen and verified
            # by the pinned archive manifest, NOT by an Enhancer patch.
            folder = client_root(Path(args.install_dir))
            if folder is None:
                raise ValueError("Verified 11.6.0 baseline client directory not found")
            verify_legacy_baseline(folder)
            print("Selected Wand client: unpatched 11.6.0 baseline", flush=True)
        else:
            # Normal launches continue to require the uniquely patched client.
            folder, reason = resolve_read_only_client(candidates, installed_helper_dir())
            if folder is None:
                raise ValueError(
                    "Live Wand launch blocked: " + reason +
                    ". Choose the exact patched app-version in Settings."
                )
            print("Selected Wand client: " + folder.name + " (" + reason + ")", flush=True)
        print("Selected Wand installation: " + str(folder), flush=True)
    if folder is None:
        raise ValueError("No unique Wand/WeMod client selected. Choose the app-version folder with resources/app.asar; this is distinct from the Proton compatibility tool.")
    if args.action == "launch-test":
        run_wand_smoke_test(folder, installed_helper_dir(), args.wine_prefix)
        return 0
    if args.action == "live-launch":
        if args.game_provider != "steam":
            raise ValueError("Live Wand handoff is limited to a selected standard Steam game")
        launch_wand_in_live_game(folder, installed_helper_dir(),
                                 args.appid, args.game_dir,
                                 **({**({"software_render": True} if args.software_render else {}),
                                     **({"in_process_gpu": True} if args.in_process_gpu else {}),
                                     **({"trace_dll_load": True} if args.trace_dll_load else {}),
                                     **({"legacy_baseline": True} if args.legacy_baseline else {}),
                                     **({"join_steam_container": True} if args.join_steam_container else {})}))
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
