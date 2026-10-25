#!/usr/bin/env python3
"""Experimental GameWeld Steam compatibility tool (explicit opt-in).

Registering merely makes a tool appear in Steam's Compatibility dropdown.
It does not select the tool for a game or modify Steam launch options, game
prefixes, or installed WeMod clients. All game/helper execution happens
ONLY after Steam itself selects GameWeld Bridge for that title.
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


def bridge_launcher_sync(*, source: Path | None = None) -> str:
    """Read-only comparison; a repository update does not refresh Steam's copy."""
    install = private_tool_dir()
    launcher = install / "launcher.py"
    source = source or Path(__file__).resolve()
    if (install.is_symlink() or not install.is_dir() or
            launcher.is_symlink() or not launcher.is_file()):
        return "NOT INSTALLED or unsafe installation"
    if source.is_symlink() or not source.is_file():
        return "UNKNOWN (source unavailable)"
    try:
        installed_hash = hashlib.sha256(launcher.read_bytes()).hexdigest()
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    except OSError:
        return "UNKNOWN (unreadable installation/source)"
    if installed_hash == source_hash:
        return "UP TO DATE"
    return "UPDATE AVAILABLE (registered Steam launcher differs from current GameWeld source)"


def upgrade_bridge(*, source: Path | None = None) -> tuple[Path, Path | None]:
    """Explicitly update only the registered private launcher; never Steam settings.

    Atomically replaces launcher.py, retaining a hash-named backup. Existing
    per-game mappings and working Proton/client configurations stay unchanged.
    """
    install = private_tool_dir()
    launcher = install / "launcher.py"
    source = source or Path(__file__).resolve()
    if (install.is_symlink() or not install.is_dir() or
            launcher.is_symlink() or not launcher.is_file() or
            source.is_symlink() or not source.is_file()):
        raise ValueError("GameWeld Bridge is not safely installed; cannot update launcher")
    if not ((install / "compatibilitytool.vdf").is_file() and
            (install / "toolmanifest.vdf").is_file() and
            (install / "compatibilitytool.vdf").read_text() == VDF_COMPAT and
            (install / "toolmanifest.vdf").read_text() == VDF_TOOL):
        raise ValueError("Registered Bridge manifests differ from the expected files")
    # Do not change an unknown tool simply because its path resembles GameWeld.
    current = launcher.read_bytes()
    candidate = source.read_bytes()
    if not candidate or b"def steam_invocation(" not in candidate or b"TOOL_ID =" not in candidate:
        raise ValueError("GameWeld Bridge source failed launcher integrity checks")
    if current == candidate:
        return launcher, None
    old_hash = hashlib.sha256(current).hexdigest()
    backup = install / f"launcher.py.backup-{old_hash[:16]}"
    if backup.is_symlink():
        raise ValueError("Refusing symlinked Bridge launcher backup")
    if backup.exists():
        if not backup.is_file() or backup.read_bytes() != current:
            raise ValueError("Existing Bridge backup has unexpected contents")
    else:
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(current)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            backup.unlink(missing_ok=True)
            raise
    fd, temporary = tempfile.mkstemp(prefix=".gameweld-launcher-", dir=install)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(candidate)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, 0o755)
        os.replace(temporary, launcher)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return launcher, backup


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


