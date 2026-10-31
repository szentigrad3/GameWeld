#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only same-prefix WeMod/Wand process residue audit for GameWeld.

A process is a *candidate*, NOT a verified GameWeld-owned process. A prefix
can be shared with other tools. Never terminate a game/Steam/Wine/helper or
trainers based on names, paths or this read-only report.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

PROVIDER_NAMES = frozenset(("wemod.exe", "wand.exe"))
GAME_ID_KEYS = ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")


def _live_context():
    file = Path(__file__).with_name("gameweld-wand-v2-live-context.py")
    spec = importlib.util.spec_from_file_location("gameweld_context_for_residue", file)
    if spec is None or spec.loader is None:
        raise RuntimeError("process_context_source_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_possible_residue(appid: int, compatdata: Path, *,
                            proc_root: Path = Path("/proc"),
                            uid: int | None = None, context=None) -> dict:
    result = {
        "appid": appid,
        "state": "read_only_provider_residue_audit",
        "reason": "none_observed",
        "same_prefix_provider_candidates": [],
        "same_prefix_provider_candidate_count": 0,
        "provider_process_ownership_verified": False,
        "trainer_cleanup_verified": False,
        "processes_signalled": 0,
        "steam_configuration_written": False,
        "steam_launch_options_changed": False,
        "game_prefix_modified": False,
    }
    if type(appid) is not int or appid < 1 or compatdata.name != str(appid):
        result["state"] = "residue_audit_unavailable"
        result["reason"] = "invalid_appid_or_compatdata"
        return result
    try:
        selected = (compatdata / "pfx").resolve(strict=True)
        if not (selected / "drive_c").is_dir():
            raise ValueError("missing selected prefix")
    except (OSError, RuntimeError, ValueError):
        result["state"] = "residue_audit_unavailable"
        result["reason"] = "selected_prefix_unavailable"
        return result
    if uid is None:
        uid = os.geteuid()
    if context is None:
        context = _live_context()
    try:
        pids = sorted((x for x in proc_root.iterdir() if x.name.isdecimal()),
                      key=lambda x: int(x.name))
    except OSError:
        result["state"] = "residue_audit_unavailable"
        result["reason"] = "proc_directory_unavailable"
        return result
    if len(pids) > 20000:
        result["state"] = "residue_audit_unavailable"
        result["reason"] = "too_many_processes_for_bounded_audit"
        return result
    for proc in pids:
        try:
            if proc.stat().st_uid != uid:
                continue
            original = context.process_start_ticks(proc)
            if original is None or original < 1:
                continue
            env = context.read_environment(proc / "environ")
            if not env.get("WINEPREFIX"):
                continue
            if Path(env["WINEPREFIX"]).resolve(strict=True) != selected:
                continue
            ids = [env[k] for k in GAME_ID_KEYS if k in env]
            if ids and any(x != str(appid) for x in ids):
                continue
            loader = context.linux_loader_basename(proc)
            if loader not in context.WINE_LOADERS:
                continue
            comm = (context.read_small(proc / "comm") or b"").decode("utf-8", "replace").strip()
            argv = context.argv_parts(context.read_small(proc / "cmdline"))
            names = {arg.replace("\\", "/").rsplit("/", 1)[-1].casefold() for arg in argv}
            providers = sorted(PROVIDER_NAMES.intersection(names))
            if not providers:
                continue
            if not any(context.game_comm_matches(comm, name) for name in providers):
                continue
            if not context.wine_modules_mapped(proc):
                continue
            if (context.process_start_ticks(proc) != original
                    or proc.stat().st_uid != uid):
                continue
            # Exact AppID and prefix markers must still hold where supplied.
            current_env = context.read_environment(proc / "environ")
            if not current_env.get("WINEPREFIX"):
                continue
            if Path(current_env["WINEPREFIX"]).resolve(strict=True) != selected:
                continue
            current_ids = [current_env[k] for k in GAME_ID_KEYS if k in current_env]
            if current_ids and any(x != str(appid) for x in current_ids):
                continue
            result["same_prefix_provider_candidates"].append({
                "linux_pid": int(proc.name),
                "linux_start_ticks": original,
                "provider_basename": providers[0],
            })
        except (OSError, RuntimeError, ValueError, TypeError):
            continue
    result["same_prefix_provider_candidate_count"] = len(result["same_prefix_provider_candidates"])
    if result["same_prefix_provider_candidate_count"]:
        result["reason"] = "possible_provider_processes_present_ownership_unverified"
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only potential WeMod/Wand residue audit")
    p.add_argument("--appid", required=True, type=int)
    p.add_argument("--compatdata", required=True, type=Path)
    a = p.parse_args(argv)
    report = report_possible_residue(a.appid, a.compatdata)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] == "read_only_provider_residue_audit" else 2


if __name__ == "__main__":
    raise SystemExit(main())
