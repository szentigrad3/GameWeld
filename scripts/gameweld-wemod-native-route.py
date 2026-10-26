#!/usr/bin/env python3
"""GameWeld: provider-native WeMod integration readiness (read-only).

A prepared WeMod prefix is NOT a launch hook. This inspector distinguishes
per-game provider context from a tested trainer attachment route. It performs
no downloads, Wine/Proton execution, prefix writes or Steam modifications.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

PROVIDERS = ("steam", "heroic", "lutris")
STEAM_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
OTHER_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


class NativeRouteBlocked(ValueError):
    pass


def _path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        return None
    return path


def native_route_report(
    provider: str,
    game_id: str | None,
    *,
    install_dir: str | None = None,
    prefix: str | None = None,
    runner: str | None = None,
) -> dict:
    if provider not in PROVIDERS:
        raise NativeRouteBlocked("No supported Windows-game provider selected")
    if not game_id or not (STEAM_ID if provider == "steam" else OTHER_ID).fullmatch(game_id):
        raise NativeRouteBlocked("Selected game needs an unambiguous provider-specific ID")

    install = _path(install_dir)
    game_prefix = _path(prefix)
    tool = _path(runner)
    notes = []
    evidence = {
        "game_install_verified": False,
        "game_prefix_present": False,
        "runner_file_present": False,
        "steam_manifest_present": False,
    }
    if install and install.is_dir():
        evidence["game_install_verified"] = True
    if game_prefix and game_prefix.is_dir() and not game_prefix.is_symlink():
        evidence["game_prefix_present"] = True
    if tool and tool.is_file() and not tool.is_symlink():
        evidence["runner_file_present"] = True

    if provider == "steam":
        if install and install.parent.name == "common" and install.parent.parent.name == "steamapps":
            manifest = install.parent.parent / ("appmanifest_" + game_id + ".acf")
            evidence["steam_manifest_present"] = manifest.is_file() and not manifest.is_symlink()
            # Use only an exact candidate location, not the game's live prefix contents.
            compatdata = install.parent.parent / "compatdata" / game_id / "pfx"
            evidence["game_prefix_present"] = compatdata.is_dir() and not compatdata.is_symlink()
        notes.append("Use Steam's original game launch path with a verified command-prefix or "
                     "other proven trainer integration. A prepared prefix alone is insufficient.")
        notes.append("Existing DeckCheatz 1.x may require Steam %command% launch options; "
                     "GameWeld does not read or change them here.")
        if not evidence["steam_manifest_present"]:
            notes.append("Steam game manifest not verified; do not infer AppID from a name.")
    elif provider == "heroic":
        notes.append("Heroic native game launch/runner/prefix must be verified with its provider adapter. "
                     "Do not change Heroic's runner or prefix automatically.")
    else:
        notes.append("Lutris native game launch/runner/prefix must be verified with its provider adapter. "
                     "Do not modify Lutris scripts or runner settings automatically.")

    return {
        "provider": provider,
        "game_id": game_id,
        "setup_scope": "Shared prepared prefix cache; per-game runtime context",
        "recommended_integration": "Provider-native (no GameWeld Steam Bridge required in design)",
        "evidence": evidence,
        "state": "NOT READY — prepared WeMod setup and in-game trainer attachment unverified",
        "legacy_bridge_required": False,
        "existing_bridge_modified": False,
        "supported_workflow": "read_only_preview",
        "game_runtime_attached": False,
        "safe_next_action": "Find prepared WeMod setup; then verify a provider-native launch adapter",
        "notes": notes,
        "mutations": "NONE: no launch, download, setup, Steam change or prefix access beyond presence checks",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--install-dir")
    parser.add_argument("--prefix")
    parser.add_argument("--runner")
    args = parser.parse_args(argv)
    try:
        result = native_route_report(
            args.provider, args.game_id, install_dir=args.install_dir,
            prefix=args.prefix, runner=args.runner,
        )
    except NativeRouteBlocked as exc:
        parser.exit(2, "GameWeld native route BLOCKED: " + str(exc) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