def resolve_setup(appid: str, game_dir: Path, *,
                  steam_root: Path | None = None,
                  proton: Path | None = None,
                  client: Path | None = None) -> tuple[Path, Path, Path]:
    """Resolve only exact installed-game evidence; no arbitrary Proton guessing.

    A setup request never changes a title that has existing Bridge settings.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid selected Steam AppID")
    if appid in load_config():
        raise ValueError("Steam Bridge already configured for this game; existing working setup preserved")
    game = game_dir.expanduser().resolve(strict=True)
    library = game.parent.parent.parent
    if not (game.is_dir() and game.parent.name == "common"
            and game.parent.parent.name == "steamapps"
            and (library / "steamapps" / ("appmanifest_" + appid + ".acf")).is_file()):
        raise ValueError("Selected game must be a Steam installation with a matching AppID manifest")
    if steam_root:
        root = steam_root.expanduser().resolve(strict=True)
    else:
        # The Steam client root, not an arbitrary secondary game-library root.
        candidates = (Path.home() / ".steam/root", Path.home() / ".local/share/Steam")
        found = [p.resolve() for p in candidates if p.is_dir()
                 and (p / "steamapps").is_dir()]
        distinct = list(dict.fromkeys(found))
        if len(distinct) == 1:
            root = distinct[0]
        elif not distinct and (library / "steam.sh").is_file():
            root = library
        else:
            raise ValueError("Cannot unambiguously locate the Steam client root; pass --steam-root")
    if not (root / "steamapps").is_dir():
        raise ValueError("Selected Steam client root has no steamapps directory")

    if proton:
        selected_proton = validate_proton(proton)
    else:
        helper = Path(__file__).with_name("gameweld-deckcheatz-proton.py")
        if not helper.is_file():
            raise ValueError("GameWeld Steam Proton resolver is not installed")
        spec = importlib.util.spec_from_file_location("gw_bridge_proton_resolver", helper)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load exact-game Proton resolver")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        options = argparse.Namespace(
            appid=appid, steam_root=str(root), install_dir=str(game),
            compatdata=str(library / "steamapps/compatdata" / appid),
            preferred_name="", preferred_path="")
        resolution = module.resolve(options)
        path = resolution.get("selected", "")
        ranked = resolution.get("candidates", [])
        best = next((c for c in ranked if c.get("path") == path), None)
        if not path or not best or best.get("score", 0) < 90:
            raise ValueError(
                "No exact Proton mapping or prefix runtime hint for this title; "
                "select Proton in Steam or provide --proton explicitly"
            )
        selected_proton = validate_proton(Path(path))
    managed = xdg_dir("XDG_DATA_HOME", ".local/share") / "gameweld/deckcheatz/wemod_data/wemod_bin"
    selected_client = validate_client(client if client else managed)
    return root, selected_proton, selected_client


def setup_game(appid: str, game_dir: Path, *,
               steam_root: Path | None = None,
               proton: Path | None = None,
               client: Path | None = None) -> Path:
    """Register an optional Steam tool and save a NEW game in game-only mode."""
    root, selected_proton, selected_client = resolve_setup(
        appid, game_dir, steam_root=steam_root, proton=proton, client=client)
    # Recheck just before mutation: never clobber a working configured title.
    if appid in load_config():
        raise ValueError("Bridge configuration changed during setup; refusing overwrite")
    target = register(root)
    configure(appid, selected_proton, selected_client, enabled=False)
    return target


def play_configured_game(appid: str, *, launch=None,
                         associated_processes=None) -> int:
    """Request Steam Play only for an enabled, registered Bridge game.

    Launch uses Steam's own compatibility-tool selection, not a second Proton
    wrapper. Unknown Steam selections are disclosed, never asserted valid.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid selected Steam AppID")
    entry = load_config().get(appid)
    if not isinstance(entry, dict):
        raise ValueError("This title has no GameWeld Bridge configuration")
    if not entry.get("trainer_enabled"):
        raise ValueError("WeMod auto-start is DISABLED for this title; enable it first")
    proton = validate_proton(Path(entry["proton"]))
    validate_client(Path(entry["client"]))
    roots = [proton.parents[3], Path.home() / ".steam/root",
             Path.home() / ".local/share/Steam"]
    registered = []
    for root in roots:
        target = root / "compatibilitytools.d" / NAME
        if target.is_symlink() and target.resolve() == private_tool_dir().resolve():
            if str(root.resolve()) not in [str(x.resolve()) for x in registered]:
                registered.append(root)
    if not registered:
        raise ValueError(
            "GameWeld Bridge is not registered in the selected Steam installation; "
            "run Bridge setup before requesting Steam Play"
        )
    if launch is None or associated_processes is None:
        source = Path(__file__).with_name("gameweld-steam-handoff.py")
        if not source.is_file():
            raise ValueError("GameWeld's Steam handoff helper is not installed")
        spec = importlib.util.spec_from_file_location("gw_bridge_play_handoff", source)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load the Steam handoff helper")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        launch = module.run_launch if launch is None else launch
        associated_processes = (module.associated_process_count
                                if associated_processes is None else associated_processes)
    if associated_processes(appid):
        raise ValueError(
            "Steam reports an existing same-AppID game session. "
            "Do not start a duplicate game/trainer; use the running one."
        )
    print("GameWeld Bridge: Steam game launch REQUESTED (not yet verified)")
    print("Steam uses the game's current Compatibility selection; "
          "GameWeld does not change it or modify launch options.")
    print("WeMod will auto-start only if Steam actually selects GameWeld Bridge.")
    return int(launch(appid))


