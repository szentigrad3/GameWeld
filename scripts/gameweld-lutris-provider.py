#!/usr/bin/env python3
"""Lutris discovery and live-session readiness for GameWeld 0.6.0 Test 4.

This provider remains read-only.  It resolves installed Lutris Windows games, their
configured Wine prefix, and the concrete launcher runtime used by current Lutris builds.  GE-Proton (Latest) is UMU-managed in modern Lutris, so
GameWeld resolves the real umu-run entry point instead of incorrectly requiring a
legacy runners/wine/<name>/bin/wine tree.  No Lutris configuration is modified and no game is launched by this provider; resolved
entries are handed to the separate Test 4 live-session helper, which validates ownership
before any trainer is started.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import sys
from typing import Any

HOME = Path(os.environ.get("HOME", "~")).expanduser()


def _real(p: Path) -> Path:
    try:
        return p.expanduser().resolve()
    except Exception:
        return p.expanduser()


def lutris_roots() -> list[tuple[Path, Path, str]]:
    """Return (config_root, data_root, source_kind) candidates."""
    out: list[tuple[Path, Path, str]] = []
    cfg_override = os.environ.get("GAMEWELD_LUTRIS_CONFIG_ROOT", "").strip()
    data_override = os.environ.get("GAMEWELD_LUTRIS_DATA_ROOT", "").strip()
    root_override = os.environ.get("GAMEWELD_LUTRIS_ROOT", "").strip()
    if cfg_override or data_override:
        cfg = Path(cfg_override or root_override or data_override).expanduser()
        data = Path(data_override or root_override or cfg_override).expanduser()
        out.append((cfg, data, "override"))
    elif root_override:
        r = Path(root_override).expanduser()
        out.append((r, r, "override"))

    xcfg = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
    xdata = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    out.extend(
        [
            (xcfg / "lutris", xdata / "lutris", "native"),
            (HOME / ".config/lutris", HOME / ".local/share/lutris", "native"),
            (
                HOME / ".var/app/net.lutris.Lutris/config/lutris",
                HOME / ".var/app/net.lutris.Lutris/data/lutris",
                "flatpak",
            ),
        ]
    )
    seen: set[tuple[str, str]] = set()
    result: list[tuple[Path, Path, str]] = []
    for cfg, data, kind in out:
        cfg, data = _real(cfg), _real(data)
        key = (str(cfg), str(data))
        if key in seen:
            continue
        if cfg.exists() or data.exists():
            seen.add(key)
            result.append((cfg, data, kind))
    return result


def _scalar(text: str) -> str:
    value = text.strip()
    if not value:
        return ""
    # Drop comments only when they are outside quotes.
    quote = None
    escaped = False
    chars: list[str] = []
    for c in value:
        if escaped:
            chars.append(c)
            escaped = False
            continue
        if c == "\\":
            chars.append(c)
            escaped = True
            continue
        if c in ("'", '"'):
            if quote == c:
                quote = None
            elif quote is None:
                quote = c
            chars.append(c)
            continue
        if c == "#" and quote is None:
            break
        chars.append(c)
    value = "".join(chars).strip()
    if not value:
        return ""
    try:
        parts = shlex.split(value, posix=True)
        if len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return value.strip('"\'')


def _set_nested(root: dict[str, Any], path: list[str], value: Any) -> None:
    cur = root
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    if path:
        cur[path[-1]] = value


def parse_lutris_yaml(path: Path) -> dict[str, Any]:
    """Parse the scalar mapping subset of Lutris YAML without requiring PyYAML.

    Test 2 preserves nested mappings such as system.env.WINEPREFIX instead of
    flattening them away.  Lists are ignored because prefix/runtime discovery
    only needs scalar configuration values.
    """
    result: dict[str, Any] = {"game": {}, "wine": {}, "system": {}}
    stack: list[tuple[int, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("-") or ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        path_keys = [k for _, k in stack] + [key]
        if not rest.strip():
            _set_nested(result, path_keys, {})
            stack.append((indent, key))
            continue
        _set_nested(result, path_keys, _scalar(rest))
    return result

def _db_rows(data_root: Path) -> list[dict[str, Any]]:
    db = data_root / "pga.db"
    if not db.is_file():
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cols = {str(r[1]) for r in con.execute("PRAGMA table_info(games)")}
        if not cols:
            con.close()
            return []
        wanted = [
            c
            for c in (
                "id",
                "name",
                "slug",
                "game_slug",
                "runner",
                "configpath",
                "directory",
                "installed",
                "platform",
            )
            if c in cols
        ]
        rows = [dict(r) for r in con.execute(f"SELECT {','.join(wanted)} FROM games")]
        con.close()
        return rows
    except Exception:
        return []


def _config_paths(config_root: Path, data_root: Path) -> list[Path]:
    candidates = [config_root / "games", data_root / "games"]
    out: list[Path] = []
    seen: set[str] = set()
    for folder in candidates:
        if not folder.is_dir():
            continue
        for pat in ("*.yml", "*.yaml"):
            for p in sorted(folder.glob(pat)):
                key = str(_real(p))
                if key not in seen:
                    seen.add(key)
                    out.append(p)
    return out


def _expand_lutris_value(value: str, *, game_dir: str = "", config_dir: str = "", data_dir: str = "") -> str:
    if not value:
        return ""
    text = value.strip()
    replacements = {
        "$GAMEDIR": game_dir,
        "${GAMEDIR}": game_dir,
        "$SCRIPTDIR": config_dir,
        "${SCRIPTDIR}": config_dir,
        "$LUTRIS_GAME_DIR": game_dir,
        "${LUTRIS_GAME_DIR}": game_dir,
        "$LUTRIS_CONFIG_DIR": config_dir,
        "${LUTRIS_CONFIG_DIR}": config_dir,
        "$LUTRIS_DATA_DIR": data_dir,
        "${LUTRIS_DATA_DIR}": data_dir,
    }
    for token, replacement in replacements.items():
        if replacement:
            text = text.replace(token, replacement)
    return os.path.expandvars(os.path.expanduser(text))


def _looks_like_wine_prefix(path: Path) -> bool:
    try:
        if not path.is_dir():
            return False
        drive_c = path / "drive_c"
        if not drive_c.is_dir():
            return False
        # Lutris prefixes normally have at least one of these.  Requiring
        # drive_c plus one marker avoids treating arbitrary game folders as a
        # prefix while still accepting freshly-created prefixes.
        markers = (path / "dosdevices", path / "system.reg", path / "user.reg", path / "userdef.reg")
        return any(m.exists() for m in markers) or (drive_c / "windows").exists()
    except OSError:
        return False


def _prefix_from_path(value: str) -> str:
    if not value:
        return ""
    norm = value.replace("\\", "/")
    low = norm.lower()
    for marker in ("/drive_c/", "/dosdevices/"):
        i = low.find(marker)
        if i > 0:
            return norm[:i]
    return ""


def _find_prefix_near(directory: str) -> str:
    """Conservatively identify a Wine prefix around Lutris' game directory."""
    if not directory:
        return ""
    base = Path(directory).expanduser()
    candidates: list[Path] = []
    # The DB directory is commonly the prefix itself.  It can also point at a
    # directory inside drive_c, so walk a few parents before checking one-level
    # child prefixes.
    cur = base
    for _ in range(5):
        candidates.append(cur)
        if cur.parent == cur:
            break
        cur = cur.parent
    try:
        if base.is_dir():
            children = [p for p in base.iterdir() if p.is_dir()]
            prefix_children = [p for p in children if _looks_like_wine_prefix(p)]
            if len(prefix_children) == 1:
                candidates.append(prefix_children[0])
    except OSError:
        pass
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_wine_prefix(cand):
            return str(cand)
    return ""


