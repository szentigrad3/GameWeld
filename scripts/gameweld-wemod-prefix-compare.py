#!/usr/bin/env python3
"""Compare two Steam Proton prefixes and an optional pre-install backup, READ ONLY.

Designed for troubleshooting WeMod Windows-runtime failures without running
Proton, Wine, winetricks or an installer. No Steam configuration is changed.
Registry evidence and DLL presence do not prove a working .NET installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def file_sha(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def netfx_registry(prefix: Path) -> dict:
    registry = prefix / "system.reg"
    result = {"registry_sha256": file_sha(registry), "framework_v4_full": [],
              "framework_v4_client": [], "wine_mono_keys": []}
    if result["registry_sha256"] is None:
        return result
    section = ""
    for line in registry.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("["):
            section = line.casefold().replace("\\\\", "\\")
            if "microsoft\\net framework setup\\ndp\\v4\\full" in section:
                result["framework_v4_full"].append({"key": line[:180]})
            elif "microsoft\\net framework setup\\ndp\\v4\\client" in section:
                result["framework_v4_client"].append({"key": line[:180]})
            elif "wine mono" in section:
                result["wine_mono_keys"].append(line[:180])
        elif any(x in section for x in (
                "microsoft\\net framework setup\\ndp\\v4\\full",
                "microsoft\\net framework setup\\ndp\\v4\\client")):
            m = re.match(r'"(Release|Version|Install)"=(.*)', line, re.I)
            if m:
                target = ("framework_v4_full" if "\\full" in section
                          else "framework_v4_client")
                if result[target]:
                    result[target][-1][m.group(1).lower()] = m.group(2)[:120]
    return result


def prefix_evidence(prefix: Path) -> dict:
    if prefix.is_symlink() or not prefix.is_dir():
        return {"present": False, "reason": "Missing or symlinked; not inspected"}
    root = prefix / "drive_c"
    result = {"present": True, "registry": netfx_registry(prefix)}
    for key, relative in (
        ("mscoree_system32", "windows/system32/mscoree.dll"),
        ("mscoree_syswow64", "windows/syswow64/mscoree.dll"),
        ("mono_directory", "windows/mono"),
    ):
        p = root / relative
        result[key] = {"present": p.exists() and not p.is_symlink(),
                       "symlink": p.is_symlink()}
    versions = {}
    for dirname in ("Microsoft.WindowsDesktop.App", "Microsoft.NETCore.App"):
        found = []
        for base in ("Program Files", "Program Files (x86)"):
            p = root / base / "dotnet/shared" / dirname
            if p.is_dir() and not p.is_symlink():
                found.extend(d.name for d in p.iterdir() if d.is_dir() and not d.is_symlink())
        versions[dirname] = sorted(set(found))[:20]
    result["net_shared_versions"] = versions
    winetricks = prefix / "winetricks.log"
    result["winetricks_log"] = (
        winetricks.read_text(encoding="utf-8", errors="replace")[-4000:]
        if winetricks.is_file() and not winetricks.is_symlink()
        and winetricks.stat().st_size < 2 * 1024 * 1024 else "unavailable"
    )
    return result


def compare(library: Path, working: str, failing: str, backup: Path | None = None,
            config_path: Path | None = None) -> dict:
    for appid in (working, failing):
        if not appid.isascii() or not appid.isdecimal() or appid.startswith("0") or len(appid) > 10:
            raise ValueError("Steam AppIDs must be positive decimal IDs")
    if working == failing:
        raise ValueError("Working and failing Steam AppIDs must differ")
    if not library.is_dir() or not (library / "steamapps").is_dir():
        raise ValueError("Steam library must have a steamapps directory")
    steamapps = library / "steamapps"
    evidence = {}
    for label, appid in (("working", working), ("failing", failing)):
        prefix = steamapps / "compatdata" / appid / "pfx"
        evidence[label] = {
            "appid": appid,
            "manifest_found": (steamapps / f"appmanifest_{appid}.acf").is_file(),
            "prefix_path": str(prefix),
            "prefix": prefix_evidence(prefix),
        }
    config = {}
    if config_path is not None and config_path.is_file() and not config_path.is_symlink():
        if config_path.stat().st_size < 1024 * 1024:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for label, appid in (("working", working), ("failing", failing)):
                    entry = data.get(appid)
                    if isinstance(entry, dict):
                        config[label] = {
                            "configured_proton": entry.get("proton", ""),
                            "wemod_client": entry.get("client", ""),
                            "wemod_gpu_fallback": entry.get("wemod_disable_gpu", False),
                            "trainer_enabled": entry.get("trainer_enabled", False),
                        }
    notes = []
    w = evidence["working"]["prefix"]
    f = evidence["failing"]["prefix"]
    if not w["present"] or not f["present"]:
        notes.append("A prefix was not found in this library. The game might use another Steam library or a linked compatdata.")
    else:
        wfull = w["registry"]["framework_v4_full"]
        ffull = f["registry"]["framework_v4_full"]
        if wfull and not ffull:
            notes.append("Working prefix has .NET v4 Full registry evidence missing from failing prefix; not proof of runtime health.")
        elif not wfull and not ffull:
            notes.append("Neither prefix has .NET v4 Full registry evidence; WeMod can use different runtime pathways.")
        if w["mscoree_system32"] != f["mscoree_system32"]:
            notes.append("mscoree.dll presence differs between the prefixes.")
        if w["net_shared_versions"] != f["net_shared_versions"]:
            notes.append(".NET shared runtime directories differ (not necessarily the cause of the Framework error).")
    if "working" in config and "failing" in config:
        if config["working"]["configured_proton"] != config["failing"]["configured_proton"]:
            notes.append("Configured Proton versions differ between the games.")
        if config["working"]["wemod_client"] == config["failing"]["wemod_client"]:
            notes.append("Both games point to the same WeMod client; prefix/runtime differences are especially relevant.")
    backup_evidence = None
    if backup is not None:
        backup_prefix = backup / "pfx"
        backup_evidence = {"path": str(backup_prefix), "prefix": prefix_evidence(backup_prefix)}
        if backup_evidence["prefix"]["present"] and f["present"]:
            same = (backup_evidence["prefix"]["registry"]["registry_sha256"] ==
                    f["registry"]["registry_sha256"])
            backup_evidence["registry_matches_current"] = same
            if not same:
                notes.append("Current Dying Light registry differs from pre-install backup. The failed installer may have changed the prefix.")
            else:
                notes.append("Current registry matches backup, but this alone does not prove the entire prefix was restored.")
    return {
        "scope": "read-only Steam prefix comparison; no installers, Wine, Proton or writes",
        "steam_library": str(library),
        "evidence": evidence,
        "bridge_configuration": config,
        "backup": backup_evidence,
        "observations": notes,
        "conclusion": "Evidence only: .NET registration does not guarantee runtime health, and this cannot verify a trainer attached to a running game.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steam-library", type=Path, required=True)
    parser.add_argument("--working-appid", default="2353250")
    parser.add_argument("--failing-appid", default="3008130")
    parser.add_argument("--preinstall-backup", type=Path)
    parser.add_argument("--config", type=Path, default=(Path(os.environ.get("XDG_CONFIG_HOME",
        str(Path.home() / ".config"))) / "gameweld/steam-bridge-games.json"))
    args = parser.parse_args()
    result = compare(args.steam_library, args.working_appid,
                     args.failing_appid, args.preinstall_backup, args.config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"READ-ONLY comparison failed: {exc}")
