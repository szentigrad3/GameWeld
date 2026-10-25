#!/usr/bin/env python3
"""Read-only Steam runtime-context audit for a running GameWeld game.

Compares the host launch context against the selected game's active Proton
runtime. Never starts Wine, modifies Steam, or opens a game prefix.
"""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BRIDGE = Path(__file__).with_name("gameweld-wemod-enhancer.py")
RUNTIME_NAMES = {
    "4183110": "SteamLinuxRuntime_4",
    "1628350": "SteamLinuxRuntime_sniper",
    "1391110": "SteamLinuxRuntime_soldier",
}
APPID_PATTERN = re.compile(r'"require_tool_appid"\s+"(\d+)"')


def parse_required_runtime(manifest_text: str) -> str | None:
    cleaned = re.sub(r"//[^\n]*", "", manifest_text)
    match = APPID_PATTERN.search(cleaned)
    return match.group(1) if match else None


def read_namespace(pid: str, proc: Path = Path("/proc")) -> str:
    try:
        return os.readlink(proc / pid / "ns/mnt")
    except OSError:
        return "unavailable"


def game_launcher_service_owned(appid: str) -> bool | None:
    """Probe D-Bus NameHasOwner only; never activate or configure a service."""
    if not appid.isascii() or not appid.isdecimal():
        raise ValueError("Steam AppID must contain digits only")
    binary = shutil.which("gdbus")
    if not binary:
        return None
    try:
        process = subprocess.run([
            binary, "call", "--session", "--dest", "org.freedesktop.DBus",
            "--object-path", "/org/freedesktop/DBus",
            "--method", "org.freedesktop.DBus.NameHasOwner",
            "com.steampowered.App" + appid,
        ], check=False, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if process.returncode != 0:
        return None
    result = process.stdout.strip().lower()
    if result == "(true,)":
        return True
    if result == "(false,)":
        return False
    return None


def audit(session: dict, proc: Path = Path("/proc"), *, appid: str | None = None) -> str:
    proton = Path(session["proton"])
    manifest = proton.parent / "toolmanifest.vdf"
    appid = None
    if manifest.is_file():
        appid = parse_required_runtime(manifest.read_text(errors="replace"))
    steamroot = Path(session["steamroot"])
    runtime_name = RUNTIME_NAMES.get(appid, "") if appid else ""
    runtime = (steamroot / "steamapps/common" / runtime_name / "_v2-entry-point"
               if runtime_name else None)
    game_ns = read_namespace(str(session["game_pid"]), proc)
    host_ns = read_namespace("self", proc)
    launcher_client = (steamroot / "steamapps/common" / runtime_name /
                       "pressure-vessel/bin/steam-runtime-launch-client"
                       if runtime_name else None)
    available_service = game_launcher_service_owned(appid) if appid else None
    lines = [
        "=== GAMEWELD STEAM RUNTIME CONTEXT (READ ONLY) ===",
        f"Game PID: {session['game_pid']}",
        f"Active Proton: {proton}",
        f"Steam root: {steamroot}",
        f"Proton runtime manifest: {manifest if manifest.is_file() else 'not found'}",
        f"Required Steam runtime AppID: {appid or 'not specified'}",
        f"Expected runtime: {runtime_name or 'unknown or not required'}",
        f"Runtime entry point: {runtime if runtime else 'unknown'}",
        f"Runtime entry point exists: {bool(runtime and runtime.is_file())}",
        f"Game mount namespace: {game_ns}",
        f"GameWeld audit mount namespace: {host_ns}",
        f"Mount namespaces differ: {game_ns != host_ns if game_ns != 'unavailable' and host_ns != 'unavailable' else 'unknown'}",
        f"Steam runtime launch-client: {launcher_client if launcher_client else 'not found'}",
        f"Steam runtime launch-client exists: {bool(launcher_client and launcher_client.is_file())}",
        f"Existing game launcher service: " +
            (("AVAILABLE" if available_service else "NOT ACTIVE") if available_service is not None else "UNVERIFIED"),
        "The game launcher service is opt-in; an inactive service cannot be joined from GameWeld.",
        "Current GameWeld direct-Wine mode does not independently enter the Steam Linux Runtime.",
        "Different namespaces alone do not prove the GPU error's cause.",
        "No Proton instance or game prefix was modified.",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", default="2353250")
    args = p.parse_args()
    if not args.appid.isascii() or not args.appid.isdecimal():
        p.error("Steam AppID must be numeric")
    spec = importlib.util.spec_from_file_location("gameweld_live_bridge", BRIDGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load GameWeld's live Steam process detector")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    try:
        session = bridge.live_steam_proton_session(args.appid)
    except (ValueError, OSError) as exc:
        print("Runtime audit blocked: " + str(exc), file=sys.stderr)
        return 1
    print(audit(session, appid=args.appid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