def _windows_path_to_prefix(raw: str, prefix: str) -> str:
    if not raw or not prefix:
        return ""
    norm = raw.replace("\\", "/").strip()
    if len(norm) >= 3 and norm[1] == ":" and norm[2] == "/":
        drive = norm[0].lower()
        tail = norm[3:].lstrip("/")
        if drive == "c":
            return str(Path(prefix) / "drive_c" / tail)
        return str(Path(prefix) / "dosdevices" / f"{drive}:" / tail)
    return ""


def _resolve_exe(raw: str, prefix: str, install: str, *, config_dir: str = "", data_dir: str = "") -> str:
    raw = _expand_lutris_value(raw, game_dir=install, config_dir=config_dir, data_dir=data_dir)
    if not raw:
        return ""
    mapped = _windows_path_to_prefix(raw, prefix)
    if mapped:
        return mapped
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    norm = raw.replace("\\", "/").lstrip("./")
    if prefix and (norm.lower().startswith("drive_c/") or norm.lower().startswith("dosdevices/")):
        return str(Path(prefix) / norm)
    if install:
        cand = Path(install) / raw
        if cand.exists():
            return str(cand)
    if prefix:
        cand = Path(prefix) / raw
        if cand.exists():
            return str(cand)
    return str((Path(install) / raw) if install else p)


