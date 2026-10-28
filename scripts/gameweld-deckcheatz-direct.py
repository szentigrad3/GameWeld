#!/usr/bin/env python3
"""GameWeld PC2: optional DeckCheatz 1.x without Steam Launch Options.

This is an independent, optional subprocess integration. No DeckCheatz source
is bundled. It can preview a direct Steam/Proton argv (read-only), and offers
a separately consented EXPERIMENTAL subprocess launch. No existing Steam
LaunchOptions are read or changed, and Steam configuration is never edited.

The upstream 1.x officially expects a Steam/Lutris command-prefix context.
We emulate the documented Steam Proton command vector, not the Steam client
launch supervisor itself. Some DRM/SteamAPI titles may require real Steam
handoff; a successful subprocess spawn is NOT proof of a game/trainer launch.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PROVIDER = "DeckCheatz/wemod-launcher"
APPID = re.compile(r"^[1-9][0-9]{0,9}$")
MAX_SCAN = 8192


class Blocked(ValueError):
    pass


def inspect_launcher(path: Path) -> dict:
    """Read-only fingerprint of a checkout selected by the user."""
    if not path.is_absolute():
        raise Blocked("Launcher path must be absolute")
    checkout = path.parent
    if not (checkout / "src/wemod.py").is_file():
        raise Blocked("DeckCheatz 1.x source layout absent (src/wemod.py)")
    source = checkout / "src/wemod.py"
    if not path.is_file() or path.name != "wemod":
        raise Blocked("Expected the repository's wemod launcher file")
    if not path.resolve().is_relative_to(checkout.resolve()):
        raise Blocked("Launcher resolves outside its checkout")
    if source.resolve() != path.resolve():
        raise Blocked("The wemod entrypoint is not the checked out src/wemod.py")
    readme = checkout / "README.md"
    license_file = checkout / "LICENSE"
    if not readme.is_file() or not license_file.is_file():
        raise Blocked("Upstream README or AGPL license missing; unknown checkout")
    readme_text = readme.read_text(encoding="utf-8", errors="replace")[:8000]
    license_text = license_file.read_text(encoding="utf-8", errors="replace")[:300]
    if "WeMod Launcher" not in readme_text or "AFFERO GENERAL PUBLIC LICENSE" not in license_text:
        raise Blocked("Not a recognized DeckCheatz 1.x checkout")
    return {
        "provider": PROVIDER,
        "path": str(path),
        "source_root": str(checkout),
        "identity": "DeckCheatz 1.x layout (not a cryptographic provenance guarantee)",
        "license": "AGPL-3.0",
        "no_source_bundled": True,
    }


def installed_candidates() -> list[Path]:
    home = Path.home()
    choices = []
    custom = os.environ.get("GAMEWELD_DECKCHEATZ_LAUNCHER", "")
    if custom:
        choices.append(Path(custom).expanduser())
    # Respect the freedesktop per-user data directory used by GameWeld's
    # managed installer, while preserving the historical default checkout.
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg and os.path.isabs(xdg):
        choices.append(Path(xdg) / "gameweld/deckcheatz/wemod")
    choices.extend((
        home / ".local/share/gameweld/deckcheatz/wemod",
        home / "wemod-launcher/wemod",
        home / "Games/wemod-launcher/wemod",
    ))
    return list(dict.fromkeys(choices))


def inspect_available() -> dict:
    candidates = []
    for path in installed_candidates():
        try:
            candidates.append(inspect_launcher(path))
        except (Blocked, OSError):
            continue
    return {
        "provider": PROVIDER,
        "mode": "read_only",
        "available_count": len(candidates),
        "checkouts": candidates,
        "message": ("Select an installed 1.x checkout and Steam game for a launch preview; "
                    "no Steam launch option edits are required."),
    }


def validate_paths(args) -> tuple[Path, Path, Path, Path, Path, Path]:
    if not args.appid or not APPID.fullmatch(args.appid):
        raise Blocked("A valid numeric Steam AppID is required")
    required = ("launcher", "proton", "game_exe", "install_dir", "compatdata", "steam_root")
    for field in required:
        if getattr(args, field) is None:
            raise Blocked("Missing explicit --" + field.replace("_", "-") +
                          "; game/proton executable paths are not guessed")
    launcher, proton, game, install, compat, steam = [
        getattr(args, x).expanduser().absolute() for x in required
    ]
    inspect_launcher(launcher)
    for obj, title in ((proton, "Proton launcher"), (game, "Game executable")):
        if not obj.is_file():
            raise Blocked(title + " missing: " + str(obj))
    if proton.name != "proton":
        raise Blocked("Selected Proton launcher must be named proton")
    if not os.access(proton, os.X_OK):
        raise Blocked("Selected Proton launcher is not executable")
    if game.suffix.lower() != ".exe":
        raise Blocked("Select the real Windows game .exe, not a shell/Steam wrapper")
    if not install.is_dir() or not game.resolve().is_relative_to(install.resolve()):
        raise Blocked("Game executable must be inside its explicit Steam install directory")
    # App manifest confirms the game ID belongs to this library.
    # Steam libraries have <library>/steamapps/common/<game>.
    steamapps = install.parent.parent
    if install.parent.name != "common" or steamapps.name != "steamapps":
        raise Blocked("Install directory must be under Steam library/steamapps/common/")
    if not (steamapps / ("appmanifest_" + args.appid + ".acf")).is_file():
        raise Blocked("Matching Steam appmanifest not found in selected library")
    if not compat.is_dir() or compat.name != args.appid or compat.parent.name != "compatdata":
        raise Blocked("Use the existing game-specific Steam compatdata/AppID directory")
    if not (compat / "pfx").is_dir():
        raise Blocked("Game prefix absent; start game normally once before opting in")
    if not steam.is_dir() or not (steam / "steamapps").is_dir():
        raise Blocked("STEAM_COMPAT_CLIENT_INSTALL_PATH must be a Steam root")
    return launcher, proton, game, install, compat, steam


def recognized_unreadable_host(process: Path) -> bool:
    """Use the same conservative non-Wine desktop exception as live handoff.

    Only exact names with inspected, non-WeMod cmdlines qualify. If either
    inspector is unavailable, fail closed rather than guessing.
    """
    directory = Path(__file__).resolve().parent
    live_path = directory / "gameweld-wemod-live-attach.py"
    names_path = directory / "gameweld-prefix-runtime-preflight.py"
    if (live_path.is_symlink() or names_path.is_symlink() or
            not live_path.is_file() or not names_path.is_file()):
        return False
    try:
        live_spec = importlib.util.spec_from_file_location("gw_direct_host_live", live_path)
        names_spec = importlib.util.spec_from_file_location("gw_direct_host_names", names_path)
        if not live_spec or not live_spec.loader or not names_spec or not names_spec.loader:
            return False
        live = importlib.util.module_from_spec(live_spec)
        names = importlib.util.module_from_spec(names_spec)
        live_spec.loader.exec_module(live)
        names_spec.loader.exec_module(names)
        return live.known_non_wine_host_with_unreadable_env(process, names)
    except (OSError, ValueError, ImportError, AttributeError):
        return False


def active_game_process(appid: str, proc_root: Path = Path("/proc")) -> bool:
    """Fail closed if a same-user process is already tagged for this AppID."""
    count = 0
    for item in proc_root.iterdir():
        if not item.name.isdigit():
            continue
        count += 1
        if count > MAX_SCAN:
            raise Blocked("Process count exceeds scan limit; refusing double game launch")
        try:
            if item.stat().st_uid != os.getuid():
                continue
            # /proc/.../environ may reveal unrelated secrets; never log it.
            with (item / "environ").open("rb") as inp:
                env = inp.read(128 * 1024 + 1)
            if len(env) > 128 * 1024:
                raise Blocked("Process environment exceeds safe inspection limit")
            if any(key + appid.encode() in env.split(b"\x00") for key in
                   (b"SteamAppId=", b"SteamGameId=", b"STEAM_COMPAT_APP_ID=")):
                return True
        except FileNotFoundError:
            # A process can exit during scanning; a vanished PID is harmless.
            continue
        except OSError as exc:
            # Some desktop services and Steam overlay UI processes expose
            # their names but not their environments on KDE/CachyOS. Only the
            # narrowly recognized host tasks may be skipped. Any Wine/Proton,
            # WeMod or unknown inaccessible task still blocks direct launch.
            if recognized_unreadable_host(item):
                continue
            raise Blocked("Cannot verify whether a game process is active") from exc
    return False


def build_plan(args) -> tuple[dict, dict[str, str]]:
    launcher, proton, game, install, compat, steam = validate_paths(args)
    argv = [sys.executable, str(launcher), str(proton),
            "waitforexitandrun", str(game), *args.game_arg]
    overrides = {
        "STEAM_COMPAT_DATA_PATH": str(compat),
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam),
        "STEAM_COMPAT_INSTALL_PATH": str(install),
        "STEAM_COMPAT_TOOL_PATHS": str(proton.parent),
        "SteamAppId": args.appid,
        "SteamGameId": args.appid,
        "SteamOverlayGameId": args.appid,
        "STEAM_COMPAT_APP_ID": args.appid,
        "WINEDLLOVERRIDES": "version=n,b",
        "WEMOD_LOG": str(launcher.parent / "wemod.log"),
        "SELF_UPDATE": "False",
        "PACKAGEPREFIX": "false",
        "TROUBLESHOOT": "False",
    }
    options_source = Path(__file__).resolve().with_name("gameweld-deckcheatz-session-options.py")
    if options_source.is_symlink() or not options_source.is_file():
        raise Blocked("DeckCheatz custom launch-option composer unavailable")
    spec = importlib.util.spec_from_file_location("gw_dc_custom_opts", options_source)
    if not spec or not spec.loader:
        raise Blocked("Cannot import custom launch-option composer")
    options = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(options)
    try:
        argv, overrides, option_report = options.compose(
            getattr(args, "steam_launch_options", "") or "", argv, overrides)
    except options.OptionBlocked as exc:
        raise Blocked(str(exc)) from exc
    return {
        "provider": PROVIDER,
        "mode": "experimental_direct_no_steam_options",
        "readiness": "preview_only_unverified",
        "appid": args.appid,
        "launcher": str(launcher),
        "proton": str(proton),
        "game_exe": str(game),
        "compatdata": str(compat),
        "game_working_directory": str(game.parent),
        "argv": argv,
        "env_overrides": overrides,
        "steam_custom_launch_composition": option_report,
        "current_steam_options_user_verified": bool(getattr(args, "steam_options_verified", False)),
        "steam_launch_options_modified": False,
        "will_invoke_steam_client": False,
        "steam_runtime_container_reproduced": False,
        "steam_api_overlay_drm_verified": False,
        "steam_launch_options_applied": False,
        "prefix_can_be_modified_by_upstream_launcher": True,
        "warning": ("Experimental! Upstream DeckCheatz 1.x is intended as a Steam/Lutris command prefix. "
                    "Direct execution may not initialize SteamAPI or supported games correctly. "
                    "Never run alongside an already-active Steam game session."),
    }, overrides


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    p = parser.add_mutually_exclusive_group()
    p.add_argument("--discover", action="store_true", help="read-only installed-checkout detection")
    p.add_argument("--preview", action="store_true", help="read-only exact argv + prefix plan")
    p.add_argument("--launch", action="store_true", help="opt-in EXPERIMENTAL direct subprocess launch")
    parser.add_argument("--appid")
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--proton", type=Path)
    parser.add_argument("--game-exe", type=Path)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--compatdata", type=Path)
    parser.add_argument("--steam-root", type=Path)
    parser.add_argument("--game-arg", action="append", default=[])
    parser.add_argument("--steam-launch-options", default="",
                        help="Exact CURRENT Steam Properties text; supported shell-free subset")
    parser.add_argument("--steam-options-verified", action="store_true",
                        help="User confirmed the selected game's current Steam Properties text")
    parser.add_argument("--confirm-prefix-changes", action="store_true")
    parser.add_argument("--experimental-direct-launch", action="store_true")
    args = parser.parse_args(argv)

    if args.discover or not (args.preview or args.launch):
        if args.confirm_prefix_changes or args.experimental_direct_launch:
            raise Blocked("Read-only discovery rejects opt-in launch flags")
        print(json.dumps(inspect_available(), indent=2))
        return 0

    plan, overrides = build_plan(args)
    if args.preview:
        if args.confirm_prefix_changes or args.experimental_direct_launch:
            raise Blocked("Read-only preview rejects all launch confirmation flags")
        print(json.dumps(plan, indent=2))
        return 0

    if not args.steam_options_verified:
        raise Blocked("Direct launch requires confirmation of CURRENT Steam Launch Options")
    if not (args.confirm_prefix_changes and args.experimental_direct_launch):
        raise Blocked("Direct launch requires BOTH --confirm-prefix-changes and "
                      "--experimental-direct-launch; preview before consenting")
    if active_game_process(args.appid):
        raise Blocked("This Steam AppID already has an active process. "
                      "Refusing to launch a duplicate game in the same Proton prefix.")
    env = os.environ.copy()
    env.update(overrides)
    # Never use shell=True or try to change Steam's game LaunchOptions.
    print("GameWeld direct provider: starting opted-in external DeckCheatz 1.x process.")
    print("Neither Steam launch options nor the GameWeld managed Wand runtime are modified.")
    print("Upstream may mutate its selected Wine prefix or download trainer components.")
    return subprocess.run(
        plan["argv"], cwd=plan["game_working_directory"], env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError) as exc:
        print("GameWeld DeckCheatz direct BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
