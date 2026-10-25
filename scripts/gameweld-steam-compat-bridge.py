#!/usr/bin/env python3
"""Experimental GameWeld Steam compatibility tool (explicit opt-in).

Registering merely makes a tool appear in Steam's Compatibility dropdown.
It does not select the tool for a game or modify Steam launch options, game
prefixes, or installed WeMod clients. All game/helper execution happens
ONLY after Steam itself selects GameWeld Bridge for that title.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

NAME = "GameWeld-Bridge"
TOOL_ID = "gameweld-bridge-experimental"
LAUNCH_VERBS = {"run", "waitforexitandrun"}
RUNTIME_DIRS = {
    "4183110": "SteamLinuxRuntime_4",
    "1628350": "SteamLinuxRuntime_sniper",
    "1391110": "SteamLinuxRuntime_soldier",
}
MAX_CONFIGURATION = 1024 * 1024
VDF_COMPAT = '''"compatibilitytools"
{
  "compat_tools"
  {
    "gameweld-bridge-experimental"
    {
      "install_path" "."
      "display_name" "GameWeld Bridge (Experimental)"
      "from_oslist" "windows"
      "to_oslist" "linux"
    }
  }
}
'''
VDF_TOOL = '''"manifest"
{
  "version" "2"
  "commandline" "/launcher.py %verb%"
}
'''


def valid_appid(appid: str) -> bool:
    return appid.isascii() and appid.isdecimal() and not appid.startswith("0") and len(appid) <= 10 and int(appid) < 2**32


def xdg_dir(variable: str, default: str) -> Path:
    value = os.environ.get(variable)
    if value and not Path(value).is_absolute():
        raise ValueError(f"{variable} must be absolute")
    return Path(value) if value else Path.home() / default


def private_tool_dir() -> Path:
    return xdg_dir("XDG_DATA_HOME", ".local/share") / "gameweld/tools/steam-compat-bridge-v1"


def config_path() -> Path:
    return xdg_dir("XDG_CONFIG_HOME", ".config") / "gameweld/steam-bridge-games.json"


def load_config() -> dict:
    file = config_path()
    if not file.is_file():
        return {}
    if file.is_symlink() or file.stat().st_size > MAX_CONFIGURATION:
        raise ValueError("Unsafe GameWeld compatibility configuration")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GameWeld compatibility configuration is not an object")
    return data


def write_config(config: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("Refusing to overwrite symlinked GameWeld configuration")
    fd, temporary = tempfile.mkstemp(prefix=".gameweld-bridge-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_proton(path: Path) -> Path:
    path = path.expanduser().resolve(strict=True)
    if path.name != "proton" or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Explicit --proton must select an executable Proton launcher")
    if not (path.parent / "toolmanifest.vdf").is_file():
        raise ValueError("Proton runtime toolmanifest.vdf is missing")
    return path


def validate_client(path: Path) -> Path:
    path = path.expanduser().resolve(strict=True)
    if path.is_symlink() or not (path / "WeMod.exe").is_file() or not (path / "resources/app.asar").is_file():
        raise ValueError("Explicit --client must select a complete standalone WeMod installation")
    if (path / "WeMod.exe").is_symlink() or (path / "resources/app.asar").is_symlink():
        raise ValueError("Refusing symlinked WeMod binaries or ASAR")
    return path


def register(steam_root: Path, *, source: Path | None = None) -> Path:
    if not steam_root.is_dir() or not (steam_root / "steamapps").is_dir():
        raise ValueError("Steam root must exist and contain steamapps")
    parent = steam_root / "compatibilitytools.d"
    install = private_tool_dir()
    source = source or Path(__file__).resolve()
    if source.is_symlink() or not source.is_file():
        raise ValueError("GameWeld launcher source is not a regular file")
    if install.exists() or install.is_symlink():
        if not install.is_dir() or install.is_symlink():
            raise ValueError("Existing GameWeld Bridge install is unsafe")
        if not (install / "launcher.py").is_file():
            raise ValueError("An incomplete GameWeld Bridge install already exists; refusing overwrite")
    else:
        install.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix=".gameweld-bridge-", dir=install.parent) as td:
            stage = Path(td) / "tool"
            stage.mkdir()
            shutil.copyfile(source, stage / "launcher.py")
            (stage / "launcher.py").chmod(0o755)
            (stage / "compatibilitytool.vdf").write_text(VDF_COMPAT, encoding="utf-8")
            (stage / "toolmanifest.vdf").write_text(VDF_TOOL, encoding="utf-8")
            stage.rename(install)
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / NAME
    if target.is_symlink():
        if target.resolve() != install.resolve():
            raise ValueError("Another compatibility tool occupies GameWeld Bridge's name")
    elif target.exists():
        raise ValueError("Refusing to replace an existing Steam compatibility tool")
    else:
        target.symlink_to(install, target_is_directory=True)
    return target


def configure(appid: str, proton: Path, client: Path, *,
              enabled: bool = False, delay: int = 12) -> None:
    if not valid_appid(appid):
        raise ValueError("Invalid game Steam AppID")
    if not 0 <= delay <= 45:
        raise ValueError("Delay must be between 0 and 45 seconds")
    proton = validate_proton(proton)
    client = validate_client(client)
    config = load_config()
    config[appid] = {
        "proton": str(proton),
        "client": str(client),
        "trainer_enabled": bool(enabled),
        "delay_seconds": delay,
    }
    write_config(config)


def set_trainer_enabled(appid: str, enabled: bool) -> bool:
    """Update an existing verified per-game bridge config; never select Steam's tool."""
    if not valid_appid(appid):
        raise ValueError("Invalid game Steam AppID")
    config = load_config()
    entry = config.get(appid)
    if not isinstance(entry, dict):
        raise ValueError("GameWeld Bridge is not yet configured for this title")
    # Fail closed on stale configuration; do not toggle an arbitrary path.
    validate_proton(Path(entry["proton"]))
    validate_client(Path(entry["client"]))
    entry["trainer_enabled"] = bool(enabled)
    write_config(config)
    return enabled


