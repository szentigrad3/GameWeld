#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-check untrusted Win32 observer *claims* against a pinned Steam game.

The observer report is untrusted input, not an authenticated Windows process
handle. Matching path, AppID and Linux birth token is candidate-level evidence
ONLY; never turn a reported Windows PID into an attachment authorization.
No Wine, game, trainer, process signals or Steam settings are involved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

WIN_PATH = re.compile(r"^([A-Za-z]):[\\/]([^\x00\r\n]*)$")
MAX_WIN_PATH = 4096


def drive_path_to_existing_file(prefix: Path, reported: str) -> Path | None:
    """Resolve a DOS drive through Wine's existing dosdevices mapping.

    Never trust UNC/device paths, relative paths, parent traversal or symlink
    escape. Prefix mapping is read-only and must already exist.
    """
    if not isinstance(reported, str) or not 3 <= len(reported) <= MAX_WIN_PATH:
        return None
    match = WIN_PATH.fullmatch(reported)
    if match is None:
        return None
    drive, remainder = match.groups()
    fields = re.split(r"[\\/]", remainder)
    if not fields or any(x in ("", ".", "..") or ":" in x for x in fields):
        return None
    try:
        prefix = prefix.resolve(strict=True)
        if not prefix.is_dir():
            return None
        link = prefix / "dosdevices" / (drive.lower() + ":")
        if not link.is_symlink():
            return None
        root = link.resolve(strict=True)
        if not root.is_dir():
            return None
        target = root.joinpath(*fields).resolve(strict=True)
        if not target.is_file() or not target.is_relative_to(root):
            return None
        return target
    except (OSError, RuntimeError, ValueError):
        return None


def compare_observer_claim(
    appid: int,
    compatdata: Path,
    game_exe: Path,
    linux_anchor: dict,
    observer: dict,
) -> dict:
    """Validate a read-only evidence contract, never Win32 attestation.

    Returns diagnostic candidate correlation, with all authoritative Win32
    verification and trainer/cleanup flags deliberately FALSE.
    """
    result = {
        "appid": appid,
        "state": "observer_evidence_rejected",
        "reason": "invalid_observer_evidence",
        "linux_game_identity_correlated": False,
        "observer_path_correlated": False,
        "observer_win32_pid_reported": False,
        "win32_pid_verified": False,
        "exact_runtime_verified": False,
        "monitor_authenticated": False,
        "monitor_attached": False,
        "trainer_launched": False,
        "trainer_attachment_verified": False,
        "trainer_cleanup_verified": False,
        "game_prefix_modified": False,
        "steam_configuration_written": False,
        "steam_launch_options_changed": False,
        "processes_signalled": 0,
    }
    if type(appid) is not int or appid < 1 or not isinstance(linux_anchor, dict):
        result["reason"] = "invalid_selected_game_identity"
        return result
    if not isinstance(observer, dict):
        return result
    if compatdata.name != str(appid) or not game_exe.is_absolute():
        result["reason"] = "inconsistent_selected_paths"
        return result
    try:
        compatdata = compatdata.resolve(strict=True)
        prefix = (compatdata / "pfx").resolve(strict=True)
        game_exe = game_exe.resolve(strict=True)
        if not prefix.is_dir() or not game_exe.is_file():
            raise ValueError("not a file/directory")
    except (OSError, ValueError, RuntimeError):
        result["reason"] = "selected_paths_unavailable"
        return result

    pid = linux_anchor.get("anchored_linux_pid", linux_anchor.get("candidate_linux_pid"))
    ticks = linux_anchor.get("anchored_process_start_ticks",
                             linux_anchor.get("candidate_start_time_ticks"))
    if (linux_anchor.get("appid") != appid
            or linux_anchor.get("state") != "linux_runtime_anchor_stable"
            or linux_anchor.get("linux_process_identity_stable") is not True
            or linux_anchor.get("same_prefix_wineserver_observed") is not True
            or type(pid) is not int or pid < 1
            or type(ticks) is not int or ticks < 1
            or linux_anchor.get("samples_completed") != 3):
        result["reason"] = "linux_anchor_not_fully_revalidated"
        return result
    result["linux_game_identity_correlated"] = True

    # The Windows observer must explicitly identify the *existing* game, not
    # report launching another instance, and must not claim multiple matches.
    if (observer.get("appid") != appid
            or observer.get("game_started_by_monitor") is not False
            or observer.get("candidate_count") != 1):
        result["reason"] = "observer_game_or_candidate_mismatch"
        return result
    if (observer.get("linux_game_pid") != pid
            or observer.get("linux_game_start_ticks") != ticks):
        result["reason"] = "observer_linux_session_mismatch"
        return result

    win_pid = observer.get("win32_game_pid")
    if type(win_pid) is not int or not 1 <= win_pid <= 0xFFFFFFFF:
        result["reason"] = "win32_process_id_not_reported"
        return result
    result["observer_win32_pid_reported"] = True
    candidate = drive_path_to_existing_file(prefix, observer.get("win32_game_executable"))
    if candidate is None or candidate != game_exe:
        result["reason"] = "observer_game_executable_mismatch"
        return result
    result["observer_path_correlated"] = True
    result["state"] = "observer_candidate_evidence_correlated"
    result["reason"] = "untrusted_observer_claim_requires_authenticated_win32_monitor"
    # Even positive evidence is insufficient: no authenticated monitor
    # handshake, protected Windows process handle, or trainer attach proof.
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only comparison of untrusted Win32 observer evidence")
    p.add_argument("--appid", required=True, type=int)
    p.add_argument("--compatdata", required=True, type=Path)
    p.add_argument("--game-exe", required=True, type=Path)
    p.add_argument("--linux-anchor-json", required=True, type=Path)
    p.add_argument("--observer-json", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        # Bound potentially untrusted reports before JSON parsing.
        if (a.linux_anchor_json.stat().st_size > 131072
                or a.observer_json.stat().st_size > 131072):
            raise ValueError("evidence too large")
        anchor = json.loads(a.linux_anchor_json.read_text(encoding="utf-8"))
        observer = json.loads(a.observer_json.read_text(encoding="utf-8"))
        report = compare_observer_claim(a.appid, a.compatdata, a.game_exe, anchor, observer)
    except (OSError, UnicodeError, ValueError, TypeError):
        report = {"appid": a.appid, "state": "observer_evidence_rejected",
                  "reason": "input_evidence_unavailable_or_invalid",
                  "win32_pid_verified": False, "trainer_attachment_verified": False,
                  "monitor_attached": False, "steam_configuration_written": False,
                  "processes_signalled": 0}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] == "observer_candidate_evidence_correlated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
