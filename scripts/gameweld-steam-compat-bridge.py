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
    # The repository script can be newer than the copy Steam actually runs.
    # A saved GPU fallback is not effective until that registered copy is synced.
    launcher_state = bridge_launcher_sync()
    if launcher_state != "UP TO DATE":
        raise ValueError(
            "Installed Steam Bridge launcher is outdated or unverified: "
            + launcher_state
            + ". Update only the registered Bridge launcher before Play; "
              "Steam settings and the game's Proton prefix do not need changing."
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


def primary_ui_state(appid: str, *, game_dir: Path | None = None) -> tuple[str, str]:
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
    launcher_state = bridge_launcher_sync()
    if launcher_state != "UP TO DATE":
        return "repair", (
            "Installed Steam Bridge launcher is outdated or unverified: "
            + launcher_state
            + ". Update the registered Bridge launcher in Advanced Providers; "
              "the game prefix and Steam settings do not need changing."
        )
    if game_dir is not None and netfx_registered_without_native_clr(appid, game_dir):
        return "runtime", (
            "Windows .NET registration exists, but the selected game prefix lacks "
            "native CLR files. Check WeMod readiness and plan an isolated .NET test; "
            "no game prefix or Steam setting was changed."
        )
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


def dotnet_prefix_status(appid: str, game_dir: Path) -> str:
    """Read-only Windows runtime evidence from this game's Steam Proton prefix.

    Registry evidence alone cannot identify the exact runtime WeMod requires.
    Never run Wine, Proton, protontricks, installers or modify the prefix.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid Steam AppID for .NET inspection")
    game = game_dir.expanduser().resolve(strict=True)
    steamapps = game.parent.parent
    manifest = steamapps / ("appmanifest_" + appid + ".acf")
    if game.parent.name != "common" or steamapps.name != "steamapps" or not manifest.is_file():
        raise ValueError("Select an installed Steam game with matching manifest")
    prefix = steamapps / "compatdata" / appid / "pfx"
    lines = [f"GameWeld read-only WeMod .NET check for AppID {appid}",
             "Scope: selected Steam game only; no prefix or game files changed.",
             f"Candidate Proton prefix: {prefix}"]
    if prefix.is_symlink() or not prefix.is_dir():
        lines += ["Prefix evidence: unavailable at this library path (not proof of missing .NET).",
                  "Check the game's actual STEAM_COMPAT_DATA_PATH before modifying anything."]
        return "\n".join(lines)
    registry = prefix / "system.reg"
    evidence = []
    if registry.is_file() and not registry.is_symlink() and registry.stat().st_size <= 32*1024*1024:
        inside = False
        for line in registry.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("["):
                # Wine encodes registry path separators as escaped backslashes.
                normal = line.casefold().replace("\\\\", "\\")
                inside = "microsoft\\net framework setup\\ndp\\" in normal
                if inside and any(tag in normal for tag in ("\\v4\\full", "\\v4\\client", "\\v3.5")):
                    evidence.append(line[:160])
            elif inside and line.startswith(('\"Release\"=', '\"Install\"=', '\"Version\"=')):
                evidence.append(line[:160])
    lines.append("Windows .NET Framework registry evidence: " +
                 ("; ".join(evidence[:12]) if evidence else "NOT FOUND / INCONCLUSIVE"))
    lines.extend(netfx_clr_evidence(prefix))
    for name, dirname in (("Windows Desktop .NET runtime","Microsoft.WindowsDesktop.App"),
                          (".NET shared runtime","Microsoft.NETCore.App")):
        roots = [prefix / "drive_c/Program Files/dotnet/shared" / dirname,
                 prefix / "drive_c/Program Files (x86)/dotnet/shared" / dirname]
        found = sorted({d.name for root in roots if root.is_dir() and not root.is_symlink()
                        for d in root.iterdir() if d.is_dir() and not d.is_symlink()})
        lines.append(name + ": " + (", ".join(found[:8]) if found else "not detected (inconclusive)"))
    state = xdg_dir("XDG_STATE_HOME", ".local/state") / "gameweld"
    if state.is_dir():
        logs = sorted((p for p in state.glob(f"steam-bridge-{appid}-*.log")
                       if p.is_file() and not p.is_symlink() and p.stat().st_size < 8*1024*1024),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            lines.append("Recent Bridge log: " + str(logs[0]))
            tail = logs[0].read_text(encoding="utf-8",errors="replace").splitlines()[-250:]
            snippets = [row.strip()[:250] for row in tail
                        if any(word in row.casefold() for word in
                               ("framework", ".net", "coreclr", "mscoree", "0x800", "err:", "failed"))]
            lines.append("Relevant log lines: " +
                         (" | ".join(snippets[-5:]) if snippets else "none detected"))
        else:
            lines.append("Recent Bridge log: none found for this AppID")
    lines += ["Diagnosis: a WeMod .NET error may indicate a missing/incompatible Windows runtime "
              "or problematic prefix; this inspection cannot prove which.",
              "Do NOT install host Linux .NET or delete the game's compatdata as a first step."]
    return "\n".join(lines)


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


def netfx_clr_evidence(prefix: Path) -> list[str]:
    """Check Windows .NET Framework v4 files without executing any runtime.

    A Steam title may be assigned a different compatdata path. Treat missing
    or symlinked candidate directories as inconclusive, not as proof of a
    broken installation. Never guess or copy files from another game.
    """
    if prefix.is_symlink() or not prefix.is_dir():
        return [".NET CLR files: INCONCLUSIVE (candidate prefix missing or symlinked)"]
    windows = prefix / "drive_c/windows/Microsoft.NET"
    if windows.is_symlink() or not windows.is_dir():
        return [".NET CLR files: INCONCLUSIVE (Microsoft.NET directory unavailable)"]
    report = []
    missing = []
    uncertain = False
    for arch in ("Framework", "Framework64"):
        folder = windows / arch / "v4.0.30319"
        if folder.is_symlink() or not folder.is_dir():
            report.append(f".NET CLR {arch}: INCONCLUSIVE (runtime folder unavailable)")
            uncertain = True
            continue
        for dll in ("clr.dll", "mscorlib.dll"):
            path = folder / dll
            if path.is_symlink():
                report.append(f".NET CLR {arch}/{dll}: INCONCLUSIVE (symlinked)")
                uncertain = True
            elif path.is_file():
                try:
                    report.append(f".NET CLR {arch}/{dll}: present ({path.stat().st_size} bytes)")
                except OSError:
                    report.append(f".NET CLR {arch}/{dll}: INCONCLUSIVE (unreadable)")
                    uncertain = True
            else:
                report.append(f".NET CLR {arch}/{dll}: MISSING from candidate prefix")
                missing.append((arch, dll))
    missing_clr = sum(dll == "clr.dll" for _, dll in missing)
    if missing_clr == 2 and not uncertain:
        report.append("WARNING: both Windows .NET Framework v4 clr.dll files are missing; "
                      "registration alone cannot establish a working CLR for WeMod.")
    elif missing_clr:
        report.append("WARNING: one or more Windows .NET Framework v4 CLR components "
                      "are absent; this is not a successful runtime check.")
    else:
        report.append(".NET CLR assessment: file presence only; loading and WeMod "
                      "compatibility NOT verified.")
    return report


def netfx_registered_without_native_clr(appid: str, game_dir: Path) -> bool:
    """Advisory blocker only when a matching candidate prefix explicitly
    claims .NET registration while *both* native Framework CLR DLLs are absent.

    A directory scan does not establish actual runtime loading. Inconclusive
    or unmatched game locations must not be mislabeled a broken native CLR.
    """
    try:
        game = game_dir.expanduser().resolve(strict=True)
        steamapps = game.parent.parent
        manifest = steamapps / f"appmanifest_{appid}.acf"
        if (not game.is_dir() or game.parent.name != "common" or
                steamapps.name != "steamapps" or not manifest.is_file() or
                manifest.is_symlink()):
            return False
        prefix = steamapps / "compatdata" / appid / "pfx"
        registry = prefix / "system.reg"
        if (registry.is_symlink() or not registry.is_file() or
                registry.stat().st_size > 32 * 1024 * 1024):
            return False
        registry_text = registry.read_text(encoding="utf-8", errors="replace")
        if "NET Framework Setup" not in registry_text:
            return False
        report = netfx_clr_evidence(prefix)
        return any(
            text.startswith("WARNING: both Windows .NET Framework v4 clr.dll files are missing")
            for text in report
        )
    except (OSError, ValueError):
        return False


def discover_ge_proton10_candidates(steamapps: Path) -> list[Path]:
    """Bounded read-only discovery; folder names are NOT engine proof.

    The selected Steam library and conventional Steam user locations are
    inspected, but no tools are installed, executed or selected for a game.
    Results are potential disposable-test runners, never a recommendation to
    replace the game's working Compatibility selection.
    """
    home = Path.home()
    steam_root = steamapps.parent
    data_home = xdg_dir("XDG_DATA_HOME", ".local/share")
    roots = (
        # Steam-discoverable tools and GE installations in the game library.
        steamapps / "common",
        steam_root / "compatibilitytools.d",
        home / ".steam" / "root" / "compatibilitytools.d",
        home / ".steam" / "steam" / "compatibilitytools.d",
        data_home / "Steam" / "compatibilitytools.d",
        home / ".local" / "share" / "Steam" / "compatibilitytools.d",
        # Reuse the existing read-only runner locations understood by
        # GameWeld's Heroic repair tooling. Never trigger that repair flow.
        data_home / "gameweld" / "repair-runtimes",
        home / ".config" / "heroic" / "tools" / "proton",
        home / ".local" / "share" / "heroic" / "tools" / "proton",
        # Distro-packaged compatibility tools, if any.
        Path("/usr/share/steam/compatibilitytools.d"),
    )
    # GE-Proton10-34 is a *label*, not a guarantee of a particular Wine
    # version, patch level, installer behavior or binary provenance.
    label = re.compile(r"(?:GE[-_ ]?Proton|Proton[-_ ]?GE)[-_ ]?10(?:[-_.]\d+)*", re.I)
    discovered: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for index, candidate in enumerate(root.iterdir()):
                if index >= 256:  # hard bound for unusual/malicious folders
                    break
                if not label.fullmatch(candidate.name):
                    continue
                if candidate.is_symlink() or not candidate.is_dir():
                    continue
                script = candidate / "proton"
                if script.is_symlink() or not script.is_file():
                    continue
                try:
                    verified = validate_proton(script)
                except (OSError, ValueError):
                    continue
                if verified not in seen:
                    seen.add(verified)
                    discovered.append(verified)
                if len(discovered) >= 12:
                    return discovered
        except (OSError, PermissionError):
            continue
    return discovered


def netfx_isolation_plan(
    appid: str,
    game_dir: Path,
    *,
    installer_path: Path | None = None,
    expected_sha256: str | None = None,
) -> str:
    """Read-only isolated .NET experiment preflight; no Wine or writes.

    A digest comparison requires a checksum independently obtained from a
    trusted publisher. A matching user-supplied digest alone is not proof of
    authenticity or compatibility, and never authorizes installation.
    """
    if not valid_appid(appid):
        raise ValueError("Invalid Steam AppID for isolated .NET test plan")
    game = game_dir.expanduser().resolve(strict=True)
    steamapps = game.parent.parent
    manifest = steamapps / f"appmanifest_{appid}.acf"
    if (not game.is_dir() or game.parent.name != "common" or
            steamapps.name != "steamapps" or not manifest.is_file() or
            manifest.is_symlink()):
        raise ValueError("Select an installed Steam game with the matching AppID manifest")

    entry = load_config().get(appid)
    if not isinstance(entry, dict):
        raise ValueError("Configure this game's Steam Bridge before planning an isolated test")
    proton = validate_proton(Path(entry["proton"]))
    client = validate_client(Path(entry["client"]))
    current = steamapps / "compatdata" / appid
    cache = xdg_dir("XDG_CACHE_HOME", ".cache")
    root = cache / "gameweld" / "netfx-isolation"
    proposed = root / f"appid-{appid}"
    disallowed = (steamapps, game, current, proton.parent, client)
    # Consider the complete proposed ancestry. A symlink outside the four
    # previously checked final components could alias a Steam/library root.
    unsafe_links = any(part.is_symlink() for part in (proposed, *proposed.parents))
    overlaps_protected = any(
        proposed == protected or proposed in protected.parents or
        protected in proposed.parents
        for protected in disallowed
    )
    occupied = proposed.exists() or proposed.is_symlink()

    nearest = next((part for part in (proposed, *proposed.parents) if part.exists()), None)
    disk_status = "INCONCLUSIVE (no readable parent filesystem)"
    enough_space = False
    if nearest is not None and not unsafe_links:
        try:
            free = shutil.disk_usage(nearest).free
            free_gib = free / (1024 ** 3)
            enough_space = free >= 8 * 1024 ** 3
            disk_status = (
                f"{free_gib:.1f} GiB available; conservative planning target: 8 GiB "
                + ("(PASS)" if enough_space else "(LOW SPACE)")
            )
        except OSError:
            pass
    ready = not (unsafe_links or overlaps_protected or occupied) and enough_space

    try:
        selection = steam_compat_selection(appid, configured_proton=proton)
    except (OSError, ValueError) as exc:
        selection = "UNVERIFIED (read-only Steam compatibility lookup failed)"
    # This is the saved Steam selection, not proof of a running process.
    lines = [
        f"GAMEWELD — ISOLATED .NET TEST PLAN • AppID {appid}",
        "Mode: PLAN ONLY (READ-ONLY; no sandbox or installer created)",
        "Selected Steam game: matching local AppID manifest filename (contents not verified)",
        f"Saved Proton executable: {proton}",
        f"Steam saved compatibility selection: {selection}",
        "Actual live Proton executable/version: NOT VERIFIED (no process executed)",
        "Candidate comparison: preserve the saved game Proton; explore GE-Proton10 "
        "ONLY in a separate disposable test after approval.",
        f"Existing game compatdata: {current} (DO NOT TOUCH)",
        f"Proposed separate workspace: {proposed}",
        "Workspace check: " +
        ("AVAILABLE FOR A FUTURE APPROVED TEST" if ready else
         "BLOCKED (occupied, symlink/overlap risk, or insufficient/unverified free space)"),
        "Scratch filesystem free space: " + disk_status,
    ]
    candidates = discover_ge_proton10_candidates(steamapps)
    if candidates:
        lines.append(f"GE-Proton10 possible runners found: {len(candidates)} "
                     "(read-only filename and toolmanifest checks)")
        for candidate in candidates:
            lines.append(f"  Candidate Proton launcher: {candidate}")
        lines.append("Wine engine version and .NET installation compatibility: "
                     "UNVERIFIED (never executed)")
    else:
        lines.append("GE-Proton10 possible runners: NOT DETECTED in scanned Steam roots "
                     "(could be installed elsewhere)")
        lines.append("No Proton version was downloaded, installed or selected.")

    if installer_path is None:
        if expected_sha256 is not None:
            raise ValueError("An expected checksum requires --installer-path")
        lines.append("Install source: NOT SELECTED OR VERIFIED")
    else:
        if (installer_path.is_symlink() or not installer_path.is_file() or
                installer_path.stat().st_size == 0 or
                installer_path.stat().st_size > 512 * 1024 ** 2):
            raise ValueError("Installer candidate must be a nonempty regular non-symlinked file no larger than 512 MiB")
        file_size = installer_path.stat().st_size
        digest = hashlib.sha256()
        with installer_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        lines.append(f"Installer candidate: {installer_path} ({file_size} bytes)")
        lines.append(f"Installer computed SHA-256: {actual}")
        if expected_sha256 is None:
            lines.append("Installer checksum: NOT VERIFIED against a trusted publisher")
        else:
            if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
                raise ValueError("Expected installer SHA-256 must be 64 hexadecimal characters")
            if actual.lower() != expected_sha256.lower():
                lines.append("Installer checksum: MISMATCH — DO NOT EXECUTE")
            else:
                lines.append("Installer checksum: MATCHES supplied digest; "
                             "publisher provenance must still be independently verified")

    lines += [
        "Compatibility of .NET installer with this Proton build: NOT VERIFIED",
        "Proton run, downloads, prefix creation, registry changes and DLL copies: NOT PERFORMED",
        "Do not run the previous dotnet48/MSI installer on the live game prefix.",
        "Before any future sandbox test: independently verify installer origin "
        "and checksum, and explicitly approve the disposable-only test.",
        "After a future sandbox test: require actual CLR loading evidence; "
        "a registry Release key or mere DLL presence is not a pass.",
        "No automatic promotion/copying from sandbox into a Steam game prefix.",
    ]
    return "\n".join(lines)

def preflight_report(appid: str, *, game_dir: Path | None = None) -> str:
    """Bounded, read-only, game-scoped readiness summary for the GUI.

    File/registry presence and historical logs never count as a successful
    runtime launch. No Wine, Proton, MSI or Steam processes are started.
    """
    if not valid_appid(appid):
        raise ValueError("Select an installed Steam Windows game")
    state, reason = primary_ui_state(appid, game_dir=game_dir)
    entry = load_config().get(appid)
    next_action = "INVESTIGATE WINDOWS .NET RUNTIME" if state == "runtime" else state.upper()
    lines = [
        f"GAMEWELD — WEMOD READINESS • Steam AppID {appid}",
        f"Next action: {next_action} — {reason}",
    ]
    if not isinstance(entry, dict):
        lines += [
            "WeMod auto-start: not configured",
            "WeMod GPU fallback: not configured",
        ]
    else:
        lines.append("WeMod auto-start: " +
                     ("ENABLED" if entry.get("trainer_enabled") else "DISABLED"))
        lines.append("WeMod GPU fallback: " +
                     ("ENABLED (--disable-gpu on WeMod only)"
                      if entry.get("wemod_disable_gpu") is True else "DISABLED"))
        lines.append("Installed Steam Bridge: " + bridge_launcher_sync())

    if game_dir is not None:
        try:
            game = game_dir.expanduser().resolve(strict=True)
            steamapps = game.parent.parent
            if (game.parent.name != "common" or steamapps.name != "steamapps" or
                    not (steamapps / ("appmanifest_" + appid + ".acf")).is_file()):
                lines.append(".NET registry: INCONCLUSIVE (selected game manifest mismatch)")
            else:
                registry = steamapps / "compatdata" / appid / "pfx/system.reg"
                if (registry.is_file() and not registry.is_symlink() and
                        registry.stat().st_size <= 32 * 1024 * 1024):
                    content = registry.read_text(encoding="utf-8", errors="replace")
                    if "NET Framework Setup" in content:
                        lines.append(".NET registry: registration entries found; "
                                     "runtime functionality NOT verified")
                    else:
                        lines.append(".NET registry: setup entries not found; "
                                     "do not install .NET based on this check alone")
                else:
                    lines.append(".NET registry: INCONCLUSIVE (prefix or registry unavailable)")
                clr_lines = netfx_clr_evidence(steamapps / "compatdata" / appid / "pfx")
                lines.extend(clr_lines)
                if state == "play" and any(line.startswith("WARNING:") for line in clr_lines):
                    lines[1] = (
                        "Next action: INVESTIGATE WINDOWS .NET RUNTIME — "
                        "Steam Bridge is configured, but the selected prefix "
                        "is missing native CLR components needed by some .NET apps. "
                        "No installation or prefix repair was attempted."
                    )
        except (OSError, ValueError):
            lines.append(".NET registry: INCONCLUSIVE (cannot inspect selected game)")

    state_dir = xdg_dir("XDG_STATE_HOME", ".local/state") / "gameweld"
    try:
        logs = sorted(
            (p for p in state_dir.glob(f"steam-bridge-{appid}-*.log")
             if p.is_file() and not p.is_symlink() and p.stat().st_size < 2 * 1024 * 1024),
            key=lambda p: p.stat().st_mtime, reverse=True,
        ) if state_dir.is_dir() else []
        if logs:
            history = logs[0].read_text(encoding="utf-8", errors="replace")
            fallback = next(
                (line.split(":", 1)[1].strip().upper()
                 for line in history.splitlines()
                 if line.startswith("WeMod GPU fallback:")),
                "NOT RECORDED",
            )
            lines.append(f"Previous Bridge handoff log: found; GPU fallback: {fallback} "
                         "(historical, not the next launch)")
        else:
            lines.append("Previous Bridge handoff log: none found for this game")
    except OSError:
        lines.append("Previous Bridge handoff log: unavailable")

    lines += [
        "Live game/WeMod connection: NOT VERIFIED (no game was launched)",
        "Safety: READ-ONLY; no .NET installer, prefix modification, or Steam setting change.",
    ]
    return "\n".join(lines)


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
    if len(sys.argv) > 1 and sys.argv[1] in {"status", "preflight", "netfx-status", "netfx-plan", "ui-state", "register", "configure", "setup", "trainer-on", "trainer-off", "trainer-gpu-off", "trainer-gpu-on", "play", "upgrade"}:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("action", choices=("status", "preflight", "netfx-status", "netfx-plan", "ui-state", "register", "configure", "setup", "trainer-on", "trainer-off", "trainer-gpu-off", "trainer-gpu-on", "play", "upgrade"))
        parser.add_argument("--steam-root", type=Path)
        parser.add_argument("--game-dir", type=Path)
        parser.add_argument("--appid")
        parser.add_argument("--proton", type=Path)
        parser.add_argument("--client", type=Path)
        parser.add_argument("--enable-trainer", action="store_true")
        parser.add_argument("--delay-seconds", type=int, default=12)
        parser.add_argument("--installer-path", type=Path)
        parser.add_argument("--expected-sha256")
        parser.add_argument("--confirm", action="store_true")
        args = parser.parse_args()
        if args.action == "ui-state":
            if not args.appid:
                raise ValueError("UI state requires --appid")
            action, reason = primary_ui_state(args.appid, game_dir=args.game_dir)
            print(action + "\t" + reason.replace("\t", " ").replace("\n", " "))
            return 0
        if args.action == "preflight":
            if not args.appid:
                raise ValueError("Preflight requires --appid")
            print(preflight_report(args.appid, game_dir=args.game_dir))
            return 0
        if args.action == "netfx-plan":
            if not args.appid or not args.game_dir:
                raise ValueError("Isolated .NET plan requires --appid and --game-dir")
            print(netfx_isolation_plan(
                args.appid, args.game_dir,
                installer_path=args.installer_path,
                expected_sha256=args.expected_sha256
            ))
            return 0
        if args.action == "netfx-status":
            if not args.appid or not args.game_dir:
                raise ValueError("Windows .NET diagnosis requires --appid and --game-dir")
            print(dotnet_prefix_status(args.appid, args.game_dir))
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
