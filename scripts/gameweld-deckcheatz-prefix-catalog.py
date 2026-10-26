#!/usr/bin/env python3
"""Read-only catalog lookup for DeckCheatz's prepared WeMod prefixes.

This code never downloads an archive, runs an installer or touches Steam/Proton
prefixes. It consumes GitHub release metadata, not executable release assets.
The archive application / backup / rollback path is intentionally NOT provided.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPO = "DeckCheatz/BuiltPrefixes-dev"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
VERSION_PATTERN = re.compile(
    r"(?:GE[-_ ]?Proton|Proton[-_ ]?GE|Proton)[-_ ]?(\d+)[._-](\d+)",
    re.IGNORECASE,
)
MAX_RELEASE_BYTES = 2 * 1024 * 1024


def parse_proton_version(text: str) -> tuple[int, int] | None:
    match = VERSION_PATTERN.search(text[:1024])
    return (int(match.group(1)), int(match.group(2))) if match else None


def list_release_assets(releases: object, proton_label: str) -> list[dict]:
    """Select possible ZIP assets; names alone are never trust evidence."""
    wanted = parse_proton_version(proton_label)
    if not isinstance(releases, list):
        raise ValueError("Release catalog must contain a list")
    ranked = []
    for release in releases[:20]:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            continue
        tag_version = parse_proton_version(tag)
        for asset in release.get("assets", [])[:30]:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            url = asset.get("browser_download_url")
            size = asset.get("size")
            if (not isinstance(name, str) or not name.lower().endswith(".zip") or
                    not isinstance(url, str) or
                    not isinstance(size, int) or not 1_000_000 <= size <= 3_000_000_000):
                continue
            location = urlsplit(url)
            if (location.scheme != "https" or location.hostname != "github.com" or
                    not location.path.startswith(f"/{REPO}/releases/download/")):
                continue
            asset_version = parse_proton_version(name) or tag_version
            if wanted is None or asset_version is None:
                rank = 0
                compatibility = "UNVERIFIED (missing version metadata)"
            elif asset_version == wanted:
                rank = 3
                compatibility = "EXACT VERSION LABEL MATCH (runtime compatibility NOT verified)"
            elif asset_version[0] == wanted[0]:
                rank = 2
                compatibility = "SAME MAJOR LABEL (compatibility uncertain)"
            else:
                rank = 1
                compatibility = "DIFFERENT MAJOR LABEL (do not auto-select)"
            ranked.append({
                "rank": rank,
                "compatibility": compatibility,
                "release": tag,
                "asset": name,
                "size": size,
                "url": url,
            })
    ranked.sort(key=lambda item: (-item["rank"], item["size"], item["release"]))
    return ranked[:8]


def fetch_release_metadata() -> object:
    request = Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "GameWeld-read-only-prefix-catalog",
        },
    )
    # Caller-initiated network read only; no credentials, user data or local
    # Wine/Proton directories are sent to the release service.
    with urlopen(request, timeout=8) as response:
        data = response.read(MAX_RELEASE_BYTES + 1)
    if len(data) > MAX_RELEASE_BYTES:
        raise ValueError("DeckCheatz release metadata exceeded safety limit")
    return json.loads(data)


def catalog_report(proton_label: str, *, releases: object | None = None) -> str:
    version = parse_proton_version(proton_label)
    lines = [
        "GAMEWELD — PREPARED WEMOD PREFIX OPTIONS (READ ONLY)",
        "Source: DeckCheatz/BuiltPrefixes-dev (third-party, unofficial)",
        f"Configured Proton label: {proton_label}",
        "Detected Proton version label: " +
        (f"{version[0]}.{version[1]}" if version else "UNKNOWN"),
        "No archive downloaded; no files copied; no game prefix modified.",
    ]
    if releases is None:
        try:
            releases = fetch_release_metadata()
        except (OSError, ValueError, TimeoutError) as error:
            return "\n".join(lines + [
                f"Release lookup: UNAVAILABLE ({type(error).__name__})",
                f"Browse releases manually: {RELEASES_PAGE}",
                "No automatic compatibility claim or prefix replacement.",
            ])
    candidates = list_release_assets(releases, proton_label)
    if not candidates:
        lines.append("Matching prefix downloads: NOT FOUND in inspected releases.")
    else:
        lines.append(f"Prepared prefix archives listed: {len(candidates)} possible asset(s)")
        for item in candidates[:4]:
            lines.append(f"- {item['release']} / {item['asset']} ({item['size'] / 1024**2:.1f} MiB)")
            lines.append(f"  Label comparison: {item['compatibility']}")
        lines.append("Archive content, account data, signatures and runtime: NOT VERIFIED")
    lines.extend([
        f"Publisher's release page: {RELEASES_PAGE}",
        "Recommended direction: use a compatible tested prepared prefix instead of repeating the failed .NET MSI installer.",
        "Before any future install: verify publisher/asset integrity, preserve the entire original game prefix and user data, and require explicit confirmation.",
        "A download or installation requires a separate approved and reversible implementation. No automated replacement is enabled.",
    ])
    return "\n".join(lines)


def main() -> int:
    """Independent of game provider, AppID and any installed game prefix."""
    import argparse
    parser = argparse.ArgumentParser(description="Read-only shared WeMod prefix release lookup")
    parser.add_argument(
        "--proton-label", default="Shared GameWeld WeMod environment",
        help="Optional informational runner label; no game must be selected",
    )
    args = parser.parse_args()
    print("Scope: SHARED PREPARED-PREFIX LIBRARY for Steam, Heroic and Lutris integrations")
    print("Provider launch integration: not tested by this catalog lookup")
    print(catalog_report(args.proton_label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
