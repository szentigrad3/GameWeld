#!/usr/bin/env python3
"""GameWeld PC2 opt-in bridge to the previously field-validated Wand Native 0.1.41.

No patches, installations or Steam config writes. 'check' is entirely read-only.
'play' explicitly asks the existing Wand Native daemon to start its own tested
one-Proton-session Wand + game flow. This is NOT PC2's live runinprefix launcher.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

TESTED_VERSION = "0.1.41"
PROTON_NAME = "GE Proton Wand SHA256"
MAX_OUTPUT = 160_000

class Blocked(ValueError):
    pass

def validated_id(value: str) -> str:
    if not (value.isascii() and value.isdecimal() and not value.startswith("0")
            and len(value) <= 10 and 0 < int(value) < 2**32):
        raise Blocked("Expected one valid installed decimal Steam App ID")
    return value

def find_cli() -> Path:
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    choices = [
        os.environ.get("GAMEWELD_WAND_NATIVE_CLI", ""),
        shutil.which("wandctl") or "",
        str(home / ".local/bin/wandctl"),
        str(data / "wand-native/bin/wandctl"),
        str(home / "Desktop/wand-native-0.1.41/bin/wandctl"),
        str(home / "Desktop/wand-native-0.1.41/target/release/wandctl"),
    ]
    for name in choices:
        if not name:
            continue
        candidate = Path(name).expanduser()
        if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve(strict=True)
    raise Blocked(
        "Existing Wand Native 0.1.41 CLI not found. Use the previously validated "
        "Wand Native release; GameWeld will not reinstall or guess a replacement.")

def run(cli: Path, *args: str, timeout: int = 15) -> str:
    try:
        done = subprocess.run(
            [str(cli), *args], check=False, capture_output=True,
            text=True, errors="replace", timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise Blocked("Wand Native CLI unavailable/timed out: " + type(exc).__name__) from exc
    output = (done.stdout + "\n" + done.stderr)[:MAX_OUTPUT]
    if done.returncode != 0:
        short = next((line.strip() for line in output.splitlines()
                      if "error" in line.lower()), "check the existing Wand Native service")
        raise Blocked("Wand Native command did not pass (" + " ".join(args[:2]) +
                      "); " + short[:450])
    return done.stdout

def json_response(cli: Path, *args: str) -> object:
    raw = run(cli, *args).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Blocked("Wand Native returned an unexpected response for " +
                      " ".join(args[:2])) from exc

def check(appid: str, game_dir: str) -> tuple[Path, Path]:
    appid = validated_id(appid)
    cli = find_cli()
    version = run(cli, "--version", timeout=5)
    if not re.search(r"(?<![0-9])0\.1\.41(?![0-9])", version):
        raise Blocked("Installed Wand Native CLI is not tested 0.1.41: " +
                      version.strip()[:100] + ". Refusing to assume a different runtime is equivalent")
    run(cli, "ping", timeout=5)
    proton_status = run(cli, "proton", "verify")
    if "Result: healthy" not in proton_status:
        raise Blocked("Isolated GE Proton Wand SHA256 tool is not verified; open "
                      "the old Wand Native Install / Repair workflow")
    inspect = json_response(cli, "inspect", appid, "--proton", PROTON_NAME)
    if not isinstance(inspect, dict):
        raise Blocked("Unexpected Wand Native game inspection")
    game = inspect.get("game")
    proton = inspect.get("proton")
    if not isinstance(game, dict) or not isinstance(proton, dict):
        raise Blocked("Wand Native inspection lacks game or Proton details")
    if str(game.get("app_id")) != appid:
        raise Blocked("Wand Native game identity does not match selected GameWeld app")
    if proton.get("display_name") != PROTON_NAME:
        raise Blocked("Wand Native did not resolve the verified isolated Proton tool")
    path = game.get("install_dir")
    if not isinstance(path, str) or not Path(path).is_dir():
        raise Blocked("The old managed runtime did not verify an installed game directory")
    if game_dir and Path(path).resolve() != Path(game_dir).resolve():
        raise Blocked("GameWeld and Wand Native disagree about the game's installed directory")

    health = json_response(cli, "provider-health", "--provider", "wemod", "--app-id", appid)
    if not isinstance(health, list) or len(health) != 1:
        raise Blocked("Wand Native WeMod provider health was not uniquely resolved")
    provider = health[0]
    if not isinstance(provider, dict) or provider.get("id") != "wemod":
        raise Blocked("Wrong Wand Native provider returned")
    if provider.get("available") is not True or provider.get("status") != "ready":
        raise Blocked("Wand Native WeMod runtime isn't ready. Use its validated Install / Repair")
    details = provider.get("details") or []
    if not isinstance(details, list):
        raise Blocked("Provider runtime evidence is incomplete")
    runtime_paths = []
    dwrite_ok = False
    for entry in details:
        if not isinstance(entry, str):
            continue
        m = re.fullmatch(r"(?:Wand|WeMod) runtime .+ at (.+)", entry)
        if m:
            runtime_paths.append(Path(m.group(1)))
        if "DWriteCore compatibility: installed beside" in entry:
            dwrite_ok = True
    if len(runtime_paths) != 1 or not runtime_paths[0].is_file():
        raise Blocked("Wand Native cannot identify its actual installed Windows client runtime")
    if not dwrite_ok:
        raise Blocked("DWriteCore is not installed beside the Wand Native runtime; "
                      "use the existing Wand Native Install / Repair (don't copy DLLs manually)")
    processes = json_response(cli, "processes", appid)
    if not isinstance(processes, dict):
        raise Blocked("Wand Native process readiness cannot be verified")
    if processes.get("best_candidate_pid") is not None:
        raise Blocked("Astrometica/game is already running; CLOSE the game before the "
                      "one-Proton-session managed launch. Nothing was launched.")
    print("Wand Native 0.1.41: VERIFIED")
    print("Isolated GE Proton Wand SHA256 tool: VERIFIED")
    print("WeMod runtime: FOUND (" + runtime_paths[0].name + ")")
    print("DWriteCore beside runtime: VERIFIED")
    print("Game identity: " + appid + " (installed)")
    print("Game process: not observed (required for managed new session)")
    print("Source runtime is managed by Wand Native, not PC2's patched client selector.")
    return cli, runtime_paths[0]

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("check", "play"))
    ap.add_argument("--appid", required=True)
    ap.add_argument("--game-dir", default="")
    ap.add_argument("--game-provider", choices=("steam", "other", "heroic", "lutris"),
                    default="steam")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    if args.game_provider != "steam":
        raise Blocked("Managed Wand Native 0.1.41 launch supports installed standard Steam games only")
    if args.action == "play" and not args.confirm:
        raise Blocked("Managed game + Wand launch requires explicit --confirm")
    cli, runtime = check(args.appid, args.game_dir)
    if args.action == "check":
        print("Read-only readiness: PASS; nothing launched or modified")
        return 0
    print("Requesting old Wand Native managed one-Proton session (game + client)", flush=True)
    print("Using old provider runtime: " + runtime.name, flush=True)
    raw = run(cli, "begin-session", args.appid, str(runtime),
              "--provider", "wemod", "--proton", PROTON_NAME,
              "--timeout-secs", "120", timeout=35)
    # A valid daemon response is required. This is a START REQUEST, not an
    # assertion that the window or trainer attached successfully.
    try:
        session = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Blocked("Wand Native begin-session response is unrecognized") from exc
    if not isinstance(session, dict):
        raise Blocked("Wand Native did not return a session record")
    print("Wand Native begin-session request: ACCEPTED")
    print("Session status: " + str(session.get("state", "unverified")))
    print("Client window, trainer detection, attachment and game startup: NOT VERIFIED")
    print("Check the original Wand Native GUI for the managed session's progress.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError) as exc:
        print("GameWeld Wand Native bridge: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
