#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only AIO Steam AppID -> unique live game -> bounded Linux PID anchor.

Uses existing Steam library VDF parsing and the Batch 13/14 identity checks.
Does not guess between installations, processes, Wine prefixes or game EXEs.
Never starts Steam, Proton, Wine, the monitor, a trainer, or a game.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def load_sibling(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location("gw_" + name.replace("-", "_").replace(".", "_"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError("required_gameweld_component_missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def canonical_dir(path: Path) -> Path | None:
    try:
        real = path.resolve(strict=True)
        return real if real.is_dir() else None
    except (OSError, RuntimeError):
        return None


def manifest_installdir(steam, manifest: Path, appid: int) -> str | None:
    try:
        if not manifest.is_file() or manifest.stat().st_size > 1024 * 1024:
            return None
        tree = steam.parse_text_vdf(manifest)
        state = steam._ci_get(tree, "AppState")
        if not isinstance(state, dict):
            return None
        if str(steam._ci_get(state, "appid")) != str(appid):
            return None
        name = steam._ci_get(state, "installdir")
        if (not isinstance(name, str) or not name.strip()
                or name in (".", "..") or Path(name).name != name
                or "/" in name or "\\" in name):
            return None
        return name
    except (OSError, ValueError, TypeError, RuntimeError):
        return None


def discover(appid: int, steam_root: Path, *,
             proc_root: Path = Path("/proc"), uid: int | None = None,
             steam=None, context=None) -> dict:
    summary = dict(
        appid=appid, state="live_game_not_found", reason="no_matching_steam_session",
        steam_library_count=0, manifest_install_dirs_found=0,
        existing_compatdata_prefixes_found=0, verified_full_exe_path_count=0,
        unique_linux_game_candidate=False, game_executable_basename=None,
        steam_configuration_written=False, steam_launch_options_changed=False,
        game_prefix_modified=False, win32_pid_verified=False,
        exact_runtime_verified=False, trainer_launched=False,
        trainer_attachment_verified=False, processes_signalled=0,
    )
    if type(appid) is not int or appid <= 0:
        summary["reason"] = "invalid_steam_appid"
        return summary
    try:
        steam_root = steam_root.resolve(strict=True)
    except (OSError, RuntimeError):
        summary["reason"] = "steam_root_not_found"
        return summary
    if steam is None:
        steam = load_sibling("gameweld-steam-shortcuts.py")
    if context is None:
        context = load_sibling("gameweld-wand-v2-live-context.py")
    if uid is None:
        uid = os.geteuid()

    libraries = []
    for path in steam.steam_library_roots(steam_root):
        real = canonical_dir(path)
        if real is not None and real not in libraries:
            libraries.append(real)
    summary["steam_library_count"] = len(libraries)
    if len(libraries) > 64:
        summary["reason"] = "too_many_steam_libraries"
        return summary

    installs: list[Path] = []
    compatdatas: list[Path] = []
    for library in libraries:
        name = manifest_installdir(steam, library / "steamapps" / f"appmanifest_{appid}.acf", appid)
        if name:
            install = canonical_dir(library / "steamapps/common" / name)
            if install is not None and install not in installs:
                installs.append(install)
        compat = library / "steamapps/compatdata" / str(appid)
        if (compat / "pfx/drive_c").is_dir():
            real = canonical_dir(compat)
            if real is not None and real not in compatdatas:
                compatdatas.append(real)
    summary["manifest_install_dirs_found"] = len(installs)
    summary["existing_compatdata_prefixes_found"] = len(compatdatas)
    if not installs or not compatdatas:
        summary["reason"] = "game_manifest_or_compatdata_missing"
        return summary

    # Collect full-path provenance from launcher argv. This is only a
    # candidate source: the exact game PID is verified separately below.
    candidates: set[tuple[Path, Path]] = set()
    try:
        proc_entries = sorted((d for d in proc_root.iterdir() if d.name.isdecimal()),
                              key=lambda p: int(p.name))
    except OSError:
        summary["reason"] = "proc_directory_unreadable"
        return summary

    for proc in proc_entries[:10000]:
        try:
            if proc.stat().st_uid != uid:
                continue
            env = context.read_environment(proc / "environ")
            compatible = [compat for compat in compatdatas
                          if context.exact_identity(env, appid, compat, compat / "pfx")]
            if not compatible:
                continue
            raw_args = context.read_small(proc / "cmdline")
            for arg in context.argv_parts(raw_args):
                path = Path(arg)
                if not path.is_absolute() or path.suffix.casefold() != ".exe":
                    continue
                try:
                    real = path.resolve(strict=True)
                    if not real.is_file():
                        continue
                except (OSError, RuntimeError):
                    continue
                if any(real.is_relative_to(install) for install in installs):
                    for compat in compatible:
                        candidates.add((compat, real))
        except (OSError, ValueError, RuntimeError):
            continue
        if len(candidates) > 64:
            summary["reason"] = "too_many_executable_candidates"
            return summary

    summary["verified_full_exe_path_count"] = len({exe for _, exe in candidates})
    matched = []
    for compat, exe in sorted(candidates, key=lambda pair: (str(pair[0]), str(pair[1]))):
        evidence = context.inspect_context(appid, compat, exe, proc_root=proc_root, uid=uid)
        if (evidence.get("state") == "linux_game_process_candidate_correlated"
                and evidence.get("exact_prefix_identity_crosschecked") is True
                and len(evidence.get("game_process_candidate_pids", [])) == 1):
            matched.append((compat, exe, evidence))
    if len(matched) != 1:
        summary["reason"] = ("ambiguous_live_game_candidates" if len(matched) > 1
                             else "no_unique_linux_game_process_identity")
        return summary
    compat, exe, evidence = matched[0]
    summary["state"] = "linux_game_candidate_discovered"
    summary["reason"] = "fresh_pid_liveness_not_yet_sampled"
    summary["unique_linux_game_candidate"] = True
    summary["game_executable_basename"] = exe.name
    summary["candidate_linux_pid"] = evidence["candidate_linux_pid"]
    summary["candidate_start_time_ticks"] = evidence["candidate_start_time_ticks"]
    # Internal paths are not included in the JSON output. An on-disk run
    # re-discovers them on every invocation; no cached path/PID authorization.
    return dict(summary, _compatdata=compat, _game_exe=exe)


def run(appid: int, steam_root: Path, *,
        samples: int = 3, interval_ms: int = 400,
        proc_root: Path = Path("/proc"), uid: int | None = None,
        steam=None, context=None, anchor=None) -> dict:
    details = discover(appid, steam_root, proc_root=proc_root, uid=uid,
                       steam=steam, context=context)
    compat = details.pop("_compatdata", None)
    exe = details.pop("_game_exe", None)
    if compat is None or exe is None:
        return details
    if anchor is None:
        anchor = load_sibling("gameweld-wand-v2-live-anchor.py")
    if context is None:
        context = load_sibling("gameweld-wand-v2-live-context.py")
    inspector = lambda ident, prefix, binary: context.inspect_context(
        ident, prefix, binary, proc_root=proc_root, uid=uid)
    evidence = anchor.verify_anchor(appid, compat, exe,
                                    pid=details["candidate_linux_pid"],
                                    start_ticks=details["candidate_start_time_ticks"],
                                    samples=samples, interval_ms=interval_ms,
                                    inspector=inspector)
    details["state"] = evidence["state"]
    details["reason"] = evidence["reason"]
    details["samples_completed"] = evidence["samples_completed"]
    details["samples_requested"] = evidence["samples_requested"]
    details["linux_process_identity_stable"] = evidence["linux_process_identity_stable"]
    details["same_prefix_wineserver_observed"] = evidence["same_prefix_wineserver_observed"]
    return details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only GameWeld Steam game ID + liveness AIO")
    parser.add_argument("--appid", required=True, type=int)
    parser.add_argument("--steam-root", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-ms", type=int, default=400)
    args = parser.parse_args(argv)
    try:
        result = run(args.appid, args.steam_root,
                     samples=args.samples, interval_ms=args.interval_ms)
    except (OSError, ValueError, RuntimeError):
        result = dict(appid=args.appid, state="live_game_not_found",
                      reason="runtime_inspection_failed",
                      trainer_attachment_verified=False, win32_pid_verified=False,
                      steam_configuration_written=False, game_prefix_modified=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "linux_runtime_anchor_stable" else 2


if __name__ == "__main__":
    sys.exit(main())
