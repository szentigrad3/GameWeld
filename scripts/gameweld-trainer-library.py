#!/usr/bin/env python3
"""GameWeld Trainer Library discovery and conservative matching.

0.5.0 Test 13 manager liveness hardening (detector rules inherited from Test 5):
- work out of the box for ordinary Linux users: XDG/HOME, common trainer folders, removable/mounted game libraries, and launcher-reported install paths;
- keep per-root scan budgets so a large library cannot starve another drive;
- expose structured Assigned / Matched / Ambiguous / Unmatched trainer rows for the UI;
- explain confidence and match reason;
- support persistent ignored trainer executables;
- support merge-mode rescans for one selected game without destroying the full report;
- include existing readable assignments in the report while never overwriting them;
- detect multiple trainer versions conservatively and surface explicit alternatives;
- prefer a unique newer semantic version only when every tied strong match has comparable version metadata;
- keep cross-game title conflicts ambiguous instead of assigning one trainer to multiple similarly named installed games;
- never mislabel an already-assigned trainer as unmatched just because assigned games were omitted from the scan manifest.
- report assignment health as Valid / Recovered / Missing;
- recover a moved trainer automatically only when its exact filename is found in exactly one known scan location;
- support a per-user duplicate-version policy: Ask me (default), Keep current, or Prefer newest;
- never delete trainer EXEs during cleanup; missing-assignment cleanup only edits GameWeld's own mapping file.
- provide fast query/sort/attention views for large normal-user libraries without rescanning;
- statically profile discovered Windows trainer executables (architecture, native/.NET runtime, elevation manifest hints, web/runtime signals, and known trainer-family signatures);
- map detected trainer families into Compatibility Engine v2 recipes that explicitly describe session ownership, automation eligibility, elevation strategy, runtime requirements, DLL overrides, validation state, and risk without silently changing launch behavior;
- apply only the proven FLiNG compatibility profile automatically for Heroic local-trainer launches when detection is High or Medium confidence; other profiles remain advisory and Steam live-session handoff is unchanged.
- support explicit per-trainer launch-policy overrides (Auto, force managed FLiNG for Heroic, or force inherit) without changing the validated launcher/session helpers.
- resolve a backend-aware effective launch preview so the Library can show what the next Steam/Heroic launch will actually do before starting the game.
- pair that preview with a native-UI direct-launch action that is enabled only for the exact trainer currently assigned to its matched game; the helper itself does not start games.
- expose per-row launch policy/effective launch fields plus a compact compatibility-readiness audit so large libraries can be reviewed at a glance without launching anything.
- let the cached library be drilled down by readiness bucket (managed FLiNG, Steam live, Heroic existing, explicit override, no target, manual policy, advisory, or attention) without rescanning or touching launch settings.
"""
from __future__ import annotations

import argparse
import atexit
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Iterable

MAX_TRAINER_BYTES = 750 * 1024 * 1024
STANDARD_ROOT_BUDGET = 6000
CONFIG_ROOT_BUDGET = 12000
INSTALL_ROOT_BUDGET = 1800
PARENT_ROOT_BUDGET = 12000

STOP = {
    "the", "a", "an", "of", "and", "or", "for", "with", "game",
    "edition", "ultimate", "complete", "definitive", "enhanced", "goty",
    "remastered", "remaster", "collection", "bundle", "windows", "pc",
}
TRAINER_WORDS = {
    "trainer", "fling", "fixed", "fix", "plus", "update", "updated",
    "steam", "gog", "epic", "win", "win64", "x64", "x86", "dx11", "dx12",
}
EXCLUDE_WORDS = {"setup", "installer", "uninstall", "uninstaller", "crashreport", "launcher"}


VERSION_RE = re.compile(r"(?i)(?<![a-z0-9])v?(\d+(?:[._-]\d+){1,4})(?![a-z0-9])")

def trainer_version_info(candidate: Path | str) -> tuple[str, tuple[int, ...] | None]:
    """Return a readable version label and a sortable semantic-ish version tuple.

    Only dotted/underscored/hyphenated numeric versions are considered. Plain
    integers such as the `12` in `Plus 12 Trainer` are deliberately ignored so
    cheat-count labels never become version numbers. For range-like trainer names
    (for example `v1.0-v1.12`) the highest parsed endpoint is used for preference
    while the UI preserves the whole discovered range.
    """
    stem = Path(candidate).stem
    seen: list[tuple[str, tuple[int, ...]]] = []
    for m in VERSION_RE.finditer(stem):
        raw = m.group(1)
        parts = tuple(int(x) for x in re.split(r"[._-]", raw))
        label = "v" + raw.replace("_", ".")
        if not any(parts == old_parts for _, old_parts in seen):
            seen.append((label, parts))
    if not seen:
        return "", None
    label = seen[0][0] if len(seen) == 1 else " → ".join(x[0] for x in seen)
    return label, max((parts for _, parts in seen))


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))


def xdg_cache_home() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))



PROFILE_SCAN_HEAD = 64 * 1024 * 1024
PROFILE_SCAN_TAIL = 32 * 1024 * 1024
PROFILE_CHUNK = 4 * 1024 * 1024
PROFILE_OVERLAP = 512
PROFILE_DETECTOR_REVISION = "0.5.0-test5-r1"
COMPAT_ENGINE_REVISION = "0.5.0-test13-r1"
DISCOVERY_REVISION = "0.5.0-test4-r1"

_PROFILE_CACHE: dict[str, tuple[int, int, tuple[str, str, str, str, str, str, str]]] = {}
_PROFILE_CACHE_LOADED = False
_PROFILE_CACHE_DIRTY = False


def profile_cache_file() -> Path:
    return xdg_cache_home() / "gameweld" / "trainer-profile-cache.tsv"