def _infer_prefix(exe: str) -> str:
    return _prefix_from_path(exe)

def _norm_runtime_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _is_ge_proton_latest(version: str) -> bool:
    # Keep legacy folder names such as ``Proton-GE-Latest`` eligible for the
    # classic runners/wine lookup; modern Lutris uses the ``ge-proton``
    # sentinel while UIs may display it as GE-Proton (Latest) / Proton-GE Latest.
    raw = " ".join((version or "").strip().casefold().split())
    return raw in {
        "ge-proton",
        "ge proton",
        "ge-proton latest",
        "ge-proton (latest)",
        "proton-ge latest",
        "proton ge latest",
    }


def _find_umu(data_roots: list[Path]) -> str:
    """Find the same UMU-style entry point modern Lutris uses for Proton.

    Lutris 0.5.22+ treats GE-Proton (Latest) as an UMU-managed sentinel rather
    than a downloadable Wine runner.  Search the user's configured override,
    PATH, Lutris' bundled runtime, and standard system share locations without
    mutating or downloading anything.
    """
    override = os.environ.get("GAMEWELD_UMU_PATH", "").strip()
    candidates: list[Path] = []
    if override:
        op = Path(os.path.expanduser(os.path.expandvars(override)))
        candidates.extend([op, op / "umu-run", op / "umu_run.py"] if op.is_dir() else [op])

    which = shutil.which("umu-run")
    if which:
        candidates.append(Path(which))

    for data in data_roots:
        candidates.extend(
            [
                data / "runtime/umu/umu-run",
                data / "runtime/umu/umu_run.py",
            ]
        )

    candidates.extend(
        [
            HOME / ".local/bin/umu-run",
            Path("/usr/local/bin/umu-run"),
            Path("/usr/bin/umu-run"),
            Path("/app/share/umu/umu-run"),
            Path("/app/share/umu/umu_run.py"),
            Path("/usr/local/share/umu/umu-run"),
            Path("/usr/local/share/umu/umu_run.py"),
            Path("/usr/share/umu/umu-run"),
            Path("/usr/share/umu/umu_run.py"),
            Path("/opt/umu/umu-run"),
            Path("/opt/umu/umu_run.py"),
        ]
    )

    seen: set[str] = set()
    for cand in candidates:
        try:
            key = str(cand.expanduser())
            if key in seen:
                continue
            seen.add(key)
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(_real(cand))
        except OSError:
            continue
    return ""