def primary_ui_state(appid: str) -> tuple[str, str]:
    """Read-only and fail-closed primary action for one Steam game.

    This only describes the saved configuration. The actual game launch
    continues to revalidate all prerequisites under play_configured_game.
    """
    if not valid_appid(appid):
        return "blocked", "Select an installed Steam Windows game."
    config = load_config()
    entry = config.get(appid)
    if not isinstance(entry, dict):
        return "setup", "Steam Bridge isn't configured for this game. Set it up first."
    try:
        proton = validate_proton(Path(entry["proton"]))
        client = validate_client(Path(entry["client"]))
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return "repair", "Saved Steam Bridge installation needs repair: " + str(exc)
    if not entry.get("trainer_enabled"):
        return "enable", "Steam Bridge is configured; enable WeMod auto-start for the next launch."
    selection = steam_compat_selection(appid, configured_proton=proton)
    if not selection.startswith("GAMEWELD BRIDGE SELECTED"):
        return "steam", (
            "Select GameWeld Bridge (Experimental) under this game's Steam "
            "Properties > Compatibility before playing with WeMod. " + selection
        )
    registered_roots = [proton.parents[3], Path.home() / ".steam/root",
                        Path.home() / ".local/share/Steam"]
    installed = private_tool_dir().resolve()
    if not any((root / "compatibilitytools.d" / NAME).is_symlink()
               and (root / "compatibilitytools.d" / NAME).resolve() == installed
               for root in registered_roots):
        return "repair", "Steam Bridge launcher registration is missing; repair setup in Settings."
    if not ((client / "version.dll").is_file()
            and (client / "resources/app.asar.backup").is_file()):
        return "repair", "WeMod Enhancer patch prerequisites are missing; check Advanced Providers."
    return "play", "Steam Bridge and WeMod are configured. Launch still requires confirmation."


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


