#!/usr/bin/env python3
"""Compare two read-only GameWeld Steam diagnostics from one test session.

No process actions, Steam changes, raw logs, command lines, environment values,
or original Steam launch-option text. Results are observations, not proof that
WeMod attached or that all Wine/Proton processes have exited.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat

MAX_JSON_BYTES = 1048576


class CompareBlocked(ValueError):
    pass


def read_snapshot(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise CompareBlocked("Snapshot is missing or symlinked")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise CompareBlocked("Snapshot is oversized")
    with path.open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise CompareBlocked("Snapshot is oversized")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CompareBlocked("Snapshot contains invalid JSON") from exc
    if not isinstance(value, dict) or value.get("mode") != "read_only":
        raise CompareBlocked("Expected a read-only GameWeld diagnostic")
    return value


def count(lifecycle: dict, name: str) -> int | None:
    v = lifecycle.get(name)
    return v if type(v) is int and 0 <= v <= 100000 else None


def snapshot_launchers(record: dict, *, scoped: bool) -> dict:
    key = ("selected_appid_launcher_processes" if scoped
           else "recognized_launcher_processes")
    rows = record.get(key, [])
    if not isinstance(rows, list):
        return {}
    counts: dict[str, int] = {}
    for row in rows[:256]:
        if not isinstance(row, dict):
            continue
        if scoped and row.get("exact_appid_environment_observed") is not True:
            continue
        role = row.get("kind")
        if role in ("gameweld_one_shot_steam_shim", "deckcheatz_or_wemod", "proton"):
            counts[role] = counts.get(role, 0) + 1
    return counts


def first_log(record: dict) -> dict | None:
    logs = record.get("deckcheatz_logs")
    if isinstance(logs, list) and len(logs) == 1 and isinstance(logs[0], dict):
        return logs[0]
    return None


def log_delta(live: dict, after: dict) -> dict:
    a, b = first_log(live), first_log(after)
    if not a or not b:
        return {"state": "unavailable_or_ambiguous"}
    x, y = a.get("size_bytes"), b.get("size_bytes")
    if (type(x) is not int or type(y) is not int or x < 0 or y < 0
            or y < x or b.get("modified_utc", "") < a.get("modified_utc", "")):
        return {"state": "log_replaced_truncated_or_unverifiable"}
    before = a.get("error_indicators", {})
    end = b.get("error_indicators", {})
    if not isinstance(before, dict) or not isinstance(end, dict):
        return {"state": "invalid_indicators"}
    changes = {}
    for key in sorted(set(before) | set(end)):
        va, vb = before.get(key, 0), end.get(key, 0)
        if type(va) is not int or type(vb) is not int or va < 0 or vb < 0:
            return {"state": "invalid_indicators"}
        changes[key] = vb - va
    return {
        "state": "append_consistent_size_and_time",
        "bytes_added_between_snapshots": y - x,
        "historical_keyword_count_changes": changes,
        "warning": ("Keyword differences cannot identify a specific error, "
                    "prove it was caused by GameWeld, or confirm trainer attachment."),
        "raw_log_lines_included": False,
    }


def compare(live: dict, after: dict) -> dict:
    appid = live.get("steam_appid")
    if (not isinstance(appid, str) or not appid.isdecimal()
            or not 0 < int(appid) < 2**32 or
            after.get("steam_appid") != appid):
        raise CompareBlocked("Both snapshots must use the same valid Steam AppID")
    if live.get("mode") != "read_only" or after.get("mode") != "read_only":
        raise CompareBlocked("Only read-only GameWeld diagnostics may be compared")
    ll, al = live.get("lifecycle"), after.get("lifecycle")
    if not isinstance(ll, dict) or not isinstance(al, dict):
        raise CompareBlocked("Missing GameWeld lifecycle evidence")
    observed = count(ll, "game_executable_candidates")
    ended = count(al, "game_executable_candidates")
    active = count(ll, "total_appid_associated_processes")
    remains = count(al, "total_appid_associated_processes")
    if any(v is None for v in (observed, ended, active, remains)):
        raise CompareBlocked("Incomplete or invalid process counts")
    scoped = ("selected_appid_launcher_processes" in live and
              "selected_appid_launcher_processes" in after)
    launcher_live = snapshot_launchers(live, scoped=scoped)
    launcher_after = snapshot_launchers(after, scoped=scoped)
    return {
        "steam_appid": appid,
        "result": ("game_executable_observed_and_appid_associations_cleared"
                   if observed > 0 and ended == 0 and remains == 0
                   else "game_or_exit_evidence_incomplete"),
        "game_executable_candidates_live": observed,
        "game_executable_candidates_after_exit": ended,
        "appid_associated_processes_live": active,
        "appid_associated_processes_after_exit": remains,
        "launcher_observation_scope": (
            "exact_same_user_appid_environment_matches"
            if scoped else "same_user_only_not_appid_specific"),
        "launcher_processes_live": launcher_live,
        "launcher_processes_after_exit": launcher_after,
        "saved_launch_options_live": live.get("saved_steam_launch_options", {}).get("state"),
        "saved_launch_options_after_exit": after.get("saved_steam_launch_options", {}).get("state"),
        "one_shot_token_live": live.get("pending_one_shot", {}).get("state"),
        "one_shot_token_after_exit": after.get("pending_one_shot", {}).get("state"),
        "deckcheatz_log_changes": log_delta(live, after),
        "game_window_verified": False,
        "wemod_trainer_attachment_verified": False,
        "all_wemod_processes_terminated_verified": False,
        "explanation": (
            "Zero associated processes is an observation, not a verified clean "
            "shutdown. Same-user Proton processes may belong to other games. "
            "A started WeMod launcher does not prove trainer attachment."
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", type=Path, required=True)
    p.add_argument("--after-exit", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = compare(read_snapshot(args.live), read_snapshot(args.after_exit))
    except (OSError, CompareBlocked) as exc:
        p.exit(2, "GameWeld session comparison BLOCKED: " + str(exc) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