def _proton_roots(data_roots: list[Path]) -> list[Path]:
    roots: list[Path] = []
    override = os.environ.get("GAMEWELD_PROTON_ROOTS", "").strip()
    if override:
        roots.extend(Path(x).expanduser() for x in override.split(os.pathsep) if x.strip())

    xdata = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    roots.extend(
        [
            xdata / "Steam/compatibilitytools.d",
            HOME / ".local/share/Steam/compatibilitytools.d",
            HOME / ".steam/root/compatibilitytools.d",
            HOME / ".steam/steam/compatibilitytools.d",
            HOME / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
        ]
    )
    for data in data_roots:
        roots.extend([data / "runners/proton", data / "runners/wine"])

    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.expanduser())
        if key in seen:
            continue
        seen.add(key)
        if root.is_dir():
            out.append(_real(root))
    return out


def _find_named_proton(version: str, data_roots: list[Path]) -> str:
    """Return a Proton tool root containing a `proton` entry point."""
    if not version:
        return ""
    want = _norm_runtime_name(version)
    for root in _proton_roots(data_roots):
        direct = root / version
        if (direct / "proton").is_file():
            return str(_real(direct))
        try:
            children = [p for p in root.iterdir() if p.is_dir()]
        except OSError:
            continue
        for child in children:
            if _norm_runtime_name(child.name) == want and (child / "proton").is_file():
                return str(_real(child))
    return ""


def _runner_wine(version: str, explicit: str, data_roots: list[Path]) -> tuple[str, str, str, str]:
    """Resolve Lutris' concrete runtime entry point.

    Returns (entry_point, source, runtime_type, compatibility_tool_root).
    For current Proton/GE-Proton configurations, entry_point is UMU because that
    is what Lutris itself executes.  For classic Wine builds it remains bin/wine.
    """
    explicit = _expand_lutris_value(explicit)
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            # Custom runner directories can contain either bin/wine or proton.
            wine = p / "bin/wine"
            proton = p / "proton"
            if wine.is_file() and os.access(wine, os.X_OK):
                return str(_real(wine)), "lutris-config", "lutris-wine", str(_real(p))
            if proton.is_file() and os.access(proton, os.X_OK):
                umu = _find_umu(data_roots)
                if umu:
                    return umu, "lutris-umu-explicit-proton", "lutris-umu-proton", str(_real(p))
        elif p.is_file() and os.access(p, os.X_OK):
            if p.name == "proton":
                umu = _find_umu(data_roots)
                if umu:
                    return umu, "lutris-umu-explicit-proton", "lutris-umu-proton", str(_real(p.parent))
            return str(_real(p)), "lutris-config", "lutris-wine", str(_real(p.parent.parent if p.parent.name == "bin" else p.parent))

    v = (version or "").strip()
    if v and _is_ge_proton_latest(v):
        umu = _find_umu(data_roots)
        if umu:
            # Modern Lutris intentionally has no fixed GE-Proton folder for the
            # Latest sentinel. UMU selects/downloads GE-Proton at launch.
            return umu, "lutris-umu-ge-proton-latest", "lutris-umu-proton", ""
        return "", "umu-missing", "lutris-umu-proton", ""

    if v:
        # Classic Lutris Wine builds still live under runners/wine/<version>.
        for data in data_roots:
            for name in (v, v.replace("System (", "").rstrip(")")):
                p = data / "runners/wine" / name / "bin/wine"
                if p.is_file() and os.access(p, os.X_OK):
                    return str(_real(p)), "lutris-runner", "lutris-wine", str(_real(p.parent.parent))

        # Installed Proton builds are also launched through UMU by current Lutris.
        proton_root = _find_named_proton(v, data_roots)
        if proton_root:
            umu = _find_umu(data_roots)
            if umu:
                return umu, "lutris-umu-installed-proton", "lutris-umu-proton", proton_root
            return "", "umu-missing", "lutris-umu-proton", proton_root

    system = shutil.which("wine")
    if system and (not v or v.lower().startswith("system")):
        return system, "system", "system-wine", str(_real(Path(system).parent))
    return "", "unresolved", "lutris-wine" if v else "", ""

