#!/usr/bin/env python3
"""Read and resolve Steam Add-a-Non-Steam-Game shortcuts without modifying Steam state.

GameWeld 0.4.0 Test 14.

Test 11 made Steam shortcuts first-class Library targets. Test 12 added initial
runtime/prefix resolution, Test 13 hardened real Steam Proton lookup, and Test 14
enables trainer handoff only for fully resolved Windows shortcuts. Discovery is
still read-only: the separate launcher validates the actual live Steam rungameid
session and exact compatdata path before using Proton runinprefix.

The resolver exposes:
* the shortcut's 32-bit AppID and 64-bit rungameid identity;
* target/start directory and coarse target kind;
* an existing compatdata directory and pfx, when present;
* the selected Steam Play compatibility-tool mapping, when Steam exposes one;
* the concrete compatibility-tool directory where it can be identified;
* a runtime hint from compatdata/config_info when that is stronger than config.vdf.

Native/script shortcuts without Proton evidence remain ineligible for Windows
trainer handoff.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib

END = 0x08
TYPE_OBJECT = 0x00
TYPE_STRING = 0x01
TYPE_INT32 = 0x02
TYPE_FLOAT32 = 0x03
TYPE_POINTER = 0x04
TYPE_WSTRING = 0x05
TYPE_COLOR = 0x06
TYPE_UINT64 = 0x07
TYPE_INT64 = 0x0A


def _read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError("unterminated binary VDF string")
    raw = data[pos:end]
    return raw.decode("utf-8", "surrogateescape"), end + 1


def _parse_map(data: bytes, pos: int = 0) -> tuple[dict[str, object], int]:
    out: dict[str, object] = {}
    n = len(data)
    while pos < n:
        typ = data[pos]
        pos += 1
        if typ == END:
            return out, pos
        key, pos = _read_cstring(data, pos)
        if typ == TYPE_OBJECT:
            value, pos = _parse_map(data, pos)
        elif typ == TYPE_STRING:
            value, pos = _read_cstring(data, pos)
        elif typ == TYPE_INT32:
            if pos + 4 > n:
                raise ValueError("truncated int32 in binary VDF")
            value = struct.unpack_from("<i", data, pos)[0]
            pos += 4
        elif typ in (TYPE_FLOAT32, TYPE_POINTER, TYPE_COLOR):
            if pos + 4 > n:
                raise ValueError("truncated 32-bit value in binary VDF")
            value = data[pos:pos + 4]
            pos += 4
        elif typ in (TYPE_UINT64, TYPE_INT64):
            if pos + 8 > n:
                raise ValueError("truncated 64-bit value in binary VDF")
            value = struct.unpack_from("<Q" if typ == TYPE_UINT64 else "<q", data, pos)[0]
            pos += 8
        elif typ == TYPE_WSTRING:
            if pos + 2 > n:
                raise ValueError("truncated wstring length in binary VDF")
            count = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            byte_len = count * 2
            if pos + byte_len > n:
                raise ValueError("truncated wstring in binary VDF")
            value = data[pos:pos + byte_len].decode("utf-16le", "replace").rstrip("\0")
            pos += byte_len
        else:
            raise ValueError(f"unsupported binary VDF type 0x{typ:02x} at key {key!r}")
        out.setdefault(key, value)
    return out, pos


def parse_shortcuts(path: Path) -> list[dict[str, object]]:
    data = path.read_bytes()
    root, _ = _parse_map(data, 0)
    shortcuts = root.get("shortcuts")
    if not isinstance(shortcuts, dict):
        shortcuts = next((v for k, v in root.items() if k.lower() == "shortcuts" and isinstance(v, dict)), {})
    rows: list[dict[str, object]] = []
    for index, value in shortcuts.items():
        if not isinstance(value, dict):
            continue
        folded = {str(k).lower(): v for k, v in value.items()}
        name = str(folded.get("appname", "")).strip()
        exe_raw = str(folded.get("exe", "")).strip()
        if not name or not exe_raw:
            continue
        rows.append({
            "index": str(index),
            "raw": value,
            "name": name,
            "exe_raw": exe_raw,
            "startdir_raw": str(folded.get("startdir", "")).strip(),
            "launch_options": str(folded.get("launchoptions", "")).strip(),
            "appid_field": folded.get("appid"),
        })
    return rows


def _vdf_unescape(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def parse_text_vdf(path: Path) -> dict[str, object]:
    """Small read-only parser for the quoted-string/braces form Steam uses."""
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens: list[str] = []
    for m in re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])', text):
        if m.group(2):
            tokens.append(m.group(2))
        else:
            tokens.append(_vdf_unescape(m.group(1) or ""))

    def parse_obj(pos: int, stop_on_brace: bool) -> tuple[dict[str, object], int]:
        out: dict[str, object] = {}
        while pos < len(tokens):
            tok = tokens[pos]
            if tok == "}":
                return out, pos + 1
            if tok == "{":
                pos += 1
                continue
            key = tok
            pos += 1
            if pos >= len(tokens):
                out.setdefault(key, "")
                break
            nxt = tokens[pos]
            if nxt == "{":
                val, pos = parse_obj(pos + 1, True)
            elif nxt == "}":
                out.setdefault(key, "")
                return out, pos + 1
            else:
                val = nxt
                pos += 1
            out.setdefault(key, val)
        return out, pos

    root, _ = parse_obj(0, False)
    return root


def _ci_get(mapping: dict[str, object], key: str) -> object | None:
    wanted = key.casefold()
    for k, v in mapping.items():
        if str(k).casefold() == wanted:
            return v
    return None


def _walk_named(mapping: object, key: str):
    if not isinstance(mapping, dict):
        return
    wanted = key.casefold()
    for k, v in mapping.items():
        if str(k).casefold() == wanted:
            yield v
        if isinstance(v, dict):
            yield from _walk_named(v, key)


def steam_roots() -> list[Path]:
    home = Path(os.environ.get("HOME", "~")).expanduser()
    candidates = [
        home / ".steam/root",
        home / ".steam/steam",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        try:
            real = p.resolve(strict=True)
        except OSError:
            continue
        key = str(real)
        if key not in seen:
            seen.add(key)
            out.append(real)
    return out


def steam_library_roots(root: Path) -> list[Path]:
    out = [root]
    vf = root / "steamapps/libraryfolders.vdf"
    try:
        tree = parse_text_vdf(vf)
    except OSError:
        tree = {}
    except Exception:
        tree = {}
    for node in _walk_named(tree, "path"):
        if not isinstance(node, str):
            continue
        p = Path(node).expanduser()
        try:
            p = p.resolve(strict=True)
        except OSError:
            continue
        if p not in out:
            out.append(p)
    # Fallback for malformed/older libraryfolders.vdf variants.
    if len(out) == 1:
        try:
            text = vf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for m in re.finditer(r'"path"\s+"([^"]+)"', text, flags=re.I):
            p = Path(m.group(1).replace("\\\\", "\\")).expanduser()
            try:
                p = p.resolve(strict=True)
            except OSError:
                continue
            if p not in out:
                out.append(p)
    return out


def _unquote_target(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == '"':
        i = 1
        escaped = False
        chars: list[str] = []
        while i < len(s):
            ch = s[i]
            if ch == '"' and not escaped:
                break
            if ch == "\\" and not escaped:
                escaped = True
                chars.append(ch)
            else:
                escaped = False
                chars.append(ch)
            i += 1
        s = "".join(chars)
    return os.path.expandvars(os.path.expanduser(s.strip('" ')))


def _clean_startdir(raw: str) -> str:
    return os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))


def _shortcut_appid(exe_raw: str, app_name: str, stored: object) -> tuple[int, str]:
    if isinstance(stored, int):
        return stored & 0xFFFFFFFF, "stored"
    if isinstance(stored, str):
        try:
            return int(stored, 0) & 0xFFFFFFFF, "stored"
        except ValueError:
            pass
    value = (zlib.crc32((exe_raw + app_name).encode("utf-8", "surrogateescape")) | 0x80000000) & 0xFFFFFFFF
    return value, "derived"


def _shortcut_gameid(appid: int) -> int:
    return ((appid & 0xFFFFFFFF) << 32) | 0x02000000


def _target_kind(executable: str) -> str:
    low = executable.casefold()
    if low.endswith((".exe", ".msi", ".bat", ".cmd")):
        return "windows"
    if low.endswith(".appimage"):
        return "linux-appimage"
    if low.endswith((".sh", ".py", ".desktop")):
        return "script"
    return "native-or-script"


def _compat_mapping_from_tree(tree: dict[str, object], appid: int) -> tuple[str, str, str, str]:
    exact = str(appid)
    for mapping in _walk_named(tree, "CompatToolMapping"):
        if not isinstance(mapping, dict):
            continue
        for candidate, source in ((exact, "exact"), ("0", "global")):
            entry = _ci_get(mapping, candidate)
            if isinstance(entry, dict):
                name = _ci_get(entry, "name")
                config = _ci_get(entry, "config")
                priority = _ci_get(entry, "priority")
                if isinstance(name, str) and name.strip():
                    return name.strip(), source, str(config or ""), str(priority or "")
    return "", "", "", ""


def _compat_tool_mapping(root: Path, userdir: Path, appid: int) -> tuple[str, str, str, str, str]:
    candidates = [
        root / "config/config.vdf",
        userdir / "config/localconfig.vdf",
    ]
    fallback: tuple[str, str, str, str, str] | None = None
    for path in candidates:
        if not path.is_file():
            continue
        try:
            tree = parse_text_vdf(path)
        except Exception:
            continue
        name, source, config, priority = _compat_mapping_from_tree(tree, appid)
        if not name:
            continue
        result = (name, source, config, priority, str(path))
        if source == "exact":
            return result
        fallback = fallback or result
    return fallback or ("", "", "", "", "")


def _tool_dirs(root: Path, libraries: list[Path]) -> list[Path]:
    home = Path(os.environ.get("HOME", "~")).expanduser()
    dirs = [
        root / "compatibilitytools.d",
        home / ".steam/root/compatibilitytools.d",
        home / ".local/share/Steam/compatibilitytools.d",
        Path("/usr/share/steam/compatibilitytools.d"),
        Path("/usr/local/share/steam/compatibilitytools.d"),
    ]
    for lib in libraries:
        dirs.append(lib / "steamapps/common")
    out: list[Path] = []
    seen: set[str] = set()
    for p in dirs:
        try:
            rp = p.resolve(strict=True)
        except OSError:
            continue
        s = str(rp)
        if s not in seen:
            seen.add(s)
            out.append(rp)
    return out


def _normalized_tool_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _walk_to_proton_root(candidate: Path, max_up: int = 12) -> Path | None:
    """Walk upward from any recorded tool subtree until a Proton root is found.

    Valve Proton config_info commonly records paths under files/, dist/, fonts/,
    or other subdirectories instead of the tool root itself.  The mature
    GameWeld Steam handoff already uses this strategy; shortcut resolution must
    do the same rather than requiring config_info to name the root directly.
    """
    try:
        p = candidate.expanduser()
    except Exception:
        p = candidate
    if p.name == "proton" and p.is_file():
        return p.parent
    if not p.is_dir():
        p = p.parent
    for _ in range(max_up):
        if not str(p) or str(p) in {"/", "."}:
            break
        proton = p / "proton"
        if proton.is_file():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return None


def _tool_manifest_matches(child: Path, tool_name: str) -> bool:
    compat = child / "compatibilitytool.vdf"
    if not compat.is_file():
        return False
    try:
        tree = parse_text_vdf(compat)
    except Exception:
        return False
    wanted = tool_name.casefold()
    wanted_norm = _normalized_tool_token(tool_name)
    for tools in _walk_named(tree, "compat_tools"):
        if not isinstance(tools, dict):
            continue
        for tool_id, meta in tools.items():
            names = [str(tool_id)]
            if isinstance(meta, dict):
                for key in ("display_name", "displayname", "name"):
                    value = _ci_get(meta, key)
                    if isinstance(value, str) and value.strip():
                        names.append(value.strip())
            for name in names:
                if name.casefold() == wanted or _normalized_tool_token(name) == wanted_norm:
                    return True
    return False


def _resolve_tool_path(root: Path, libraries: list[Path], tool_name: str) -> str:
    if not tool_name:
        return ""
    folded = tool_name.casefold()
    normalized = _normalized_tool_token(tool_name)
    fallback: Path | None = None
    for base in _tool_dirs(root, libraries):
        direct = base / tool_name
        if direct.is_dir() and (direct / "proton").is_file():
            return str(direct)
        try:
            children = list(base.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or not (child / "proton").is_file():
                continue
            if child.name.casefold() == folded:
                return str(child)
            # Steam-provided Proton builds are frequently registered out-of-band
            # in appinfo.vdf and therefore ship no local compatibilitytool.vdf.
            # Match stable aliases such as proton_experimental <->
            # "Proton - Experimental" by punctuation-insensitive directory name.
            if _normalized_tool_token(child.name) == normalized:
                return str(child)
            if _tool_manifest_matches(child, tool_name):
                return str(child)
            # Keep a conservative semantic fallback for official Proton aliases
            # without guessing between multiple versioned installations.
            child_norm = _normalized_tool_token(child.name)
            if normalized.startswith("proton") and child_norm.startswith("proton"):
                tail = normalized.removeprefix("proton")
                if tail and tail in child_norm and fallback is None:
                    fallback = child
    return str(fallback) if fallback is not None else ""


def _compatdata_runtime_hint(compatdata: Path) -> tuple[str, str]:
    info = compatdata / "config_info"
    try:
        raw = info.read_bytes()
    except OSError:
        return "", ""
    # config_info is normally text but older/newer Proton layouts can contain
    # NUL separators. Treat both line and NUL boundaries as records.
    text = raw.replace(b"\0", b"\n").decode("utf-8", errors="replace")
    candidates: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        value = line.strip().strip('"')
        if value.startswith("/"):
            candidates.append(value)
        for m in re.finditer(r'(/[A-Za-z0-9_ .+@%/,:=\-]*(?:Proton|proton|compatibilitytools)[A-Za-z0-9_ .+@%/,:=\-]*)', value):
            candidates.append(m.group(1).strip())
    for value in candidates:
        value = value.strip().strip('"').rstrip(",;)")
        if not value or value in seen:
            continue
        seen.add(value)
        root = _walk_to_proton_root(Path(value))
        if root is not None:
            return root.name, str(root)
    # Compatibility fallback mirroring the established Steam helper: when one
    # long record contains a files/ or dist/ subtree, walk from the prefix before
    # that marker even if the remainder contains spaces or metadata.
    for value in text.splitlines():
        for marker in ("/files/", "/dist/"):
            if marker not in value:
                continue
            prefix = value.split(marker, 1)[0].strip().strip('"')
            root = _walk_to_proton_root(Path(prefix))
            if root is not None:
                return root.name, str(root)
    return "", ""


def _find_compatdata(libraries: list[Path], appid: int) -> tuple[str, str, str, str]:
    for lib in libraries:
        c = lib / "steamapps/compatdata" / str(appid)
        if not c.exists():
            continue
        pfx = c / "pfx"
        prefix = pfx if pfx.exists() else c
        runtime_name, runtime_path = _compatdata_runtime_hint(c)
        return str(c), str(prefix), runtime_name, runtime_path
    return "", "", "", ""


def _resolve_shortcut(root: Path, userdir: Path, libraries: list[Path], row: dict[str, object]) -> dict[str, object]:
    appid, appid_source = _shortcut_appid(str(row["exe_raw"]), str(row["name"]), row.get("appid_field"))
    gameid = _shortcut_gameid(appid)
    exe = _unquote_target(str(row["exe_raw"]))
    start = _clean_startdir(str(row.get("startdir_raw", "")))
    executable = Path(exe) if exe else Path()
    install = Path(start) if start else executable.parent
    kind = _target_kind(exe)

    compatdata, prefix, runtime_hint_name, runtime_hint_path = _find_compatdata(libraries, appid)
    mapped_name, mapping_scope, mapping_config, mapping_priority, mapping_file = _compat_tool_mapping(root, userdir, appid)
    mapped_path = _resolve_tool_path(root, libraries, mapped_name)

    # Existing compatdata/config_info reflects the runtime that actually created
    # or last updated the prefix, so prefer its concrete path over a mapping name.
    compat_tool = runtime_hint_name or mapped_name
    compat_tool_path = runtime_hint_path or mapped_path
    if runtime_hint_path:
        compat_source = "compatdata-config-info"
    elif mapped_name:
        compat_source = f"steam-config-{mapping_scope}"
    else:
        compat_source = "unresolved"

    compatdata_found = bool(compatdata)
    prefix_found = bool(prefix)
    runtime_found = bool(compat_tool_path)
    steam_play_evidence = compatdata_found or runtime_found or bool(mapped_name)

    if steam_play_evidence and prefix_found and runtime_found:
        resolution_state = "resolved-steam-play"
        resolution_label = "Steam Play runtime + compatdata resolved"
        runtime_resolved = True
    elif steam_play_evidence and prefix_found:
        resolution_state = "prefix-resolved-runtime-name-only" if mapped_name else "prefix-resolved-runtime-unknown"
        resolution_label = "Compatdata/prefix resolved; concrete Proton tool path unresolved"
        runtime_resolved = False
    elif steam_play_evidence:
        resolution_state = "steam-play-configured-prefix-missing"
        resolution_label = "Steam Play compatibility selected; compatdata prefix not created yet"
        runtime_resolved = False
    elif kind in {"linux-appimage", "native-or-script", "script"}:
        resolution_state = "native-or-script-no-proton-evidence"
        resolution_label = "Native/script shortcut; no Steam Play compatdata detected"
        runtime_resolved = False
    else:
        resolution_state = "windows-target-proton-unresolved"
        resolution_label = "Windows shortcut detected; Steam Play runtime/prefix unresolved"
        runtime_resolved = False

    return {
        "appid": str(appid),
        "gameid": str(gameid),
        "launch_uri": f"steam://rungameid/{gameid}",
        "key": f"steam-shortcut:{appid}",
        "provider": "steam-shortcut",
        "runner": "steam-shortcut",
        "name": str(row["name"]),
        "install_dir": str(install),
        "executable": exe,
        "prefix": prefix,
        "compatdata": compatdata,
        "target_kind": kind,
        "launch_options": str(row.get("launch_options", "")),
        "steam_root": str(root),
        "steam_user": userdir.name,
        "shortcuts_file": str(userdir / "config/shortcuts.vdf"),
        "shortcut_index": str(row["index"]),
        "appid_source": appid_source,
        "compat_tool": compat_tool,
        "compat_tool_path": compat_tool_path,
        "compat_tool_source": compat_source,
        "compat_mapping_name": mapped_name,
        "compat_mapping_scope": mapping_scope,
        "compat_mapping_config": mapping_config,
        "compat_mapping_priority": mapping_priority,
        "compat_mapping_file": mapping_file,
        "compatdata_found": compatdata_found,
        "prefix_found": prefix_found,
        "runtime_found": runtime_found,
        "runtime_resolved": runtime_resolved,
        "resolution_state": resolution_state,
        "resolution_label": resolution_label,
        # Test 14 allows launch only when both the concrete Steam Play runtime
        # and compatdata/prefix were resolved. The launcher still validates the
        # actual live session before handing the trainer into runinprefix.
        "launch_supported": bool(runtime_resolved and kind == "windows"),
    }


def discover() -> list[dict[str, object]]:
    discovered: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for root in steam_roots():
        libraries = steam_library_roots(root)
        userdata = root / "userdata"
        try:
            users = sorted((p for p in userdata.iterdir() if p.is_dir()), key=lambda p: p.name)
        except OSError:
            users = []
        for userdir in users:
            path = userdir / "config/shortcuts.vdf"
            if not path.is_file():
                continue
            try:
                rows = parse_shortcuts(path)
            except (OSError, ValueError) as exc:
                print(json.dumps({"warning": f"Could not parse {path}: {exc}"}), file=sys.stderr)
                continue
            for row in rows:
                resolved = _resolve_shortcut(root, userdir, libraries, row)
                key = (int(resolved["appid"]), str(resolved["name"]).casefold(), str(resolved["executable"]))
                if key in seen:
                    continue
                seen.add(key)
                discovered.append(resolved)
    discovered.sort(key=lambda x: (str(x["name"]).casefold(), str(x["appid"])))
    return discovered


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="emit one JSON line per resolved Steam non-Steam shortcut")
    sub.add_parser("count", help="print discovered shortcut count")
    one = sub.add_parser("resolve", help="emit one JSON object for an AppID/key if discovered")
    one.add_argument("identity")
    args = ap.parse_args(argv)
    rows = discover()
    if args.cmd == "count":
        print(len(rows))
        return 0
    if args.cmd == "resolve":
        identity = str(args.identity)
        if identity.startswith("steam-shortcut:"):
            identity = identity.split(":", 1)[1]
        for row in rows:
            if str(row.get("appid")) == identity or str(row.get("gameid")) == identity:
                print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
                return 0
        return 1
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
