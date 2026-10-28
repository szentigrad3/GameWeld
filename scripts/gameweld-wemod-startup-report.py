#!/usr/bin/env python3
"""Read-only, privacy-preserving triage of one GameWeld WeMod Proton launch.

Finds the latest same-user per-AppID private log. Reports only fixed category
labels/counts, never raw log text, Steam options, user paths or secrets.
A Proton subprocess or log entry does NOT establish WeMod window or attachment.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

MAX_LOG_BYTES = 16 * 1024 * 1024
TAIL_BYTES = 64 * 1024
VALID_APPID = re.compile(r"[1-9][0-9]{0,9}\Z")

# Fixed, public labels; no captured log text may appear in report.
PATTERNS = {
    "proton_command_or_verb_rejected": re.compile(
        rb"unknown (?:command|verb|action)|invalid (?:command|verb|action)|unrecognised (?:command|verb)", re.I),
    "proton_or_steam_runtime_error": re.compile(
        rb"proton.{0,90}(?:error|fail|missing|traceback)|steam compat.{0,70}(?:error|missing)|pressure.vessel.{0,70}(?:failed|error)", re.I),
    "wine_process_creation_failed": re.compile(
        rb"failed to (?:start|launch|create|execute)|wine:.*(?:error|failed)|could not (?:execute|start|launch)", re.I),
    "missing_file_or_dll": re.compile(
        rb"no such file or directory|file not found|filenotfounderror|module not found|cannot find|failed to load.{0,70}(?:dll|so)", re.I),
    "prefix_or_configuration_problem": re.compile(
        rb"wineprefix|compatdata|prefix.{0,70}(?:not found|missing|failed|error)|wine server", re.I),
    "electron_gpu_or_vulkan_problem": re.compile(
        rb"gpu.process|gpu process|gpu.*error.code|vk_error|vulkan.*(?:error|fail)|failed to initialize.*gpu|error_code.?43", re.I),
    "window_or_display_problem": re.compile(
        rb"(?:x11|wayland|display|xserver|window).{0,70}(?:error|failed|not found|unavailable)|cannot open display", re.I),
    "python_traceback_or_exception": re.compile(
        rb"traceback \(most recent call last\)|(?:syntaxerror|valueerror|importerror|runtimeerror|oserror|typeerror):", re.I),
    "network_or_authentication_problem": re.compile(
        rb"(?:download|https?|connection|authentication|login).{0,60}(?:failed|error|refused|timed out)", re.I),
    "other_failure_keyword": re.compile(rb"error|fatal|fail(?:ed|ure)?|exception|could not|unable to", re.I),
}
# Specific fixed GPU/Electron signatures. Counts may include repeated copies
# of the same error; never serialize raw lines, paths, error codes or tokens.
GPU_SIGNATURES = {
    "gpu_process_launch_failed": re.compile(rb"gpu process launch failed", re.I),
    "gpu_process_exited_unexpectedly": re.compile(rb"gpu process exited unexpectedly", re.I),
    "gpu_process_not_usable": re.compile(rb"gpu process isn.t usable", re.I),
    "gpu_process_crashed": re.compile(rb"gpu.process.{0,50}(?:crash|terminated)", re.I),
    "vulkan_initialization_failed": re.compile(
        rb"(?:vulkan|vk_error).{0,75}(?:error|fail|unavailable|unsupported)", re.I),
    "direct_composition_error": re.compile(rb"direct.composition.{0,80}(?:error|fail)", re.I),
    "gpu_sandbox_failure": re.compile(rb"gpu.sandbox.{0,80}(?:error|fail)", re.I),
}

STAGES = {
    "proton_invoked": re.compile(rb"Proton:|runinprefix", re.I),
    "wine_invoked": re.compile(rb"\bwine(?:64)?(?:-preloader)?\b|wineserver", re.I),
    "wemod_executable_mentioned": re.compile(rb"WeMod\.exe", re.I),
    "electron_mentioned": re.compile(rb"electron|chromium", re.I),
}


class Blocked(ValueError):
    pass


def default_log_root(*, v2: bool = False) -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg and not Path(xdg).is_absolute():
        raise Blocked("XDG_STATE_HOME is not absolute")
    base = Path(xdg) if xdg else Path.home() / ".local/state"
    return base / ("wand/sessions" if v2 else "gameweld/wemod-live")


def choose_log(appid: str, root: Path) -> Path:
    if not root.is_dir() or root.is_symlink():
        raise Blocked("Private WeMod log directory missing or symlinked")
    matches = []
    with os.scandir(root) as entries:
        for item in entries:
            if len(matches) >= 2000:
                raise Blocked("Too many candidate log files")
            if not item.name.startswith(appid + "-") or not item.name.endswith(".log"):
                continue
            if not re.fullmatch(re.escape(appid) + r"-[0-9]{12,25}\.log", item.name):
                continue
            try:
                if item.is_file(follow_symlinks=False):
                    st = item.stat(follow_symlinks=False)
                    if st.st_uid == os.getuid() and st.st_size <= MAX_LOG_BYTES:
                        matches.append((st.st_mtime_ns, Path(item.path)))
            except OSError:
                continue
    if not matches:
        raise Blocked("No GameWeld per-AppID WeMod launch log found")
    return max(matches, key=lambda x: x[0])[1]


def summarize(appid: str, path: Path) -> dict:
    if not VALID_APPID.fullmatch(appid) or int(appid) >= 2 ** 32:
        raise Blocked("Invalid Steam AppID")
    if path.is_symlink():
        raise Blocked("Refusing symlinked log")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_size > MAX_LOG_BYTES):
            raise Blocked("Unsafe owner, file type or log size")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            stream.seek(max(0, st.st_size - TAIL_BYTES))
            data = stream.read(TAIL_BYTES + 1)
        if len(data) > TAIL_BYTES:
            raise Blocked("Log read exceeded bound")
    finally:
        os.close(fd)
    lines = data.splitlines()
    counts = {name: sum(bool(rx.search(line[:4096])) for line in lines)
              for name, rx in PATTERNS.items()}
    stages = {name: sum(bool(rx.search(line[:4096])) for line in lines)
              for name, rx in STAGES.items()}
    gpu_signatures = {name: sum(bool(rx.search(line[:4096])) for line in lines)
                      for name, rx in GPU_SIGNATURES.items()}
    return {
        "steam_appid": appid,
        "state": "redacted_log_triage",
        "source": "latest_owned_gameweld_wemod_live_log",
        "total_log_bytes": st.st_size,
        "bytes_examined": len(data),
        "lines_examined": len(lines),
        "failure_category_counts": {k: v for k, v in counts.items() if v},
        "observed_stage_marker_counts": {k: v for k, v in stages.items() if v},
        "gpu_failure_signature_counts": {k: v for k, v in gpu_signatures.items() if v},
        "category_counts_may_overlap_or_repeat": True,
        "raw_log_content_included": False,
        "steam_options_changed": False,
        "game_launched_by_diagnostic": False,
        "wemod_window_verified": False,
        "trainer_attachment_verified": False,
        "note": ("These are possible causes, not proof. An empty category list "
                 "does not prove that WeMod opened, and the launcher may have "
                 "exited without writing a useful error."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--log", type=Path, help="explicit same-user private log (otherwise latest matching AppID)")
    parser.add_argument("--v2", action="store_true", help="use isolated Wand v2 private session logs, never legacy handoff logs")
    args = parser.parse_args(argv)
    try:
        if not VALID_APPID.fullmatch(args.appid) or int(args.appid) >= 2 ** 32:
            raise Blocked("Invalid Steam AppID")
        path = args.log if args.log is not None else choose_log(
            args.appid, default_log_root(v2=args.v2))
        result = summarize(args.appid, path)
        result["launcher_channel"] = "wand_v2_private_session" if args.v2 else "gameweld_live_handoff"
        result["source"] = ("latest_owned_wand_v2_private_session_log" if args.v2
                            else "latest_owned_gameweld_wemod_live_log")
    except (Blocked, OSError) as exc:
        # Do not return exception text containing a user-supplied path.
        print(json.dumps({"steam_appid": args.appid,
                          "state": "triage_blocked",
                          "reason": "Log missing, unreadable, unsafe or ambiguous",
                          "raw_log_content_included": False}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