def _profile_clean(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _load_profile_cache() -> None:
    global _PROFILE_CACHE_LOADED
    if _PROFILE_CACHE_LOADED:
        return
    _PROFILE_CACHE_LOADED = True
    try:
        lines = profile_cache_file().read_text(errors="replace").splitlines()
    except OSError:
        return
    # Profile classification rules evolve independently of trainer files.  A
    # size/mtime-only cache therefore becomes stale across detector upgrades.
    # Require an explicit detector revision; legacy/unversioned caches are
    # intentionally ignored and replaced on the next successful profile write.
    expected = f"META\tDETECTOR_REVISION\t{PROFILE_DETECTOR_REVISION}"
    if not lines or lines[0] != expected:
        return
    for raw in lines[1:]:
        p = raw.split("\t")
        if len(p) < 10:
            continue
        path = p[0]
        try:
            size = int(p[1]); mtime_ns = int(p[2])
        except ValueError:
            continue
        fields = tuple(p[3:10])
        if len(fields) == 7:
            _PROFILE_CACHE[path] = (size, mtime_ns, fields)  # type: ignore[assignment]


def _flush_profile_cache() -> None:
    global _PROFILE_CACHE_DIRTY
    if not _PROFILE_CACHE_DIRTY:
        return
    try:
        target = profile_cache_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(f"META\tDETECTOR_REVISION\t{PROFILE_DETECTOR_REVISION}\n")
            for path in sorted(_PROFILE_CACHE, key=str.casefold):
                size, mtime_ns, fields = _PROFILE_CACHE[path]
                vals = [path, str(size), str(mtime_ns), *fields]
                f.write("\t".join(_profile_clean(x) for x in vals) + "\n")
        tmp.replace(target)
        _PROFILE_CACHE_DIRTY = False
    except OSError:
        pass


atexit.register(_flush_profile_cache)


def _pe_metadata(path: Path) -> tuple[bool, str, bool]:
    """Return (valid_pe, architecture, has_clr_header)."""
    try:
        with path.open("rb") as f:
            dos = f.read(64)
            if len(dos) < 64 or dos[:2] != b"MZ":
                return False, "Unknown", False
            pe_off = struct.unpack_from("<I", dos, 0x3C)[0]
            if pe_off <= 0 or pe_off > 32 * 1024 * 1024:
                return False, "Unknown", False
            f.seek(pe_off)
            head = f.read(24)
            if len(head) < 24 or head[:4] != b"PE\0\0":
                return False, "Unknown", False
            machine = struct.unpack_from("<H", head, 4)[0]
            opt_size = struct.unpack_from("<H", head, 20)[0]
            arch = {
                0x014C: "x86",
                0x8664: "x64",
                0xAA64: "ARM64",
                0x01C4: "ARM",
            }.get(machine, f"PE machine 0x{machine:04x}")
            optional = f.read(opt_size)
            if len(optional) < 2:
                return True, arch, False
            magic = struct.unpack_from("<H", optional, 0)[0]
            data_dir_off = 96 if magic == 0x10B else (112 if magic == 0x20B else -1)
            has_clr = False
            if data_dir_off >= 0:
                com_off = data_dir_off + (14 * 8)
                if len(optional) >= com_off + 8:
                    rva, size = struct.unpack_from("<II", optional, com_off)
                    has_clr = bool(rva and size)
            return True, arch, has_clr
    except (OSError, struct.error, OverflowError):
        return False, "Unknown", False


def _scan_profile_markers(path: Path) -> set[str]:
    patterns: dict[str, tuple[bytes, ...]] = {
        "fling-strong": (
            b"flingtrainer.com", b"www.flingtrainer.com", b"fling trainer",
            "flingtrainer.com".encode("utf-16le"), "www.flingtrainer.com".encode("utf-16le"), "fling trainer".encode("utf-16le"),
        ),
        "fling-weak": (b"fling", "fling".encode("utf-16le")),
        "cheat-happens-aurora": (
            b"cheathappens\\auroranext", b"auroranext\\aurora", b"cheathappensoverlay_x64",
            "cheathappens\\auroranext".encode("utf-16le"), "auroranext\\aurora".encode("utf-16le"),
        ),
        "cheat-happens": (
            b"cheat happens", b"cheathappens.com", b"www.cheathappens.com", b"cheathappens",
            "cheat happens".encode("utf-16le"), "cheathappens.com".encode("utf-16le"), "www.cheathappens.com".encode("utf-16le"),
        ),
        "cheat-evolution": (
            b"cheatevolution.com", b"cheatevolution.cevapp.app", b"cheatevolution",
            "cheatevolution.com".encode("utf-16le"), "cheatevolution.cevapp.app".encode("utf-16le"), "cheatevolution".encode("utf-16le"),
        ),
        "wemod": (
            b"wemod.com", b"www.wemod.com", b"wemod.exe", b"wemod",
            "wemod.com".encode("utf-16le"), "www.wemod.com".encode("utf-16le"), "wemod.exe".encode("utf-16le"), "wemod".encode("utf-16le"),
        ),
        "mrantifun": (
            b"mrantifun.net", b"mrantifun.com", b"mrantifun",
            "mrantifun.net".encode("utf-16le"), "mrantifun.com".encode("utf-16le"), "mrantifun".encode("utf-16le"),
        ),
        "wininet": (b"wininet.dll", "wininet.dll".encode("utf-16le")),
        "iertutil": (b"iertutil.dll", "iertutil.dll".encode("utf-16le")),
        "urlmon": (b"urlmon.dll", "urlmon.dll".encode("utf-16le")),
        "winhttp": (b"winhttp.dll", "winhttp.dll".encode("utf-16le")),
        "mshtml": (b"mshtml.dll", "mshtml.dll".encode("utf-16le")),
        "webview2": (b"webview2loader", b"microsoft.web.webview2", "webview2loader".encode("utf-16le")),
        "dwrite": (b"dwrite.dll", "dwrite.dll".encode("utf-16le")),
        "dwritecore": (b"dwritecore.dll", "dwritecore.dll".encode("utf-16le")),
        "mscoree": (b"mscoree.dll", "mscoree.dll".encode("utf-16le")),
        "require-admin": (b"requireadministrator", "requireadministrator".encode("utf-16le")),
        "highest": (b"highestavailable", "highestavailable".encode("utf-16le")),
        "as-invoker": (b"asinvoker", "asinvoker".encode("utf-16le")),
    }
    found: set[str] = set()
    try:
        size = path.stat().st_size
        windows: list[tuple[int, int]] = []
        head_end = min(size, PROFILE_SCAN_HEAD)
        windows.append((0, head_end))
        if size > head_end:
            tail_start = max(head_end, size - PROFILE_SCAN_TAIL)
            if tail_start < size:
                windows.append((tail_start, size))
        with path.open("rb") as f:
            for start, end in windows:
                f.seek(start)
                remain = end - start
                carry = b""
                while remain > 0:
                    chunk = f.read(min(PROFILE_CHUNK, remain))
                    if not chunk:
                        break
                    remain -= len(chunk)
                    block = (carry + chunk).lower()
                    for name, pats in patterns.items():
                        if name in found:
                            continue
                        if any(pat in block for pat in pats):
                            found.add(name)
                    carry = block[-PROFILE_OVERLAP:] if len(block) > PROFILE_OVERLAP else block
    except OSError:
        pass
    return found


def _fling_filename_hint(path: Path) -> bool:
    """Recognise common packed FLiNG release filenames without trusting them as proof.

    Some FLiNG trainers are packed/managed and expose no FLiNG strings in the PE
    windows we scan.  Their public filenames commonly end in forms such as
    ``v1.0 Plus 12 Trainer.exe`` or ``v1.0 Plus 12 Trainer Fixed.exe``.  This is
    only a medium-confidence family hint; embedded signatures still win.
    """
    name = path.name.casefold().strip()
    return bool(re.search(
        r"(?:^|[ _.-])v?\d+(?:\.\d+)*(?:\s*[-–]\s*v?\d+(?:\.\d+)*)?\s+plus\s+\d+\s+trainer(?:\s+fixed)?\.exe$",
        name,
        re.IGNORECASE,
    ))


def _vendor_filename_hints(path: Path) -> set[str]:
    """Return explicit vendor-name hints from the executable filename.

    Test 4 retains literal-only vendor naming here.  Generic words such as
    ``trainer``, ``manager`` or ``plus`` are never treated as vendor evidence.
    Filename hints are Medium confidence at most and never enable a new automatic
    compatibility path.
    """
    name = path.name.casefold()
    hints: set[str] = set()
    if "cheat happens" in name or "cheathappens" in name:
        hints.add("cheat-happens")
    if "cheat evolution" in name or "cheatevolution" in name:
        hints.add("cheat-evolution")
    if "mrantifun" in name or "mr anti fun" in name:
        hints.add("mrantifun")
    if "wemod" in name or "we mod" in name:
        hints.add("wemod")
    return hints


def _bundle_profile_markers(path: Path) -> set[str]:
    """Return conservative package-level evidence for known trainer managers.

    The manager fingerprints remain grounded in real Cheat Evolution and Cheat Happens
    Aurora packages.  Package evidence is deliberately based on a small set of
    companion filenames that are difficult to hit accidentally; it never scans or
    executes neighboring binaries.
    """
    out: set[str] = set()
    try:
        parent = path.parent
        names = {x.name.casefold() for x in parent.iterdir() if x.is_file()}
    except OSError:
        return out
    base = path.name.casefold()
    if base == "cheatevolution.exe":
        required = {"launcher.exe", "lua53-64.dll", "speedhack-x86_64.dll"}
        if required.issubset(names):
            out.add("cheat-evolution-bundle")
    if base == "aurora.exe":
        required = {"chmt64.dll", "cheathappensoverlay_x64.dll", "webview2loader.dll"}
        if required.issubset(names):
            out.add("cheat-happens-aurora-bundle")
        if "chdotnetcorehelper.dll" in names or "dotnetcore.bootstrapper.dll" in names:
            out.add("dotnet-self-contained-bundle")
        if "webview2loader.dll" in names:
            out.add("webview2-bundle")
    return out


def _is_provider_manager_candidate(path: Path) -> bool:
    """Conservatively exclude standalone manager frontends from title matching.

    HexTrainer.exe is ambiguous on its own. Only accept the exact manager
    executable in a directory itself named HexTrainer; game-named EXEs remain
    candidates. Existing user assignments are never changed by this classifier.
    """
    if path.name.casefold() == "hextrainer.exe" and path.parent.name.casefold() == "hextrainer":
        return True
    marks = _bundle_profile_markers(path)
    return bool({"cheat-evolution-bundle", "cheat-happens-aurora-bundle"} & marks)


def _vendor_marker_labels(marks: set[str]) -> list[str]:
    # MrAntiFun's current ecosystem is distributed through WeMod, so those two
    # signatures belong to one provider family for conflict purposes.
    labels = {
        "fling-strong": "FLiNG",
        "cheat-happens-aurora": "Cheat Happens",
        "cheat-happens-aurora-bundle": "Cheat Happens",
        "cheat-happens": "Cheat Happens",
        "cheat-evolution": "Cheat Evolution",
        "cheat-evolution-bundle": "Cheat Evolution",
        "wemod": "WeMod / MrAntiFun",
        "mrantifun": "WeMod / MrAntiFun",
    }
    out: list[str] = []
    for key, label in labels.items():
        if key in marks and label not in out:
            out.append(label)
    return out


def analyze_trainer_profile(candidate: Path | str) -> tuple[str, str, str, str, str, str, str]:
    """Return profile, arch, runtime, elevation, confidence, signals, recommendation.

    Detection is static. Test 5 retains the real-package fingerprints for Cheat Evolution
    and Cheat Happens Aurora, keeps the portable Test 4 scanner, and hardens
    vendor-conflict handling from field FLiNG samples without broadening automation.
    """
    global _PROFILE_CACHE_DIRTY
    p = Path(candidate).expanduser().resolve(strict=False)
    cp = str(p)
    try:
        st = p.stat()
        if not p.is_file():
            raise OSError
    except OSError:
        return ("Unavailable", "—", "—", "—", "—", "Trainer file missing", "Recover or choose a readable trainer before compatibility analysis.")

    _load_profile_cache()
    cached = _PROFILE_CACHE.get(cp)
    if cached and cached[0] == st.st_size and cached[1] == st.st_mtime_ns:
        return cached[2]

    valid_pe, arch, has_clr = _pe_metadata(p)
    binary_marks = _scan_profile_markers(p)
    bundle_marks = _bundle_profile_markers(p)
    marks = binary_marks | bundle_marks
    if "cheat-happens-aurora" in marks or "cheat-happens-aurora-bundle" in marks:
        runtime = ".NET self-contained / Avalonia"
    elif "cheat-evolution" in marks or "cheat-evolution-bundle" in marks:
        runtime = "Native Windows + Lua"
    elif has_clr or "mscoree" in marks:
        runtime = ".NET / CLR"
    elif valid_pe:
        runtime = "Native Windows"
    else:
        runtime = "Unknown"

    if "require-admin" in marks:
        elevation = "Administrator requested"
    elif "highest" in marks:
        elevation = "Highest available"
    elif "as-invoker" in marks:
        elevation = "Standard user (asInvoker)"
    else:
        elevation = "Not declared"

    web = [x for x in ("wininet", "iertutil", "urlmon", "winhttp", "mshtml", "webview2") if x in marks]
    if "webview2-bundle" in marks and "webview2" not in web:
        web.append("webview2")
    render = [x for x in ("dwrite", "dwritecore") if x in marks]
    sigs: list[str] = []

    filename_fling = _fling_filename_hint(p)
    filename_vendor_hints = _vendor_filename_hints(p)
    vendor_markers = _vendor_marker_labels(marks)

    # Field hardening (Test 5): two independently strong FLiNG signals
    # (official FLiNG marker + the established public release-name pattern)
    # outrank incidental WeMod/MrAntiFun strings embedded in some FLiNG trainer
    # binaries.  This does *not* suppress conflicts with Cheat Happens, Cheat
    # Evolution, explicit non-FLiNG vendor filenames, or real manager bundles.
    # Those remain manual-review hard stops.
    fling_field_override = False
    competing_markers = [x for x in vendor_markers if x != "FLiNG"]
    if "fling-strong" in marks and filename_fling and competing_markers:
        only_wemod_crossrefs = all(x == "WeMod / MrAntiFun" for x in competing_markers)
        explicit_other_vendor = bool(filename_vendor_hints)
        manager_bundle = bool({"cheat-happens-aurora-bundle", "cheat-evolution-bundle"} & marks)
        if only_wemod_crossrefs and not explicit_other_vendor and not manager_bundle:
            fling_field_override = True

    if _is_provider_manager_candidate(p) and p.name.casefold() == "hextrainer.exe":
        profile, confidence = "HexTrainer manager (identity review)", "Medium"
        sigs.append("Exact HexTrainer.exe within HexTrainer directory; package not authenticated")
        recommendation = "Treat as a possible multi-game manager. Do not auto-match to a single title or change existing manual assignments. Confirm the official client identity before launching or updating."
    elif fling_field_override:
        profile, confidence = "FLiNG compatibility", "High"
        sigs.append("FLiNG signature")
        sigs.append("Cross-provider text ignored for family selection: WeMod / MrAntiFun")
        recommendation = "Heroic launch policy: automatically use pinned GE-Proton10-34 + Wine-Wayland and Windows-token elevation. Steam keeps the existing live Proton-session handoff. Incidental WeMod/MrAntiFun text was not allowed to override the matching FLiNG release identity."
    elif len(vendor_markers) > 1:
        profile, confidence = "Conflicting trainer signatures", "Low"
        sigs.append("Conflicting vendor signatures: " + ", ".join(vendor_markers))
        recommendation = "Do not change compatibility automatically. Multiple substantive vendor signatures were detected; review the trainer manually before choosing any explicit policy."
    elif "cheat-happens-aurora" in marks or "cheat-happens-aurora-bundle" in marks:
        profile, confidence = "Cheat Happens Aurora manager", "High"
        sigs.append("Cheat Happens Aurora signature")
        recommendation = "Aurora is a multi-game trainer manager, not a per-game trainer EXE. Keep its package intact and do not auto-assign it to a game; field-launch validation is required before GameWeld manages its runtime."
    elif "cheat-evolution" in marks or "cheat-evolution-bundle" in marks:
        profile, confidence = "Cheat Evolution manager", "High"
        sigs.append("Cheat Evolution signature")
        recommendation = "Cheat Evolution is a multi-game trainer manager. Keep Launcher.exe and companion Lua/DLL files beside CheatEvolution.exe; do not auto-assign it to a game until its launch flow is field-validated."
    elif "fling-strong" in marks:
        profile, confidence = "FLiNG compatibility", "High"
        sigs.append("FLiNG signature")
        recommendation = "Heroic launch policy: automatically use pinned GE-Proton10-34 + Wine-Wayland and Windows-token elevation. Steam keeps the existing live Proton-session handoff."
    elif "cheat-happens" in marks:
        profile, confidence = "Cheat Happens trainer", "High"
        sigs.append("Cheat Happens signature")
        recommendation = "Use the game's existing Proton/Wine session first; elevation/runtime requirements are shown separately. Advisory only."
    elif "wemod" in marks or "mrantifun" in marks:
        profile, confidence = "WeMod-related trainer", "High"
        sigs.append("WeMod / MrAntiFun ecosystem signature")
        recommendation = "Treat as WeMod launcher/runtime-sensitive; no automatic compatibility change is inferred."
    elif len(filename_vendor_hints) > 1:
        profile, confidence = "Conflicting trainer signatures", "Low"
        sigs.append("Conflicting vendor filename hints: " + ", ".join(sorted(filename_vendor_hints)))
        recommendation = "Do not change compatibility automatically. The executable filename names more than one trainer ecosystem."
    elif "cheat-happens" in filename_vendor_hints:
        profile, confidence = "Cheat Happens trainer", "Medium"
        sigs.append("Cheat Happens filename hint")
        recommendation = "Likely Cheat Happens trainer from explicit filename evidence. Keep the game's existing Proton/Wine session; advisory only until real-game validation."
    elif "cheat-evolution" in filename_vendor_hints:
        profile, confidence = "Cheat Evolution manager", "Medium"
        sigs.append("Cheat Evolution filename hint")
        recommendation = "Likely Cheat Evolution manager from explicit filename evidence. Package-level validation is required before treating it as a provider manager."
    elif "wemod" in filename_vendor_hints or "mrantifun" in filename_vendor_hints:
        profile, confidence = "WeMod-related trainer", "Medium"
        sigs.append("WeMod / MrAntiFun filename hint")
        recommendation = "Likely WeMod-related executable from explicit filename evidence. Treat as launcher/runtime-sensitive; advisory only."
    elif filename_fling:
        profile, confidence = "FLiNG compatibility", "Medium"
        sigs.append("FLiNG-style trainer filename")
        recommendation = "Likely packed FLiNG-family trainer: Heroic automatically uses pinned GE-Proton10-34 + Wine-Wayland and Windows-token elevation. Steam keeps the existing live Proton-session handoff."
    elif has_clr or "mscoree" in marks:
        profile, confidence = ".NET trainer", "High"
        recommendation = "Keep the trainer in the game's compatibility context; a compatible .NET runtime may be required. Advisory only."
    elif web:
        profile, confidence = "Web-backed trainer", "Medium"
        recommendation = "Web/runtime-sensitive trainer; verify rendering before applying any DLL/runtime override. Advisory only."
    elif valid_pe:
        profile, confidence = "Generic native trainer", "Medium"
        recommendation = "Use the game's existing Proton/Wine session; no special compatibility override inferred."
    else:
        profile, confidence = "Unknown Windows trainer", "Low"
        recommendation = "No compatibility override inferred because the PE header could not be fully validated."

    if "fling-weak" in marks and "fling-strong" not in marks and not vendor_markers:
        sigs.append("FLiNG text hint")
        if profile == "Generic native trainer":
            profile, confidence = "Possible FLiNG trainer", "Medium"
            recommendation = "Possible FLiNG profile candidate; weak text evidence is not sufficient for automatic compatibility changes."
    if web:
        sigs.append("web DLLs: " + ", ".join(web))
    if render:
        sigs.append("text/render: " + ", ".join(render))
    if has_clr:
        sigs.append("CLR header")
    if bundle_marks:
        sigs.append("package: " + ", ".join(sorted(bundle_marks)))
    if elevation != "Not declared":
        sigs.append(elevation)
    if not valid_pe:
        sigs.append("PE header incomplete")
    signals = "; ".join(sigs) if sigs else "No special static compatibility signals"

    fields = (profile, arch, runtime, elevation, confidence, signals, recommendation)
    _PROFILE_CACHE[cp] = (st.st_size, st.st_mtime_ns, fields)
    _PROFILE_CACHE_DIRTY = True
    return fields


# Compatibility Engine v2 deliberately separates *detection* from *action*.
# A recipe is an inspectable recommendation contract.  Only recipes marked
# automation="validated" may participate in automatic runtime changes, and in
# 0.5.0 Test 8 keeps FLiNG as the only automatic per-game profile. Trainer managers remain unassigned, but may be launched explicitly either standalone or into an already-running compatible game session.
# Everything else is advisory until validated by a later 0.5.x test line.
def compatibility_recipe_from_profile(
    profile: str,
    confidence: str,
    runtime: str,
    elevation: str,
    signals: str,
) -> tuple[str, str, str, str, str, str, str, str, str]:
    """Return recipe_id, validation, session, automation, elevation, runtime,
    dll_overrides, risk, rationale for a detected profile.

    The engine is intentionally data-like and backend-neutral.  Launcher-specific
    policy remains in trainer_effective_launch_plan(), which preserves the proven
    0.4 Steam/Heroic ownership rules.
    """
    if profile == "FLiNG compatibility" and confidence in {"High", "Medium"}:
        return (
            "fling-managed-v1",
            "Validated",
            "Heroic: managed compatibility session; Steam: existing live Proton session",
            "Automatic on Heroic only; Steam path unchanged",
            "Windows-token administrator when requested and not explicitly overridden",
            "Heroic pinned GE-Proton10-34 + Wine-Wayland; Steam uses game-selected Proton",
            "Heroic trainer process: builtin wininet + iertutil; Steam: no recipe DLL change",
            "Low on validated Heroic/Steam paths",
            "The FLiNG family is the only v2 recipe currently allowed to alter Heroic runtime selection automatically.",
        )
    if profile == "Conflicting trainer signatures":
        return (
            "conflicting-signatures-review-v1",
            "Advisory",
            "Keep the game's existing compatibility session until the trainer is reviewed",
            "No automatic compatibility action",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            runtime or "Unknown",
            "None inferred automatically",
            "High uncertainty — multiple trainer ecosystems were detected",
            "Conflicting static evidence is treated as a hard stop for automatic family-specific compatibility selection.",
        )
    if profile == "Cheat Happens Aurora manager":
        return (
            "cheat-happens-aurora-manager-v1",
            "Sample-backed advisory",
            "Multi-game manager application; do not infer a per-game ownership session",
            "Explicit manager launch: standalone Proton-first or same-session game attachment; one signature-gated render fallback; never assigned to a game",
            elevation if elevation != "Not declared" else "Preserve Aurora elevation behavior",
            "Dedicated manager prefix; installed Proton preferred, ordinary Wine fallback",
            "Only after the observed Avalonia/ANGLE D3D shader crash: retry with packaged av_libglesv2 disabled via WINEDLLOVERRIDES; package files are not modified",
            "Medium-low for game attachment — standalone Aurora GUI/login rendering was field-validated in Test 7; same-session game attachment remains unvalidated",
            "Test 7 field validation showed Aurora rendering correctly with the Proton-first manager recipe. Test 8 keeps game assignment disabled and adds explicit attachment to an already-running compatible game session so Aurora can share that game's Windows process namespace.",
        )
    if profile == "Cheat Evolution manager":
        return (
            "cheat-evolution-manager-v1",
            "Sample-backed advisory",
            "Multi-game manager application; keep its package directory intact",
            "Explicit manager launch: standalone Wine-first or same-session game attachment; never assigned to a game",
            elevation if elevation != "Not declared" else "Preserve Cheat Evolution elevation behavior",
            "Dedicated manager prefix; ordinary Wine preferred because the Test 6 field launch reached a live manager session",
            "None inferred automatically",
            "Medium-low for game attachment — standalone Cheat Evolution GUI/login rendering was field-validated in Test 7; same-session game attachment remains unvalidated",
            "Test 7 field validation showed Cheat Evolution rendering correctly with the Wine-first manager recipe. Test 8 preserves standalone behavior and adds explicit same-session attachment while keeping per-game auto-matching blocked.",
        )
    if profile == "Cheat Happens trainer":
        return (
            "cheat-happens-inherit-v1",
            "Advisory",
            "Inherit the game's existing Steam/Heroic compatibility session",
            "No automatic runtime switch in Test 5",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            "Use the game-selected Wine/Proton runtime; validate vendor/runtime dependencies before promotion",
            "None inferred automatically",
            "Medium — family detected, automatic recipe not yet validated",
            "Compatibility Engine v2 recognizes the family but intentionally keeps launch behavior unchanged until a dedicated validation pass.",
        )
    if profile == "WeMod-related trainer":
        return (
            "wemod-launcher-sensitive-v1",
            "Advisory",
            "Launcher-sensitive; keep the game's existing session and do not synthesize a second launcher session",
            "No automatic compatibility action",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            "Vendor launcher/runtime dependencies must be validated before any managed recipe is enabled",
            "None inferred automatically",
            "High — launcher/runtime coupling may be stronger than a standalone trainer",
            "Detected WeMod markers are useful for classification, not proof that a standalone trainer recipe is safe.",
        )
    if profile == ".NET trainer":
        return (
            "dotnet-inherit-v1",
            "Advisory",
            "Inherit the game's existing compatibility session",
            "No automatic runtime switch",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            ".NET/CLR availability may be required inside the selected prefix",
            "None inferred automatically",
            "Medium — runtime dependency known, family/vendor unknown",
            "A structural CLR header is strong runtime evidence but is not enough to infer a safe vendor-specific compatibility override.",
        )
    if profile == "Web-backed trainer":
        return (
            "web-backed-inherit-v1",
            "Advisory",
            "Inherit the game's existing compatibility session",
            "No automatic runtime switch",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            "Web/rendering components may depend on Wine Internet, WebView2, or text rendering support",
            "Do not force web DLL overrides until the exact family is validated",
            "Medium — web stack is compatibility-sensitive",
            "Static web DLL markers identify a dependency class, not a safe universal override set.",
        )
    if profile == "Generic native trainer":
        return (
            "native-inherit-v1",
            "Advisory",
            "Inherit the game's existing compatibility session",
            "No automatic runtime switch",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            "Native Windows executable; use the game-selected Wine/Proton runtime",
            "None inferred automatically",
            "Low to medium — no special static requirements detected",
            "The safest default for an unknown native trainer is to stay inside the game's existing compatibility context.",
        )
    if profile == "Possible FLiNG trainer":
        return (
            "possible-fling-review-v1",
            "Advisory",
            "Inherit the game's existing compatibility session",
            "No automatic FLiNG promotion from weak evidence",
            elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
            runtime or "Unknown",
            "None inferred automatically",
            "Medium — FLiNG evidence is weak",
            "Weak text evidence is deliberately insufficient to select the validated managed FLiNG recipe.",
        )
    return (
        "unknown-review-v1",
        "Advisory",
        "No managed compatibility session inferred",
        "No automatic compatibility action",
        elevation if elevation != "Not declared" else "Preserve existing trainer elevation behavior",
        runtime or "Unknown",
        "None inferred automatically",
        "High uncertainty",
        "The trainer does not have enough static evidence for a more specific compatibility recipe.",
    )


def trainer_compatibility_recipe(candidate: Path | str) -> tuple[str, str, str, str, str, str, str, str, str, str, str]:
    profile, arch, runtime, elevation, confidence, signals, recommendation = analyze_trainer_profile(candidate)
    recipe = compatibility_recipe_from_profile(profile, confidence, runtime, elevation, signals)
    return (COMPAT_ENGINE_REVISION, profile, confidence, *recipe)


def compatibility_recipe_summary(candidate: Path | str) -> str:
    revision, profile, confidence, recipe_id, validation, session, automation, elevation, runtime, dlls, risk, rationale = trainer_compatibility_recipe(candidate)
    return f"{recipe_id} • {validation} • {automation}"


def trainer_profile_evidence(candidate: Path | str) -> tuple[str, str, str, str, str, str]:
    """Return detector revision, engine revision, markers, filename hints, PE state and summary."""
    p = Path(candidate).expanduser().resolve(strict=False)
    valid_pe, arch, has_clr = _pe_metadata(p)
    marks = (_scan_profile_markers(p) | _bundle_profile_markers(p)) if p.is_file() else set()
    hints = _vendor_filename_hints(p) if p.name else set()
    if _fling_filename_hint(p):
        hints.add("fling-style-release-name")
    marker_text = ", ".join(sorted(marks)) if marks else "none"
    hint_text = ", ".join(sorted(hints)) if hints else "none"
    pe_text = f"{'valid' if valid_pe else 'incomplete'} PE • {arch} • CLR={'yes' if has_clr else 'no'}"
    vendors = _vendor_marker_labels(marks)
    competing = [x for x in vendors if x != "FLiNG"]
    fling_field_resolved = (
        "fling-strong" in marks
        and _fling_filename_hint(p)
        and competing
        and all(x == "WeMod / MrAntiFun" for x in competing)
        and not _vendor_filename_hints(p)
        and not ({"cheat-happens-aurora-bundle", "cheat-evolution-bundle"} & marks)
    )
    if fling_field_resolved:
        summary = "resolved field identity: FLiNG; incidental WeMod/MrAntiFun cross-reference retained as evidence"
    elif len(vendors) > 1:
        summary = "conflict: " + ", ".join(vendors)
    elif "cheat-happens-aurora-bundle" in marks:
        summary = "real-package manager evidence: Cheat Happens Aurora"
    elif "cheat-evolution-bundle" in marks:
        summary = "real-package manager evidence: Cheat Evolution"
    elif vendors:
        summary = "strong vendor evidence: " + vendors[0]
    elif hints:
        summary = "filename-only vendor/family evidence"
    else:
        summary = "no vendor-specific evidence"
    return (PROFILE_DETECTOR_REVISION, COMPAT_ENGINE_REVISION, marker_text, hint_text, pe_text, summary)


PROFILE_POLICY_MODES = {"auto", "managed-fling", "inherit"}


def profile_policy_file() -> Path:
    return xdg_config_home() / "gameweld" / "trainer-profile-policy.tsv"


def _read_profile_policies() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = profile_policy_file().read_text(errors="replace").splitlines()
    except OSError:
        return out
    for raw in lines:
        if "\t" not in raw:
            continue
        path, mode = raw.split("\t", 1)
        mode = mode.strip().lower()
        if path and mode in PROFILE_POLICY_MODES and mode != "auto":
            out[path] = mode
    return out


def trainer_profile_policy(candidate: Path | str) -> str:
    cp = _canonical_path(candidate)
    return _read_profile_policies().get(cp, "auto")


def set_trainer_profile_policy(candidate: Path | str, mode: str) -> int:
    mode = mode.strip().lower()
    if mode not in PROFILE_POLICY_MODES:
        print(f"Invalid trainer profile policy: {mode}", file=sys.stderr)
        return 2
    cp = _canonical_path(candidate)
    if not cp or "\t" in cp or "\n" in cp or "\r" in cp:
        print("Invalid trainer path", file=sys.stderr)
        return 2
    policies = _read_profile_policies()
    if mode == "auto":
        policies.pop(cp, None)
    else:
        policies[cp] = mode
    target = profile_policy_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for path in sorted(policies, key=str.casefold):
                f.write(f"{path}\t{policies[path]}\n")
        tmp.replace(target)
    except OSError as e:
        print(f"Could not save trainer profile policy: {e}", file=sys.stderr)
        return 1
    print(mode)
    return 0


def trainer_profile_policy_label(candidate: Path | str) -> str:
    mode = trainer_profile_policy(candidate)
    return {
        "auto": "Automatic (use detected compatibility profile)",
        "managed-fling": "Manual: force managed FLiNG session for Heroic",
        "inherit": "Manual: inherit the game's existing session",
    }.get(mode, "Automatic (use detected compatibility profile)")


def trainer_launch_policy(candidate: Path | str) -> tuple[str, str, str, str, str, str]:
    """Return action, profile, confidence, runtime, elevation and reason.

    Test 5 keeps automatic behavior narrow and retains the explicit per-trainer
    user policy. ``managed-fling`` may force the already-proven Heroic managed
    FLiNG session for a trainer the detector cannot classify, while ``inherit``
    disables automatic FLiNG switching for that trainer. ``auto`` preserves the
    Test 5 High/Medium FLiNG default rule while adding explicit per-trainer overrides. Steam remains on its validated live-session
    handoff regardless; the native UI scopes ``heroic-fling-managed`` to Heroic.
    """
    profile, arch, runtime, elevation, confidence, signals, recommendation = analyze_trainer_profile(candidate)
    override = trainer_profile_policy(candidate)
    if override == "managed-fling":
        action = "heroic-fling-managed"
        reason = (
            "Manual per-trainer override -> Heroic pinned GE-Proton10-34 + Wine-Wayland; "
            "request Windows-token elevation unless an explicit environment override is present"
        )
    elif override == "inherit":
        action = "inherit"
        reason = "Manual per-trainer override -> keep the existing game/session path"
    elif profile == "FLiNG compatibility" and confidence in {"High", "Medium"}:
        action = "heroic-fling-managed"
        reason = (
            f"{profile} ({confidence}) -> Heroic pinned GE-Proton10-34 + Wine-Wayland; "
            "request Windows-token elevation unless the user explicitly overrides it"
        )
    else:
        action = "inherit"
        if profile in {"Cheat Happens Aurora manager", "Cheat Evolution manager", "HexTrainer manager (identity review)"}:
            reason = "Recognized multi-game trainer manager; no automatic per-game launch override until field validation"
        else:
            reason = "No automatic launch override; keep the existing game/session path"
    return action, profile, confidence, runtime, elevation, reason


def _env_is_auto_value(value: str | None) -> bool:
    return not value or not value.strip() or value.strip().lower() == "auto"


def _auto_profile_enabled() -> bool:
    value = os.environ.get("GAMEWELD_AUTO_TRAINER_PROFILE", "").strip().lower()
    return value not in {"off", "never", "0", "false"}


def _compat_env_override() -> str:
    for name in ("GAMEWELD_LOCAL_TRAINER_COMPAT_SESSION", "GAMEWELD_FLING_COMPAT_SESSION"):
        value = os.environ.get(name)
        if not _env_is_auto_value(value):
            return f"{name}={value}"
    return ""


def _elevation_env_override() -> str:
    value = os.environ.get("GAMEWELD_TRAINER_ELEVATION")
    if not _env_is_auto_value(value):
        return f"GAMEWELD_TRAINER_ELEVATION={value}"
    return ""


def trainer_effective_launch_plan(candidate: Path | str, backend: str) -> tuple[str, str, str, str, str, str, str, str]:
    """Resolve the backend-aware next-launch preview without changing launch behavior.

    The preview intentionally mirrors the native UI launch boundary used since
    Test 5: Steam always keeps the proven live Proton-session handoff; Heroic
    may use the validated managed FLiNG session when the detector/manual policy
    requests it and no explicit GAMEWELD compatibility override supersedes it.
    """
    backend = (backend or "unassigned").strip().lower()
    if backend not in {"steam", "steam-shortcut", "steam-shortcut-resolved", "steam-shortcut-native", "heroic", "unassigned"}:
        backend = "unassigned"
    action, profile, confidence, detected_runtime, detected_elevation, policy_reason = trainer_launch_policy(candidate)
    policy_mode = trainer_profile_policy(candidate)

    if backend == "steam-shortcut-resolved":
        label = "Steam non-Steam shortcut live Proton-session handoff"
        reason = "GameWeld can launch this shortcut through its Steam rungameid when needed, validate the exact live compatdata session, and then hand the trainer into that same Proton prefix with runinprefix."
        return ("steam-live-session", label, "Shortcut-selected live Steam Proton session", "Existing Steam trainer elevation behavior", policy_mode, profile, confidence, reason)

    if backend == "steam-shortcut-native":
        label = "Steam non-Steam shortcut has no resolved Proton session"
        reason = "This native/script shortcut has no Steam Play compatdata/runtime evidence. A Windows trainer cannot be handed to a Proton prefix that does not exist."
        return ("steam-shortcut-native", label, "No resolved Steam Play prefix", "Windows trainer handoff unavailable", policy_mode, profile, confidence, reason)

    if backend == "steam-shortcut":
        label = "Steam non-Steam shortcut discovered — compatibility resolution incomplete"
        reason = "GameWeld can see the shortcut but has not resolved both a concrete Steam Play runtime and compatdata prefix. Direct trainer launch remains blocked until the runtime/prefix resolves."
        return ("steam-shortcut-pending", label, "Shortcut discovered; runtime/prefix resolution incomplete", "Trainer launch disabled until runtime/prefix resolution succeeds", policy_mode, profile, confidence, reason)

    if backend == "steam":
        label = "Steam live Proton-session handoff"
        reason = "Steam is intentionally frozen on the proven live-session path; Heroic managed-FLiNG policy never replaces the Steam runtime."
        return ("steam-live-session", label, "Game-selected live Steam Proton session", "Existing Steam trainer elevation behavior", policy_mode, profile, confidence, reason)

    if backend == "unassigned":
        label = "No launch target assigned"
        reason = "Assign the trainer to an installed game before GameWeld can resolve a backend-specific launch path."
        return ("unassigned", label, "—", "—", policy_mode, profile, confidence, reason)

    # Heroic path. Explicit environment overrides are diagnostic/user intent and
    # remain authoritative exactly as in the native launcher.
    compat_override = _compat_env_override()
    elevation_override = _elevation_env_override()
    manual_managed = policy_mode == "managed-fling"

    if action == "heroic-fling-managed":
        if compat_override:
            label = "Heroic explicit compatibility override"
            runtime = compat_override
            elevation = elevation_override or "Existing/automatic elevation behavior"
            reason = f"Managed FLiNG was requested, but explicit compatibility override {compat_override} remains authoritative."
            return ("heroic-explicit-compat", label, runtime, elevation, policy_mode, profile, confidence, reason)
        if manual_managed or _auto_profile_enabled():
            label = "Heroic managed FLiNG session"
            runtime = "GE-Proton10-34 + Wine-Wayland"
            elevation = elevation_override or "Windows-token administrator requested"
            source = "manual per-trainer policy" if manual_managed else f"detected {profile} ({confidence}) profile"
            reason = f"{source} -> use the already-proven Heroic managed compatibility session."
            return ("heroic-fling-managed", label, runtime, elevation, policy_mode, profile, confidence, reason)
        label = "Heroic existing session (automatic profile switching disabled)"
        reason = "The trainer is launch-eligible for managed FLiNG, but GAMEWELD_AUTO_TRAINER_PROFILE disables automatic application."
        return ("heroic-inherit-auto-disabled", label, "Heroic game-selected Wine/Proton session", elevation_override or "Existing trainer elevation behavior", policy_mode, profile, confidence, reason)

    label = "Heroic existing game/session path"
    reason = policy_reason
    return ("heroic-inherit", label, "Heroic game-selected Wine/Proton session", elevation_override or "Existing trainer elevation behavior", policy_mode, profile, confidence, reason)


_SHORTCUT_BACKEND_CACHE: dict[str, str] = {}

def _shortcut_backend_for_key(key: str) -> str:
    if key in _SHORTCUT_BACKEND_CACHE:
        return _SHORTCUT_BACKEND_CACHE[key]
    backend = "steam-shortcut"
    helper = Path(__file__).with_name("gameweld-steam-shortcuts.py")
    try:
        cp = subprocess.run([sys.executable, str(helper), "resolve", key], text=True, capture_output=True, timeout=5, check=False)
        if cp.returncode == 0 and cp.stdout.strip():
            import json
            row = json.loads(cp.stdout.splitlines()[0])
            if bool(row.get("runtime_resolved")):
                backend = "steam-shortcut-resolved"
            elif str(row.get("resolution_state", "")).startswith("native-or-script"):
                backend = "steam-shortcut-native"
    except Exception:
        pass
    _SHORTCUT_BACKEND_CACHE[key] = backend
    return backend

def _backend_for_row(row) -> str:
    key = str(row[1] if len(row) > 1 else "")
    if key.startswith("heroic:"):
        return "heroic"
    if key.startswith("steam-shortcut:"):
        return _shortcut_backend_for_key(key)
    if key:
        return "steam"
    return "unassigned"


def _launch_plan_summary(row) -> str:
    path = str(row[5] if len(row) > 5 else "")
    if not path:
        return "No launch target assigned"
    plan, label, runtime, elevation, mode, profile, confidence, reason = trainer_effective_launch_plan(path, _backend_for_row(row))
    detail = label
    if runtime and runtime != "—":
        detail += f" • {runtime}"
    if elevation and elevation != "—":
        detail += f" • {elevation}"
    return detail


def _row_launch_readiness(row) -> tuple[str, str, str]:
    """Return policy label, effective launch label, and launch-plan code for a row."""
    path = str(row[5] if len(row) > 5 else "")
    if not path:
        return ("Automatic", "No launch target assigned", "unassigned")
    policy = trainer_profile_policy_label(path)
    plan, label, runtime, elevation, mode, profile, confidence, reason = trainer_effective_launch_plan(
        path, _backend_for_row(row)
    )
    return (policy, label, plan)


def _compatibility_audit(rows) -> dict[str, int]:
    """Summarize unique trainers by their effective next-launch path."""
    counts = {
        "total": 0, "managed": 0, "steam": 0, "inherit": 0,
        "explicit": 0, "unassigned": 0, "manual": 0,
        "advisory": 0, "attention": 0,
    }
    seen: set[str] = set()
    for row in rows:
        path = str(row[5] if len(row) > 5 else "")
        cp = _canonical_path(path) if path else ""
        if cp and cp in seen:
            continue
        if cp:
            seen.add(cp)
        counts["total"] += 1
        state = str(row[0] if len(row) > 0 else "")
        if state in {"MISSING", "AMBIG", "UNMATCHED"}:
            counts["attention"] += 1
        enriched = _enrich_row_profile(row)
        profile = str(enriched[9] if len(enriched) > 9 else "")
        confidence = str(enriched[13] if len(enriched) > 13 else "")
        recipe = trainer_compatibility_recipe(path) if path else ()
        validation = str(recipe[4]) if len(recipe) > 4 else "Advisory"
        if validation != "Validated":
            counts["advisory"] += 1
        if path and trainer_profile_policy(path) != "auto":
            counts["manual"] += 1
        _policy, _label, code = _row_launch_readiness(row)
        if code == "heroic-fling-managed": counts["managed"] += 1
        elif code == "steam-live-session": counts["steam"] += 1
        elif code in {"heroic-inherit", "heroic-inherit-auto-disabled"}: counts["inherit"] += 1
        elif code == "heroic-explicit-compat": counts["explicit"] += 1
        else: counts["unassigned"] += 1
    return counts


def _enrich_row_profile(row):
    r = list(row)
    while len(r) < 9:
        r.append("")
    # Never trust persisted compatibility columns as detector truth.  The
    # trainer path is the durable fact; profile fields are derived data and are
    # refreshed through the revisioned cache whenever reports are read/written.
    path = r[5] if len(r) > 5 else ""
    fields = analyze_trainer_profile(path) if path else ("Unavailable", "—", "—", "—", "—", "No trainer path", "No compatibility recommendation available.")
    return r[:9] + list(fields)


def roots_file() -> Path:
    return xdg_config_home() / "gameweld" / "trainer-folders.txt"


def ignored_file() -> Path:
    return xdg_config_home() / "gameweld" / "trainer-ignore.txt"


def assignment_file() -> Path:
    return xdg_config_home() / "gameweld" / "local-trainers.tsv"


def version_policy_file() -> Path:
    return xdg_config_home() / "gameweld" / "trainer-version-policy.txt"


def report_file() -> Path:
    return xdg_cache_home() / "gameweld" / "trainer-library-last.tsv"


VALID_POLICIES = {"ask", "keep-current", "prefer-newest"}


def version_policy() -> str:
    try:
        value = version_policy_file().read_text(errors="replace").strip().lower()
    except OSError:
        value = "ask"
    return value if value in VALID_POLICIES else "ask"


def set_version_policy(value: str) -> int:
    value = value.strip().lower()
    if value not in VALID_POLICIES:
        print(f"Invalid policy: {value}", file=sys.stderr)
        return 2
    p = version_policy_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value + "\n", encoding="utf-8")
    print(value)
    return 0


