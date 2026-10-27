#!/usr/bin/env python3
"""Conservative Linux procfs check for an ACTIVE Wine/Proton game prefix.

Read-only advisory. It inspects same-UID process environments in memory,
emits NO environment variables, game paths, or credentials in output and
does not terminate processes, change Steam launch settings or authorize setup.
No process found does NOT prove that a prefix is idle; the actual installer
requires a separately validated provider-specific close/lock protocol.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat

STEAM_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
OTHER_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
MAX_ENV_BYTES = 1024 * 1024
MAX_PROCESS_NAME_BYTES = 16 * 1024
MAX_PIDS = 50000


class RuntimePreflightRefused(ValueError):
    pass


def verify_prefix(provider: str, game_id: str, prefix: Path, *, allow_missing: bool = False) -> Path:
    if provider not in ("steam", "heroic", "lutris"):
        raise RuntimePreflightRefused("Unsupported provider")
    identifier = STEAM_ID if provider == "steam" else OTHER_ID
    if not game_id or not identifier.fullmatch(game_id):
        raise RuntimePreflightRefused("Selected game ID is invalid")
    if (not prefix.is_absolute() or prefix.is_symlink() or
            any(parent.is_symlink() for parent in prefix.parents) or
            (not prefix.is_dir() and not (allow_missing and not prefix.exists()
                                            and prefix.parent.is_dir()))):
        raise RuntimePreflightRefused("Choose an existing non-symlinked absolute prefix")
    return prefix


def environment_vars(blob: bytes) -> dict[str, str]:
    """Only read whitelisted keys; never retain unknown or secret variables."""
    found: dict[str, str] = {}
    for entry in blob.split(b"\x00"):
        if b"=" not in entry:
            continue
        name, value = entry.split(b"=", 1)
        if name not in (b"WINEPREFIX", b"STEAM_COMPAT_DATA_PATH", b"SteamAppId",
                        b"SteamGameId", b"SteamCompatAppId"):
            continue
        try:
            found[name.decode("ascii")] = value.decode("utf-8", "surrogateescape")
        except UnicodeError:
            continue
    return found


def is_wemod_process(pid: Path) -> bool | None:
    """Read bounded process names, independently checking argv and comm.

    This only finds a WeMod.exe name candidate, never verifies attachment.
    A missing cmdline must not conceal an accessible Linux comm name.
    """
    inspected = False
    try:
        with (pid / "cmdline").open("rb") as stream:
            raw = stream.read(MAX_PROCESS_NAME_BYTES + 1)
        if 0 < len(raw) <= MAX_PROCESS_NAME_BYTES:
            inspected = True
            for arg in raw.split(b"\x00"):
                if not arg:
                    continue
                name = arg.strip(b"\"' ").replace(b"\\", b"/").split(b"/")[-1]
                if name.lower() == b"wemod.exe":
                    return True
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        pass
    try:
        with (pid / "comm").open("rb") as stream:
            comm = stream.read(257)
        if 0 < len(comm) <= 256:
            inspected = True
            if comm.strip().lower() == b"wemod.exe":
                return True
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        pass
    return False if inspected else None


def procfs_report(
    provider: str,
    game_id: str,
    prefix: Path,
    *,
    proc_root: Path = Path("/proc"),
    current_uid: int | None = None,
    allow_missing_prefix: bool = False,
) -> dict:
    prefix = verify_prefix(provider, game_id, prefix, allow_missing=allow_missing_prefix)
    uid = os.getuid() if current_uid is None else current_uid
    base = str(prefix)
    steam_compat = str(prefix.parent) if prefix.name == "pfx" else ""
    matches: list[int] = []
    wemod_candidates = 0
    wemod_name_unknown = 0
    wemod_name_inspected = 0
    unreadable = 0
    scanned = 0
    if not proc_root.is_dir():
        raise RuntimePreflightRefused("procfs is unavailable")
    try:
        processes = sorted((p for p in proc_root.iterdir() if p.name.isdigit()),
                           key=lambda p: int(p.name))
    except OSError as exc:
        raise RuntimePreflightRefused("Cannot enumerate procfs processes") from exc
    if len(processes) > MAX_PIDS:
        return {
            "state": "UNKNOWN", "matching_processes": [],
            "unreadable_same_user_processes": len(processes) - MAX_PIDS,
            "scanned_same_user_processes": 0,
            "provider": provider, "game_id": game_id,
            "game_runtime_idle_verified": False,
            "wemod_process_candidates": 0,
            "wemod_process_name_inspected": 0,
            "wemod_process_name_unreadable": 0,
            "wemod_process_state": "UNVERIFIED",
            "trainer_attached": False,
            "installer_authorized": False, "reason": "Process count above inspection limit"
        }
    for pid in processes:
        try:
            owner = pid.stat(follow_symlinks=False).st_uid
            if owner != uid:
                continue
            raw = (pid / "environ").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            # Process exited between enumeration and read.
            continue
        except (PermissionError, OSError):
            unreadable += 1
            continue
        scanned += 1
        if len(raw) > MAX_ENV_BYTES:
            unreadable += 1
            continue
        found = environment_vars(raw)
        wine_match = found.get("WINEPREFIX") == base
        steam_match = (
            provider == "steam" and steam_compat != "" and
            found.get("STEAM_COMPAT_DATA_PATH") == steam_compat and
            (found.get("SteamAppId") == game_id or
             found.get("SteamGameId") == game_id or
             found.get("SteamCompatAppId") == game_id)
        )
        if wine_match or steam_match:
            matches.append(int(pid.name))
            process_name = is_wemod_process(pid)
            if process_name is True:
                wemod_candidates += 1
                wemod_name_inspected += 1
            elif process_name is None:
                wemod_name_unknown += 1
            else:
                wemod_name_inspected += 1
    # A positive match blocks immediately. A negative result is advisory only.
    state = "ACTIVE" if matches else "UNKNOWN" if unreadable else "IDLE_CANDIDATE"
    wemod_state = (
        "CANDIDATE_VISIBLE" if wemod_candidates else
        "UNVERIFIED" if wemod_name_unknown or unreadable or not matches else
        "NOT_SEEN"
    )
    return {
        "provider": provider, "game_id": game_id,
        "state": state,
        "matching_processes": matches[:50],
        "matching_process_count": len(matches),
        "wemod_process_candidates": wemod_candidates,
        "wemod_process_name_inspected": wemod_name_inspected,
        "wemod_process_state": wemod_state,
        "wemod_process_name_unreadable": wemod_name_unknown,
        "trainer_attached": False,
        "unreadable_same_user_processes": unreadable,
        "scanned_same_user_processes": scanned,
        "game_runtime_idle_verified": False,
        "installer_authorized": False,
        "provider_specific_lock_verified": False,
        "reason": {
            "ACTIVE": "Processes still reference this selected prefix",
            "UNKNOWN": "At least one same-user process could not be inspected",
            "IDLE_CANDIDATE": "No matching environment found; other namespaces or launch methods may exist",
        }[state],
        "note": "Procfs observation only. Never treat this result as permission to modify the game."
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("steam", "heroic", "lutris"))
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--prefix", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        outcome = procfs_report(args.provider, args.game_id, args.prefix)
    except (RuntimePreflightRefused, OSError) as exc:
        parser.exit(2, f"GameWeld runtime preflight BLOCKED — {exc}\n")
    print(json.dumps(outcome, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
