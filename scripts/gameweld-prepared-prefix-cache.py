#!/usr/bin/env python3
"""Download a third-party prepared WeMod ZIP to a shared cache, never a game.

Intentionally opt-in. A stored ZIP is only structurally checked: no publisher
signature, successful CLR runtime, trainer attachment, or game compatibility is
implied. This tool does NOT extract the ZIP or edit Steam/Heroic/Lutris data.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
from typing import Callable
import uuid
import zipfile

SOURCE_REPO = "DeckCheatz/BuiltPrefixes-dev"
MAX_DOWNLOAD_BYTES = 3_000_000_000
CHUNK = 1024 * 1024
TIMEOUT = 30


class CacheRefused(ValueError):
    pass


def validate_release_url(url: str) -> tuple[str, str]:
    """Only allow versioned release asset URLs from the configured project."""
    parsed = urlsplit(url)
    prefix = f"/{SOURCE_REPO}/releases/download/"
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or
            parsed.username is not None or parsed.password is not None or
            parsed.port not in (None, 443) or parsed.query or parsed.fragment or
            not parsed.path.startswith(prefix)):
        raise CacheRefused("Archive URL must be a direct DeckCheatz GitHub release asset")
    parts = parsed.path[len(prefix):].split("/")
    if (len(parts) != 2 or any(not p or p in (".", "..") for p in parts) or
            any("%" in p for p in parts)):
        raise CacheRefused("Invalid release tag or asset name")
    tag, filename = map(unquote, parts)
    if ("/" in tag or "\\" in tag or "/" in filename or "\\" in filename or
            not filename.lower().endswith(".zip") or
            not all(ch.isalnum() or ch in "._+-" for ch in tag + filename)):
        raise CacheRefused("Release asset must be a simple ZIP filename")
    return tag, filename


def safe_cache_root(root: Path) -> Path:
    """Check ancestry before any cache mutations; never follow a symlink."""
    if not root.is_absolute():
        raise CacheRefused("Cache location must be absolute")
    if any(p.lower() in {"steamapps", "compatdata", "pfx"} for p in root.parts):
        raise CacheRefused("Cache cannot be inside Steam or a game prefix")
    if any(ancestor.is_symlink() for ancestor in (root, *root.parents)):
        raise CacheRefused("Symlinked cache ancestry is forbidden")
    if root.exists() and not root.is_dir():
        raise CacheRefused("Cache path is not a directory")
    return root


def _load_zip_audit():
    script = Path(__file__).resolve().with_name("gameweld-prepared-prefix-audit.py")
    if script.is_symlink() or not script.is_file():
        raise CacheRefused("Shared ZIP safety inspector is missing")
    spec = importlib.util.spec_from_file_location("prepared_archive_audit", script)
    if spec is None or spec.loader is None:
        raise CacheRefused("Cannot load prepared ZIP safety inspector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_matching_rejected_release(
    cache_root: Path, *, tag: str, filename: str, declared_size: int
) -> str | None:
    """Prevent automatic repeats of an already rejected release and size.

    A quarantine receipt is evidence of a local previous rejection, NOT
    publisher identity, a security attestation, or proof a remote URL has not
    since changed. Operators may explicitly retry a republished asset.
    """
    directory = cache_root / "rejected"
    if not directory.exists():
        return None
    if (directory.is_symlink() or not directory.is_dir() or
            stat.S_IMODE(directory.stat().st_mode) & 0o077):
        raise CacheRefused("Rejected archive directory is unsafe")
    records = sorted(directory.glob("*.rejected.json"))
    if len(records) > 16:
        raise CacheRefused("Too many rejected release records; inspect cache manually")
    for record in records:
        if (record.is_symlink() or not record.is_file() or
                record.stat().st_size > 4096):
            raise CacheRefused("Unsafe rejected release metadata")
        try:
            entry = json.loads(record.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError) as exc:
            raise CacheRefused("Unreadable rejected release metadata") from exc
        if not isinstance(entry, dict):
            raise CacheRefused("Invalid rejected release metadata")
        sha = record.name.removesuffix(".rejected.json")
        if (len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha) or
                entry.get("sha256") != sha):
            raise CacheRefused("Inconsistent rejected release checksum metadata")
        candidate = directory / (sha + ".zip")
        if (entry.get("source") == SOURCE_REPO and
                entry.get("status") == "REJECTED_NOT_STAGEABLE" and
                entry.get("release_tag") == tag and
                entry.get("asset_name") == filename and
                entry.get("bytes") == declared_size and
                candidate.is_file() and not candidate.is_symlink() and
                candidate.stat().st_size == declared_size):
            return sha[:12]
    return None


def acquire_to_cache(
    url: str,
    *,
    declared_size: int,
    cache_root: Path,
    approved: bool,
    opener=urlopen,
    progress: Callable[[str, int, int], None] | None = None,
    retry_rejected: bool = False,
) -> dict:
    """Acquire and inspect untrusted ZIP bytes; never unpack or run them."""
    tag, filename = validate_release_url(url)
    if not approved:
        raise CacheRefused("Explicit --approve-cache-download is required")
    if type(declared_size) is not int or not 1_000_000 <= declared_size <= MAX_DOWNLOAD_BYTES:
        raise CacheRefused("Declared asset size is outside accepted bounds")
    root = safe_cache_root(cache_root)
    previously_rejected = find_matching_rejected_release(
        root, tag=tag, filename=filename, declared_size=declared_size)
    if previously_rejected and not retry_rejected:
        raise CacheRefused(
            "This selected release and size were already rejected for ZIP filename "
            "collisions (archive " + previously_rejected + "). NO DOWNLOAD STARTED. "
            "Its files cannot be merged safely based on names; select an upstream "
            "corrected release. Only an independently confirmed reupload under the "
            "same tag/size should be retried with explicit --retry-rejected.")
    existing = next((part for part in (root, *root.parents) if part.exists()), None)
    if existing is None:
        raise CacheRefused("No existing parent filesystem for cache")
    try:
        free = shutil.disk_usage(existing).free
    except OSError as exc:
        raise CacheRefused("Cannot confirm free space for cache") from exc
    if free < declared_size * 2 + 512 * 1024 * 1024:
        raise CacheRefused("Not enough free space for isolated cache download")

    # All mutations are confined to this exact cache subtree. No ZIP
    # extraction, Wine invocation, game-file access or account-data reads.
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe_cache_root(root)
    incoming = root / "incoming"
    stored = root / "downloads"
    for d in (incoming, stored):
        if d.is_symlink():
            raise CacheRefused("Cache subfolder is symlinked")
        d.mkdir(mode=0o700, exist_ok=True)
    temp = incoming / (uuid.uuid4().hex + ".part")
    request = Request(url, headers={
        "Accept": "application/octet-stream",
        "User-Agent": "GameWeld-prepared-prefix-cache",
    })
    length = 0
    digest = hashlib.sha256()
    last_percent = -5
    if progress is not None:
        progress("DOWNLOAD", 0, declared_size)
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as output:
            with opener(request, timeout=TIMEOUT) as response:
                final_url = urlsplit(response.geturl())
                if (final_url.scheme != "https" or
                        final_url.hostname not in {
                            "github.com", "release-assets.githubusercontent.com",
                        }):
                    raise CacheRefused("Download redirect left the trusted GitHub asset hosts")
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    length += len(chunk)
                    if length > declared_size or length > MAX_DOWNLOAD_BYTES:
                        raise CacheRefused("Downloaded bytes exceeded declared asset size")
                    digest.update(chunk)
                    output.write(chunk)
                    percent = length * 100 // declared_size
                    if progress is not None and percent >= last_percent + 5:
                        progress("DOWNLOAD", length, declared_size)
                        last_percent = percent
            output.flush()
            os.fsync(output.fileno())
        if length != declared_size:
            raise CacheRefused("Downloaded file size does not match GitHub release metadata")

        if progress is not None:
            progress("VERIFY", length, declared_size)
        audit = _load_zip_audit()
        try:
            with zipfile.ZipFile(temp) as archive:
                entries, uncompressed = audit.inspect_zip_members(archive)
                if archive.testzip() is not None:
                    raise CacheRefused("ZIP CRC check failed")
        except audit.UnsafePreparedPrefix as exc:
            # Retain ONLY completed ZIPs rejected for filename collisions in
            # a separate non-stageable directory for offline investigation.
            # Everything else fails closed and the temporary ZIP is deleted.
            if str(exc) == "Duplicate/case-colliding archive entries":
                rejected = root / "rejected"
                if rejected.is_symlink():
                    raise CacheRefused("Unsafe rejected-archive cache") from exc
                rejected.mkdir(mode=0o700, exist_ok=True)
                if (not rejected.is_dir() or rejected.is_symlink() or
                        stat.S_IMODE(rejected.stat().st_mode) & 0o077):
                    raise CacheRefused("Rejected archive folder must be private") from exc
                digest_name = digest.hexdigest()
                quarantined = rejected / (digest_name + ".zip")
                existing_quarantine = list(rejected.glob("*.zip"))
                if quarantined.is_symlink():
                    raise CacheRefused("Unsafe existing rejected archive") from exc
                if not quarantined.exists() and len(existing_quarantine) < 2:
                    # Atomic relocation: never enters downloads/ and cannot
                    # be selected by Stage; only preserve bounded diagnostics.
                    os.replace(temp, quarantined)
                    receipt = rejected / (digest_name + ".rejected.json")
                    if not receipt.exists() and not receipt.is_symlink():
                        try:
                            fd = os.open(receipt,
                                os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                getattr(os, "O_NOFOLLOW", 0), 0o600)
                            with os.fdopen(fd, "w", encoding="utf-8") as output:
                                json.dump({
                                    "sha256": digest_name, "bytes": length,
                                    "source": SOURCE_REPO,
                                    "release_tag": tag, "asset_name": filename,
                                    "status": "REJECTED_NOT_STAGEABLE",
                                }, output, sort_keys=True)
                                output.write("\n")
                                output.flush()
                                os.fsync(output.fileno())
                        except OSError:
                            # A rejected ZIP remains inspectable even if its
                            # source receipt could not be saved. Never imply
                            # provenance from a missing or invalid receipt.
                            receipt.unlink(missing_ok=True)
                raise CacheRefused(
                    "ZIP safety check failed: Duplicate/case-colliding archive entries. "
                    "The complete rejected ZIP is isolated when space permits; "
                    "run gameweld-prepared-prefix-cache.py --rejected-status "
                    "for a read-only classification. NOT saved for staging."
                ) from exc
            raise CacheRefused(f"ZIP safety check failed: {exc}") from exc
        except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
            # Low-level exceptions can include untrusted archive names/paths.
            raise CacheRefused("Unsafe or invalid prepared-prefix ZIP") from exc

        sha = digest.hexdigest()
        destination = stored / (sha + ".zip")
        metadata_path = stored / (sha + ".source.json")
        if (destination.exists() or destination.is_symlink() or
                metadata_path.exists() or metadata_path.is_symlink()):
            raise CacheRefused("An existing archive or metadata record must not be overwritten")
        # Preserve the asset name so a ZIP that intentionally omits the
        # Proton 'version' file can still be matched to the game prefix.
        # Release metadata is NOT a publisher signature or compatibility proof.
        source_record = {
            "sha256": sha, "bytes": length, "source": SOURCE_REPO,
            "release_tag": tag, "asset_name": filename,
            "publisher_authenticity": "UNVERIFIED",
        }
        os.replace(temp, destination)
        try:
            fd = os.open(metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(source_record, output, sort_keys=True, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
        except OSError:
            metadata_path.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        if progress is not None:
            progress("CACHED", length, declared_size)
        return {
            "source": SOURCE_REPO, "release_tag": tag, "asset_name": filename,
            "sha256": sha, "bytes": length, "zip_entries": entries,
            "declared_unpacked_bytes": uncompressed,
            "cache_path": str(destination), "archive_structural_check": "PASS",
            "publisher_authenticity": "UNVERIFIED",
            "game_compatibility": "UNVERIFIED",
            "installed_to_game": False,
            "trainer_verified": False,
        }
    finally:
        if temp.exists():
            temp.unlink()



def rejected_cache_status(cache_root: Path) -> str:
    """Read only rejected archive metadata; never extract or trust rejected ZIPs."""
    root = safe_cache_root(cache_root)
    directory = root / "rejected"
    lines = ["GAMEWELD — REJECTED ZIP COLLISIONS (READ ONLY)",
             "Rejected ZIPs are NOT completed cache downloads and cannot be staged."]
    if not directory.exists():
        return "\n".join(lines + ["Rejected archives: 0"])
    if directory.is_symlink() or not directory.is_dir():
        raise CacheRefused("Unsafe rejected-archive directory")
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise CacheRefused("Rejected-archive directory is not private")
    paths = sorted(directory.glob("*.zip"))
    lines.append(f"Rejected archives: {len(paths)}")
    audit = _load_zip_audit()
    for path in paths[:2]:
        sha = path.stem
        if (path.is_symlink() or not path.is_file() or
                len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha) or
                not 0 < path.stat().st_size <= MAX_DOWNLOAD_BYTES):
            lines.append("Rejected archive skipped: invalid cached file")
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                counts, examples = audit.classify_zip_collisions(archive)
                # This diagnostic does not bypass the strict Step 1/Step 2
                # validator. It only checks for additional rejection reasons.
                noncollision_error = None
                try:
                    audit.check_other_zip_safety_without_approving_collisions(archive)
                except audit.UnsafePreparedPrefix as exc:
                    noncollision_error = str(exc)
                payload_comparison = audit.compare_case_collision_bytes(archive)
        except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError,
                audit.UnsafePreparedPrefix) as exc:
            lines.append("Rejected archive index cannot be safely inspected")
            continue
        lines.append("Archive SHA-256 filename prefix: " + sha[:12])
        receipt = directory / (sha + ".rejected.json")
        if receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size < 4096:
            try:
                source_record = json.loads(receipt.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError, OSError):
                source_record = {}
            if (isinstance(source_record, dict) and
                    source_record.get("sha256") == sha and
                    source_record.get("source") == SOURCE_REPO and
                    source_record.get("status") == "REJECTED_NOT_STAGEABLE"):
                lines.append("Source metadata receipt present (publisher authenticity unverified)")
        lines.extend(f"{kind}: {count}" for kind, count in counts.items())
        if noncollision_error:
            lines.append("Additional ZIP metadata safety check: BLOCKED - " +
                         noncollision_error)
        else:
            lines.append("Additional ZIP metadata safety check: PASS "
                         "(excluding case collisions; full CRC NOT checked)")
        lines.extend(f"Collision payloads {kind}: {count}"
                     for kind, count in payload_comparison.items())
        lines.extend("Collision example: " + example for example in examples)
        if counts["case_collision"] and (
                payload_comparison["different_payload"] or
                payload_comparison["size_mismatch"]):
            lines.append("VERDICT: BLOCKED BY GAMEWELD'S CURRENT SAFE STAGING POLICY. "
                         f"{counts['case_collision']} case-only path pair(s) may coexist "
                         "on a case-sensitive filesystem but have distinct "
                         "contents or sizes, so no automatic "
                         "merge or case-normalization is permitted. "
                         "Do NOT stage or install this archive until "
                         "runtime-safe handling is independently verified, "
                         "or select a corrected release.")
        lines.append("Comparison is read-only; identical payloads are NOT approval to stage.")
    lines.append("No archive installed, extracted, executed, or approved for staging.")
    return "\n".join(lines)


def main() -> int:
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-asset-url")
    parser.add_argument("--declared-size", type=int)
    parser.add_argument("--approve-cache-download", action="store_true")
    parser.add_argument("--retry-rejected", action="store_true",
                        help="Only for independently confirmed same-tag reuploads; "
                             "retains the old rejected ZIP")
    parser.add_argument("--progress", action="store_true",
                        help="Emit progress records for a parent GUI; no installation")
    default_cache = Path(os.environ.get("XDG_CACHE_HOME") or
                         str(Path.home() / ".cache"))
    parser.add_argument("--cache-root", type=Path,
                        default=default_cache / "gameweld/prepared-wemod")
    parser.add_argument("--rejected-status", action="store_true",
                        help="Inspect quarantined ZIP filenames locally (read only)")
    args = parser.parse_args()
    if args.rejected_status:
        if (args.release_asset_url or args.declared_size is not None or
                args.approve_cache_download or args.retry_rejected or args.progress):
            parser.error("--rejected-status cannot start a download")
        try:
            print(rejected_cache_status(args.cache_root))
        except (CacheRefused, OSError) as exc:
            parser.exit(2, f"Rejected ZIP inspection BLOCKED: {exc}\n")
        return 0
    if not args.release_asset_url or args.declared_size is None:
        parser.error("download requires --release-asset-url and --declared-size")
    if args.retry_rejected and not args.approve_cache_download:
        parser.error("--retry-rejected also requires explicit --approve-cache-download")
    def cancel_download(signum, frame):
        raise CacheRefused("Cancelled by user; incomplete download discarded")
    if args.progress:
        signal.signal(signal.SIGINT, cancel_download)
        signal.signal(signal.SIGTERM, cancel_download)
    def print_progress(stage: str, current: int, total: int) -> None:
        print(f"PROGRESS\t{stage}\t{current}\t{total}", flush=True)
    try:
        result = acquire_to_cache(
            args.release_asset_url, declared_size=args.declared_size,
            approved=args.approve_cache_download,
            cache_root=args.cache_root,
            progress=print_progress if args.progress else None,
            retry_rejected=args.retry_rejected,
        )
    except (CacheRefused, OSError, ValueError) as exc:
        parser.exit(2, f"Prepared prefix cache: BLOCKED — {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
