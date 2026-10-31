#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GameWeld backend handoff to a DeckCheatz/v2 monitor already running in the game's runtime.

Not a launcher GUI and not a separate Proton invocation. Fail closed when
the local monitor endpoint/token prerequisites or live Linux process anchor fail.
Windows PID, trainer attachment, and trainer cleanup require independent proof.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

def _load_live_anchor():
    source = Path(__file__).with_name("gameweld-wand-v2-live-anchor.py")
    spec = importlib.util.spec_from_file_location("gameweld_wand_live_anchor_for_session", source)
    if spec is None or spec.loader is None:
        raise ValueError("live_anchor_source_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def execute_bounded_monitor(command: list[str], env: dict[str, str]):
    """Use a bounded streaming protocol, not 24 hours of capture_output."""
    source = Path(__file__).with_name("gameweld-wand-v2-bounded-monitor.py")
    spec = importlib.util.spec_from_file_location("gameweld_wand_bounded_monitor", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("upstream_monitor_runner_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_monitor(command, env, timeout_seconds=86400,
                              max_stdout_bytes=262144)


def verify_running_linux_game(appid: int, compatdata: Path, game_exe: Path) -> tuple[bool, str]:
    """Revalidate a freshly acquired same-prefix PID/start tick before handoff.

    This is only a Linux process safety gate. The upstream runtime must
    independently establish Win32 process identity and monitor ownership.
    """
    try:
        module = _load_live_anchor()
        fresh = module.acquire_fresh_anchor(appid, compatdata, game_exe)
        if fresh.get("state") != "linux_anchor_acquired":
            return False, "linux_game_anchor_not_acquired"
        pid = fresh.get("anchored_linux_pid")
        ticks = fresh.get("anchored_process_start_ticks")
        sampled = module.verify_anchor(appid, compatdata, game_exe,
                                       pid=pid, start_ticks=ticks,
                                       samples=3, interval_ms=400)
    except (OSError, ValueError, RuntimeError, ImportError, AttributeError, TypeError):
        return False, "linux_game_anchor_inspection_failed"
    if (sampled.get("state") != "linux_runtime_anchor_stable"
            or sampled.get("samples_completed") != 3
            or sampled.get("linux_process_identity_stable") is not True
            or sampled.get("same_prefix_wineserver_observed") is not True
            or sampled.get("anchored_linux_pid") != pid
            or sampled.get("anchored_process_start_ticks") != ticks):
        return False, "linux_game_anchor_not_stable"
    return True, "linux_game_anchor_stable"


def _load_session_lock():
    source = Path(__file__).with_name("gameweld-wand-v2-session-lock.py")
    spec = importlib.util.spec_from_file_location("gameweld_wand_v2_session_lock", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("session_lock_source_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_possible_provider_residue(appid: int, compatdata: Path) -> dict:
    """Advisory post-session evidence, not GameWeld-owned cleanup proof."""
    source = Path(__file__).with_name("gameweld-wand-v2-residue-audit.py")
    try:
        spec = importlib.util.spec_from_file_location("gameweld_wand_residue_for_session", source)
        if spec is None or spec.loader is None:
            raise RuntimeError("residue_source_missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.report_possible_residue(appid, compatdata)
        if report.get("state") != "read_only_provider_residue_audit":
            raise RuntimeError("residue_scan_unavailable")
        count = report.get("same_prefix_provider_candidate_count")
        if type(count) is not int or count < 0:
            raise RuntimeError("residue_scan_invalid_count")
        return {
            "provider_residue_audit_state": "read_only_provider_residue_audit",
            "same_prefix_provider_candidate_count": count,
            "provider_process_ownership_verified": False,
        }
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError, ImportError):
        return {
            "provider_residue_audit_state": "residue_audit_unavailable",
            "same_prefix_provider_candidate_count": None,
            "provider_process_ownership_verified": False,
        }


def _run_guarded_session(a, blocked, source):
    # Fail closed before starting any upstream DeckCheatz session.
    # The existence of a localhost monitor endpoint and an opaque token does
    # not by itself prove a trusted Win32 process/attachment identity.
    game_ok, game_reason = verify_running_linux_game(a.appid, a.compatdata, a.game_exe)
    if not game_ok:
        return blocked(game_reason)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(source) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    command = [sys.executable, "-m", "wand_launcher.entrypoint", "--no-prompt",
               "--appid", str(a.appid), "--compatdata", str(a.compatdata),
               "--client-exe", str(a.client), "--game-exe", str(a.game_exe),
               "--monitor-endpoint", a.monitor_endpoint, "--run-attached-monitor", "--observe-existing-game"]
    # The upstream child is directly owned by this bridge. Stream stdout into a
    # bounded memory buffer; never let 24 hours of logs grow capture_output.
    try:
        result = execute_bounded_monitor(command, env)
    except RuntimeError as exc:
        allowed = {
            "upstream_monitor_invalid_limits", "upstream_monitor_spawn_failed",
            "upstream_monitor_direct_child_unreaped", "upstream_monitor_timeout",
            "upstream_monitor_output_pipe_not_closed", "upstream_monitor_output_read_failed",
            "upstream_monitor_output_limit_exceeded", "upstream_monitor_output_not_utf8",
            "upstream_monitor_runner_missing",
        }
        return blocked(str(exc) if str(exc) in allowed else "upstream_monitor_session_failed")
    except (OSError, subprocess.TimeoutExpired):
        return blocked("upstream_monitor_session_failed")
    if result.returncode:
        return blocked("upstream_monitor_rejected")
    try:
        report = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        return blocked("upstream_session_report_invalid")
    if not isinstance(report, dict):
        return blocked("upstream_session_report_invalid")
    if "appid" in report and (type(report["appid"]) is not int or report["appid"] != a.appid):
        return blocked("upstream_appid_mismatch")
    # This is an observe-existing-game bridge; an upstream claim to have
    # launched the actual Steam game means session ownership has diverged.
    if report.get("game_started_by_monitor") is True:
        return blocked("upstream_unexpected_game_launch")
    if report.get("state") != "monitor_session_finished":
        return blocked("upstream_monitor_not_finished")
    if report.get("game_started") is not True or report.get("trainer_process_started") is not True:
        return blocked("upstream_monitor_partial_start")
    if type(report.get("game_exit_code")) is not int:
        return blocked("upstream_game_exit_unreported")
    if report.get("trainer_cleanup_verified") is not True:
        return blocked("upstream_trainer_cleanup_unverified")
    residue = inspect_possible_provider_residue(a.appid, a.compatdata)
    print(json.dumps({"state": "gameweld_wand_v2_session_finished", "appid": a.appid,
                      **residue,
                      "game_exit_code": report.get("game_exit_code"),
                      "game_started": report.get("game_started", False),
                      "trainer_process_started": report.get("trainer_process_started", False),
                      "trainer_attachment_verified": False,
                      "trainer_cleanup_verified": False,
                      "upstream_trainer_cleanup_reported": True,
                      "steam_launch_options_changed": False, "game_prefix_modified": False}))
    return 0

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
    # A private, nonblocking per-AppID flock is held throughout the
    # expensive liveness gate and complete upstream child lifecycle.
    # A second GameWeld instance cannot start another monitor for this AppID.
    try:
        lock_impl = _load_session_lock()
        lock_fd = lock_impl.acquire_session_lock(a.appid)
    except RuntimeError as exc:
        reason = str(exc)
        known = {
            "duplicate_gameweld_session", "invalid_session_appid",
            "unsafe_session_runtime_directory",
            "session_runtime_directory_not_private",
            "session_runtime_directory_unavailable", "session_lock_unavailable",
            "unsafe_session_lock_file", "session_lock_path_changed",
            "session_lock_source_missing",
        }
        return blocked(reason if reason in known else "gameweld_session_lock_failed")
    except (OSError, ValueError):
        return blocked("gameweld_session_lock_failed")
    try:
        return _run_guarded_session(a, blocked, source)
    finally:
        lock_impl.release_session_lock(lock_fd)

if __name__ == "__main__":
    sys.exit(run())
