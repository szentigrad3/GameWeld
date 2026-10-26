#!/usr/bin/env python3
"""GameWeld prepared .NET/WeMod prefix import REHEARSAL (never live game install).

DeckCheatz keeps a GE-Proton-matched prepared prefix with .NET dependencies.
This helper identifies a cached, verified *staged* archive, checks its
compatibility with ONE selected game's existing Proton version, and builds an
ISOLATED merged candidate preserving existing game data in the original.

The candidate is an offline test artifact, NOT an installed game prefix.
No Proton/Wine/game launch, Steam Launch Options/Compatibility change, DLL
injection, restore or live prefix replacement occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

APP_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
GE_VERSION = re.compile(r"ge[-_ ]?proton[-_ ]?(\d+)[._-](\d+)", re.I)
COPY_LIMIT = 60 * 1024**3
RESERVE = 512 * 1024**2
CHUNK = 1024 * 1024
PROTECTED_ANCESTORS = {"steamapps", "compatdata"}


class ImportBlocked(ValueError):
    pass


def private_root(root: Path, name: str) -> Path:
    if (not root.is_absolute() or root.name != name or
            root.parent.name != "gameweld" or root.is_symlink() or
            any(x.is_symlink() for x in root.parents) or
            any(x.lower() in PROTECTED_ANCESTORS for x in root.parts)):
        raise ImportBlocked("Only GameWeld's private cache/state directories are accepted")
    if root.exists() and (
        not root.is_dir() or (stat.S_IMODE(root.stat().st_mode) & 0o077)
    ):
        raise ImportBlocked("GameWeld private root must be a private 0700 directory")
    return root


def version_parts(value: str) -> tuple[int, int] | None:
    result = GE_VERSION.search(value)
    return (int(result.group(1)), int(result.group(2))) if result else None


def load_version(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ImportBlocked("Proton version metadata missing or unsafe")
    return path.read_text(encoding="utf-8", errors="replace").strip()


def steam_game(appid: str, install: Path) -> Path:
    if not APP_ID.fullmatch(appid):
        raise ImportBlocked("Select a valid numeric Steam AppID")
    if (not install.is_absolute() or install.is_symlink() or
            not install.is_dir() or install.parent.name != "common" or
            install.parent.parent.name != "steamapps"):
        raise ImportBlocked("Select a real steamapps/common game directory")
    steamapps = install.parent.parent
    manifest = steamapps / f"appmanifest_{appid}.acf"
    if manifest.is_symlink() or not manifest.is_file():
        raise ImportBlocked("Matching Steam AppID manifest not found in this library")
    compat = steamapps / "compatdata" / appid
    if compat.is_symlink() or not compat.is_dir():
        raise ImportBlocked("Selected game Proton compatdata directory missing")
    pfx = compat / "pfx"
    if pfx.is_symlink() or not pfx.is_dir():
        raise ImportBlocked("Selected game has no usable Proton pfx")
    return compat


def files_and_bytes(directory: Path) -> tuple[int, int]:
    n = total = 0
    for base, dirs, files in os.walk(directory, followlinks=False):
        for filename in files:
            item = Path(base) / filename
            entry = item.lstat()
            if stat.S_ISREG(entry.st_mode):
                total += entry.st_size
            elif not stat.S_ISLNK(entry.st_mode):
                raise ImportBlocked("Unsafe special file in game or staged environment")
            n += 1
            if n > 200_000 or total > COPY_LIMIT:
                raise ImportBlocked("Game or prepared prefix exceeds safe cloning limits")
        for folder in dirs:
            if not (Path(base) / folder).is_symlink():
                continue
            n += 1
    return n, total


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(CHUNK), b""):
            digest.update(part)
    return digest.hexdigest()


def staged_prefix(stage_dir: Path, cache_root: Path) -> tuple[Path, dict]:
    root = private_root(cache_root, "prepared-wemod")
    stages = root / "staging"
    if (stage_dir.parent != stages or not DIGEST.fullmatch(stage_dir.name) or
            stages.is_symlink() or stage_dir.is_symlink() or
            not stage_dir.is_dir()):
        raise ImportBlocked("Select a content-addressed GameWeld staged archive")
    manifest_file = stage_dir / "manifest.json"
    if (manifest_file.is_symlink() or not manifest_file.is_file() or
            manifest_file.stat().st_size > 16 * 1024**2):
        raise ImportBlocked("Staged manifest is missing or unsafe")
    try:
        metadata = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ImportBlocked("Staged manifest is invalid") from exc
    if (not isinstance(metadata, dict) or
            metadata.get("source_archive_sha256") != stage_dir.name or
            metadata.get("installed_to_game") is not False):
        raise ImportBlocked("Staged archive identity/installation state is invalid")
    payload = stage_dir / "payload"
    if not payload.is_dir() or payload.is_symlink():
        raise ImportBlocked("Staged archive has no safe payload")
    # DeckCheatz package_prefix archives the compatdata root, which contains
    # 'version' and 'pfx' including .NET/registry assets and marker.
    if not (payload / "pfx").is_dir() or (payload / "pfx").is_symlink():
        raise ImportBlocked("Archive is not a full Proton compatdata template (missing pfx)")
    marker = payload / "pfx" / ".wemod_installer"
    if marker.is_symlink() or not marker.is_file():
        raise ImportBlocked("Staged template lacks DeckCheatz .wemod_installer marker")
    return payload, metadata


def manifest_preflight(payload: Path, metadata: dict) -> tuple[int, int]:
    files = metadata.get("files")
    if not isinstance(files, list) or len(files) > 40_000:
        raise ImportBlocked("Invalid staged file manifest")
    total = 0
    seen: set[str] = set()
    for f in files:
        if not isinstance(f, dict):
            raise ImportBlocked("Invalid staged manifest member")
        name, digest, size = f.get("path"), f.get("sha256"), f.get("bytes")
        if (not isinstance(name, str) or not name or
                name.startswith("/") or "\\" in name or
                any(p in (".", "..", "") for p in name.split("/")) or
                name in seen or not isinstance(digest, str) or
                not DIGEST.fullmatch(digest) or
                type(size) is not int or size < 0):
            raise ImportBlocked("Invalid staged manifest path/digest/size")
        seen.add(name)
        file = payload.joinpath(*name.split("/"))
        if (file.is_symlink() or not file.is_file() or
                file.stat().st_size != size or sha256(file) != digest):
            raise ImportBlocked("Staged file altered since extraction; aborting")
        total += size
        if total > COPY_LIMIT:
            raise ImportBlocked("Staged file total exceeds safety quota")
    # Ignore archive directories but reject untracked, unexpected files.
    file_count, bytes_count = files_and_bytes(payload)
    if file_count != len(files) or bytes_count != total:
        raise ImportBlocked("Staged payload has untracked or missing entries")
    return len(files), total


def preview(appid: str, install: Path, stage: Path, *,
            cache_root: Path, state_root: Path) -> tuple[dict, dict]:
    game = steam_game(appid, install)
    private_root(state_root, "prefix-imports")
    payload, metadata = staged_prefix(stage, cache_root)
    actual = load_version(game / "version")
    current = version_parts(actual)
    # DeckCheatz archives omit version; use recorded GitHub release asset name.
    asset = metadata.get("source_asset")
    release = metadata.get("source_release")
    source_version = version_parts(asset) if isinstance(asset, str) else None
    if not source_version and isinstance(release, str):
        source_version = version_parts(release)
    embedded_path = payload / "version"
    embedded_version = version_parts(load_version(embedded_path)) if embedded_path.exists() else None
    if source_version and embedded_version and source_version != embedded_version:
        raise ImportBlocked("Prepared Proton version disagrees with asset metadata")
    downloaded = embedded_version or source_version
    if not current or not downloaded:
        raise ImportBlocked("GE-Proton version cannot be established from game and cache record")
    if current != downloaded:
        raise ImportBlocked("Prepared GE-Proton version does not match selected game's prefix")
    template_count, template_bytes = manifest_preflight(payload, metadata)
    source_count, source_bytes = files_and_bytes(game)
    collisions = 0
    registry = 0
    for member in metadata["files"]:
        rel = member["path"]
        destination = game.joinpath(*rel.split("/"))
        if destination.exists() or destination.is_symlink():
            collisions += 1
            if rel.casefold() in ("pfx/system.reg", "pfx/user.reg",
                                  "pfx/userdef.reg"):
                registry += 1
    report = {
        "appid": appid,
        "mode": "PREVIEW_COMPATIBLE_PREPARED_PREFIX",
        "ge_proton_major": current[0],
        "ge_proton_minor": current[1],
        "version_match": True,
        "prepared_dotnet_environment_candidate": True,
        "template_files": template_count,
        "template_bytes": template_bytes,
        "game_prefix_files": source_count,
        "game_prefix_bytes": source_bytes,
        "overlapping_files": collisions,
        "registry_conflicts": registry,
        "existing_prefix_preserved": True,
        "source_authenticity_verified": False,
        "live_game_modified": False,
        "live_install_supported": False,
        "trainer_attached": False,
        "no_steam_launch_options_required_for_preview": True,
        "next": "Prepare isolated candidate; never replace live prefix based on preview",
    }
    return report, {"game": game, "payload": payload, "manifest": metadata}


def prepare_candidate(report: dict, paths: dict, *, state_root: Path,
                      approved: bool) -> dict:
    if not approved:
        raise ImportBlocked("Explicit --approve-isolated-copy is required")
    root = private_root(state_root, "prefix-imports")
    if not report["version_match"]:
        raise ImportBlocked("Proton version mismatch")
    source, payload = paths["game"], paths["payload"]
    # Refuse a racing archive/prefix and ensure a complete independent copy.
    manifest_preflight(payload, paths["manifest"])
    _, game_bytes = files_and_bytes(source)
    if shutil.disk_usage(source).free < game_bytes + 2 * RESERVE:
        raise ImportBlocked("Insufficient free disk for isolated candidate")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if root.is_symlink():
        raise ImportBlocked("Private state directory replaced by a symlink")
    temp = Path(tempfile.mkdtemp(prefix=".incoming-", dir=root))
    target = root / f"{report['appid']}-{paths['manifest']['source_archive_sha256'][:16]}"
    try:
        candidate = temp / "compatdata"
        # Symlinks are preserved, never followed: Wine dosdevices often contains
        # links, including z: -> /. Do not let those links redirect overlays.
        shutil.copytree(source, candidate, symlinks=True)
        for entry in paths["manifest"]["files"]:
            relative = entry["path"]
            dest = candidate.joinpath(*relative.split("/"))
            if any(p.is_symlink() for p in (dest, *list(dest.parents)[:len(relative.split("/"))])):
                raise ImportBlocked("Staged overlay would traverse a game-prefix symlink")
            if dest.is_dir():
                raise ImportBlocked("Staged file conflicts with a game directory")
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Only isolated copy changes. Registry data is overwritten ONLY in
            # the candidate; the real game registry remains identical.
            shutil.copyfile(payload / relative, dest, follow_symlinks=False)
            if sha256(dest) != entry["sha256"]:
                raise ImportBlocked("Merged isolated candidate failed file verification")
        if target.exists() or target.is_symlink():
            raise ImportBlocked("Isolated candidate already exists; refusing overwrite")
        result = {
            **report,
            "mode": "ISOLATED_CANDIDATE_PREPARED",
            "candidate_dir": str(target),
            "live_game_modified": False,
            "live_install_supported": False,
            "trainer_attached": False,
            "game_original_preserved": True,
            "note": "No game prefix has been installed or replaced",
        }
        with (temp / "candidate.json").open("x", encoding="utf-8") as file:
            json.dump(result, file, indent=2, sort_keys=True)
            file.write("\n")
        os.chmod(temp / "candidate.json", 0o600)
        os.rename(temp, target)
        return result
    finally:
        if temp.exists() and not temp.is_symlink():
            shutil.rmtree(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appid", required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--stage-dir", type=Path)
    parser.add_argument("--single-staged", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=Path(
        os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    ) / "gameweld/prepared-wemod")
    parser.add_argument("--state-root", type=Path, default=Path(
        os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    ) / "gameweld/prefix-imports")
    parser.add_argument("--prepare-isolated-copy", action="store_true")
    parser.add_argument("--approve-isolated-copy", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.approve_isolated_copy and not args.prepare_isolated_copy:
            raise ImportBlocked("Approval is only valid for isolated-copy preparation")
        selected = args.stage_dir
        if args.single_staged:
            if selected is not None:
                raise ImportBlocked("Select a path or use automatic single-stage selection")
            stages = args.cache_root / "staging"
            if stages.is_symlink() or not stages.is_dir():
                raise ImportBlocked("No staged prepared prefix is available")
            found = [p for p in stages.iterdir() if p.is_dir() and not p.is_symlink()]
            if len(found) != 1:
                raise ImportBlocked("Exactly one staged prefix is required")
            selected = found[0]
        if selected is None:
            raise ImportBlocked("A staged prefix must be selected")
        report, paths = preview(args.appid, args.install_dir, selected,
                                cache_root=args.cache_root, state_root=args.state_root)
        if args.prepare_isolated_copy:
            report = prepare_candidate(report, paths, state_root=args.state_root,
                                       approved=args.approve_isolated_copy)
    except (ImportBlocked, OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, "GameWeld prepared prefix import BLOCKED — " + str(exc) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
