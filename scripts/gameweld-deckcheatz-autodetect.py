#!/usr/bin/env python3
"""GameWeld experimental DeckCheatz/Proton auto discovery.

The safe first step is --dry-run: inspect Steam libraries, per-AppID prefix,
game executable candidates and a matching Proton tool WITHOUT launching or
writing Steam config. Never guess between ambiguous .exe or Proton options.

--launch is a separately consented experimental subprocess (NOT Steam's
official launch runtime, and NOT proof of SteamAPI/DRM/overlay).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
MAX_MANIFEST = 2 * 1024 * 1024
MAX_LIBRARY_VDF = 4 * 1024 * 1024
MAX_VERSION = 4096
MAX_SCAN_ENTRIES = 5000
MAX_EXE_CANDIDATES = 40


class DiscoveryBlocked(ValueError):
    pass


def import_script(filename: str, label: str):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(label, source)
    if not spec or not spec.loader:
        raise DiscoveryBlocked("Required GameWeld helper missing: " + filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vdf(path: Path, *, max_bytes=MAX_MANIFEST) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise DiscoveryBlocked("Missing, symlinked, or oversized Steam VDF: " + str(path))
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise DiscoveryBlocked("Oversized Steam VDF")
    try:
        parsed = import_script("gameweld-steam-launch-options-preserve.py",
                               "gw_auto_vdf")
        return parsed.parse_vdf(data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise DiscoveryBlocked("Steam VDF is not UTF-8") from exc


def only(node: dict, key: str):
    if not isinstance(node, dict):
        raise DiscoveryBlocked("Steam VDF has unexpected structure")
    matches = node.get(key.casefold(), [])
    if len(matches) > 1:
        raise DiscoveryBlocked("Ambiguous duplicate VDF key: " + key)
    return matches[0] if matches else None


def steam_root(explicit: Path | None = None, *, home: Path | None = None) -> Path:
    home = home or Path.home()
    candidates = ([explicit] if explicit is not None else [
        home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"
    ])
    found = set()
    for path in candidates:
        try:
            root = path.expanduser().resolve(strict=True)
        except OSError:
            continue
        if (root / "steamapps").is_dir() and (root / "userdata").is_dir():
            found.add(root)
    if not found:
        raise DiscoveryBlocked("Steam installation not found; set --steam-root")
    if len(found) != 1:
        raise DiscoveryBlocked("Several Steam roots found; set --steam-root explicitly")
    return found.pop()


def libraries(root: Path) -> list[Path]:
    sources = [root]
    path = root / "steamapps/libraryfolders.vdf"
    if path.is_file():
        root_vdf = vdf(path, max_bytes=MAX_LIBRARY_VDF)
        outer = only(root_vdf, "libraryfolders")
        if not isinstance(outer, dict):
            raise DiscoveryBlocked("Steam libraryfolders.vdf lacks a libraryfolders object")
        for key, values in outer.items():
            if not key.isdecimal() or len(values) != 1:
                continue
            item = values[0]
            raw = only(item, "path") if isinstance(item, dict) else item
            if isinstance(raw, str) and raw:
                sources.append(Path(raw))
    output = []
    for candidate in sources:
        try:
            folder = candidate.expanduser().resolve(strict=True)
        except OSError:
            continue
        if (folder / "steamapps").is_dir() and folder not in output:
            output.append(folder)
    return output


def find_install(root: Path, appid: str) -> tuple[Path, Path, Path]:
    matches = []
    for folder in libraries(root):
        steamapps = folder / "steamapps"
        manifest = steamapps / ("appmanifest_" + appid + ".acf")
        if not manifest.is_file() or manifest.is_symlink():
            continue
        body = only(vdf(manifest), "AppState")
        if not isinstance(body, dict):
            raise DiscoveryBlocked("Game appmanifest lacks AppState object")
        installed_id = only(body, "appid")
        name = only(body, "installdir")
        if installed_id != appid or not isinstance(name, str) or not name:
            raise DiscoveryBlocked("Game appmanifest ID or installdir is invalid")
        common = (steamapps / "common").resolve()
        install = (common / name).resolve()
        if not install.is_relative_to(common) or not install.is_dir():
            raise DiscoveryBlocked("Steam game install directory missing or escapes its library")
        compat = steamapps / "compatdata" / appid
        if compat.is_symlink() or not (compat / "pfx").is_dir():
            raise DiscoveryBlocked("This game's Proton prefix is missing; launch it normally once")
        matches.append((install, compat, manifest))
    if len(matches) == 0:
        raise DiscoveryBlocked("Steam game appmanifest not found across registered libraries")
    if len(matches) > 1:
        raise DiscoveryBlocked("Multiple libraries contain this AppID; resolve duplicate manifests")
    return matches[0]


def choose_exe(install: Path, selected: Path | None = None, *,
               ignore_game_exe_env: bool = False) -> Path:
    if selected is None and not ignore_game_exe_env:
        raw = os.environ.get("GAME_EXE")
        if raw:
            selected = Path(raw)
    if selected is not None:
        target = selected if selected.is_absolute() else install / selected
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(install):
            raise DiscoveryBlocked("Explicit game exe is missing or outside install")
        if target.suffix.casefold() != ".exe":
            raise DiscoveryBlocked("Explicit game binary must be a Windows .exe")
        return target
    candidates = []
    scanned = 0
    for path in install.rglob("*"):
        scanned += 1
        if scanned > MAX_SCAN_ENTRIES:
            raise DiscoveryBlocked("Game file scan exceeds limit; specify --game-exe")
        if len(path.relative_to(install).parts) > 6:
            continue
        if path.suffix.casefold() == ".exe" and path.is_file() and not path.is_symlink():
            candidates.append(path)
            if len(candidates) > MAX_EXE_CANDIDATES:
                raise DiscoveryBlocked("Many Windows executables found; specify --game-exe")
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise DiscoveryBlocked("No Windows game executable found; specify --game-exe")
    # Only pick if EXACTLY one executable clearly contains the distinctive
    # installed game name (after normalizing spaces/punctuation).
    normalized = re.sub(r"[^a-z0-9]", "", install.name.casefold())
    selected = [x for x in candidates
                if normalized and normalized in
                re.sub(r"[^a-z0-9]", "", x.stem.casefold())]
    if len(selected) == 1:
        return selected[0]
    # Some official executables insert "Game" and architecture suffixes
    # between the game's title words: e.g. DyingLightGame_TheBeast_x64_rwdi.exe.
    # Accept only a UNIQUE all-title-token match, not a fuzzy best guess.
    def words(value: str) -> list[str]:
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
        return re.findall(r"[a-z0-9]+", spaced.casefold())

    title_words = [x for x in words(install.name)
                   if x not in {"the", "a", "an", "of", "and", "edition", "definitive"}
                   and len(x) >= 3]
    if len(title_words) >= 2:
        strong = []
        for candidate in candidates:
            name_parts = words(candidate.stem)
            position = 0
            for token in title_words:
                try:
                    position = name_parts.index(token, position) + 1
                except ValueError:
                    break
            else:
                # Any second title-matched .exe is ambiguous, even if its name
                # says "Launcher". Never silently ignore that competing target.
                strong.append(candidate)
        if len(strong) == 1 and not set(words(strong[0].stem)) & {
                "launcher", "setup", "uninstall", "crashreporter",
                "settings", "redist"}:
            return strong[0]
    # A generic game might have separate launcher/tools/bootstrap exe files.
    # The first/x64 path is NEVER an acceptable automatic fallback.
    listed = "; ".join(str(x.relative_to(install)) for x in candidates[:15])
    raise DiscoveryBlocked("Ambiguous game executables: " + listed +
                           ". Pass --game-exe (or GAME_EXE).")


def resolve_exe_for_install(appid: str, install: Path) -> Path:
    """Read-only Steam manifest-backed executable resolution for GameWeld UI."""
    if not APPID.fullmatch(appid) or int(appid) >= 2**32:
        raise DiscoveryBlocked("Invalid Steam AppID")
    if (not install.is_dir() or install.is_symlink() or
            install.parent.name != "common" or
            install.parent.parent.name != "steamapps"):
        raise DiscoveryBlocked("Install directory must be a plain Steam common title")
    manifest = install.parent.parent / ("appmanifest_" + appid + ".acf")
    if manifest.is_symlink() or not manifest.is_file():
        raise DiscoveryBlocked("No matching Steam appmanifest")
    app_state = only(vdf(manifest), "AppState")
    if not isinstance(app_state, dict) or (only(app_state, "appid") != appid or
            only(app_state, "installdir") != install.name):
        raise DiscoveryBlocked("Steam appmanifest does not match selected title")
    return choose_exe(install, ignore_game_exe_env=True)


def proton_version(compat: Path) -> str:
    version = compat / "version"
    if (version.is_symlink() or not version.is_file() or
            version.stat().st_size > MAX_VERSION):
        raise DiscoveryBlocked("Steam Proton version record missing; specify --proton-dir")
    raw = version.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if len(raw) != 1 or not raw[0] or len(raw[0]) > 256:
        raise DiscoveryBlocked("Steam Proton version record is not a usable tool name")
    return raw[0]


def choose_proton(root: Path, compat: Path, folders: list[Path],
                  explicit: Path | None = None) -> tuple[Path, str]:
    if explicit is None:
        custom = os.environ.get("PROTON_DIR")
        if custom:
            explicit = Path(custom)
    if explicit is not None:
        selected = explicit.expanduser().resolve()
        proton = selected if selected.name == "proton" else selected / "proton"
        if not proton.is_file() or not os.access(proton, os.X_OK):
            raise DiscoveryBlocked("Explicit Proton directory lacks executable proton script")
        return proton, "EXPLICIT_OVERRIDE"
    version = proton_version(compat)
    candidates = []
    for folder in [root / "compatibilitytools.d",
                   *[lib / "steamapps/common" for lib in folders]]:
        if folder.is_dir():
            for tool in folder.iterdir():
                if tool.is_dir() and tool.name.casefold() == version.casefold():
                    proton = tool / "proton"
                    if proton.is_file() and os.access(proton, os.X_OK):
                        candidates.append(proton.resolve())
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise DiscoveryBlocked("Could not unambiguously match recorded Proton tool '" +
                               version + "' to a launcher; set --proton-dir")
    return candidates[0], version


def find_launcher(override: Path | None = None) -> Path:
    provider = import_script("gameweld-deckcheatz-direct.py", "gw_auto_provider")
    choices = [override] if override else provider.installed_candidates()
    valid = []
    for candidate in choices:
        if candidate is None:
            continue
        try:
            provider.inspect_launcher(candidate)
            if candidate not in valid:
                valid.append(candidate)
        except (OSError, ValueError):
            continue
    if len(valid) != 1:
        raise DiscoveryBlocked("Need one recognized DeckCheatz 1.x launcher; set --launcher")
    return valid[0]


def steam_running() -> bool:
    exe = shutil.which("pgrep")
    if not exe:
        return False
    result = subprocess.run([exe, "-x", "-u", str(os.getuid()), "steam"],
                            capture_output=True, check=False, timeout=5)
    return result.returncode == 0


def build(args) -> tuple[dict, list[str]]:
    if not APPID.fullmatch(args.appid) or int(args.appid) >= 2**32:
        raise DiscoveryBlocked("Numeric Steam AppID required")
    root = steam_root(args.steam_root)
    install, compat, manifest = find_install(root, args.appid)
    exe = choose_exe(install, args.game_exe)
    proton, tool = choose_proton(root, compat, libraries(root), args.proton_dir)
    launcher = find_launcher(args.launcher)
    provider = import_script("gameweld-deckcheatz-direct.py", "gw_direct_from_auto")
    flags = ["--appid", args.appid, "--launcher", str(launcher),
             "--proton", str(proton), "--game-exe", str(exe),
             "--install-dir", str(install), "--compatdata", str(compat),
             "--steam-root", str(root)]
    for arg in args.game_arg:
        flags.extend(["--game-arg", arg])
    provider_args = argparse.Namespace(
        appid=args.appid, launcher=launcher, proton=proton, game_exe=exe,
        install_dir=install, compatdata=compat, steam_root=root,
        game_arg=list(args.game_arg)
    )
    plan, unused_env = provider.build_plan(provider_args)
    running = steam_running()
    plan.update({
        "mode": "READ_ONLY_AUTO_DISCOVERY",
        "game_manifest": str(manifest),
        "detected_proton_version": tool,
        "steam_running_detected": running,
        "steam_launch_options_modified": False,
        "steam_runtime_container_reproduced": False,
        "steamapi_overlay_drm_verified": False,
        "auto_selected_exe": args.game_exe is None and not os.environ.get("GAME_EXE"),
        "auto_selected_proton": args.proton_dir is None and not os.environ.get("PROTON_DIR"),
        "safe_to_launch_claimed": False,
        "warning": ("Direct Proton bypasses Steam's runtime/container supervisor and "
                    "per-game launch options. Steam running alone does not prove "
                    "Steam API/overlay/DRM or trainer attachment will work."),
    })
    return plan, flags


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true",
                        help="Read-only resolved command and paths (default)")
    action.add_argument("--launch", action="store_true",
                        help="Experimental direct launch requiring two separate acknowledgements")
    action.add_argument("--resolve-game-exe", action="store_true",
                        help="Read-only manifest-backed EXE resolution for the selected game")
    parser.add_argument("--appid", required=True)
    parser.add_argument("--steam-root", type=Path)
    parser.add_argument("--game-exe", type=Path)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--proton-dir", type=Path)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--game-arg", action="append", default=[])
    parser.add_argument("--confirm-prefix-changes", action="store_true")
    parser.add_argument("--experimental-direct-launch", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.resolve_game_exe:
            if (args.install_dir is None or args.confirm_prefix_changes or
                    args.experimental_direct_launch or args.game_exe is not None):
                raise DiscoveryBlocked("EXE resolution requires --install-dir only; never launches")
            exe = resolve_exe_for_install(args.appid, args.install_dir)
            print(json.dumps({"status": "resolved", "selected": str(exe),
                              "method": "unique_manifest_backed_title_match",
                              "game_launched": False, "steam_options_modified": False}))
            return 0
        plan, flags = build(args)
        if not args.launch:
            if args.confirm_prefix_changes or args.experimental_direct_launch:
                raise DiscoveryBlocked("Dry-run cannot accept launch approvals")
            print(json.dumps(plan, indent=2))
            return 0
        if not (args.confirm_prefix_changes and args.experimental_direct_launch):
            raise DiscoveryBlocked("Real launch requires BOTH --confirm-prefix-changes "
                                   "and --experimental-direct-launch")
        if not plan["steam_running_detected"]:
            raise DiscoveryBlocked("Steam desktop client is not running")
        direct = import_script("gameweld-deckcheatz-direct.py", "gw_auto_launch")
        return direct.main(["--launch", *flags, "--confirm-prefix-changes",
                            "--experimental-direct-launch"])
    except (DiscoveryBlocked, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print("GameWeld DeckCheatz auto discovery BLOCKED: " + str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
