#!/usr/bin/env python3
"""GameWeld: provider-native WeMod integration readiness (read-only).

A prepared WeMod prefix is NOT a launch hook. This inspector distinguishes
per-game provider context from a tested trainer attachment route. It performs
no downloads, Wine/Proton execution, prefix writes or Steam modifications.
"""
from __future__ import annotations

import argparse
import importlib.util
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

def runtime_activity(provider: str, game_id: str, prefix: Path | None,
                     *, proc_root: Path | None = None) -> dict:
    """Run the peer read-only procfs check when available, never authorize writes."""
    result = {
        "state": "UNKNOWN",
        "reason": "Game-prefix process activity not verified",
        "matching_process_count": 0,
        "unreadable_same_user_processes": 0,
        "installer_authorized": False,
        "game_runtime_idle_verified": False,
    }
    if prefix is None or not prefix.is_dir() or prefix.is_symlink():
        result["reason"] = "Exact existing game prefix is not established"
        return result
    script = Path(__file__).with_name("gameweld-prefix-runtime-preflight.py")
    if not script.is_file() or script.is_symlink():
        result["reason"] = "Read-only runtime inspector unavailable"
        return result
    try:
        spec = importlib.util.spec_from_file_location("gameweld_runtime_activity", script)
        if spec is None or spec.loader is None:
            return result
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        options = {} if proc_root is None else {"proc_root": proc_root}
        report = checker.procfs_report(provider, game_id, prefix, **options)
        state = report["state"]
        if state not in ("ACTIVE", "UNKNOWN", "IDLE_CANDIDATE"):
            return result
        return {
            "state": state,
            "reason": report["reason"],
            "matching_process_count": report.get("matching_process_count", 0),
            "unreadable_same_user_processes": report.get(
                "unreadable_same_user_processes", 0),
            "installer_authorized": False,
            "game_runtime_idle_verified": False,
        }
    except (OSError, ValueError, KeyError, ImportError, AttributeError):
        result["reason"] = "Read-only process check could not be completed"
        return result


def native_route_report(
    provider: str,
    game_id: str | None,
    *,
    install_dir: str | None = None,
    prefix: str | None = None,
    runner: str | None = None,
    proc_root: Path | None = None,
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

    runtime_prefix = game_prefix
    if provider == "steam":
        if install and install.parent.name == "common" and install.parent.parent.name == "steamapps":
            manifest = install.parent.parent / ("appmanifest_" + game_id + ".acf")
            evidence["steam_manifest_present"] = manifest.is_file() and not manifest.is_symlink()
            # Use only an exact candidate location, not the game's live prefix contents.
            compatdata = install.parent.parent / "compatdata" / game_id / "pfx"
            evidence["game_prefix_present"] = compatdata.is_dir() and not compatdata.is_symlink()
            runtime_prefix = compatdata if evidence["game_prefix_present"] else None
        else:
            # Do not infer Steam game identity from an arbitrary prefix path.
            runtime_prefix = None
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

    process = runtime_activity(
        provider, game_id, runtime_prefix if evidence["game_prefix_present"] else None,
        proc_root=proc_root
    )
    return {
        "provider": provider,
        "game_id": game_id,
        "setup_scope": "Shared prepared prefix cache; per-game runtime context",
        "recommended_integration": "Provider-native (no GameWeld Steam Bridge required in design)",
        "evidence": evidence,
        "process_activity": process,
        "state": "NOT READY — prepared WeMod setup and in-game trainer attachment unverified",
        "legacy_bridge_required": False,
        "existing_bridge_modified": False,
        "supported_workflow": "read_only_preview",
        "game_runtime_attached": False,
        "safe_next_action": "Find prepared WeMod setup; then verify a provider-native launch adapter",
        "notes": notes,
        "mutations": "NONE: no launch, download, setup, Steam change or prefix access beyond presence checks",
    }


def human_readable_report(report: dict) -> str:
    """Concise UX status for all supported providers, no false trainer READY."""
    provider = report["provider"]
    evidence = report["evidence"]
    title = {"steam": "Steam", "heroic": "Heroic", "lutris": "Lutris"}[provider]
    present = lambda value: "FOUND" if value else "NOT VERIFIED"
    lines = [
        f"GAMEWELD — WEMOD GAME CONNECTION • {title}",
        f"Selected game: {report['game_id']}",
        "Launch approach: Original game platform (no GameWeld Steam Bridge needed)",
        "Game folder: " + present(evidence["game_install_verified"]) +
        " (presence only, not game identity verification)",
    ]
    if provider == "steam":
        lines += [
            "Steam AppID manifest: " + present(evidence["steam_manifest_present"]) +
            " (filename check; contents not verified)",
            "Steam Proton prefix: " + present(evidence["game_prefix_present"]),
            "Separate Wine runner: NOT REQUIRED for this Steam check",
        ]
    else:
        lines += [
            f"{title} game prefix: " + present(evidence["game_prefix_present"]),
            f"{title} configured Wine/Proton runner: " +
            present(evidence["runner_file_present"]) +
            " (presence only; runner has not been executed)",
        ]
    runtime = report.get("process_activity", {})
    status = runtime.get("state", "UNKNOWN")
    lines.append("Game activity: " + {
        "ACTIVE": "ACTIVE — matching Wine/Proton process detected; close the game before setup",
        "UNKNOWN": "UNKNOWN — unable to prove whether the game is closed",
        "IDLE_CANDIDATE": "NO MATCH FOUND — game closure is still unverified",
    }.get(status, "UNKNOWN — runtime check unavailable"))
    lines.extend([
        "Prepared WeMod environment: NOT VERIFIED",
        "Trainer attachment to this game: NOT VERIFIED",
        "Status: SETUP REQUIRED — original-platform integration and trainer "
        "compatibility not yet proven",
        "Next step: Find prepared WeMod setup; then validate this game's "
        "native trainer attachment before enabling Play with WeMod.",
        "Install permission: BLOCKED — process scan never authorizes game changes",
        "Safety: READ-ONLY; no game, Steam Bridge, WeMod installer or prefix changes.",
    ])
    if provider == "steam" and not evidence["steam_manifest_present"]:
        lines.append("Warning: exact Steam AppID manifest not found in selected library.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--install-dir")
    parser.add_argument("--prefix")
    parser.add_argument("--runner")
    parser.add_argument("--format", choices=("json", "text"), default="json",
                        help="JSON for scripts; concise text for GameWeld GUI")
    args = parser.parse_args(argv)
    try:
        result = native_route_report(
            args.provider, args.game_id, install_dir=args.install_dir,
            prefix=args.prefix, runner=args.runner,
        )
    except NativeRouteBlocked as exc:
        parser.exit(2, "GameWeld native route BLOCKED: " + str(exc) + "\n")
    if args.format == "text":
        print(human_readable_report(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