def set_trainer_gpu_fallback(appid: str, enabled: bool) -> bool:
    """Opt-in Electron rendering workaround for just this WeMod launch.

    Does not change the game's graphics, Steam options or other AppIDs.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid Steam AppID for WeMod display workaround")
    config = load_config()
    entry = config.get(appid)
    if not isinstance(entry, dict):
        raise ValueError("This game has no configured Steam Bridge")
    validate_proton(Path(entry["proton"]))
    validate_client(Path(entry["client"]))
    entry["wemod_disable_gpu"] = bool(enabled)
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
        stream.write(("WeMod GPU fallback: " + ("enabled" if entry.get("wemod_disable_gpu") is True else "disabled") + "\n").encode())
        stream.flush()
        child = subprocess.Popen(
            [str(proton), "runinprefix", str(client / "WeMod.exe")]
            + (["--disable-gpu"] if entry.get("wemod_disable_gpu") is True else []),
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


def steam_compat_selection(appid: str, *,
                           steam_roots: list[Path] | None = None,
                           configured_proton: Path | None = None) -> str:
    """Read Steam's stored per-game compatibility selection, without mutation.

    Do not assume that GameWeld is selected merely because it is installed.
    Steam can be running with unsaved configuration changes, so even a
    matching VDF mapping is only saved-settings evidence, not a running session.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid game Steam AppID")
    if steam_roots is None:
        candidates = [Path.home() / ".steam/root", Path.home() / ".local/share/Steam"]
        if configured_proton is not None:
            proton = Path(configured_proton).expanduser()
            # Official Steam Proton installs live in steamapps/common/<tool>.
            if proton.parent.parent.name == "common" and proton.parent.parent.parent.name == "steamapps":
                candidates.insert(0, proton.parent.parent.parent.parent)
        steam_roots = candidates
    source = Path(__file__).with_name("gameweld-steam-shortcuts.py")
    if not source.is_file():
        return "UNVERIFIED (Steam settings resolver unavailable)"
    spec = importlib.util.spec_from_file_location("gw_bridge_steam_selection", source)
    if spec is None or spec.loader is None:
        return "UNVERIFIED (Steam settings resolver unavailable)"
    import sys as _sys
    module = importlib.util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found: set[str] = set()
    roots_seen: set[Path] = set()
    for root in steam_roots:
        try:
            root = Path(root).expanduser().resolve(strict=True)
        except OSError:
            continue
        if root in roots_seen or not (root / "steamapps").is_dir():
            continue
        roots_seen.add(root)
        user_data = root / "userdata"
        accounts = []
        try:
            accounts = [p for p in user_data.iterdir() if p.is_dir() and p.name.isdecimal()]
        except OSError:
            pass
        # Include a synthetic dummy user path for installations whose
        # global config.vdf contains the mapping but userdata is empty.
        if not accounts:
            accounts = [root / "userdata/0"]
        for account in accounts:
            name, scope, _, _, _ = module._compat_tool_mapping(root, account, int(appid))
            if name and scope == "exact":
                found.add(name)
    if not found:
        return "UNVERIFIED (no saved exact game mapping readable)"
    if len(found) > 1:
        return "UNVERIFIED (conflicting saved tool mappings)"
    selected = next(iter(found))
    token = re.sub(r"[^a-z0-9]", "", selected.casefold())
    if token in {"gameweldbridgeexperimental", "gameweldbridge"}:
        return "GAMEWELD BRIDGE SELECTED (saved Steam mapping)"
    return f"OTHER TOOL SELECTED (saved Steam mapping: {selected})"