def _read_assignments() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        for raw in assignment_file().read_text(errors="replace").splitlines():
            if "\t" not in raw:
                continue
            key, path = raw.split("\t", 1)
            if key and path:
                out.append((key, path))
    except OSError:
        pass
    return out


def _write_assignments(rows: list[tuple[str, str]]) -> None:
    p = assignment_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for key, path in rows:
            f.write(f"{key}\t{path}\n")
    os.replace(tmp, p)


def replace_assignment(key: str, path: str | None) -> bool:
    try:
        rows = [(k, v) for k, v in _read_assignments() if k != key]
        if path:
            rows.append((key, _canonical_path(path)))
        _write_assignments(rows)
        return True
    except OSError:
        return False


def prune_missing_assignments() -> int:
    rows = _read_assignments()
    kept: list[tuple[str, str]] = []
    removed = 0
    for key, path in rows:
        try:
            ok = Path(path).expanduser().is_file()
        except OSError:
            ok = False
        if ok:
            kept.append((key, path))
        else:
            removed += 1
    try:
        _write_assignments(kept)
    except OSError as e:
        print(f"Could not update trainer assignments: {e}", file=sys.stderr)
        return 1
    print(removed)
    return 0


def _expand_user_dir_value(value: str) -> Path | None:
    value = value.strip().strip('"')
    if not value:
        return None
    home = str(Path.home())
    value = value.replace("$HOME", home).replace("${HOME}", home)
    value = os.path.expandvars(os.path.expanduser(value))
    return Path(value)


