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


def associated_process_count(appid: str, root: str = "/proc") -> int:
    if not valid_appid(appid):
        return 0
    count, examined = 0, 0
    expected = {(key + "=" + appid).encode() for key in KEYS}
    try:
        entries = os.scandir(root)
    except OSError:
        return 0
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
                    count += 1
            except (OSError, PermissionError):
                continue
    return count


def run_launch(appid: str, *, steam: str | None = None,
               duration: float = OBSERVE_SECONDS,
               require_idle_before_launch: bool = False) -> int:
    executable = steam or shutil.which("steam")
    if not executable:
        print("Steam executable: NOT FOUND on GameWeld's PATH.", flush=True)
        print("Launch result: FAILED (Steam command unavailable).", flush=True)
        return 3
    print("Steam executable: FOUND", flush=True)
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
            child = subprocess.Popen(
                [executable, "-applaunch", appid],
                stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            print("Steam -applaunch command: STARTED", flush=True)
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
    except OSError as exc:
        print(f"Steam command: COULD NOT EXECUTE ({type(exc).__name__}).", flush=True)
        print("Launch result: FAILED (Steam command could not be executed).", flush=True)
        return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "launch"))
    parser.add_argument("--appid", required=True)
    parser.add_argument("--confirm", action="store_true")
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
        print("No Steam command or trainer was launched.", flush=True)
        return 0
    if not args.confirm:
        parser.error("Steam launch requires an explicit --confirm from GameWeld's user dialog")
    return run_launch(args.appid,
                      require_idle_before_launch=args.require_idle_before_launch)


if __name__ == "__main__":
    sys.exit(main())
