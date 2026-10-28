#!/usr/bin/env python3
"""Compose user-verified Steam Launch Options into one DeckCheatz session.

Never edits Steam config. Only a known, shell-free subset is supported.
Unknown wrappers/expressions fail closed rather than dropping custom options.
"""
from __future__ import annotations
import re
import shlex
import argparse
import importlib.util
import json
from pathlib import Path

class OptionBlocked(ValueError):
    pass

MAX_OPTION = 16384
ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
KNOWN_WRAPPERS = frozenset(("mangohud", "gamemoderun"))
PROTECTED = frozenset((
    "STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
    "STEAM_COMPAT_TOOL_PATHS", "STEAM_COMPAT_INSTALL_PATH",
    "STEAM_COMPAT_APP_ID", "SteamAppId", "SteamGameId", "SteamOverlayGameId",
    "WEMOD_LOG", "WINEDLLOVERRIDES",
))
SHELL_SYNTAX = re.compile("[;&|$<>\\\\\\n\\r" + chr(96) + "]")


def compose(text: str, command: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str], dict]:
    """Return only this session's argv and environment; original Steam settings persist."""
    if not isinstance(text, str) or len(text) > MAX_OPTION or "\0" in text:
        raise OptionBlocked("Invalid or oversized Steam launch options")
    if SHELL_SYNTAX.search(text):
        raise OptionBlocked("Complex Steam shell expressions require manual review; no launch attempted")
    try:
        parts = shlex.split(text, posix=True)
    except ValueError as exc:
        raise OptionBlocked("Invalid quoting in Steam Launch Options") from exc
    if any("wemod" in p.casefold() or "deckcheatz" in p.casefold() for p in parts):
        raise OptionBlocked("Existing trainer wrapper found; refuse double WeMod launch")
    count = parts.count("%command%")
    if count > 1:
        raise OptionBlocked("Multiple %command% placeholders cannot be composed")
    if count == 1:
        marker = parts.index("%command%")
        before, after = parts[:marker], parts[marker + 1:]
    elif all(p.startswith("-") for p in parts):
        before, after = [], parts
    else:
        raise OptionBlocked("Unknown Steam options without a %command% placeholder")
    if any(not a.startswith("-") or a in ("-", "--") or
           "\0" in a or "%" in a for a in after):
        raise OptionBlocked("Unsupported game arguments after %command%; no options dropped")
    result_env = dict(env)
    assignments = []
    at = 0
    while at < len(before) and "=" in before[at]:
        k, v = before[at].split("=", 1)
        if not ENV_KEY.fullmatch(k) or k in PROTECTED or k.startswith("STEAM_COMPAT_"):
            raise OptionBlocked("Protected or malformed environment override in Steam options: " + k)
        if not v:
            raise OptionBlocked("Empty environment override in Steam options")
        assignments.append(k)
        result_env[k] = v
        at += 1
    wrappers = []
    while at < len(before):
        name = before[at]
        if name in KNOWN_WRAPPERS:
            wrappers.append(name)
            at += 1
            continue
        if name == "gamescope":
            end = before.index("--", at + 1) if "--" in before[at + 1:] else -1
            if end < 0:
                raise OptionBlocked("Gamescope wrapper must use an explicit -- before %command%")
            flags = before[at + 1:end]
            if any(not re.fullmatch(r"-{1,2}[A-Za-z0-9_.=-]+|[0-9]+", f)
                   for f in flags):
                raise OptionBlocked("Unsupported Gamescope parameters; custom options unchanged")
            wrappers.extend([name, *flags, "--"])
            at = end + 1
            continue
        raise OptionBlocked("Unsupported custom command wrapper: " + name)
    new_argv = [*wrappers, *command, *after]
    return new_argv, result_env, {
        "source": "user_verified_current_steam_properties",
        "custom_options_present": bool(parts),
        "environment_keys_applied": assignments,
        "wrapper_argv": wrappers,
        "game_arguments": after,
        "steam_launch_options_modified": False,
        "steam_launch_options_restoration_required": False,
        "original_user_options_remain_in_steam": True,
        "steam_runtime_supervisor_reproduced": False,
    }


def read_saved_options(appid: str) -> dict:
    """Inspect Steam's SAVED option for autofill, never assert it matches the live UI."""
    source = Path(__file__).resolve().with_name("gameweld-steam-launch-options-preserve.py")
    if source.is_symlink() or not source.is_file():
        return {"status": "unknown", "reason": "Launch option inspector unavailable"}
    try:
        spec = importlib.util.spec_from_file_location("gw_dc_saved_options", source)
        if not spec or not spec.loader:
            raise OptionBlocked("Launch option inspector unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config, _account = module.find_config(appid, None, None)
        value = module.launch_option(config, appid)
        return {"status": "saved_snapshot", "value": value,
                "warning": "Verify against CURRENT Steam Properties; saved options may be stale"}
    except (OSError, ValueError) as exc:
        return {"status": "unknown", "reason": str(exc)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-saved", action="store_true")
    p.add_argument("--appid", required=True)
    args = p.parse_args()
    if not args.read_saved:
        p.error("Only read-only saved-options inspection is exposed")
    print(json.dumps(read_saved_options(args.appid)))