def xdg_user_dir(name: str) -> Path | None:
    p = xdg_config_home() / "user-dirs.dirs"
    try:
        for line in p.read_text(errors="replace").splitlines():
            if line.startswith(f"XDG_{name}_DIR="):
                return _expand_user_dir_value(line.split("=", 1)[1])
    except OSError:
        pass
    fallback = {"DOWNLOAD": "Downloads", "DESKTOP": "Desktop", "DOCUMENTS": "Documents"}.get(name)
    return Path.home() / fallback if fallback else None


def configured_roots() -> list[Path]:
    out: list[Path] = []
    try:
        for line in roots_file().read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = _expand_user_dir_value(line)
            if p:
                out.append(p)
    except OSError:
        pass
    return out


def _canonical_path(path: str | Path) -> str:
    try:
        return str(Path(path).expanduser().resolve(strict=False))
    except OSError:
        return str(Path(path).expanduser())


def ignored_paths() -> set[str]:
    out: set[str] = set()
    try:
        for line in ignored_file().read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.add(_canonical_path(line))
    except OSError:
        pass
    return out


def add_root(path: str) -> int:
    p = Path(path).expanduser().resolve(strict=False)
    if not p.is_dir():
        print(f"Not a directory: {p}", file=sys.stderr)
        return 2
    rf = roots_file()
    rf.parent.mkdir(parents=True, exist_ok=True)
    existing = {str(x.resolve(strict=False)) for x in configured_roots()}
    if str(p) not in existing:
        with rf.open("a", encoding="utf-8") as f:
            f.write(str(p) + "\n")
    print(str(p))
    return 0