def _art(config_root: Path, data_root: Path, slug: str, appid: str) -> str:
    cache_candidates = [
        config_root.parent / "cache/lutris",
        HOME / ".cache/lutris",
        HOME / ".var/app/net.lutris.Lutris/cache/lutris",
        data_root,
    ]
    names = [x for x in (slug, appid) if x]
    for base in cache_candidates:
        for folder in ("coverart", "banners", "icons"):
            for n in names:
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    p = base / folder / f"{n}{ext}"
                    if p.is_file():
                        return str(p)
    return ""


def _emit_game(
    cfg: Path,
    parsed: dict[str, Any],
    meta: dict[str, Any],
    config_root: Path,
    data_root: Path,
    kind: str,
    all_data_roots: list[Path],
) -> dict[str, Any] | None:
    game = parsed.get("game") if isinstance(parsed.get("game"), dict) else {}
    wine = parsed.get("wine") if isinstance(parsed.get("wine"), dict) else {}
    runner = str(meta.get("runner") or parsed.get("runner") or "wine").strip()
    # 0.6.0 Test 3 still limits discovery to Windows/Wine entries while concrete runtime resolution is field-validated.
    if runner and runner.lower() not in ("wine", "proton", "umu"):
        return None
    installed = meta.get("installed")
    if installed is not None and str(installed).lower() in ("0", "false", "no"):
        return None
    stem = cfg.stem
    dbid = str(meta.get("id") or "").strip()
    slug = str(meta.get("slug") or meta.get("game_slug") or parsed.get("slug") or parsed.get("game_slug") or stem).strip()
    appid = dbid or stem
    name = str(meta.get("name") or parsed.get("name") or slug.replace("-", " ").strip() or appid).strip()
    db_directory = _expand_lutris_value(str(meta.get("directory") or ""), config_dir=str(cfg.parent), data_dir=str(data_root))
    working_raw = str(game.get("working_dir") or game.get("working-dir") or "")
    install = _expand_lutris_value(working_raw, game_dir=db_directory, config_dir=str(cfg.parent), data_dir=str(data_root)) or db_directory

    system = parsed.get("system") if isinstance(parsed.get("system"), dict) else {}
    env = system.get("env") if isinstance(system.get("env"), dict) else {}
    prefix_raw = str(game.get("prefix") or parsed.get("prefix") or env.get("WINEPREFIX") or env.get("wineprefix") or "")
    prefix = _expand_lutris_value(prefix_raw, game_dir=db_directory or install, config_dir=str(cfg.parent), data_dir=str(data_root))
    prefix_source = "game-prefix" if (game.get("prefix") or parsed.get("prefix")) else ("system-env" if (env.get("WINEPREFIX") or env.get("wineprefix")) else "")

    exe_raw = str(game.get("exe") or parsed.get("exe") or "")
    # If the config omits prefix, recover it conservatively from any Linux path
    # already rooted inside drive_c/dosdevices, then from Lutris' DB directory.
    expanded_exe_for_infer = _expand_lutris_value(exe_raw, game_dir=db_directory or install, config_dir=str(cfg.parent), data_dir=str(data_root))
    if not prefix:
        prefix = _infer_prefix(expanded_exe_for_infer) or _infer_prefix(install) or _find_prefix_near(db_directory or install)
        if prefix:
            prefix_source = "path-inference" if _infer_prefix(expanded_exe_for_infer) or _infer_prefix(install) else "lutris-directory"

    exe = _resolve_exe(exe_raw, prefix, db_directory or install, config_dir=str(cfg.parent), data_dir=str(data_root))
    if not prefix and exe:
        prefix = _infer_prefix(exe)
        if prefix:
            prefix_source = "executable-inference"
    if not install and exe:
        try:
            install = str(Path(exe).parent)
        except Exception:
            install = ""
    version = str(wine.get("version") or parsed.get("wine_version") or "").strip()
    explicit_wine = str(wine.get("wine_path") or wine.get("wine-path") or wine.get("wine") or "").strip()
    wine_bin, wine_source, wine_type, compat_root = _runner_wine(version, explicit_wine, all_data_roots)

    prefix_found = bool(prefix and Path(prefix).is_dir())
    exe_found = bool(exe and Path(exe).is_file())
    runtime_found = bool(wine_bin and Path(wine_bin).is_file() and os.access(wine_bin, os.X_OK))
    if prefix_found and exe_found and runtime_found:
        state = "resolved"
        label = "Lutris game, Wine prefix and configured runtime resolved"
    elif prefix_found and runtime_found:
        state = "partial-executable"
        label = "Lutris prefix/runtime resolved; game executable needs confirmation"
    elif prefix_found:
        state = "partial-runtime"
        label = "Lutris prefix resolved; configured Wine runtime not found yet"
    else:
        state = "partial-prefix"
        label = "Lutris game discovered; Wine prefix not resolved yet"

    launch_uri = f"lutris:rungameid/{dbid}" if dbid else (f"lutris:rungame/{slug}" if slug else "")
    return {
        "appid": appid,
        "key": f"lutris:{appid}",
        "provider": "lutris",
        "runner": runner or "wine",
        "name": name,
        "install_dir": install,
        "executable": exe,
        "prefix": prefix,
        "prefix_source": prefix_source,
        "wine_type": wine_type,
        "wine_bin": wine_bin,
        "wine_name": version or (Path(wine_bin).parent.parent.name if wine_bin else ""),
        "art_path": _art(config_root, data_root, slug, appid),
        "launch_uri": launch_uri,
        "compat_tool": version,
        "compat_tool_path": compat_root or (str(Path(wine_bin).parent.parent) if wine_bin and Path(wine_bin).parent.name == "bin" else (str(Path(wine_bin).parent) if wine_bin else "")),
        "compat_tool_source": wine_source,
        "resolution_state": state,
        "resolution_label": label,
        "target_kind": "windows",
        "prefix_found": prefix_found,
        "runtime_found": runtime_found,
        "executable_found": exe_found,
        "launch_supported": bool(state == "resolved" and launch_uri),
        "session_handoff_supported": bool(state == "resolved" and launch_uri),
        "config_path": str(cfg),
        "lutris_root": str(data_root),
        "lutris_source": kind,
        "slug": slug,
    }


