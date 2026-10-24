#!/usr/bin/env python3
"""GameWeld PC2 managed game + Wand session, based on Wand Native's one-session flow.

A separate old wandctl/wandd installation is NOT needed. Read-only check
reports each missing prerequisite. Confirmed play may copy an existing,
verified PE DWriteCore beside Wand and start ONE Proton batch (Wand then game).
Does NOT download modified Wine/crypt32 binaries or change Steam launch options.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

LABEL = "GameWeld one-Proton-session (Wand Native 0.1.41 design)"
TOOL = "GE-Proton-Wand-SHA256"
PROTON_DISPLAY = "GE Proton Wand SHA256"
# Fingerprints of the built crypt32 payload in the already-tested 0.1.41 release.
EXPECTED = {
    "x86_64-windows": "2d613ab5f0f03c77c9434e9c201be629e21f51d5e5eed9139d68e54c759aa775",
    "i386-windows": "6efa5676914916dd79dee7618340984d5dcf51873d73b28cb974d03f8ece50da",
}

class Blocked(ValueError):
    pass


@dataclass
class Plan:
    appid: str
    game_dir: Path
    game_exe: Path
    wand_exe: Path
    proton: Path
    steam_root: Path
    compat: Path
    prefix: Path
    dwrite_source: Path
    dwrite_target: Path
    state_dir: Path
    windows_user: str


def valid_appid(raw: str) -> str:
    if not (raw.isascii() and raw.isdecimal() and len(raw) <= 10
            and str(int(raw)) == raw and 0 < int(raw) < 2**32):
        raise Blocked("Invalid exact Steam App ID")
    return raw


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def steam_install(game_dir: Path, appid: str) -> tuple[Path, Path, Path]:
    game_dir = game_dir.resolve(strict=True)
    # A Steam common directory is required; never infer a different game's
    # prefix from a shortcut or from HOME alone.
    common = game_dir.parent
    if common.name != "common" or common.parent.name != "steamapps":
        raise Blocked("Selected game directory is not an installed Steam steamapps/common game")
    steamapps = common.parent
    manifest = steamapps / ("appmanifest_" + appid + ".acf")
    if not manifest.is_file():
        raise Blocked("Steam install manifest for selected app ID is missing: " + manifest.name)
    text = manifest.read_text(encoding="utf-8", errors="replace")
    if not re.search(r'(?im)^\s*"appid"\s+"' + appid + r'"\s*$', text):
        raise Blocked("Selected Steam app manifest does not match app ID")
    compat = steamapps / "compatdata" / appid
    prefix = compat / "pfx"
    if not (prefix / "drive_c" / "users").is_dir():
        raise Blocked("The game's existing Proton prefix is missing; start the game once normally through Steam first")
    return steamapps, compat.resolve(), prefix.resolve()


def _proton_candidates(steamapps: Path) -> list[Path]:
    """Bounded searches for existing, installed compatibility tools only.

    Includes other Steam libraries and Flatpak. Never scans /proc, downloads
    binaries, or treats an arbitrary extracted Proton archive as installed.
    """
    home = Path.home()
    roots = [
        steamapps.parent,
        home / ".local/share/Steam",
        home / ".steam/root",
        home / ".steam/steam",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
        Path("/mnt/games/Steam"),
    ]
    # Steam may live on another disk. Enumerate only shallow library roots;
    # do not recurse over the user's home directory or entire /mnt.
    for base in (Path("/mnt"), Path("/run/media")):
        if base.is_dir():
            for pattern in ("*/compatibilitytools.d", "*/*/compatibilitytools.d",
                            "*/Steam/compatibilitytools.d",
                            "*/SteamLibrary/compatibilitytools.d"):
                for directory in list(base.glob(pattern))[:32]:
                    roots.append(directory.parent)
    roots = roots[:128]
    explicit = os.environ.get("GAMEWELD_MANAGED_PROTON")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            raise Blocked("GAMEWELD_MANAGED_PROTON must be an absolute compatibility-tool root")
        roots.insert(0, p.parent.parent if p.parent.name == "compatibilitytools.d" else p)
    result = []
    seen: set[str] = set()
    for root in roots:
        possible = root / "compatibilitytools.d" / TOOL
        if explicit and root == Path(explicit) and root.name == TOOL:
            possible = root
        key = str(possible.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            result.append(possible)
    return result


def _known_recovery_archives() -> list[Path]:
    """Only discover old 0.1.41 build products; never auto-extract or install."""
    home = Path.home()
    paths = [
        home / "Desktop/wand-native-0.1.41/dist/wand-native-0.1.41-linux-x86_64.zip",
        home / "Desktop/wand-native-0.1.41/dist/GE-Proton-Wand-SHA256.tar.gz",
        home / "Desktop/wand-crypt32-payload.zip",
        home / "Downloads/wand-native-0.1.41-linux-x86_64.zip",
        home / "Downloads/wand-crypt32-payload.zip",
        home / "src/wand-ge-proton/build/GE-Proton-Wand-SHA256.tar.gz",
        home / "Desktop/wand-native-0.1.41/payload/crypt32",
    ]
    return [p for p in paths if p.exists() and not p.is_symlink()]


def _verify_isolated_tool(root: Path) -> Path:
    """Verify the actual proven 0.1.41 crypt32 code before trusting metadata.

    A missing old WAND-HYBRID.json is recoverable WITHOUT WRITING IT if
    both on-disk patched DLLs match the exact field-tested release hashes.
    Existing-but-invalid metadata is NOT silently ignored. The Steam tool
    declaration must still identify the expected isolated compatibility tool.
    """
    proton = root / "proton"
    metadata = root / "WAND-HYBRID.json"
    descriptor = root / "compatibilitytool.vdf"
    if not (proton.is_file() and os.access(proton, os.X_OK)):
        raise Blocked("Proton launcher is missing/not executable")
    if not descriptor.is_file() or descriptor.is_symlink():
        raise Blocked("Steam compatibilitytool.vdf is missing or symlinked")
    try:
        description = descriptor.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise Blocked("Cannot read Steam compatibility-tool manifest") from exc
    if not re.search(r'"display_name"\s+"GE Proton Wand SHA256"', description):
        raise Blocked("Steam compatibility-tool manifest does not identify GE Proton Wand SHA256")

    # Inspect the *real code-bearing DLLs* even if the historical metadata is
    # missing. A JSON file alone is not proof of modified crypt32 behavior.
    for arch, fingerprint in EXPECTED.items():
        matches = list((root / "files").glob("**/" + arch + "/crypt32.dll"))
        if len(matches) != 1 or matches[0].is_symlink():
            raise Blocked("Exactly one installed " + arch + " crypt32.dll required")
        try:
            found_hash = sha256(matches[0])
        except OSError as exc:
            raise Blocked("Cannot hash installed " + arch + " crypt32.dll") from exc
        if found_hash != fingerprint:
            raise Blocked(arch + " crypt32 SHA-256 mismatch (expected " +
                          fingerprint + ", found " + found_hash + ")")

    if metadata.is_symlink():
        raise Blocked("WAND-HYBRID.json is symlinked; refusing unsafe metadata")
    if metadata.exists():
        if not metadata.is_file():
            raise Blocked("WAND-HYBRID.json is not a regular file")
        try:
            obj = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise Blocked("Existing WAND-HYBRID.json cannot be parsed") from exc
        if not isinstance(obj, dict) or obj.get("tool_id") != TOOL:
            raise Blocked("Existing WAND-HYBRID.json tool identity does not match")
        for arch, fingerprint in EXPECTED.items():
            if obj.get("patched_" + arch.split("-")[0] + "_crypt32_sha256") != fingerprint:
                raise Blocked(arch + " WAND-HYBRID.json payload hash does not match proven release")
        print("GE Proton Wand SHA256: both patched crypt32 DLLs and metadata VERIFIED", flush=True)
    else:
        # This is sufficient cryptographic release evidence. Do not modify
        # an installation just to satisfy our own earlier JSON-only gate.
        print("GE Proton Wand SHA256: WAND-HYBRID.json ABSENT; BOTH exact proven "
              "crypt32 DLL hashes VERIFIED. Proceeding read-only without "
              "inventing/replacing metadata.", flush=True)
    return proton.resolve(strict=True)


def find_proton(steamapps: Path) -> tuple[Path, Path]:
    checked = _proton_candidates(steamapps)
    installed = [path for path in checked if path.is_dir()]
    verified: list[Path] = []
    rejected: list[str] = []
    for path in installed:
        try:
            verified.append(_verify_isolated_tool(path.resolve(strict=True)))
        except (Blocked, OSError, ValueError) as exc:
            rejected.append(str(path) + ": " + str(exc))

    distinct = {str(p): p for p in verified}
    if len(distinct) != 1:
        archive_paths = _known_recovery_archives()
        explanation = (
            "Expected one verified GE Proton Wand SHA256 tool; found " +
            str(len(installed)) + " candidate(s) in " + str(len(checked)) +
            " checked locations, " + str(len(distinct)) + " verified."
        )
        if rejected:
            explanation += " Candidate errors: " + " | ".join(rejected[:4])
        if archive_paths:
            explanation += " Previous tested-release recovery files FOUND (not installed): " + (
                " | ".join(str(p) for p in archive_paths[:6]))
        else:
            explanation += (" No known previous release/archive paths found. "
                            "The 0.1.41 release was previously built at "
                            "~/Desktop/wand-native-0.1.41/dist/ and "
                            "~/src/wand-ge-proton/build/.")
        explanation += (
            " The current repo does not include its compiled crypt32 payload. "
            "No Proton tools were installed, modified or downloaded."
        )
        raise Blocked(explanation)

    home = Path.home()
    roots = [
        home / ".steam/root",
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
    ]
    steam_root = next((p.resolve() for p in roots if p.is_dir()), None)
    if steam_root is None:
        raise Blocked("Steam client root is missing; isolated Proton tool verified but "
                      "no client install directory was found")
    return next(iter(distinct.values())), steam_root


def _client_module():
    path = Path(__file__).resolve().with_name("gameweld-wemod-enhancer.py")
    spec = importlib.util.spec_from_file_location("gameweld_wemod_client", path)
    if spec is None or spec.loader is None:
        raise Blocked("GameWeld Wand client verification helper missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verified_client() -> Path:
    helper = _client_module()
    root, reason = helper.resolve_read_only_client(
        helper.available_clients(None), helper.installed_helper_dir())
    if root is None:
        raise Blocked("No uniquely verified patched Wand/WeMod client: " + reason)
    candidates = [root / name for name in ("Wand.exe", "WeMod.exe", "wand.exe", "wemod.exe")]
    valid = [c for c in candidates if c.is_file() and not c.is_symlink()]
    if len(valid) != 1:
        raise Blocked("The verified client must have exactly one direct Wand.exe/WeMod.exe executable")
    return valid[0].resolve(strict=True)


def choose_game_exe(game: Path, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute() or not p.is_file():
            raise Blocked("Explicit Windows game .exe must be an existing absolute path")
        p = p.resolve(strict=True)
        if not p.is_relative_to(game) or p.suffix.lower() != ".exe":
            raise Blocked("Explicit game .exe must belong to the selected installed Steam game")
        return p
    # Only exact main-name matches qualify; avoid selecting launchers,
    # crash handlers, installers or an arbitrary shipping executable.
    wanted = re.sub(r"[^a-z0-9]", "", game.name.lower())
    choices = []
    for p in game.rglob("*.exe"):
        if len(p.relative_to(game).parts) > 4:
            continue
        if p.is_symlink() or not p.is_file():
            continue
        if re.sub(r"[^a-z0-9]", "", p.stem.lower()) == wanted:
            choices.append(p.resolve(strict=True))
        if len(choices) > 16:
            break
    if len(choices) != 1:
        raise Blocked("Unable to select one exact Windows game executable (" +
                      str(len(choices)) + " exact matches). Set WAND_GAME_EXE explicitly to the correct file.")
    return choices[0]


def existing_game_process(appid: str, game_dir: Path) -> bool:
    inspected = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        inspected += 1
        if inspected > 10000:
            break
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            with (entry / "environ").open("rb") as f:
                raw = f.read(131072)
            if any((key + appid).encode() in raw.split(b"\0") for key in
                   ("SteamAppId=", "SteamGameId=", "STEAM_COMPAT_APP_ID=")):
                name = (entry / "comm").read_text(errors="replace").strip().lower()
                if (name.endswith(".exe") and name not in {
                    "services.exe", "explorer.exe", "wineboot.exe", "steam.exe",
                    "svchost.exe", "rpcss.exe", "plugplay.exe", "conhost.exe",
                    "crashpad.exe", "crashreport.exe", "start.exe",
                    "rundll32.exe", "msiexec.exe", "reg.exe",
                }):
                    return True
            cwd = (entry / "cwd").resolve()
            if cwd.is_relative_to(game_dir):
                cmd = (entry / "cmdline").read_bytes().lower()
                if b".exe" in cmd and b"wineboot" not in cmd:
                    return True
        except (OSError, ValueError):
            continue
    return False


def dwrite_source(wand: Path) -> tuple[Path, Path]:
    target = wand.parent / "DWriteCore.dll"
    shared = Path.home() / ".local/share/wand/dwritecore/2.1.0/DWriteCore.dll"
    for candidate in (target, shared):
        if candidate.is_symlink():
            continue
        try:
            with candidate.open("rb") as f:
                signature = f.read(2)
            if candidate.stat().st_size > 1024 * 1024 and signature == b"MZ":
                return candidate, target
        except OSError:
            continue
    raise Blocked("Microsoft DWriteCore 2.1.0 is not installed. "
                  "The old provider requires it; GameWeld will not download a substitute automatically.")


def plan(appid: str, game_dir: str, game_exe: str | None) -> Plan:
    valid_appid(appid)
    if not game_dir or not Path(game_dir).is_absolute():
        raise Blocked("No verified Steam game installation selected in GameWeld")
    game = Path(game_dir).resolve(strict=True)
    steamapps, compat, prefix = steam_install(game, appid)
    if existing_game_process(appid, game):
        raise Blocked("Selected game is already running; CLOSE it before a managed one-Proton-session launch")
    proton, steamroot = find_proton(steamapps)
    wand = verified_client()
    dwrite, target = dwrite_source(wand)
    user_dir = prefix / "drive_c/users"
    windows_user = "steamuser" if (user_dir / "steamuser").is_dir() else ""
    if not windows_user:
        names = [p.name for p in user_dir.iterdir()
                 if p.is_dir() and p.name.lower() not in
                 ("public", "default", "default user", "all users")]
        if len(names) != 1:
            raise Blocked("Cannot uniquely identify the Windows user profile inside the selected Proton prefix")
        windows_user = names[0]
    if any(ch in windows_user for ch in ('"', '%', '!', '\r', '\n', '\\', ':')):
        raise Blocked("Windows user profile cannot safely be passed to the managed session")
    statehome = os.environ.get("XDG_STATE_HOME")
    if statehome and not Path(statehome).is_absolute():
        raise Blocked("XDG_STATE_HOME must be absolute")
    state = Path(statehome) if statehome else Path.home() / ".local/state"
    return Plan(appid, game, choose_game_exe(game, game_exe), wand, proton,
                steamroot, compat, prefix, dwrite, target,
                state / "gameweld/managed-wand", windows_user)


def to_win(path: Path, prefix: Path) -> str:
    canonical = path.resolve(strict=False)
    mappings = []
    for entry in (prefix / "dosdevices").glob("?:"):
        try:
            drive = entry.name[0].upper()
            if drive == "Z":
                continue
            mapped = entry.resolve(strict=True)
            if canonical == mapped or canonical.is_relative_to(mapped):
                mappings.append((len(mapped.parts), drive, mapped))
        except (OSError, ValueError):
            continue
    if mappings:
        _, drive, mapped = max(mappings, key=lambda x: x[0])
        value = drive + ":\\" + str(canonical.relative_to(mapped)).replace("/", "\\")
    else:
        value = "Z:" + str(canonical).replace("/", "\\")
    if any(ch in value for ch in ('"', "%", "!", "\r", "\n")):
        raise Blocked("Unsafe batch path characters in selected executable or stage file")
    return value


def build_batch(p: Plan, batch: Path, stage: Path) -> str:
    wand = to_win(p.wand_exe, p.prefix)
    game = to_win(p.game_exe, p.prefix)
    wd = to_win(p.wand_exe.parent, p.prefix)
    gd = to_win(p.game_exe.parent, p.prefix)
    trace = to_win(stage, p.prefix)
    user = p.windows_user
    lines = [
        "@echo off",
        "set \"SteamAppId=" + p.appid + "\"",
        "set \"SteamGameId=" + p.appid + "\"",
        "set \"SteamOverlayGameId=" + p.appid + "\"",
        "set \"STEAM_COMPAT_APP_ID=" + p.appid + "\"",
        "echo batch-start > \"" + trace + "\"",
        "set \"WAND_SAVED_USERPROFILE=%USERPROFILE%\"",
        "set \"WAND_SAVED_APPDATA=%APPDATA%\"",
        "set \"WAND_SAVED_LOCALAPPDATA=%LOCALAPPDATA%\"",
        "set \"WAND_SAVED_HOMEDRIVE=%HOMEDRIVE%\"",
        "set \"WAND_SAVED_HOMEPATH=%HOMEPATH%\"",
        "set \"USERPROFILE=C:\\users\\" + user + "\"",
        "set \"APPDATA=C:\\users\\" + user + "\\AppData\\Roaming\"",
        "set \"LOCALAPPDATA=C:\\users\\" + user + "\\AppData\\Local\"",
        "set \"HOMEDRIVE=C:\"",
        "set \"HOMEPATH=\\users\\" + user + "\"",
        "echo starting-wand >> \"" + trace + "\"",
        "start \"\" /D \"" + wd + "\" \"" + wand + "\"",
        "set \"USERPROFILE=%WAND_SAVED_USERPROFILE%\"",
        "set \"APPDATA=%WAND_SAVED_APPDATA%\"",
        "set \"LOCALAPPDATA=%WAND_SAVED_LOCALAPPDATA%\"",
        "set \"HOMEDRIVE=%WAND_SAVED_HOMEDRIVE%\"",
        "set \"HOMEPATH=%WAND_SAVED_HOMEPATH%\"",
        "echo starting-game >> \"" + trace + "\"",
        "start \"\" /D \"" + gd + "\" \"" + game + "\"",
        "echo dispatched >> \"" + trace + "\"",
        "exit /b 0",
    ]
    return "\r\n".join(lines) + "\r\n"


def play(p: Plan) -> None:
    # No modification occurs in the read-only check. Confirmed play may copy
    # the existing Microsoft DWriteCore DLL beside its exact Wand executable.
    if not p.dwrite_target.is_file():
        shutil.copy2(p.dwrite_source, p.dwrite_target)
    p.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    batch = p.state_dir / ("appid-" + p.appid + "-launch.bat")
    stage = p.state_dir / ("appid-" + p.appid + "-stage.txt")
    log = p.state_dir / ("appid-" + p.appid + "-proton.log")
    if any(x.is_symlink() for x in (batch, stage, log)):
        raise Blocked("Managed session refuses symlinked batch/stage/log output")
    body = build_batch(p, batch, stage)
    batch.write_bytes(body.encode("utf-8"))
    os.chmod(batch, 0o600)
    stage.unlink(missing_ok=True)
    env = dict(os.environ)
    # Pin only this managed Wine child to native-first version.dll loading.
    # Leave unrelated DLL overrides unchanged and avoid global modifications.
    overrides = [part for part in env.get("WINEDLLOVERRIDES", "").split(";")
                 if part and not part.lower().startswith("version=")]
    env["WINEDLLOVERRIDES"] = ";".join(overrides + ["version=n,b"])
    env.update({
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(p.steam_root),
        "STEAM_COMPAT_DATA_PATH": str(p.compat),
        "WINEPREFIX": str(p.prefix),
        "STEAM_COMPAT_APP_ID": p.appid,
        "SteamAppId": p.appid,
        "SteamGameId": p.appid,
        "STEAM_COMPAT_LIBRARY_PATHS": str(p.game_dir.parents[2]),
        "STEAM_COMPAT_INSTALL_PATH": str(p.game_dir),
    })
    with log.open("w", encoding="utf-8") as stream:
        stream.write("GameWeld managed Wand one-session request (not game/trainer proof)\n")
        stream.flush()
        child = subprocess.Popen(
            [str(p.proton), "waitforexitandrun", str(batch)],
            cwd=str(p.game_dir), env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    print("One managed Proton session: REQUEST SENT")
    print("Proton launch PID: " + str(child.pid))
    print("Game startup, Wand renderer, trainer attachment: NOT VERIFIED")
    print("Stage log: " + str(stage))
    print("Proton log: " + str(log))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("check", "play"))
    ap.add_argument("--appid", required=True)
    ap.add_argument("--game-provider", default="steam")
    ap.add_argument("--game-dir", required=True)
    ap.add_argument("--game-exe")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args(argv)
    if a.game_provider != "steam":
        raise Blocked("The managed one-Proton-session integration requires an installed standard Steam game")
    if a.action == "play" and not a.confirm:
        raise Blocked("Managed session requires explicit --confirm")
    p = plan(a.appid, a.game_dir, a.game_exe or os.environ.get("WAND_GAME_EXE"))
    print(LABEL + ": READINESS PASS")
    print("Selected app: " + p.appid)
    print("Game executable: " + str(p.game_exe))
    print("Isolated GE Proton Wand SHA256: VERIFIED (both crypt32 payload hashes)")
    print("DWriteCore: VERIFIED (local or shared)")
    print("Wand client: VERIFIED patch and direct executable")
    if a.action == "check":
        print("Read-only: no real game, Wand, Proton, patcher or installer launched")
        return 0
    play(p)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError) as exc:
        print("GameWeld managed Wand: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