def ignore_path(path: str) -> int:
    p = Path(path).expanduser().resolve(strict=False)
    if p.suffix.lower() != ".exe":
        print(f"Not a trainer executable path: {p}", file=sys.stderr)
        return 2
    ig = ignored_file()
    ig.parent.mkdir(parents=True, exist_ok=True)
    existing = ignored_paths()
    if str(p) not in existing:
        with ig.open("a", encoding="utf-8") as f:
            f.write(str(p) + "\n")
    print(str(p))
    return 0


def clear_ignored() -> int:
    try:
        ignored_file().unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"Could not clear ignored trainers: {e}", file=sys.stderr)
        return 1
    return 0


def normalize(text: str, trainer: bool = False) -> tuple[str, list[str]]:
    s = Path(text).stem.lower()
    # Steam titles often keep punctuation that trainer filenames flatten.
    # In particular, Assassin's Creed becomes "Assassins Creed" in many FLiNG
    # filenames.  Remove intra-word apostrophes before tokenising so those are
    # treated as the same conservative title rather than "assassin" + "s".
    s = re.sub(r"(?<=\w)['’](?=\w)", "", s)
    s = s.replace("&", " and ")
    s = re.sub(r"\bv?\d+(?:[._-]\d+){0,4}\b", " ", s)
    s = re.sub(r"\bplus\s*\d+\b|\+\s*\d+", " ", s)
    s = re.sub(r"\bbuild\s*\d+\b", " ", s)
    toks = re.findall(r"[a-z0-9]+", s)
    drop = STOP | (TRAINER_WORDS if trainer else set())
    toks = [t for t in toks if t not in drop and not (trainer and t.isdigit())]
    return " ".join(toks), toks


def looks_like_trainer(p: Path) -> bool:
    if p.suffix.lower() != ".exe":
        return False
    # Real-sample manager rule retained in Test 5: known multi-game managers often do not contain the
    # word "trainer" in the executable name.  Discover only when their package
    # companion fingerprint is present, so generic Aurora.exe-style names do not
    # become false positives across a normal Downloads tree.
    if _is_provider_manager_candidate(p):
        return True
    low = p.stem.lower()
    toks = set(re.findall(r"[a-z0-9]+", low))
    if toks & EXCLUDE_WORDS:
        return False
    return "trainer" in low or "fling" in low


def walk_candidates(root: Path, max_depth: int, max_files: int) -> tuple[list[Path], int]:
    """Scan one root with its own traversal budget."""
    root = root.expanduser()
    if not root.is_dir():
        return [], 0
    base_depth = len(root.parts)
    stack = [root]
    seen_dirs: set[tuple[int, int]] = set()
    found: list[Path] = []
    files_seen = 0
    while stack:
        d = stack.pop()
        try:
            st = d.stat()
            ident = (st.st_dev, st.st_ino)
            if ident in seen_dirs:
                continue
            seen_dirs.add(ident)
            entries = list(os.scandir(d))
        except (OSError, PermissionError):
            continue

        dirs: list[Path] = []
        for ent in entries:
            try:
                if ent.is_file(follow_symlinks=False):
                    files_seen += 1
                    p = Path(ent.path)
                    if looks_like_trainer(p):
                        try:
                            if p.stat().st_size <= MAX_TRAINER_BYTES:
                                found.append(p.resolve(strict=False))
                        except OSError:
                            pass
                elif ent.is_dir(follow_symlinks=False) and not ent.name.startswith("."):
                    dirs.append(Path(ent.path))
            except OSError:
                continue

        if files_seen >= max_files:
            continue
        for child in dirs:
            depth = len(child.parts) - base_depth
            if depth <= max_depth:
                stack.append(child)
    return found, files_seen


def score_candidate(game_name: str, candidate: Path) -> tuple[int, str]:
    gp, gt = normalize(game_name, trainer=False)
    cp, ct = normalize(candidate.name, trainer=True)
    if not gt or not ct:
        return 0, "No usable title words"
    gs, cs = set(gt), set(ct)
    if gp and cp == gp:
        return 100, "Exact normalized game title"
    if gp and gp in cp:
        # Test 15: an exact normalized title must outrank a shorter installed
        # title that merely appears inside the trainer title. This matters for
        # libraries containing related games such as "Control Ultimate Edition"
        # (normalized to "control") and "CONTROL Resonant". Treat extra
        # significant title words as a plausible/manual match, not an automatic
        # high-confidence owner.
        return 90, "Full normalized game title appears in trainer name with additional title words"
    if gs.issubset(cs):
        # Likewise, a subset-only match is not strong enough to compete with an
        # exact normalized title for cross-game ownership. The old >=92 score
        # could manufacture ambiguity between a base/edition title and a distinct
        # sequel/subtitle trainer.
        return 90, "All significant game-title words are present with additional title words"
    common = len(gs & cs)
    if common == 0:
        return 0, "No significant title words in common"
    recall = common / len(gs)
    precision = common / len(cs)
    score = int(round((0.75 * recall + 0.25 * precision) * 100))
    if len(gs) == 1 and not gs.issubset(cs):
        return 0, "Single-word game title is not an exact token match"
    return score, f"{common}/{len(gs)} significant game-title words matched"


def parse_manifest(path: Path):
    games = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            raw = raw.rstrip("\r\n")
            if not raw:
                continue
            parts = raw.split("\t")
            if len(parts) < 3:
                continue
            key, name, install_dir = parts[:3]
            provider = parts[3] if len(parts) > 3 else ""
            assignment = parts[4] if len(parts) > 4 else ""
            games.append((key, name, install_dir, provider, assignment))
    return games


def _canon_dir(p: Path | None) -> Path | None:
    if not p:
        return None
    try:
        p = p.expanduser().resolve(strict=False)
    except OSError:
        return None
    return p if p.is_dir() else None


TRAINER_FOLDER_NAMES = {
    "trainer", "trainers", "game trainer", "game trainers", "game-trainers",
    "cheats", "game cheats", "game-cheats",
}
LIBRARY_HINT_NAMES = {
    "games", "game", "steamlibrary", "steam library", "steam", "heroic",
    "lutris", "bottles", "gaming",
}


def _safe_child_dirs(base: Path) -> list[Path]:
    """List direct child directories without following symlinks.

    Portable discovery deliberately enumerates directory names only; it does not
    recursively crawl arbitrary mounts just because they exist.
    """
    try:
        return [Path(ent.path) for ent in os.scandir(base)
                if not ent.name.startswith(".") and ent.is_dir(follow_symlinks=False)]
    except (OSError, PermissionError):
        return []


def _named_trainer_dirs(base: Path | None) -> list[Path]:
    cp = _canon_dir(base)
    if cp is None:
        return []
    return [child for child in _safe_child_dirs(cp) if child.name.casefold() in TRAINER_FOLDER_NAMES]


def _mount_library_anchors() -> list[Path]:
    """Return shallow mount/library anchors suitable for *named-folder* probing.

    We never scan /mnt, /media or /run/media wholesale.  Only direct mount
    children (and one conventional Games/Steam/Heroic-style child beneath them)
    are considered as anchors from which a folder literally named Trainers/Cheats
    can be discovered.
    """
    user = os.environ.get("USER") or Path.home().name
    roots = [Path("/mnt"), Path("/media") / user, Path("/run/media") / user]
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        cp = _canon_dir(root)
        if cp is None:
            continue
        for child in _safe_child_dirs(cp):
            key = _canonical_path(child)
            if key not in seen:
                seen.add(key); out.append(child)
            for grand in _safe_child_dirs(child):
                if grand.name.casefold() not in LIBRARY_HINT_NAMES:
                    continue
                gkey = _canonical_path(grand)
                if gkey not in seen:
                    seen.add(gkey); out.append(grand)
    return out


def _install_ancestor_anchors(install: Path, levels: int = 6) -> list[Path]:
    """Return a bounded ancestor chain for a launcher-reported install folder."""
    out: list[Path] = []
    cur = install
    for _ in range(levels):
        parent = cur.parent
        if parent == cur:
            break
        out.append(parent)
        cur = parent
    return out


