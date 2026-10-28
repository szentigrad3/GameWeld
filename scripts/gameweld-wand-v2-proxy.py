#!/usr/bin/env python3
"""Opt-in bridge to a user-installed Wand v2 development checkout.

No game or Steam configuration changes. Never falls back to the old wrapper.
The v2 command itself verifies the exact live Steam prefix and asks for consent
upstream in the GameWeld GTK UI before attempting the WeMod client subprocess.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

class ProxyBlocked(ValueError):
    pass

def source_path() -> Path:
    home = Path.home()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and not Path(xdg).is_absolute():
        raise ProxyBlocked("xdg_not_absolute")
    base = Path(xdg) if xdg else home / ".local/share"
    root = base / "gameweld/wand-v2/src"
    files = [root, root / "wand_launcher", root / "wand_launcher/entrypoint.py",
             root / "wand_launcher/__init__.py"]
    for file in files:
        if file.is_symlink() or not file.exists():
            raise ProxyBlocked("v2_not_installed_or_symlinked")
        st = file.lstat()
        if st.st_uid != os.getuid():
            raise ProxyBlocked("v2_source_wrong_owner")
        if file.suffix == ".py" and not stat.S_ISREG(st.st_mode):
            raise ProxyBlocked("v2_source_not_regular")
        if file.suffix != ".py" and not stat.S_ISDIR(st.st_mode):
            raise ProxyBlocked("v2_source_not_directory")
    return root

def invoke(appid: str, game_dir: Path, *, launch: bool,
           accept_unreadable_process_risk: bool = False,
           client_software_rendering: bool = False) -> dict:
    if not appid.isdecimal() or not 0 < int(appid) < 2**32:
        raise ProxyBlocked("invalid_appid")
    if not game_dir.is_absolute():
        raise ProxyBlocked("game_dir_not_absolute")
    source = source_path()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(source)
    cmd = [sys.executable, "-m", "wand_launcher", "attach",
           "--appid", appid, "--install-dir", str(game_dir)]
    if launch:
        cmd.append("--approve-existing-prefix-change")
    if accept_unreadable_process_risk:
        cmd.append("--accept-unreadable-process-risk")
    if client_software_rendering:
        cmd.append("--client-software-rendering")
    p = subprocess.run(cmd, env=env, capture_output=True, text=True,
                       timeout=40, check=False)
    if p.returncode not in (0, 2, 3):
        raise ProxyBlocked("v2_subprocess_failed")
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise ProxyBlocked("v2_json_unavailable") from exc
    if not isinstance(data, dict):
        raise ProxyBlocked("v2_invalid_reply")
    data["v2_integration"] = True
    data["steam_settings_changed_by_proxy"] = False
    data["return_code"] = p.returncode
    return data

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--appid", required=True)
    p.add_argument("--install-dir", required=True, type=Path)
    p.add_argument("--launch-client", action="store_true")
    p.add_argument("--accept-unreadable-process-risk", action="store_true",
                   help="only with explicit GameWeld user approval; <=8 unreadable processes")
    p.add_argument("--client-software-rendering", action="store_true",
                   help="opt-in Electron GPU fallback for WeMod.exe only")
    a = p.parse_args(argv)
    try:
        r = invoke(a.appid, a.install_dir, launch=a.launch_client,
                   accept_unreadable_process_risk=a.accept_unreadable_process_risk,
                   client_software_rendering=a.client_software_rendering)
    except (ProxyBlocked, OSError, subprocess.TimeoutExpired) as exc:
        r = {"state":"blocked", "reason_code":
             str(exc) if isinstance(exc, ProxyBlocked) else type(exc).__name__,
             "can_attempt_with_explicit_consent": False,
             "steam_launch_options_changed": False,
             "trainer_attachment_verified": False}
        print(json.dumps(r, indent=2))
        return 2
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if r["return_code"] in (0, 3) else 2

if __name__ == "__main__":
    raise SystemExit(main())
