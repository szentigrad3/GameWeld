#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GameWeld backend handoff to a DeckCheatz/v2 monitor already running in the game's runtime.

Not a launcher GUI and not a separate Proton invocation. Fail closed when
GameWeld has not supplied a verified process monitor endpoint and session token.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Internal GameWeld/Wand v2 session bridge")
    p.add_argument("--appid", required=True, type=int)
    p.add_argument("--compatdata", required=True, type=Path)
    p.add_argument("--client", required=True, type=Path)
    p.add_argument("--game-exe", required=True, type=Path)
    p.add_argument("--monitor-endpoint", required=True)
    p.add_argument("--rewrite-root", required=True, type=Path)
    a = p.parse_args(argv)
    def blocked(why: str) -> int:
        print(json.dumps({"state": "gameweld_wand_v2_blocked", "reason": why, "appid": a.appid,
                          "steam_launch_options_changed": False, "game_prefix_modified": False}))
        return 2
    if a.appid < 1 or a.compatdata.name != str(a.appid) or not (a.compatdata / "pfx/drive_c").is_dir():
        return blocked("game_prefix_or_appid_mismatch")
    if not a.client.is_absolute() or not a.game_exe.is_absolute() or not a.client.is_file() or not a.game_exe.is_file():
        return blocked("client_or_game_executable_missing")
    match = re.fullmatch(r"(?:127\.0\.0\.1|localhost):([0-9]{1,5})", a.monitor_endpoint)
    if match is None or not 1 <= int(match.group(1)) <= 65535:
        return blocked("monitor_not_localhost")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", os.getenv("WAND_MONITOR_SESSION_TOKEN", "")):
        return blocked("monitor_token_missing")
    source = a.rewrite_root.resolve() / "src"
    if not (source / "wand_launcher/entrypoint.py").is_file():
        return blocked("deckcheatz_v2_source_missing")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(source) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    command = [sys.executable, "-m", "wand_launcher.entrypoint", "--no-prompt",
               "--appid", str(a.appid), "--compatdata", str(a.compatdata),
               "--client-exe", str(a.client), "--game-exe", str(a.game_exe),
               "--monitor-endpoint", a.monitor_endpoint, "--run-attached-monitor"]
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                check=False, timeout=3600)
    except (OSError, subprocess.TimeoutExpired):
        return blocked("upstream_monitor_session_failed")
    if result.returncode:
        return blocked("upstream_monitor_rejected")
    try:
        report = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        return blocked("upstream_session_report_invalid")
    if report.get("state") != "monitor_session_finished":
        return blocked("upstream_monitor_not_finished")
    if report.get("game_started") is not True or report.get("trainer_process_started") is not True:
        return blocked("upstream_monitor_partial_start")
    if type(report.get("game_exit_code")) is not int:
        return blocked("upstream_game_exit_unreported")
    if report.get("trainer_cleanup_verified") is not True:
        return blocked("upstream_trainer_cleanup_unverified")
    print(json.dumps({"state": "gameweld_wand_v2_session_finished", "appid": a.appid,
                      "game_exit_code": report.get("game_exit_code"),
                      "game_started": report.get("game_started", False),
                      "trainer_process_started": report.get("trainer_process_started", False),
                      "trainer_attachment_verified": False,
                      "trainer_cleanup_verified": True,
                      "steam_launch_options_changed": False, "game_prefix_modified": False}))
    return 0

if __name__ == "__main__":
    sys.exit(run())