def discover_candidates(games):
    specs: dict[str, tuple[Path, int, int, set[str]]] = {}

    def add(kind: str, p: Path | None, depth: int, budget: int):
        cp = _canon_dir(p)
        if cp is None:
            return
        key = str(cp)
        old = specs.get(key)
        if old:
            specs[key] = (cp, max(depth, old[1]), max(budget, old[2]), old[3] | {kind})
        else:
            specs[key] = (cp, depth, budget, {kind})

    # Normal-user defaults first.  These are intentionally distro-agnostic and
    # respect freedesktop XDG user-directory remapping.
    add("GameWeld trainers", xdg_data_home() / "gameweld" / "trainers", 4, STANDARD_ROOT_BUDGET)
    add("Downloads", xdg_user_dir("DOWNLOAD"), 3, STANDARD_ROOT_BUDGET)
    add("Desktop", xdg_user_dir("DESKTOP"), 2, 4000)
    add("Documents", xdg_user_dir("DOCUMENTS"), 2, 4000)

    # Conventional dedicated folders under HOME are cheap and predictable.
    home = Path.home()
    for base in (home, home / "Games", home / "games"):
        for p in _named_trainer_dirs(base):
            add("Auto-discovered trainer folder", p, 4, CONFIG_ROOT_BUDGET)

    # Shallow removable/mounted-library probing: only folders explicitly named
    # Trainers/Cheats are admitted, never an unrestricted /mnt or /media crawl.
    for anchor in _mount_library_anchors():
        for p in _named_trainer_dirs(anchor):
            add("Auto-discovered mounted trainer folder", p, 4, CONFIG_ROOT_BUDGET)

    for p in configured_roots():
        add("User-added", p, 4, CONFIG_ROOT_BUDGET)

    assigned_candidates: list[Path] = []
    for _, _, install, provider, assignment in games:
        if assignment:
            ap = Path(assignment).expanduser().resolve(strict=False)
            try:
                if ap.is_file() and ap.suffix.lower() == ".exe" and ap.stat().st_size <= MAX_TRAINER_BYTES:
                    assigned_candidates.append(ap)
            except OSError:
                pass
        if not install:
            continue
        ip = _canon_dir(Path(install))
        if ip is None:
            continue
        add(f"{provider or 'Launcher'} library parent", ip.parent, 0, PARENT_ROOT_BUDGET)
        add(f"{provider or 'Launcher'} game folder", ip, 1, INSTALL_ROOT_BUDGET)
        # A user may keep one central Trainers folder beside/above several game
        # libraries (for example /mnt/games/Trainers while Steam lives below
        # /mnt/games/Steam/steamapps/common).  Probe only literal trainer-folder
        # names along the bounded launcher path; do not broaden the library scan.
        for anchor in _install_ancestor_anchors(ip):
            for p in _named_trainer_dirs(anchor):
                add(f"{provider or 'Launcher'} nearby trainer folder", p, 4, CONFIG_ROOT_BUDGET)

    ignored = ignored_paths()
    candidates: list[Path] = []
    seen_files: set[str] = set()
    scanned_roots: list[tuple[str, Path, int, int]] = []
    for _, (p, depth, budget, kinds) in specs.items():
        found, seen_count = walk_candidates(p, depth, budget)
        scanned_roots.append((", ".join(sorted(kinds)), p, depth, seen_count))
        for cand in found:
            s = str(cand)
            if s in ignored:
                continue
            if s not in seen_files:
                seen_files.add(s)
                candidates.append(cand)
    for cand in assigned_candidates:
        sc = str(cand)
        if sc in ignored:
            continue
        if sc not in seen_files:
            seen_files.add(sc)
            candidates.append(cand)
    candidates.sort(key=lambda p: str(p).lower())
    return candidates, scanned_roots


def _clean_field(s: object) -> str:
    return str(s).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def read_report() -> dict[str, object]:
    data: dict[str, object] = {"meta": {}, "roots": [], "trainers": [], "results": [], "rows": []}
    rf = report_file()
    if not rf.is_file():
        return data
    try:
        for raw in rf.read_text(errors="replace").splitlines():
            p = raw.split("\t")
            if not p:
                continue
            if p[0] == "META" and len(p) >= 3:
                data["meta"][p[1]] = p[2]  # type: ignore[index]
            elif p[0] == "ROOT" and len(p) >= 3:
                data["roots"].append(p[1:])  # type: ignore[union-attr]
            elif p[0] == "TRAINER" and len(p) >= 2:
                data["trainers"].append(p[1])  # type: ignore[union-attr]
            elif p[0] == "RESULT" and len(p) >= 6:
                data["results"].append(p[1:6])  # type: ignore[union-attr]
            elif p[0] == "ROW" and len(p) >= 8:
                row = p[1:17]
                while len(row) < 16:
                    row.append("")
                data["rows"].append(row)  # type: ignore[union-attr]
    except OSError:
        pass
    return data


def write_report(*, game_count: int, candidates: Iterable[Path | str], roots, results, rows) -> None:
    rf = report_file()
    try:
        rf.parent.mkdir(parents=True, exist_ok=True)
        trainers = sorted({_canonical_path(p) for p in candidates}, key=str.lower)
        with rf.open("w", encoding="utf-8") as f:
            f.write(f"META\tSCANNED_AT\t{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}\n")
            f.write(f"META\tGAMES\t{game_count}\n")
            f.write(f"META\tCANDIDATES\t{len(trainers)}\n")
            f.write(f"META\tIGNORED\t{len(ignored_paths())}\n")
            f.write(f"META\tPROFILE_DETECTOR_REVISION\t{PROFILE_DETECTOR_REVISION}\n")
            f.write(f"META\tDISCOVERY_REVISION\t{DISCOVERY_REVISION}\n")
            for root in roots:
                if len(root) == 4 and isinstance(root[1], Path):
                    kinds, path, depth, seen_count = root
                    f.write(f"ROOT\t{_clean_field(kinds)}\t{_clean_field(path)}\tdepth={depth}\tfiles={seen_count}\n")
                else:
                    f.write("ROOT\t" + "\t".join(_clean_field(x) for x in root) + "\n")
            for p in trainers:
                f.write(f"TRAINER\t{_clean_field(p)}\n")
            for r in results:
                f.write("RESULT\t" + "\t".join(_clean_field(x) for x in r[:5]) + "\n")
            for row in rows:
                enriched = _enrich_row_profile(row)
                f.write("ROW\t" + "\t".join(_clean_field(x) for x in enriched[:16]) + "\n")
    except OSError:
        pass


def recover_missing_assignments(games, candidates):
    """Recover moved trainer mappings conservatively.

    Recovery is automatic only when the old assignment is missing and exactly
    one discovered trainer has the exact same filename *and* still strongly
    matches the game title. The trainer file itself is never moved or deleted.
    """
    recovered: dict[str, tuple[str, str]] = {}
    out = []
    for key, name, install, provider, assignment in games:
        if not assignment:
            out.append((key, name, install, provider, assignment))
            continue
        old = Path(assignment).expanduser().resolve(strict=False)
        try:
            exists = old.is_file()
        except OSError:
            exists = False
        if exists:
            out.append((key, name, install, provider, str(old)))
            continue

        basename = old.name.casefold()
        exact = []
        for cand in candidates:
            if _is_provider_manager_candidate(cand):
                continue
            if cand.name.casefold() != basename:
                continue
            score, _ = score_candidate(name, cand)
            if score >= 92:
                exact.append(cand)
        exact = list(dict.fromkeys(exact))
        if len(exact) == 1 and replace_assignment(key, str(exact[0])):
            new_path = str(exact[0])
            recovered[key] = (str(old), new_path)
            out.append((key, name, install, provider, new_path))
        else:
            out.append((key, name, install, provider, str(old)))
    return out, recovered


def build_match_data(games, candidates, recovered=None):
    recovered = recovered or {}
    policy = version_policy()
    results = []
    rows = []
    referenced: set[str] = set()
    manager_paths = {str(c) for c in candidates if _is_provider_manager_candidate(c)}
    match_candidates = [c for c in candidates if str(c) not in manager_paths]

    # Test 15: exact normalized title ownership is authoritative for an
    # unassigned candidate. If "CONTROL Resonant" is installed alongside
    # "Control Ultimate Edition", the Resonant trainer must belong to the
    # exact Resonant title instead of being surfaced as an ambiguity for the
    # shorter normalized "control" title. Manual/existing assignments still
    # win and are never rewritten here.
    exact_owners: dict[str, set[str]] = {}
    for key, name, _, _, _ in games:
        for c in match_candidates:
            score, _ = score_candidate(name, c)
            if score == 100:
                exact_owners.setdefault(str(c), set()).add(key)

    # A single trainer can strongly match multiple installed titles after
    # normalization. Equal top-score ownership remains explicit/ambiguous only
    # when there really are multiple equally exact/strong owners.
    ownership: dict[str, list[tuple[int, str, str]]] = {}
    for key, name, _, _, _ in games:
        for c in match_candidates:
            score, _ = score_candidate(name, c)
            if score >= 92:
                ownership.setdefault(str(c), []).append((score, key, name))
    conflicted: set[str] = set()
    for path, owners in ownership.items():
        owners.sort(reverse=True, key=lambda x: x[0])
        if len(owners) > 1 and owners[0][0] == owners[1][0]:
            conflicted.add(path)

    for key, name, _, _, assignment in games:
        assigned_path: Path | None = None
        if assignment:
            ap = Path(assignment).expanduser().resolve(strict=False)
            try:
                assigned_ok = ap.is_file() and ap.suffix.lower() == ".exe"
            except OSError:
                assigned_ok = False
            if assigned_ok:
                assigned_path = ap
                score, title_reason = score_candidate(name, ap)
                health = "Recovered" if key in recovered else "Valid"
                reason = "Recovered moved trainer assignment" if key in recovered else "Existing readable trainer assignment"
                if score:
                    reason += f"; title check: {title_reason}"
                version_label, assigned_version = trainer_version_info(ap)

                strong_alternatives = []
                for c in match_candidates:
                    if str(c) == str(ap) or str(c) in conflicted:
                        continue
                    cscore, creason = score_candidate(name, c)
                    if cscore < 92:
                        continue
                    cversion_label, cversion_key = trainer_version_info(c)
                    strong_alternatives.append((cscore, c, creason, cversion_label, cversion_key))

                # Explicit opt-in only: Prefer newest may replace an existing
                # assignment when the current and every strong alternative have
                # comparable versions and exactly one trainer is uniquely newest.
                if policy == "prefer-newest" and strong_alternatives:
                    comparable = [(score, ap, title_reason, version_label, assigned_version)] + strong_alternatives
                    if all(x[4] is not None for x in comparable):
                        highest = max(x[4] for x in comparable)
                        newest = [x for x in comparable if x[4] == highest]
                        if len(newest) == 1 and newest[0][1] != ap:
                            chosen = newest[0]
                            if replace_assignment(key, str(chosen[1])):
                                ap = chosen[1]
                                score = chosen[0]
                                title_reason = chosen[2]
                                version_label = chosen[3]
                                assigned_version = chosen[4]
                                health = "Updated"
                                reason = f"Version policy Prefer newest selected a uniquely newer trainer; title check: {title_reason}"

                results.append((key, name, "ASSIGNED", score, ap))
                referenced.add(str(ap))
                rows.append(("ASSIGNED", key, name, score if score else "", reason, ap, ap.parent, version_label, health))

                # Existing/manual assignments always win. Still surface other
                # strong versions for this same game as alternatives so the user
                # can explicitly switch without GameWeld replacing anything,
                # unless Prefer newest already made an explicit policy update.
                for c in match_candidates:
                    if str(c) == str(ap) or str(c) in conflicted:
                        continue
                    cscore, creason = score_candidate(name, c)
                    if cscore < 92:
                        continue
                    version_label, _ = trainer_version_info(c)
                    reason2 = f"Alternative trainer for assigned game; version policy is {policy}. {creason}"
                    referenced.add(str(c))
                    rows.append(("ALTERNATE", key, name, cscore, reason2, c, c.parent, version_label, "Available"))
                continue

            # Keep stale mappings visible instead of silently pretending the
            # game is unassigned. A full/selected scan may recover this row when
            # the same filename is found uniquely in a known location.
            version_label, _ = trainer_version_info(ap)
            results.append((key, name, "MISSING", 0, ap))
            rows.append(("MISSING", key, name, "", "Assigned trainer file is missing. Rescan can recover it automatically only when the exact filename is found uniquely.", ap, ap.parent, version_label, "Missing"))
            for c in match_candidates:
                if str(c) in conflicted:
                    continue
                cscore, creason = score_candidate(name, c)
                if cscore < 92:
                    continue
                cversion_label, _ = trainer_version_info(c)
                referenced.add(str(c))
                rows.append(("ALTERNATE", key, name, cscore, "Possible replacement for missing assignment; choose explicitly. " + creason, c, c.parent, cversion_label, "Available"))
            continue

        ranked = []
        for c in match_candidates:
            owners = exact_owners.get(str(c), set())
            if owners and key not in owners:
                # Another installed game is the exact normalized owner of this
                # trainer. Do not manufacture a lower-confidence ambiguity for
                # this game merely because their titles overlap.
                continue
            score, reason = score_candidate(name, c)
            if score >= 80:
                version_label, version_key = trainer_version_info(c)
                ranked.append((score, str(c).lower(), c, reason, version_label, version_key))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        if not ranked:
            results.append((key, name, "NONE", 0, ""))
            continue

        best_score = ranked[0][0]
        best_tied = [x for x in ranked if x[0] == best_score]

        # If the best candidate itself equally fits another installed game, do
        # not auto-assign it. Keep all plausible rows visible for explicit choice.
        if best_score >= 92 and any(str(x[2]) in conflicted for x in best_tied):
            opts = ranked[:5]
            results.append((key, name, "AMBIG", best_score, " | ".join(str(x[2]) for x in opts)))
            for score, _, cand, reason, version_label, _ in opts:
                extra = "Strong title match also fits another installed game; choose explicitly. " + reason if str(cand) in conflicted else reason
                referenced.add(str(cand))
                rows.append(("AMBIG", key, name, score, extra, cand, cand.parent, version_label, "Available"))
            continue

        if best_score >= 92 and len(best_tied) > 1:
            # Multiple equally strong trainer filenames for one game are a
            # version set only when every contender exposes comparable semantic
            # version metadata and exactly one has the highest version.
            versioned = [x for x in best_tied if x[5] is not None]
            if policy == "prefer-newest" and len(versioned) == len(best_tied):
                highest = max(x[5] for x in versioned)
                newest = [x for x in versioned if x[5] == highest]
                if len(newest) == 1:
                    chosen = newest[0]
                    score, _, best, best_reason, version_label, _ = chosen
                    results.append((key, name, "MATCH", score, best))
                    referenced.add(str(best))
                    rows.append(("MATCH", key, name, score, f"{best_reason}; version policy Prefer newest selected the unique newest trainer", best, best.parent, version_label, "Available"))
                    for alt in best_tied:
                        if alt is chosen:
                            continue
                        ascore, _, cand, areason, aversion, _ = alt
                        referenced.add(str(cand))
                        rows.append(("ALTERNATE", key, name, ascore, f"Older/alternate trainer version; {areason}", cand, cand.parent, aversion, "Available"))
                    continue

            # Equal strong matches without a unique comparable newest version are
            # intentionally ambiguous. Ask me is the default; Keep current has no
            # current choice for an unassigned game. Filename mtime/order is never
            # used to guess.
            opts = ranked[:5]
            results.append((key, name, "AMBIG", best_score, " | ".join(str(x[2]) for x in opts)))
            for score, _, cand, reason, version_label, _ in opts:
                referenced.add(str(cand))
                rows.append(("AMBIG", key, name, score, f"Multiple equally strong trainer versions; version policy is {policy}; choose explicitly. " + reason, cand, cand.parent, version_label, "Available"))
            continue

        best_score, _, best, best_reason, version_label, _ = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else -1
        if best_score >= 92 and (len(ranked) == 1 or second_score < best_score - 7):
            results.append((key, name, "MATCH", best_score, best))
            referenced.add(str(best))
            rows.append(("MATCH", key, name, best_score, best_reason, best, best.parent, version_label, "Available"))
        else:
            opts = ranked[:5]
            results.append((key, name, "AMBIG", best_score, " | ".join(str(x[2]) for x in opts)))
            for score, _, cand, reason, version_label, _ in opts:
                referenced.add(str(cand))
                rows.append(("AMBIG", key, name, score, reason, cand, cand.parent, version_label, "Available"))

    for cand in candidates:
        if str(cand) not in referenced:
            version_label, _ = trainer_version_info(cand)
            if str(cand) in manager_paths:
                rows.append(("MANAGER", "", "", 0, "Recognized multi-game trainer manager; GameWeld deliberately does not title-match or auto-assign manager applications to individual games.", cand, cand.parent, version_label, "Available"))
            else:
                rows.append(("UNMATCHED", "", "", 0, "No plausible high-confidence game-title match", cand, cand.parent, version_label, "Available"))
    return results, rows


