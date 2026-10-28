#!/usr/bin/env python3
"""PC2 Steam game-only launch handoff with truthful, read-only result reporting.

GameWeld validates the installed game with its own source backend and asks for
explicit user confirmation BEFORE invoking this helper. No trainer, compatibility
patch, launch options, or Wine prefix are ever modified here.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import tempfile
import time

KEYS = ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")
MAX_PROC = 8192
MAX_ENV = 128 * 1024
OBSERVE_SECONDS = 12


def valid_appid(text: str) -> bool:
    return (
        text.isascii() and text.isdecimal() and not text.startswith("0")
        and len(text) <= 10 and 0 < int(text) < 2**32
    )


def associated_processes(appid: str, root: str = "/proc") -> list[pathlib.Path]:
    """Return same-user PIDs with exact AppID environment tokens; no guessing.

    Never expose a process's full environment or command line. The result is
    only an association, not proof that the game executable is running.
    """
    if not valid_appid(appid):
        return []
    found = []
    examined = 0
    expected = {(key + "=" + appid).encode() for key in KEYS}
    try:
        entries = os.scandir(root)
    except OSError:
        return []
    with entries:
        for item in entries:
            if not item.name.isascii() or not item.name.isdecimal():
                continue
            examined += 1
            if examined > MAX_PROC:
                break
            path = pathlib.Path(item.path)
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                with (path / "environ").open("rb") as stream:
                    env = stream.read(MAX_ENV + 1)
                if len(env) > MAX_ENV:
                    continue
                if expected.intersection(env.split(b"\0")):
                    found.append(path)
            except OSError:
                # Missing/exiting/unreadable process: cannot infer identity.
                continue
    return found


def associated_process_count(appid: str, root: str = "/proc") -> int:
    return len(associated_processes(appid, root))


def _safe_process_basename(text: str, *, path: bool = False) -> str:
    name = text.strip().removesuffix(" (deleted)")
    if path:
        name = os.path.basename(name)
    if not name or len(name) > 80:
        return "unavailable"
    if all(ch.isascii() and (ch.isalnum() or ch in "._+-") for ch in name):
        return name
    return "redacted"


def associated_process_details(appid: str, root: str = "/proc") -> list[tuple[int, str, str, str]]:
    """Read-only, redacted process roles; classification is NOT game proof."""
    records = []
    for directory in associated_processes(appid, root):
        try:
            pid = int(directory.name)
            comm = _safe_process_basename((directory / "comm").read_text()[:128])
        except (OSError, ValueError):
            comm = "unavailable"
            try:
                pid = int(directory.name)
            except ValueError:
                continue
        try:
            executable = _safe_process_basename(os.readlink(directory / "exe"), path=True)
        except OSError:
            executable = "unavailable"
        names = (comm + " " + executable).lower()
        if any(part in names for part in (
                "steamwebhelper", "steam-runtime", "steamservice",
                "pressure-vessel", "reaper")):
            role = "steam_helper"
        elif any(part in names for part in (
                "wineserver", "services.exe", "explorer.exe", "conhost.exe",
                "winedevice.exe", "rpcss.exe", "plugplay.exe",
                "wine64", "wine-preloader")):
            role = "wine_runtime"
        elif comm.lower().endswith(".exe"):
            role = "windows_executable_candidate"
        else:
            role = "other_associated"
        records.append((pid, comm, executable, role))
    return sorted(records)


def run_launch(appid: str, *, steam: str | None = None,
               duration: float = OBSERVE_SECONDS,
               require_idle_before_launch: bool = False,
               transport: str = "applaunch") -> int:
    if transport not in ("applaunch", "steam-uri"):
        print("Launch result: FAILED (unsupported Steam transport).", flush=True)
        return 3
    executable = steam or shutil.which("xdg-open" if transport == "steam-uri" else "steam")
    if not executable:
        print("Steam executable: NOT FOUND on GameWeld's PATH.", flush=True)
        print("Launch result: FAILED (Steam command unavailable).", flush=True)
        return 3
    print("Steam executable: FOUND", flush=True)
    print("Steam launch transport: " + transport, flush=True)
    previous = associated_process_count(appid)
    if previous:
        print(f"Steam app-ID associated processes BEFORE launch: {previous}", flush=True)
    if require_idle_before_launch and previous:
        print("Launch result: FAILED (this Steam AppID already has a running associated process).", flush=True)
        print("The game and any WeMod session must be closed before requesting a new wrapper launch.", flush=True)
        return 3
    # The running Steam client may accept IPC and return immediately; stdout
    # therefore goes to an ephemeral file, not a pipe that keeps GameWeld
    # waiting forever because a game inherited the file descriptor.
    try:
        with tempfile.TemporaryFile(mode="w+b") as output:
            # A Steam URI is a separate, manually selected retry path, never
            # an automatic second launch after an unconfirmed first request.
            argv = ([executable, "steam://rungameid/" + appid]
                    if transport == "steam-uri" else
                    [executable, "-applaunch", appid])
            # Do not pass GameWeld's temporary source-AppDir and test flags
            # into Steam. Keep DISPLAY, WAYLAND_DISPLAY, DBUS and normal
            # desktop environment so Steam IPC/URL handlers still work.
            child_env = {key: value for key, value in os.environ.items()
                         if key not in ("APPDIR", "WAND_NATIVE_BACKEND")
                         and not key.startswith("GAMEWELD_PC2_")
                         and not key.startswith("GAMEWELD_NATIVE_")}
            child = subprocess.Popen(
                argv, env=child_env,
                stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            try:
                print("Steam " + transport + " command: STARTED", flush=True)
                deadline = time.monotonic() + max(0, duration)
                while True:
                    status = child.poll()
                    if status is not None and status != 0:
                        print(f"Steam command exit status: {status}", flush=True)
                        print("Launch result: FAILED (Steam command returned an error).", flush=True)
                        return 3
                    observed = associated_process_count(appid)
                    if observed and (not previous or observed > previous):
                        print(f"Steam app-ID associated processes: {observed}", flush=True)
                        print("Launch result: STEAM_ASSOCIATION_OBSERVED", flush=True)
                        print("Game executable, visible window and trainer: NOT VERIFIED.", flush=True)
                        return 0
                    if time.monotonic() >= deadline:
                        if status is None:
                            print("Steam command: STILL RUNNING (left untouched).", flush=True)
                        else:
                            print(f"Steam command exit status: {status}", flush=True)
                        if observed:
                            print(f"Existing app-ID associated processes: {observed}", flush=True)
                        print("Launch result: UNCONFIRMED (no new game-associated process evidence).", flush=True)
                        print("Steam may still be starting the game; check Steam or its game logs.", flush=True)
                        return 2
                    time.sleep(0.5)
            finally:
                # Do not kill or block on Steam: the client can keep this
                # command alive after GameWeld finishes its observation.
                # A daemon waiter retains/reaps Popen without ResourceWarning.
                if child.poll() is None:
                    threading.Thread(
                        target=child.wait,
                        name="gameweld-steam-handoff-reaper",
                        daemon=True,
                    ).start()
    except OSError as exc:
        print(f"Steam command: COULD NOT EXECUTE ({type(exc).__name__}).", flush=True)
        print("Launch result: FAILED (Steam command could not be executed).", flush=True)
        return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "launch"))
    parser.add_argument("--appid", required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--details", action="store_true",
                        help="Read-only redacted process names for AppID associations")
    parser.add_argument("--transport", choices=("applaunch", "steam-uri"),
                        default="applaunch", help="Explicit Steam handoff transport")
    parser.add_argument("--require-idle-before-launch", action="store_true",
                        help="Fail before launching if the exact AppID has an existing process")
    args = parser.parse_args()
    if not valid_appid(args.appid):
        parser.error("Invalid decimal Steam App ID")
    print("PC2 game-only Steam handoff: App ID " + args.appid, flush=True)
    if args.action == "status":
        print("Steam executable: " + (
            "FOUND" if shutil.which("steam") else "NOT FOUND"
        ), flush=True)
        print("Read-only app-ID associated process count: " +
              str(associated_process_count(args.appid)), flush=True)
        if args.details:
            details = associated_process_details(args.appid)
            if not details:
                print("Process details: none visible", flush=True)
            for pid, comm, executable, role in details:
                print(f"AppID association: PID={pid} role={role} "
                      f"comm={comm} executable={executable}", flush=True)
            print("Process roles are heuristic; no game executable verified.", flush=True)
        print("No Steam command or trainer was launched.", flush=True)
        return 0
    if not args.confirm:
        parser.error("Steam launch requires an explicit --confirm from GameWeld's user dialog")
    return run_launch(args.appid,
                      require_idle_before_launch=args.require_idle_before_launch,
                      transport=args.transport)


if __name__ == "__main__":
    sys.exit(main())