def game_appid() -> str:
    compat = os.environ.get("STEAM_COMPAT_DATA_PATH", "")
    if compat and Path(compat).name.isdecimal():
        return Path(compat).name
    return os.environ.get("SteamAppId", "") or os.environ.get("SteamGameId", "")


def runtime_entry(proton: Path, steam_root: Path) -> Path:
    manifest = proton.parent / "toolmanifest.vdf"
    clean = re.sub(r"//[^\n]*", "", manifest.read_text(encoding="utf-8", errors="replace"))
    match = re.search(r'"require_tool_appid"\s+"(\d+)"', clean)
    name = RUNTIME_DIRS.get(match.group(1)) if match else None
    if not name:
        raise ValueError("Proton needs an unsupported or unspecified Steam runtime")
    entry = steam_root / "steamapps/common" / name / "_v2-entry-point"
    if not entry.is_file() or not os.access(entry, os.X_OK):
        raise ValueError("Required Steam runtime entry point is unavailable")
    return entry


def is_game_start(verb: str, argv: list[str]) -> bool:
    if verb not in LAUNCH_VERBS:
        return False
    disallowed = {"installscript", "steam.exe", "steamworks"}
    return not any(Path(x).name.lower() in disallowed for x in argv)


def start_trainer(entry: dict, appid: str, proton: Path) -> subprocess.Popen | None:
    if not entry.get("trainer_enabled"):
        return None
    client = validate_client(Path(entry["client"]))
    if not ((client / "resources/app.asar.backup").is_file() and
            (client / "version.dll").is_file()):
        print("[GameWeld Bridge] Patch verification prerequisite missing; not launching WeMod", flush=True)
        return None
    state = xdg_dir("XDG_STATE_HOME", ".local/state") / "gameweld"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = state / f"steam-bridge-{appid}-{os.getpid()}-{time.time_ns()}.log"
    env = os.environ.copy()
    env["WINEDLLOVERRIDES"] = ";".join(
        part for part in env.get("WINEDLLOVERRIDES", "").split(";")
        if part and part.split("=", 1)[0].lower() != "version"
    ).strip(";")
    env["WINEDLLOVERRIDES"] = ";".join(filter(None, (env["WINEDLLOVERRIDES"], "version=n,b")))
    with log.open("xb") as stream:
        stream.write(b"GameWeld Steam bridge: unverified WeMod runtime\n")
        stream.flush()
        child = subprocess.Popen(
            [str(proton), "runinprefix", str(client / "WeMod.exe")],
            cwd=client, env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT,
        )
    print(f"[GameWeld Bridge] WeMod handoff PID {child.pid}; log {log}", flush=True)
    return child