def merge_report_data(games, candidates, roots, results, rows):
    old = read_report()
    old_meta = old["meta"]  # type: ignore[assignment]
    keys = {g[0] for g in games}

    old_trainers = [p for p in old["trainers"] if Path(p).is_file()]  # type: ignore[index]
    merged_candidates = list(dict.fromkeys([*old_trainers, *(str(p) for p in candidates)]))

    root_seen: set[tuple[str, str]] = set()
    merged_roots = []
    for r in old["roots"]:  # type: ignore[index]
        if len(r) >= 2:
            k = (r[0], r[1])
            if k not in root_seen:
                root_seen.add(k); merged_roots.append(r)
    for kinds, path, depth, seen_count in roots:
        rr = [str(kinds), str(path), f"depth={depth}", f"files={seen_count}"]
        k = (rr[0], rr[1])
        if k not in root_seen:
            root_seen.add(k); merged_roots.append(rr)

    merged_results = [r for r in old["results"] if r and r[0] not in keys]  # type: ignore[index]
    merged_results.extend(results)

    merged_rows = []
    for r in old["rows"]:  # type: ignore[index]
        if len(r) < 8:
            continue
        # Replace rows belonging to the rescanned game. Unmatched rows are
        # rebuilt below from the final candidate/reference set.
        if r[0] in {"UNMATCHED", "MANAGER"}:
            continue
        if r[1] and r[1] in keys:
            continue
        merged_rows.append(r)
    merged_rows.extend(r for r in rows if r[0] != "UNMATCHED")

    # Drop duplicate match/ambiguity rows by state/key/path.
    dedup = []
    seen = set()
    for r in merged_rows:
        if len(r) < 8:
            continue
        r = list(r)
        while len(r) < 16:
            r.append("")
        k = (str(r[0]), str(r[1]), _canonical_path(r[5]))
        if k in seen:
            continue
        seen.add(k); dedup.append(r)

    # Rebuild unmatched trainers from the merged candidate set so a trainer
    # cannot appear in both Matched and Unmatched after a selected-game rescan.
    referenced = {_canonical_path(r[5]) for r in dedup if len(r) >= 8 and r[0] in {"ASSIGNED", "MATCH", "ALTERNATE", "AMBIG", "MANAGER"}}
    ignored = ignored_paths()
    for p in merged_candidates:
        cp = _canonical_path(p)
        if cp in ignored or cp in referenced:
            continue
        version_label, _ = trainer_version_info(cp)
        pp = Path(cp)
        if _is_provider_manager_candidate(pp):
            dedup.append(("MANAGER", "", "", 0, "Recognized multi-game trainer manager; GameWeld deliberately does not title-match or auto-assign manager applications to individual games.", cp, str(pp.parent), version_label, "Available"))
        else:
            dedup.append(("UNMATCHED", "", "", 0, "No plausible high-confidence game-title match", cp, str(pp.parent), version_label, "Available"))

    try:
        old_count = int(old_meta.get("GAMES", "0"))  # type: ignore[union-attr]
    except (TypeError, ValueError):
        old_count = 0
    return max(old_count, len(games)), merged_candidates, merged_roots, merged_results, dedup


def auto_match(manifest: Path, merge: bool = False) -> int:
    games = parse_manifest(manifest)
    if not games:
        return 0
    candidates, roots = discover_candidates(games)
    games, recovered = recover_missing_assignments(games, candidates)
    results, rows = build_match_data(games, candidates, recovered=recovered)

    for key, name, state, score, detail in results:
        if state == "ASSIGNED":
            print(f"ASSIGNED\t{key}\t{score}\t{detail}")
        elif state == "MATCH":
            print(f"MATCH\t{key}\t{score}\t{detail}")
        elif state == "AMBIG":
            print(f"AMBIG\t{key}\t{score}\t{detail}")
        elif state == "MISSING":
            print(f"MISSING\t{key}\t0\t{detail}")
        else:
            print(f"NONE\t{key}")

    game_count = len(games)
    out_candidates: Iterable[Path | str] = candidates
    out_roots = roots
    out_results = results
    out_rows = rows
    if merge:
        game_count, out_candidates, out_roots, out_results, out_rows = merge_report_data(
            games, candidates, roots, results, rows
        )

    write_report(
        game_count=game_count,
        candidates=out_candidates,
        roots=out_roots,
        results=out_results,
        rows=out_rows,
    )
    print(f"STATS\t{len(candidates)}\t{len(roots)}")
    return 0


def _active_rows(data):
    ignored = ignored_paths()
    out = []
    for r in data["rows"]:  # type: ignore[index]
        if len(r) < 8:
            continue
        if _canonical_path(r[5]) in ignored:
            continue
        out.append(_enrich_row_profile(r))
    return out


def _score_int(value: object) -> int:
    try:
        return int(str(value).strip() or "0")
    except ValueError:
        return 0


READINESS_FILTERS = {"all", "managed", "steam", "heroic-existing", "explicit", "unassigned", "manual", "advisory", "attention"}


def _row_matches_query(row, query: str) -> bool:
    if not query:
        return True
    q = query.casefold()
    policy, launch, code = _row_launch_readiness(row)
    hay = " ".join([*(str(x) for x in row), policy, launch, code]).casefold()
    return q in hay


def _row_matches_readiness(row, readiness: str) -> bool:
    """Filter one cached Trainer Library row by effective compatibility readiness.

    This is intentionally derived from the same launch-preview/policy functions as
    Test 8.  It does not re-profile a launch differently and never mutates policy,
    assignments, or runtime settings.
    """
    readiness = (readiness or "all").strip().lower()
    if readiness not in READINESS_FILTERS or readiness == "all":
        return True
    state = str(row[0] if len(row) > 0 else "")
    path = str(row[5] if len(row) > 5 else "")
    enriched = _enrich_row_profile(row)
    profile = str(enriched[9] if len(enriched) > 9 else "")
    confidence = str(enriched[13] if len(enriched) > 13 else "")
    _policy, _label, code = _row_launch_readiness(row)
    if readiness == "managed":
        return code == "heroic-fling-managed"
    if readiness == "steam":
        return code == "steam-live-session"
    if readiness == "heroic-existing":
        return code in {"heroic-inherit", "heroic-inherit-auto-disabled"}
    if readiness == "explicit":
        return code == "heroic-explicit-compat"
    if readiness == "unassigned":
        return code == "unassigned"
    if readiness == "manual":
        return bool(path) and trainer_profile_policy(path) != "auto"
    if readiness == "advisory":
        recipe = trainer_compatibility_recipe(path) if path else ()
        return len(recipe) <= 4 or str(recipe[4]) != "Validated"
    if readiness == "attention":
        return state in {"MISSING", "AMBIG", "UNMATCHED"}
    return True


def _sort_rows(rows, sort_by: str):
    state_order = {"MISSING": 0, "AMBIG": 1, "ASSIGNED": 2, "MATCH": 3, "ALTERNATE": 4, "MANAGER": 5, "UNMATCHED": 6}
    if sort_by == "game":
        return sorted(rows, key=lambda r: (str(r[2]).casefold(), str(r[5]).casefold()))
    if sort_by == "confidence":
        return sorted(rows, key=lambda r: (-_score_int(r[3]), str(r[2]).casefold(), str(r[5]).casefold()))
    if sort_by == "version":
        def vk(r):
            _label, parsed = trainer_version_info(r[5])
            # Put real versions first and sort newest first by negating components.
            parts = parsed or ()
            padded = tuple(list(parts) + [0] * (5 - len(parts)))[:5]
            return (0 if parsed else 1, tuple(-x for x in padded), str(r[2]).casefold(), str(r[5]).casefold())
        return sorted(rows, key=vk)
    if sort_by == "trainer":
        return sorted(rows, key=lambda r: (Path(str(r[5])).name.casefold(), str(r[2]).casefold()))
    if sort_by == "profile":
        return sorted(rows, key=lambda r: (str(r[9] if len(r) > 9 else "").casefold(), str(r[2]).casefold(), str(r[5]).casefold()))
    if sort_by == "policy":
        return sorted(rows, key=lambda r: (_row_launch_readiness(r)[0].casefold(), str(r[2]).casefold(), str(r[5]).casefold()))
    if sort_by == "launch":
        return sorted(rows, key=lambda r: (_row_launch_readiness(r)[1].casefold(), str(r[2]).casefold(), str(r[5]).casefold()))
    return sorted(rows, key=lambda r: (state_order.get(str(r[0]), 99), str(r[2]).casefold(), -_score_int(r[3]), str(r[5]).casefold()))


def print_rows(query: str = "", sort_by: str = "status", attention: bool = False, readiness: str = "all") -> int:
    data = read_report()
    rows = _active_rows(data)
    if attention:
        rows = [r for r in rows if r[0] in {"MISSING", "AMBIG", "UNMATCHED"}]
    rows = [r for r in rows if _row_matches_readiness(r, readiness)]
    rows = [r for r in rows if _row_matches_query(r, query)]
    rows = _sort_rows(rows, sort_by)
    for r in rows:
        # Gtk-side parsing uses a compact delimiter parser. Emit a visible
        # placeholder for empty table cells so consecutive tabs cannot collapse
        # columns for unmatched/manual rows. The persisted TSV keeps real empties.
        fields = [(_clean_field(x) if str(x) else "—") for x in _enrich_row_profile(r)[:16]]
        policy, launch, _plan_code = _row_launch_readiness(r)
        fields.extend([_clean_field(policy or "Automatic"), _clean_field(launch or "No launch target assigned")])
        print("ROW\t" + "\t".join(fields))
    return 0