def format_status(appid: str | None = None, *,
                  game_dir: Path | None = None,
                  steam_root: Path | None = None) -> str:
    config = load_config()
    if appid:
        if not valid_appid(appid):
            raise ValueError("Invalid game Steam AppID")
        entry = config.get(appid)
        if not isinstance(entry, dict):
            lines = [f"GameWeld Bridge AppID {appid}: NOT CONFIGURED",
                     "No Steam compatibility selection was changed."]
            if game_dir is not None:
                try:
                    root, proton, client = resolve_setup(
                        appid, game_dir, steam_root=steam_root)
                except (ValueError, OSError) as exc:
                    lines.append("First-time setup readiness: BLOCKED")
                    lines.append("Reason: " + str(exc))
                else:
                    lines.append("First-time setup readiness: READY (read-only)")
                    lines.append("Verified Steam root: " + str(root))
                    lines.append("Exact Proton candidate: " + str(proton))
                    lines.append("Existing managed WeMod client: " + str(client))
                    lines.append("Setup will start game-only, with WeMod auto-start DISABLED.")
                    lines.append("Steam Compatibility selection remains a separate manual step.")
            return "\n".join(lines)
        return ("GameWeld Bridge AppID: " + appid +
                "\nConfigured Proton: " + str(entry.get("proton", "")) +
                "\nConfigured WeMod: " + str(entry.get("client", "")) +
                "\nTrainer auto-start: " +
                ("ENABLED" if entry.get("trainer_enabled") else "DISABLED") +
                "\nWeMod GPU fallback: " +
                ("ENABLED (WeMod.exe --disable-gpu)" if entry.get("wemod_disable_gpu") is True else "DISABLED (default)") +
                "\nSteam Compatibility selection: " +
                steam_compat_selection(appid, configured_proton=Path(entry.get("proton", ""))) +
                "\nInstalled Steam Bridge launcher: " + bridge_launcher_sync() +
                "\nEnhancer patch prerequisites: " +
                ("PRESENT (files only; DLL runtime loading not verified)"
                 if (Path(entry.get("client", "")) / "version.dll").is_file()
                 and (Path(entry.get("client", "")) / "resources/app.asar.backup").is_file()
                 else "MISSING or unverified") +
                "\nChanges take effect on the next game launch.")
    return (f"Staged launcher: {private_tool_dir() / 'launcher.py'}\n" +
            f"Installed Steam Bridge launcher: {bridge_launcher_sync()}\n" +
            f"Configured AppIDs: {', '.join(sorted(config)) or 'none'}\n" +
            "No Steam game compatibility setting or launch option has been changed.")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"status", "ui-state", "register", "configure", "setup", "trainer-on", "trainer-off", "trainer-gpu-off", "trainer-gpu-on", "play", "upgrade"}:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("action", choices=("status", "ui-state", "register", "configure", "setup", "trainer-on", "trainer-off", "trainer-gpu-off", "trainer-gpu-on", "play", "upgrade"))
        parser.add_argument("--steam-root", type=Path)
        parser.add_argument("--game-dir", type=Path)
        parser.add_argument("--appid")
        parser.add_argument("--proton", type=Path)
        parser.add_argument("--client", type=Path)
        parser.add_argument("--enable-trainer", action="store_true")
        parser.add_argument("--delay-seconds", type=int, default=12)
        parser.add_argument("--confirm", action="store_true")
        args = parser.parse_args()
        if args.action == "ui-state":
            if not args.appid:
                raise ValueError("UI state requires --appid")
            action, reason = primary_ui_state(args.appid)
            print(action + "\t" + reason.replace("\t", " ").replace("\n", " "))
            return 0
        if args.action == "status":
            print("GameWeld Bridge experimental compatibility tool (read-only)")
            print(format_status(args.appid, game_dir=args.game_dir,
                                steam_root=args.steam_root))
            return 0
        if not args.confirm:
            raise ValueError("Registration/configuration requires explicit --confirm")
        if args.action == "upgrade":
            launcher, backup = upgrade_bridge()
            print(f"GameWeld Bridge launcher: {launcher}")
            print("Update result: " + ("UPDATED" if backup is not None else "ALREADY CURRENT"))
            if backup is not None:
                print(f"Previous launcher backup: {backup}")
            print("No game, Wine prefix, WeMod patch, per-game setting or Steam mapping changed.")
            print("Restart Steam before the next game launch to load the updated compatibility-tool launcher.")
        elif args.action == "register":
            if args.steam_root is None:
                raise ValueError("Register requires --steam-root")
            target = register(args.steam_root.expanduser().resolve(strict=True))
            print(f"Registered: {target}")
            print("Restart Steam, then explicitly select GameWeld Bridge (Experimental) per game.")
        elif args.action == "play":
            if not args.appid:
                raise ValueError("Play requires --appid")
            return play_configured_game(args.appid)
        elif args.action == "setup":
            if not all((args.appid, args.game_dir)):
                raise ValueError("Setup requires --appid and --game-dir")
            target = setup_game(args.appid, args.game_dir,
                                steam_root=args.steam_root,
                                proton=args.proton, client=args.client)
            print(f"Steam Bridge registered: {target}")
            print(f"Steam Bridge configured AppID {args.appid}: game-only (trainer disabled)")
            print("Restart Steam and select GameWeld Bridge (Experimental) under this game's Compatibility tab.")
            print("Steam Launch Options and other game configurations remain unchanged.")
        elif args.action in {"trainer-on", "trainer-off"}:
            if not args.appid:
                raise ValueError("Trainer toggle requires --appid")
            enabled = set_trainer_enabled(args.appid, args.action == "trainer-on")
            print(f"GameWeld Bridge trainer for AppID {args.appid}: " +
                  ("ENABLED" if enabled else "DISABLED"))
            print("Takes effect on the next Steam game launch; no Steam settings or running processes changed.")
        elif args.action in {"trainer-gpu-off", "trainer-gpu-on"}:
            if not args.appid:
                raise ValueError("WeMod display workaround requires --appid")
            disable_gpu = set_trainer_gpu_fallback(args.appid, args.action == "trainer-gpu-off")
            print(f"WeMod Electron GPU rendering for AppID {args.appid}: " +
                  ("DISABLED (--disable-gpu)" if disable_gpu else "NORMAL (default)"))
            print("Only WeMod's next launch is affected. Game graphics, Proton selection, Steam options and other games unchanged.")
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
