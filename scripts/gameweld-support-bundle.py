#!/usr/bin/env python3
"""Create a narrowly scoped GameWeld support bundle for one selected game.

The bundle intentionally avoids global environment dumps and unrelated game logs.
It contains only the selected game's resolved launch metadata, trainer diagnostics,
Trainer Library rows that match that game, Compatibility Engine v2 recipe/evidence diagnostics, and GameWeld state logs whose filename
is tied to that selected app/runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _xdg_dir(var: str, fallback: Path) -> Path:
    v = os.environ.get(var, "").strip()
    return Path(v).expanduser() if v else fallback


HOME = Path.home()
STATE = _xdg_dir("XDG_STATE_HOME", HOME / ".local/state") / "gameweld"
DOWNLOADS = Path(os.environ.get("XDG_DOWNLOAD_DIR", "")).expanduser() if os.environ.get("XDG_DOWNLOAD_DIR") else HOME / "Downloads"


def safe_id(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_.-]+", "-", s.strip()).strip("-.")
    return out[:96] or "game"


def redact(s: str) -> str:
    if not s:
        return ""
    home = str(HOME)
    if home and home != "/" and s.startswith(home):
        return "~" + s[len(home):]
    return s


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_helper(args: list[str]) -> str:
    helper = Path(__file__).with_name("gameweld-trainer-library.py")
    if not helper.is_file():
        return "Trainer Library helper unavailable.\n"
    cp = subprocess.run([sys.executable, str(helper), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    return cp.stdout or f"Trainer Library helper exited {cp.returncode}.\n"


def selected_log_paths(provider: str, runner: str, appid: str) -> list[Path]:
    if not STATE.is_dir() or not appid:
        return []
    a = re.sub(r"[^A-Za-z0-9_.-]", "_", appid)
    r = re.sub(r"[^A-Za-z0-9_.-]", "_", runner or "legendary")
    names: list[str] = []
    if provider == "steam-shortcut":
        names += [f"steam-shortcut-trainer-{appid}.log"]
    elif provider == "steam":
        names += [f"local-trainer-{appid}.log", f"native-profile-{appid}.log", f"cheat-table-{appid}.log"]
    elif provider == "heroic":
        names += [
            f"heroic-{r}-{a}.log",
            f"heroic-local-trainer-{r}-{a}.log",
            f"heroic-session-control-{r}-{a}.log",
            f"heroic-session-finalizer-{r}-{a}.log",
            f"heroic-trainer-runtime-{r}-{a}.log",
            f"heroic-cheat-table-{r}-{a}.log",
        ]
    out = []
    for name in names:
        p = STATE / name
        if p.is_file():
            out.append(p)
    return out


def selected_session_paths(provider: str, appid: str) -> list[Path]:
    if not STATE.is_dir() or not appid:
        return []
    if provider != "steam-shortcut":
        return []
    names = [f"steam-shortcut-session-{appid}.txt"]
    return [STATE / n for n in names if (STATE / n).is_file()]


def write_text(zf: zipfile.ZipFile, name: str, text: str) -> None:
    zf.writestr(name, text.replace(str(HOME), "~"))


def file_meta(path: Path) -> dict:
    try:
        st = path.stat()
        return {
            "name": path.name,
            "size_bytes": st.st_size,
            "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
            "sha256": sha256_file(path),
        }
    except OSError as exc:
        return {"name": path.name, "error": str(exc)}


def support_policy_text(trainer: str, backend: str) -> str:
    """Return backend-aware policy diagnostics without implying Heroic on Steam."""
    if not trainer:
        return "No trainer is assigned.\n"
    profile_policy = run_helper(["profile-policy", trainer]).strip()
    launch_plan = run_helper(["launch-plan", trainer, backend]).strip()
    lines = [
        "GameWeld effective launch policy for the selected backend",
        f"BACKEND\t{backend}",
        profile_policy,
        launch_plan,
        "NOTE\tDetected FLiNG profile policy is backend-scoped: Steam and Steam non-Steam shortcuts retain their live Proton-session handoff; Heroic may use the managed FLiNG session.",
    ]
    return "\n".join(x for x in lines if x) + "\n"


def create(args: argparse.Namespace) -> Path:
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else DOWNLOADS
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"GameWeld-support-{safe_id(args.name)}-{stamp}.zip"
    trainer = Path(args.trainer).expanduser() if args.trainer else None

    summary = {
        "gameweld_version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "game": {
            "name": args.name,
            "key": args.key,
            "provider": args.provider,
            "appid": args.appid,
            "launch_id": args.launch_id,
            "runner": args.runner,
            "target_kind": args.target_kind,
            "executable": redact(args.executable),
            "install_dir": redact(args.install_dir),
            "prefix": redact(args.prefix),
            "compatdata": redact(args.compatdata),
            "compat_tool": args.compat_tool,
            "compat_tool_path": redact(args.compat_tool_path),
            "compat_tool_source": args.compat_tool_source,
            "resolution_state": args.resolution_state,
            "resolution_label": args.resolution,
        },
        "trainer": {
            "path": redact(args.trainer),
            "exists": bool(trainer and trainer.is_file()),
            "size_bytes": trainer.stat().st_size if trainer and trainer.is_file() else None,
            "sha256": sha256_file(trainer) if trainer and trainer.is_file() else None,
        },
        "system": {
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
            "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        },
    }

    log_paths = selected_log_paths(args.provider, args.runner, args.appid)
    session_paths = selected_session_paths(args.provider, args.appid)
    log_index = [file_meta(p) for p in log_paths]
    session_index = [file_meta(p) for p in session_paths]
    manifest = {
        "scope": "selected-game-only",
        "privacy": "No global environment dump, browser data, unrelated game logs, or trainer executable bytes are included.",
        "logs": [p.name for p in log_paths],
        "session_snapshots": [p.name for p in session_paths],
        "log_index": log_index,
        "session_index": session_index,
    }

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        write_text(zf, "summary.json", json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        write_text(zf, "manifest.json", json.dumps(manifest, indent=2) + "\n")
        if args.trainer:
            write_text(zf, "trainer/profile.txt", run_helper(["profile", args.trainer]))
            write_text(zf, "trainer/profile-evidence.txt", run_helper(["profile-evidence", args.trainer]))
            write_text(zf, "trainer/compatibility-recipe.txt", run_helper(["profile-recipe", args.trainer]))
            backend = "unassigned"
            if args.provider == "steam-shortcut":
                backend = "steam-shortcut-resolved" if args.compat_tool_path and args.compatdata else "steam-shortcut"
            elif args.provider == "steam":
                backend = "steam"
            elif args.provider == "heroic":
                backend = "heroic"
            elif args.provider == "lutris":
                backend = "unassigned"
            write_text(zf, "trainer/launch-policy.txt", support_policy_text(args.trainer, backend))
            write_text(zf, "trainer/launch-plan.txt", run_helper(["launch-plan", args.trainer, backend]))
        if args.name:
            write_text(zf, "trainer-library/rows.txt", run_helper(["rows", "--query", args.name]))
            write_text(zf, "trainer-library/game-attention.txt", run_helper(["game-rows", "--query", args.name]))
        write_text(zf, "logs/index.json", json.dumps({"logs": log_index, "session_snapshots": session_index}, indent=2) + "\n")
        for p in log_paths:
            try:
                data = p.read_text(errors="replace")
            except OSError as exc:
                data = f"Could not read log: {exc}\n"
            write_text(zf, f"logs/{p.name}", data)
        for p in session_paths:
            try:
                data = p.read_text(errors="replace")
            except OSError as exc:
                data = f"Could not read session snapshot: {exc}\n"
            write_text(zf, f"session/{p.name}", data)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("create")
    for name in ["version","name","key","provider","appid","launch-id","runner","target-kind","executable","install-dir","prefix","compatdata","compat-tool","compat-tool-path","compat-tool-source","resolution-state","resolution","trainer"]:
        c.add_argument("--" + name, default="")
    c.add_argument("--output-dir", default="")
    args = ap.parse_args()
    if args.cmd == "create":
        out = create(args)
        print(out)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