def inner(argv: list[str], entry: dict, appid: str) -> int:
    verb, *args = argv
    proton = validate_proton(Path(entry["proton"]))
    if not is_game_start(verb, args):
        return subprocess.call([str(proton), verb, *args])
    game = subprocess.Popen([str(proton), verb, *args])
    trainer = None
    try:
        if entry.get("trainer_enabled"):
            time.sleep(min(max(int(entry.get("delay_seconds", 12)), 0), 45))
            if game.poll() is None:
                try:
                    trainer = start_trainer(entry, appid, proton)
                except (OSError, ValueError) as exc:
                    print(f"[GameWeld Bridge] WeMod not launched: {exc}", flush=True)
        return game.wait()
    finally:
        # Only stop the trainer *launcher* started by this invocation.
        # Never terminate the game or the shared Proton wineserver.
        if trainer is not None and trainer.poll() is None:
            trainer.terminate()


def steam_invocation(argv: list[str]) -> int:
    if not argv:
        raise ValueError("Steam provided no compatibility-tool verb")
    appid = game_appid()
    if not valid_appid(appid):
        raise ValueError("Steam did not identify a valid game AppID")
    config = load_config()
    if appid not in config:
        raise ValueError("Steam selected GameWeld Bridge for an unconfigured AppID; no game started")
    entry = config[appid]
    if os.environ.get("GAMEWELD_BRIDGE_INNER") == "1":
        return inner(argv, entry, appid)
    proton = validate_proton(Path(entry["proton"]))
    root_var = os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH", "")
    if not root_var:
        raise ValueError("Steam did not provide its installation root")
    root = Path(root_var).resolve(strict=True)
    runtime = runtime_entry(proton, root)
    env = os.environ.copy()
    env["GAMEWELD_BRIDGE_INNER"] = "1"
    return subprocess.call([
        str(runtime), "--verb=" + argv[0], "--", sys.executable,
        str(Path(__file__).resolve()), *argv,
    ], env=env)


def format_status(appid: str | None = None) -> str:
    config = load_config()
    if appid:
        if not valid_appid(appid):
            raise ValueError("Invalid game Steam AppID")
        entry = config.get(appid)
        if not isinstance(entry, dict):
            return (f"GameWeld Bridge AppID {appid}: NOT CONFIGURED\n"
                    "No Steam compatibility selection was changed.")
        return ("GameWeld Bridge AppID: " + appid +
                "\nConfigured Proton: " + str(entry.get("proton", "")) +
                "\nConfigured WeMod: " + str(entry.get("client", "")) +
                "\nTrainer auto-start: " +
                ("ENABLED" if entry.get("trainer_enabled") else "DISABLED") +
                "\nActual Steam compatibility-tool selection: NOT VERIFIED" +
                "\nChanges take effect on the next game launch.")
    return (f"Staged launcher: {private_tool_dir() / 'launcher.py'}\n" +
            f"Configured AppIDs: {', '.join(sorted(config)) or 'none'}\n" +
            "No Steam game compatibility setting or launch option has been changed.")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"status", "register", "configure", "trainer-on", "trainer-off"}:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("action", choices=("status", "register", "configure", "trainer-on", "trainer-off"))
        parser.add_argument("--steam-root", type=Path)
        parser.add_argument("--appid")
        parser.add_argument("--proton", type=Path)
        parser.add_argument("--client", type=Path)
        parser.add_argument("--enable-trainer", action="store_true")
        parser.add_argument("--delay-seconds", type=int, default=12)
        parser.add_argument("--confirm", action="store_true")
        args = parser.parse_args()
        if args.action == "status":
            print("GameWeld Bridge experimental compatibility tool (read-only)")
            print(format_status(args.appid))
            return 0
        if not args.confirm:
            raise ValueError("Registration/configuration requires explicit --confirm")
        if args.action == "register":
            if args.steam_root is None:
                raise ValueError("Register requires --steam-root")
            target = register(args.steam_root.expanduser().resolve(strict=True))
            print(f"Registered: {target}")
            print("Restart Steam, then explicitly select GameWeld Bridge (Experimental) per game.")
        elif args.action in {"trainer-on", "trainer-off"}:
            if not args.appid:
                raise ValueError("Trainer toggle requires --appid")
            enabled = set_trainer_enabled(args.appid, args.action == "trainer-on")
            print(f"GameWeld Bridge trainer for AppID {args.appid}: " +
                  ("ENABLED" if enabled else "DISABLED"))
            print("Takes effect on the next Steam game launch; no Steam settings or running processes changed.")
        else:
            if not all((args.appid, args.proton, args.client)):
                raise ValueError("Configure requires --appid, --proton and --client")
            configure(args.appid, args.proton, args.client,
                      enabled=args.enable_trainer, delay=args.delay_seconds)
            print(f"Configured AppID {args.appid}; trainer enabled: {args.enable_trainer}")
        return 0
    return steam_invocation(sys.argv[1:])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[GameWeld Bridge] {exc}", file=sys.stderr)
        sys.exit(2)