def print_audit(query: str = "") -> int:
    data = read_report()
    rows = _active_rows(data)
    rows = [r for r in rows if _row_matches_query(r, query)]
    c = _compatibility_audit(rows)
    order = ("total", "managed", "steam", "inherit", "explicit", "unassigned", "manual", "advisory", "attention")
    print("AUDIT\t" + "\t".join(str(c[k]) for k in order))
    return 0


def print_game_rows(query: str = "", sort_by: str = "status") -> int:
    data = read_report()
    results = data["results"]  # type: ignore[assignment]
    issue_rows = []
    for r in results:
        if len(r) < 5:
            continue
        key, name, state, score, detail = r[:5]
        if state not in {"MISSING", "AMBIG", "NONE"}:
            continue
        shown = {"MISSING": "Missing", "AMBIG": "Ambiguous", "NONE": "No trainer"}.get(state, state)
        issue = (
            "Assigned trainer file is missing" if state == "MISSING" else
            "Multiple plausible trainers need a choice" if state == "AMBIG" else
            "No plausible trainer match found in the last scan"
        )
        row = [state, key, name, score, issue, detail]
        if not _row_matches_query(row, query):
            continue
        issue_rows.append(row)
    state_order = {"MISSING": 0, "AMBIG": 1, "NONE": 2}
    if sort_by == "confidence":
        issue_rows.sort(key=lambda r: (-_score_int(r[3]), str(r[2]).casefold()))
    else:
        issue_rows.sort(key=lambda r: ((str(r[2]).casefold(),) if sort_by == "game" else (state_order.get(str(r[0]), 99), str(r[2]).casefold())))
    for state, key, name, score, issue, detail in issue_rows:
        fields = [state, key, name, score if str(score) else "0", issue, detail or "—"]
        print("GAME\t" + "\t".join(_clean_field(x) for x in fields))
    return 0



def _profile_summary(row) -> str:
    r = _enrich_row_profile(row)
    profile, arch, runtime, elevation, confidence = r[9], r[10], r[11], r[12], r[13]
    return f"{profile} ({confidence}) • {arch} • {runtime} • {elevation}"


def _profile_policy_summary(row) -> str:
    r = _enrich_row_profile(row)
    path = r[5] if len(r) > 5 else ""
    return trainer_profile_policy_label(path) if path else "Automatic"


def print_report() -> int:
    rf = report_file()
    if not rf.is_file():
        print("No Trainer Library scan has completed yet.\n\nPress Scan / Auto-Match Trainers to create the first report.")
        return 0

    data = read_report()
    meta = data["meta"]  # type: ignore[assignment]
    roots = data["roots"]  # type: ignore[assignment]
    trainers = [p for p in data["trainers"] if _canonical_path(p) not in ignored_paths()]  # type: ignore[index]
    results = data["results"]  # type: ignore[assignment]
    rows = _active_rows(data)

    print("TRAINER LIBRARY — LAST SCAN")
    print(f"Scanned: {meta.get('SCANNED_AT', 'unknown')}")  # type: ignore[union-attr]
    print(f"Games represented in report: {meta.get('GAMES', '0')}")  # type: ignore[union-attr]
    print(f"Trainer executables discovered: {len(trainers)}")
    print(f"Ignored trainer executables: {len(ignored_paths())}")
    print(f"Duplicate-version policy: {version_policy()}")

    assigned = [r for r in rows if r[0] == "ASSIGNED"]
    matches = [r for r in rows if r[0] == "MATCH"]
    alternatives = [r for r in rows if r[0] == "ALTERNATE"]
    ambig = [r for r in rows if r[0] == "AMBIG"]
    managers = [r for r in rows if r[0] == "MANAGER"]
    unmatched = [r for r in rows if r[0] == "UNMATCHED"]
    none = [r for r in results if len(r) >= 3 and r[2] == "NONE"]

    print("\nASSIGNED / MATCHED")
    if assigned:
        for r in assigned:
            _, _, name, score, reason, path, source, version, health = r[:9]
            score_text = f"{score}%" if str(score).strip() else "manual"
            print(f"  ● {name} — {score_text}{(' — ' + version) if version else ''} — health: {health or 'Valid'} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}\n    Source: {source}")
    if matches:
        for r in matches:
            _, _, name, score, reason, path, source, version, _ = r[:9]
            print(f"  ✓ {name} — {score}%{(' — ' + version) if version else ''} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}\n    Source: {source}")
    if not assigned and not matches:
        print("  No existing assignments or high-confidence matches recorded.")

    print("\nALTERNATIVE VERSIONS")
    if alternatives:
        for r in alternatives:
            _, _, name, score, reason, path, source, version, _ = r[:9]
            print(f"  ↳ {name} — {score}%{(' — ' + version) if version else ''} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}\n    Source: {source}")
    else:
        print("  No alternate trainer versions recorded.")

    print("\nAMBIGUOUS")
    if ambig:
        for r in ambig:
            _, _, name, score, reason, path, source, version, _ = r[:9]
            print(f"  ? {name} — {score}%{(' — ' + version) if version else ''} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}\n    Source: {source}")
    else:
        print("  No ambiguous trainer matches.")

    print("\nTRAINER MANAGERS")
    if managers:
        for r in managers:
            _, _, _, _, reason, path, source, version, _ = r[:9]
            print(f"  ◈ {Path(path).name}{(' — ' + version) if version else ''} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Source: {source}")
    else:
        print("  No recognized multi-game trainer managers recorded.")

    print("\nUNMATCHED TRAINERS")
    if unmatched:
        for r in unmatched:
            _, _, _, _, reason, path, source, version, _ = r[:9]
            print(f"  · {Path(path).name}{(' — ' + version) if version else ''} — {reason}\n    {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}\n    Source: {source}")
    else:
        print("  No unmatched trainer executables.")

    if none:
        print(f"\n{len(none)} game(s) had no plausible trainer match.")

    missing = [r for r in rows if r[0] == "MISSING"]
    if missing:
        print("\nHEALTH ISSUES")
        for r in missing:
            _, _, name, _, reason, path, _, _, health = r[:9]
            print(f"  ! {name} — {health or 'Missing'} — {reason}\n    Last assigned path: {path}\n    Compatibility: {_profile_summary(r)}\n    Compatibility recipe: {compatibility_recipe_summary(path)}\n    Launch policy: {_profile_policy_summary(r)}\n    Effective next launch: {_launch_plan_summary(r)}")

    print("\nSEARCH LOCATIONS")
    if roots:
        game_roots = [r for r in roots if r and "game folder" in r[0].lower()]
        other_roots = [r for r in roots if not r or "game folder" not in r[0].lower()]
        for r in other_roots:
            if len(r) < 2:
                continue
            extra = " • ".join(r[2:]) if len(r) > 2 else ""
            print(f"  • {r[0]}: {r[1]}{(' • ' + extra) if extra else ''}")
        if game_roots:
            print(f"  • {len(game_roots)} individual game install folder(s) were also scanned shallowly.")
    else:
        print("  No scan roots recorded.")

    print("\nCompatibility Engine v2 keeps detection separate from action: only the already-validated FLiNG recipe may alter Heroic runtime selection automatically in 0.5.0 Test 13; Overview exposes the selected game Launch With surface for assigned/local trainers, the existing Steam WeMod provider, Aurora, Cheat Evolution, and user-chosen trainer EXEs. Manager applications remain unassigned and join only validated live game sessions. Automatic matching is conservative. Fully resolved Windows Steam non-Steam shortcuts use a visible-game readiness barrier before trainer handoff: GameWeld validates the exact resolved compatdata/Proton session, waits for the configured Windows game executable, then waits for a mapped X11/XWayland game window when available (or a conservative continuous-process grace period as fallback) before using Proton runinprefix in that same prefix. Native/script shortcuts without Proton evidence remain blocked. Ordinary Steam live-session handoff and the validated Heroic managed FLiNG path remain unchanged. The default duplicate-version policy is Ask me. Missing assignments are recovered only when the exact trainer filename is found uniquely in a known scan location. Trainer files are never deleted by Library maintenance.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    am = sp.add_parser("auto-match")
    am.add_argument("--manifest", required=True, type=Path)
    am.add_argument("--merge-report", action="store_true")
    ar = sp.add_parser("add-root")
    ar.add_argument("path")
    ig = sp.add_parser("ignore")
    ig.add_argument("path")
    sp.add_parser("clear-ignored")
    pol = sp.add_parser("set-policy")
    pol.add_argument("value", choices=sorted(VALID_POLICIES))
    sp.add_parser("policy")
    sp.add_parser("prune-missing")
    sp.add_parser("list-roots")
    sp.add_parser("report")
    rows = sp.add_parser("rows")
    rows.add_argument("--query", default="")
    rows.add_argument("--sort", choices=["status", "game", "confidence", "version", "trainer", "profile", "policy", "launch"], default="status")
    rows.add_argument("--attention", action="store_true")
    rows.add_argument("--readiness", choices=sorted(READINESS_FILTERS), default="all")
    audit = sp.add_parser("audit")
    audit.add_argument("--query", default="")
    prof = sp.add_parser("profile")
    prof.add_argument("path")
    recipe = sp.add_parser("profile-recipe")
    recipe.add_argument("path")
    evidence = sp.add_parser("profile-evidence")
    evidence.add_argument("path")
    launch_pol = sp.add_parser("launch-policy")
    launch_pol.add_argument("path")
    launch_plan = sp.add_parser("launch-plan")
    launch_plan.add_argument("path")
    launch_plan.add_argument("backend", choices=["steam", "steam-shortcut", "steam-shortcut-resolved", "steam-shortcut-native", "heroic", "unassigned"])
    prof_pol = sp.add_parser("profile-policy")
    prof_pol.add_argument("path")
    set_prof_pol = sp.add_parser("set-profile-policy")
    set_prof_pol.add_argument("path")
    set_prof_pol.add_argument("mode", choices=sorted(PROFILE_POLICY_MODES))
    games = sp.add_parser("game-rows")
    games.add_argument("--query", default="")
    games.add_argument("--sort", choices=["status", "game", "confidence"], default="status")
    args = ap.parse_args()
    if args.cmd == "auto-match":
        return auto_match(args.manifest, merge=args.merge_report)
    if args.cmd == "add-root":
        return add_root(args.path)
    if args.cmd == "ignore":
        return ignore_path(args.path)
    if args.cmd == "clear-ignored":
        return clear_ignored()
    if args.cmd == "set-policy":
        return set_version_policy(args.value)
    if args.cmd == "policy":
        print(version_policy())
        return 0
    if args.cmd == "prune-missing":
        return prune_missing_assignments()
    if args.cmd == "list-roots":
        for p in configured_roots():
            print(p)
        return 0
    if args.cmd == "report":
        return print_report()
    if args.cmd == "rows":
        return print_rows(args.query, args.sort, args.attention, args.readiness)
    if args.cmd == "audit":
        return print_audit(args.query)
    if args.cmd == "profile":
        fields = analyze_trainer_profile(args.path)
        print("PROFILE\t" + "\t".join(_clean_field(x) for x in fields))
        return 0
    if args.cmd == "profile-recipe":
        fields = trainer_compatibility_recipe(args.path)
        print("COMPAT_RECIPE\t" + "\t".join(_clean_field(x) for x in fields))
        return 0
    if args.cmd == "profile-evidence":
        fields = trainer_profile_evidence(args.path)
        print("PROFILE_EVIDENCE\t" + "\t".join(_clean_field(x) for x in fields))
        return 0
    if args.cmd == "launch-policy":
        fields = trainer_launch_policy(args.path)
        print("POLICY\t" + "\t".join(_clean_field(x) for x in fields))
        return 0
    if args.cmd == "launch-plan":
        fields = trainer_effective_launch_plan(args.path, args.backend)
        print("LAUNCH_PLAN\t" + "\t".join(_clean_field(x) for x in fields))
        return 0
    if args.cmd == "profile-policy":
        mode = trainer_profile_policy(args.path)
        print("PROFILE_POLICY\t" + mode + "\t" + _clean_field(trainer_profile_policy_label(args.path)))
        return 0
    if args.cmd == "set-profile-policy":
        return set_trainer_profile_policy(args.path, args.mode)
    if args.cmd == "game-rows":
        return print_game_rows(args.query, args.sort)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
