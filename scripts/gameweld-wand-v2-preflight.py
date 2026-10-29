#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Internal GameWeld-to-DeckCheatz v2 preflight adapter.

GameWeld remains the GUI and owns the game/runtime session. This script
only checks launcher prerequisites; no Steam settings or process mutations.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

def prepare(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GameWeld internal Wand v2 preflight")
    parser.add_argument("--appid", required=True, type=int)
    parser.add_argument("--compatdata", required=True)
    parser.add_argument("--client", required=True)
    parser.add_argument("--rewrite-root", required=True, type=Path)
    parser.add_argument("--client-sha256")
    args = parser.parse_args(argv)
    source = args.rewrite_root.resolve() / "src"
    if not (source / "wand_launcher" / "entrypoint.py").is_file():
        print(json.dumps({"state": "blocked", "reason": "deckcheatz_rewrite_missing"}))
        return 2
    env = dict(os.environ)
    env["PYTHONPATH"] = str(source) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    command = [
        sys.executable, "-m", "wand_launcher.entrypoint", "--no-prompt",
        "--appid", str(args.appid), "--compatdata", args.compatdata,
        "--client-exe", args.client, "--prepare-only",
    ]
    if args.client_sha256:
        command += ["--client-sha256", args.client_sha256]
    env.pop("GIO_LAUNCHED_DESKTOP_FILE", None)
    env.pop("GIO_LAUNCHED_DESKTOP_FILE_PID", None)
    try:
        result = subprocess.run(
            command, env=env, capture_output=True, text=True,
            check=False, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        print(json.dumps({"state": "blocked", "reason": "rewrite_preflight_failed"}))
        return 2
    if result.returncode != 0:
        print(json.dumps({"state": "blocked", "reason": "rewrite_preflight_rejected"}))
        return 2
    try:
        summary = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        print(json.dumps({"state": "blocked", "reason": "rewrite_report_invalid"}))
        return 2
    if summary.get("state") != "preflight_ready_only":
        print(json.dumps({"state": "blocked", "reason": "rewrite_not_ready"}))
        return 2
    print(json.dumps({
        "state": "gameweld_wand_v2_preflight_passed", "appid": args.appid,
        "game_launched": False, "trainer_launched": False,
        "steam_launch_options_changed": False,
        "compatibility_tool_changed": False,
    }))
    return 0

if __name__ == "__main__":
    sys.exit(prepare())