def discover() -> list[dict[str, Any]]:
    roots = lutris_roots()
    data_roots = [data for _, data, _ in roots]
    games: list[dict[str, Any]] = []
    seen: set[str] = set()
    for config_root, data_root, kind in roots:
        rows = _db_rows(data_root)
        by_config: dict[str, dict[str, Any]] = {}
        by_slug: dict[str, dict[str, Any]] = {}
        for row in rows:
            cp = str(row.get("configpath") or "").strip()
            if cp:
                by_config[Path(cp).stem] = row
            for key in ("slug", "game_slug"):
                v = str(row.get(key) or "").strip()
                if v:
                    by_slug[v] = row
        for cfg in _config_paths(config_root, data_root):
            parsed = parse_lutris_yaml(cfg)
            stem = cfg.stem
            pslug = str(parsed.get("slug") or parsed.get("game_slug") or "")
            meta = by_config.get(stem) or (by_slug.get(pslug) if pslug else None) or {}
            payload = _emit_game(cfg, parsed, meta, config_root, data_root, kind, data_roots)
            if not payload:
                continue
            key = str(payload["key"])
            if key in seen:
                continue
            seen.add(key)
            games.append(payload)
    games.sort(key=lambda g: str(g.get("name", "")).casefold())
    return games


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        for game in discover():
            print(json.dumps(game, ensure_ascii=False, separators=(",", ":")))
        return 0
    if cmd == "roots":
        for cfg, data, kind in lutris_roots():
            print(json.dumps({"config_root": str(cfg), "data_root": str(data), "source": kind}, separators=(",", ":")))
        return 0
    print("usage: gameweld-lutris-provider.py [list|roots]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
