#!/usr/bin/env python3
"""Steam-owned GameWeld + WeMod launch experiment (without Steam option edits).

One user click requests Steam to launch its own game, verifies the real Windows
game task in its exact Steam AppID/prefix, then joins the existing Proton Wine
server to start an installed WeMod binary without a second Proton bootstrap. This does not use the
DeckCheatz 1.x direct game-executable launch vector and cannot claim trainer
attachment merely because WeMod started.

Never copies a prefix, silently installs binaries, patches Steam, or changes
Steam Launch Options. First-time external provider installation remains
separately consented through GameWeld.
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
import time

STEAM_APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
GAME_TIMEOUT = 90
POLL_SECONDS = 0.75


def load_observer():
    here = Path(__file__).with_name("gameweld-platform-session.py")
    spec = importlib.util.spec_from_file_location("gw_pc2_platform_session", here)
    if spec is None or spec.loader is None:
        raise RuntimeError("GameWeld session observer unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installed_wemod(launcher: Path, compatdata: Path) -> Path | None:
    """Only use a known installed WeMod executable; never select a game EXE."""
    checkout = launcher.parent
    choices = [
        checkout / "wemod_data" / "wemod_bin" / "WeMod.exe",
        checkout / "wemod_data" / "wemod_bin" / "Wand.exe",
    ]
    # The game's installed WeMod takes precedence when available. This is
    # bounded to known user-profile locations, no arbitrary recursive scan.
    users = compatdata / "pfx" / "drive_c" / "users"
    if users.is_dir():
        for u in sorted(users.iterdir(), key=lambda x: x.name)[:16]:
            if not u.is_dir() or u.is_symlink():
                continue
            for app in ("WeMod", "Wand"):
                choices.insert(0, u / "AppData" / "Local" / app / (app + ".exe"))
    for path in choices:
        try:
            if path.is_file() and path.stat().st_size >= 64:
                with path.open("rb") as f:
                    if f.read(2) == b"MZ":
                        return path.resolve(strict=True)
        except OSError:
            pass
    return None


def preflight(appid: str, install: Path, game: Path, compat: Path,
              proton: Path, steam_root: Path, launcher: Path) -> dict:
    if not STEAM_APPID.fullmatch(appid):
        raise ValueError("Invalid Steam AppID")
    # Refuse arbitrary install dirs, symlinked executable escape paths, and
    # mismatched app manifests, even when the GUI supplied stale metadata.
    root = install.resolve(strict=True)
    target = game.resolve(strict=True)
    prefix = compat.resolve(strict=True)
    proton_file = proton.resolve(strict=True)
    steam = steam_root.resolve(strict=True)
    actual_launcher = launcher.resolve(strict=True)
    if (root.parent.name != "common" or root.parent.parent.name != "steamapps"
        or not (root.parent.parent / ("appmanifest_" + appid + ".acf")).is_file()):
        raise ValueError("Game must be installed under its matching Steam appmanifest")
    if game.is_symlink() or not game.is_file() or game.suffix.casefold() != ".exe" or not target.is_relative_to(root):
        raise ValueError("Game executable must belong to the selected Steam installation")
    if prefix.name != appid or prefix.parent.name != "compatdata" or not (prefix / "pfx").is_dir():
        raise ValueError("Incorrect or uninitialized game Proton prefix")
    if proton.name != "proton" or not proton_file.is_file() or not os.access(proton_file, os.X_OK):
        raise ValueError("Proton runtime is unavailable")
    if not (steam / "steamapps").is_dir():
        raise ValueError("Steam root is invalid")
    if (launcher.name != "wemod" or
        not (launcher.parent / "src/wemod.py").is_file() or
        actual_launcher != (launcher.parent / "src/wemod.py").resolve(strict=True)):
        raise ValueError("DeckCheatz checkout must be installed before using WeMod")
    wemod = installed_wemod(launcher, prefix)
    if wemod is None:
        raise ValueError("No previously installed WeMod.exe/Wand.exe found; use managed DeckCheatz setup")
    if not shutil.which("steam"):
        raise ValueError("Steam is not available on PATH")
    return {
        "appid": appid,
        "game_exe": str(target),
        "install": str(root),
        "compatdata": str(prefix),
        "proton": str(proton_file),
        "steam_root": str(steam),
        "wemod_exe": str(wemod),
        "mode": "STEAM_OWNED_GAME_THEN_SAME_PREFIX_WEMOD",
    }


def log_path(appid: str) -> Path:
    home = Path.home()
    base = Path(os.environ.get("XDG_STATE_HOME") or str(home / ".local/state"))
    if not base.is_absolute():
        raise ValueError("XDG_STATE_HOME must be absolute")
    directory = base / "gameweld" / "steam-wemod"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    return directory / (appid + "-" + str(int(time.time())) + "-" + str(os.getpid()) + ".log")


def begin_steam(appid: str) -> None:
    with open(os.devnull, "wb") as devnull:
        # Steam normally forwards this request to its already-running client.
        # Command exit 0 is not interpreted as a game-process success.
        subprocess.Popen(
            ["steam", "-applaunch", appid],
            stdin=devnull, stdout=devnull, stderr=devnull,
            start_new_session=True, close_fds=True,
        )


def active_wine_handoff(plan: dict, game_pid: int,
                        proc_root: Path = Path("/proc")) -> tuple[list[str], dict[str, str]]:
    """Join the observed game's active wineserver; do NOT bootstrap Proton twice.

    This follows the existing GameWeld Wand live-session method. Refuse an
    ambiguous runtime or prefix instead of touching the wrong Wine session.
    Only the exact game's read-only process environment is used. No launcher
    settings, registry, prefixes, Steam files or game executable are changed.
    """
    prefix = Path(plan["compatdata"]).resolve(strict=True)
    game_prefix = (prefix / "pfx").resolve(strict=True)
    proton_root = Path(plan["proton"]).parent.resolve(strict=True)
    wine = next((p for p in (
        proton_root / "files/bin/wine",
        proton_root / "files/bin/wine64",
        proton_root / "files/lib/wine/x86_64-unix/wine",
    ) if p.is_file() and os.access(p, os.X_OK)), None)
    wineserver = next((p for p in (
        proton_root / "files/bin/wineserver",
        proton_root / "files/lib/wine/x86_64-unix/wineserver",
    ) if p.is_file() and os.access(p, os.X_OK)), None)
    if wine is None or wineserver is None:
        raise ValueError("Selected Steam Proton runtime lacks Wine/wineserver binaries")

    task = proc_root / str(game_pid)
    try:
        if task.stat().st_uid != os.getuid():
            raise ValueError("Observed game process belongs to another user")
        raw = (task / "environ").read_bytes()[:262145]
        if len(raw) > 262144:
            raise ValueError("Observed game environment is too large")
    except OSError as exc:
        raise ValueError("Game process exited before WeMod handoff") from exc

    variables: dict[str, str] = {}
    for token in raw.split(b"\\0"):
        key, sep, value = token.partition(b"=")
        if not sep:
            continue
        try:
            name = key.decode("ascii")
            if name in {
                "WINEPREFIX", "WINELOADER", "WINESERVER", "WINEDEBUG",
                "WINEDLLOVERRIDES", "WINEESYNC", "WINEFSYNC", "WINEARCH",
                "LD_LIBRARY_PATH", "SteamAppId", "SteamGameId",
                "STEAM_COMPAT_APP_ID", "STEAM_COMPAT_DATA_PATH",
                "STEAM_COMPAT_TOOL_PATHS", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
                "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
            } or name.startswith(("PROTON_", "DXVK_", "VKD3D_")):
                variables[name] = value.decode("utf-8")
        except UnicodeError:
            continue

    if not any(variables.get(key) == plan["appid"] for key in
               ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")):
        raise ValueError("Live process Steam AppID does not match selected game")
    live_compat = variables.get("STEAM_COMPAT_DATA_PATH", "")
    live_wineprefix = variables.get("WINEPREFIX", "")
    if not (
        (live_compat.startswith("/") and os.path.realpath(live_compat) == str(prefix))
        or
        (live_wineprefix.startswith("/") and
         os.path.realpath(live_wineprefix) == str(game_prefix))
    ):
        raise ValueError("Live game's Wine prefix identity is different")
    live_tools = variables.get("STEAM_COMPAT_TOOL_PATHS", "")
    if live_tools and str(proton_root) not in {
        os.path.realpath(value) for value in live_tools.split(":") if value.startswith("/")
    }:
        raise ValueError("Selected Proton tool differs from active game's runtime")

    environment = os.environ.copy()
    for name, value in variables.items():
        if name not in {"PROTON_USE_X11_EXCLUSIVE"}:
            environment[name] = value
    display = environment.get("DISPLAY", "")
    if not display:
        raise ValueError("No X11/XWayland DISPLAY for the existing Wine window session")
    environment["WINEPREFIX"] = str(game_prefix)
    environment["WINELOADER"] = str(wine)
    environment["WINESERVER"] = str(wineserver)
    environment["STEAM_COMPAT_DATA_PATH"] = str(prefix)
    environment["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = plan["steam_root"]
    environment["STEAM_COMPAT_TOOL_PATHS"] = str(proton_root)
    environment["STEAM_COMPAT_APP_ID"] = plan["appid"]
    environment["SteamAppId"] = plan["appid"]
    environment["SteamGameId"] = plan["appid"]
    environment["WINE_GRAPHICS_DRIVER"] = "x11"
    environment["PROTON_USE_X11_EXCLUSIVE"] = Path(plan["wemod_exe"]).name
    environment.pop("LD_PRELOAD", None)
    environment.pop("MANGOHUD", None)
    return [str(wine), plan["wemod_exe"]], environment


def launch(plan: dict, *, observer=None, start_steam=begin_steam,
           spawn=subprocess.Popen, timeout: float = GAME_TIMEOUT,
           log=None, proton_output: Path | None = None) -> dict:
    obs = observer if observer is not None else load_observer()
    appid = plan["appid"]
    exe = Path(plan["game_exe"])
    prefix = Path(plan["compatdata"])
    emit = log or (lambda line: print(line, flush=True))
    matched = obs.matching_game_processes(appid, exe, prefix)
    if matched:
        emit("EXISTING_GAME_PROCESS_IDENTIFIED: Steam launch request skipped; no duplicate game")
    else:
        emit("STEAM_LAUNCH_REQUESTED: " + appid)
        start_steam(appid)
        deadline = time.monotonic() + max(0, timeout)
        while not matched and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
            matched = obs.matching_game_processes(appid, exe, prefix)
    if not matched:
        emit("GAME_PROCESS_UNCONFIRMED: WeMod not started; Steam may still be loading the game")
        return {"state": "GAME_PROCESS_UNCONFIRMED", "trainer_verified": False}
    emit("GAME_PROCESS_IDENTITY_OBSERVED: " + ",".join(map(str, matched)))
    try:
        argv, environment = active_wine_handoff(plan, matched[0])
    except (OSError, ValueError) as exc:
        emit("WEMOD_HANDOFF_BLOCKED: " + str(exc))
        return {"state": "WEMOD_HANDOFF_BLOCKED", "trainer_verified": False}
    emit("WEMOD_ACTIVE_WINESERVER_JOIN_REQUESTED: game-owned prefix; no second Proton bootstrap")
    # Never discard Wine/WeMod errors in field builds. Only the selected
    # helper's stdout/stderr is captured (not the entire Steam/game environment).
    # Each session gets a new owner-only log, not a reusable public /tmp file.
    output_stream = None
    try:
        if proton_output is not None:
            descriptor = os.open(proton_output,
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            output_stream = os.fdopen(descriptor, "w", encoding="utf-8")
            emit("WEMOD_PROTON_OUTPUT_LOG: " + str(proton_output))
        proc = spawn(argv, cwd=str(Path(plan["wemod_exe"]).parent),
                     env=environment, stdin=subprocess.DEVNULL,
                     stdout=output_stream if output_stream else subprocess.DEVNULL,
                     stderr=subprocess.STDOUT if output_stream else subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)
    except OSError as exc:
        emit("WEMOD_START_FAILED: " + type(exc).__name__ + ": " + str(exc))
        return {"state": "WEMOD_START_FAILED", "trainer_verified": False}
    finally:
        if output_stream is not None:
            output_stream.close()
    # A launched WeMod process does NOT establish that a trainer attached.
    emit("WEMOD_PROCESS_REQUESTED: pid " + str(proc.pid)
         + "; trainer attach/render remains UNVERIFIED")
    return {"state": "WEMOD_PROCESS_REQUESTED", "pid": proc.pid,
            "game_pid": matched[0], "trainer_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "launch"))
    for name in ("appid", "install-dir", "game-exe", "compatdata",
                 "proton", "steam-root", "launcher"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        plan = preflight(args.appid, Path(args.install_dir), Path(args.game_exe),
                         Path(args.compatdata), Path(args.proton),
                         Path(args.steam_root), Path(args.launcher))
    except (OSError, ValueError) as exc:
        print("GAMEWELD_STEAM_WEMOD_BLOCKED: " + str(exc), flush=True)
        return 3
    if args.action == "probe":
        print(json.dumps({"ready": True, "appid": args.appid,
                          "mode": plan["mode"], "launch_performed": False,
                          "trainer_verified": False}))
        return 0
    log_file = log_path(args.appid)
    descriptor = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        def report(message: str):
            file.write(message + "\n")
            file.flush()
        report("GAMEWELD_STEAM_WEMOD_V1: appid=" + args.appid)
        report("No Launch Options changes; launcher requests Steam -applaunch")
        output_log = log_file.with_suffix(".proton.log")
        outcome = launch(plan, log=report, proton_output=output_log)
        report("FINAL_STATE: " + outcome["state"])
    return 0 if outcome["state"] == "WEMOD_PROCESS_REQUESTED" else 4


if __name__ == "__main__":
    sys.exit(main())
