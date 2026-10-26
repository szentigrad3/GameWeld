#!/usr/bin/env python3
"""Experimental, opt-in WeMod *client-only* handoff to a live Steam Proton game.

No Steam Launch Options, Steam Bridge, additional game instance, or provider
configuration changes. PREVIEW BY DEFAULT. The live Proton runinprefix action
can still write to the game's EXISTING Wine prefix and is NOT approved for
one-click public release. It is not a trainer-attachment verifier.

Only processes belonging to this UID and with a selected AppID + exact
STEAM_COMPAT_DATA_PATH may supply a Proton tool/root hint. Unrelated process
environment variables, command lines and tokens are never printed or copied.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

APPID = re.compile(r"[1-9][0-9]{0,9}\Z")
CHUNK = 1024 * 1024
MAX_PIDS = 50000
ALLOW_ENV = ("STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
             "STEAM_COMPAT_TOOL_PATHS", "SteamAppId", "SteamGameId",
             "STEAM_COMPAT_APP_ID", "SteamCompatAppId")
INHERIT_ENV = (
    "HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL", "LC_CTYPE",
    "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE",
    "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY",
)


class AttachBlocked(ValueError):
    pass


def is_plain_dir(path: Path) -> bool:
    return path.is_absolute() and path.is_dir() and not path.is_symlink()


def read_env(pid: Path) -> dict[str, str]:
    """Whitelist ONLY the launch-context variables needed by the helper."""
    with (pid / "environ").open("rb") as source:
        raw = source.read(CHUNK + 1)
    if len(raw) > CHUNK:
        raise AttachBlocked("Oversized process environment")
    result: dict[str, str] = {}
    for entry in raw.split(b"\x00"):
        if b"=" not in entry:
            continue
        key, val = entry.split(b"=", 1)
        if key.decode("ascii", "ignore") not in ALLOW_ENV:
            continue
        try:
            result[key.decode("ascii")] = val.decode("utf-8", "surrogateescape")
        except UnicodeError:
            continue
    return result


def validate_steam_game(appid: str, install_dir: Path) -> Path:
    if not APPID.fullmatch(appid) or int(appid) >= 2**32:
        raise AttachBlocked("Invalid Steam AppID")
    install = install_dir.expanduser()
    if not is_plain_dir(install):
        raise AttachBlocked("Select an existing non-symlinked Steam game directory")
    steamapps = install.parent.parent
    if install.parent.name != "common" or steamapps.name != "steamapps":
        raise AttachBlocked("Selected game must be in steamapps/common")
    manifest = steamapps / ("appmanifest_" + appid + ".acf")
    if manifest.is_symlink() or not manifest.is_file():
        raise AttachBlocked("Selected library has no matching AppID manifest")
    compat = steamapps / "compatdata" / appid
    if not is_plain_dir(compat) or not is_plain_dir(compat / "pfx"):
        raise AttachBlocked("Exact AppID Proton prefix is missing")
    return compat


def validate_client(client_dir: Path) -> Path:
    client = client_dir.expanduser()
    if not is_plain_dir(client):
        raise AttachBlocked("Prepared WeMod client directory missing or symlinked")
    exe = client / "WeMod.exe"
    asar = client / "resources" / "app.asar"
    if (exe.is_symlink() or asar.is_symlink() or
            not exe.is_file() or not asar.is_file()):
        raise AttachBlocked("WeMod client must contain ordinary WeMod.exe and app.asar")
    return client


def proton_from_tools(tool_paths: str) -> list[Path]:
    """Find concrete launchers from the selected session, not arbitrary Proton."""
    candidates: list[Path] = []
    for field in tool_paths.split(":"):
        if not field or not field.startswith("/"):
            continue
        directory = Path(field)
        launcher = directory / "proton"
        if (launcher.is_file() and launcher.name == "proton" and
                os.access(launcher, os.X_OK) and
                (directory / "toolmanifest.vdf").is_file()):
            try:
                real = launcher.resolve(strict=True)
            except OSError:
                continue
            if real not in candidates:
                candidates.append(real)
    return candidates


def same_path(value: str, wanted: Path) -> bool:
    if not value or not value.startswith("/"):
        return False
    try:
        return Path(value).resolve(strict=True) == wanted.resolve(strict=True)
    except OSError:
        return False


def live_context(
    appid: str, compat: Path, *,
    proc_root: Path = Path("/proc"),
    uid: int | None = None,
) -> dict:
    """Fail closed on missing, inaccessible or conflicting live runtime hints."""
    uid = os.getuid() if uid is None else uid
    if not proc_root.is_dir():
        raise AttachBlocked("Linux procfs is not accessible")
    processes = [p for p in proc_root.iterdir() if p.name.isdecimal()]
    if len(processes) > MAX_PIDS:
        raise AttachBlocked("Too many processes for an unambiguous runtime preflight")
    matched = 0
    unreadable = 0
    contexts: dict[tuple[str, str], dict] = {}
    client_candidate_seen = False
    # Import our existing read-only name scanner; no code from downloaded ZIPs.
    import importlib.util
    inspector = Path(__file__).resolve().with_name("gameweld-prefix-runtime-preflight.py")
    if inspector.is_symlink() or not inspector.is_file():
        raise AttachBlocked("Trusted local process-name inspector unavailable")
    spec = importlib.util.spec_from_file_location("gw_live_name_inspector", inspector)
    if spec is None or spec.loader is None:
        raise AttachBlocked("Cannot import process-name inspector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for process in processes:
        try:
            if process.stat(follow_symlinks=False).st_uid != uid:
                continue
            found = read_env(process)
        except (OSError, AttachBlocked):
            unreadable += 1
            continue
        if not same_path(found.get("STEAM_COMPAT_DATA_PATH", ""), compat):
            continue
        ids = (found.get("SteamAppId"), found.get("SteamGameId"),
               found.get("STEAM_COMPAT_APP_ID"), found.get("SteamCompatAppId"))
        if appid not in ids:
            continue
        matched += 1
        if module.is_wemod_process(process) is True:
            client_candidate_seen = True
        steam_root = found.get("STEAM_COMPAT_CLIENT_INSTALL_PATH", "")
        tool_paths = found.get("STEAM_COMPAT_TOOL_PATHS", "")
        candidates = proton_from_tools(tool_paths)
        if (not steam_root or not is_plain_dir(Path(steam_root)) or
                not (Path(steam_root) / "steamapps").is_dir() or
                not candidates):
            continue
        for proton in candidates:
            key = (str(proton), str(Path(steam_root).resolve(strict=True)))
            contexts[key] = {"proton": proton, "steam_root": Path(steam_root),
                             "tool_paths": tool_paths}
    return {
        "matched_processes": matched,
        "unreadable_processes": unreadable,
        "wemod_already_visible": client_candidate_seen,
        "contexts": contexts,
    }


def default_client() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", "")
    if data_home and not Path(data_home).is_absolute():
        raise AttachBlocked("XDG_DATA_HOME must be absolute")
    data = Path(data_home) if data_home else Path.home() / ".local/share"
    return data / "gameweld/deckcheatz/wemod_data/wemod_bin"


def plan(
    appid: str, install_dir: Path, client_dir: Path, *,
    proc_root: Path = Path("/proc"), uid: int | None = None,
) -> tuple[dict, dict]:
    compat = validate_steam_game(appid, install_dir)
    context = live_context(appid, compat, proc_root=proc_root, uid=uid)
    blockers = []
    client = None
    try:
        client = validate_client(client_dir)
    except (AttachBlocked, OSError) as exc:
        blockers.append(str(exc))
    if context["matched_processes"] == 0:
        blockers.append("No exact running Steam game-prefix process found")
    if context["unreadable_processes"]:
        blockers.append("Some same-user process environments were inaccessible")
    if context["wemod_already_visible"]:
        blockers.append("A matching WeMod.exe process is already visible; refuse duplicate")
    if len(context["contexts"]) != 1:
        blockers.append("Could not uniquely resolve the running Steam Proton tool and root")
    selected = next(iter(context["contexts"].values())) if len(context["contexts"]) == 1 else None
    report = {
        "mode": "live_client_handoff_preview",
        "appid": appid,
        "game_launch": "Steam's already-running original game session only",
        "matching_prefix_processes": context["matched_processes"],
        "wemod_already_visible": context["wemod_already_visible"],
        "unique_proton_context": selected is not None,
        "managed_client_present": client is not None,
        "blockers": blockers,
        "can_attempt_with_explicit_consent": not blockers,
        "steam_launch_options_changed": False,
        "steam_bridge_required": False,
        "new_game_launched": False,
        "existing_prefix_may_be_changed_by_proton": True,
        "trainer_attachment_verified": False,
        "in_game_activation_verified": False,
    }
    private = {"client": client, "compat": compat, "context": selected}
    return report, private


def launch(report: dict, private: dict, *, approved: bool,
           state_root: Path | None = None) -> dict:
    if not approved or not report["can_attempt_with_explicit_consent"]:
        raise AttachBlocked("Explicit approval and a clean live-session preflight are required")
    runtime = private["context"]
    client = private["client"]
    if runtime is None or client is None:
        raise AttachBlocked("Client or exact selected Steam runtime was not resolved")
    state = state_root or (Path(os.environ.get("XDG_STATE_HOME") or
                          str(Path.home() / ".local/state")) / "gameweld/wemod-live")
    if not state.is_absolute() or state.is_symlink():
        raise AttachBlocked("Unsafe private diagnostic directory")
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat.S_IMODE(state.stat().st_mode) & 0o077:
        raise AttachBlocked("Private diagnostic directory must have mode 0700")
    log_path = state / (report["appid"] + "-" + str(time.time_ns()) + ".log")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(log_path, flags, 0o600)
    env = {key: value for key, value in os.environ.items() if key in INHERIT_ENV}
    env.update({
        "STEAM_COMPAT_DATA_PATH": str(private["compat"]),
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(runtime["steam_root"]),
        "STEAM_COMPAT_TOOL_PATHS": runtime["tool_paths"],
        "SteamAppId": report["appid"],
        "SteamGameId": report["appid"],
        "STEAM_COMPAT_APP_ID": report["appid"],
        "WINEDLLOVERRIDES": "version=n,b",
        "WEMOD_LOG": str(log_path),
    })
    argv = [str(runtime["proton"]), "runinprefix", str(client / "WeMod.exe")]
    try:
        with os.fdopen(fd, "wb") as log:
            child = subprocess.Popen(argv, cwd=client, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, close_fds=True)
    except OSError:
        log_path.unlink(missing_ok=True)
        raise
    return {
        "mode": "EXPERIMENTAL_CLIENT_HANDOFF_REQUESTED",
        "pid": child.pid,
        "log": str(log_path),
        "steam_launch_options_changed": False,
        "steam_bridge_used": False,
        "new_game_launched": False,
        "trainer_attachment_verified": False,
        "in_game_activation_verified": False,
        "message": "Client subprocess requested; confirm WeMod connection and actual in-game effect manually."
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--client-dir", type=Path)
    parser.add_argument("--launch-client", action="store_true")
    parser.add_argument("--approve-prefix-may-change", action="store_true")
    parser.add_argument("--approve-experimental-live-attach", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.launch_client and (
                args.approve_prefix_may_change or args.approve_experimental_live_attach):
            raise AttachBlocked("Preview never accepts live launch approval flags")
        report, private = plan(args.appid, args.install_dir,
                               args.client_dir or default_client())
        if args.launch_client:
            if not (args.approve_prefix_may_change and
                    args.approve_experimental_live_attach):
                raise AttachBlocked("Both live-attach approvals are required")
            result = launch(report, private, approved=True)
        else:
            result = report
    except (AttachBlocked, OSError, ValueError) as exc:
        parser.exit(2, "GameWeld WeMod live attach BLOCKED — " + str(exc) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
