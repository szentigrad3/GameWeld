#!/usr/bin/env python3
"""Read-only bounded HTTP Range inspection of a DeckCheatz prepared ZIP directory.

Never downloads member contents, extracts, executes or writes game/cache files.
The server MUST honor Range; full-body responses are refused immediately.
This probe does not establish publisher identity or make a ZIP installable.
"""
from __future__ import annotations

import argparse
from collections import Counter
import io
import re
import struct
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

ALLOWED_HOSTS = {"github.com", "release-assets.githubusercontent.com"}
RELEASE_PREFIX = "/DeckCheatz/BuiltPrefixes-dev/releases/download/"
TAIL_BYTES = 65557
MAX_CD_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 3_000_000_000
MAX_ENTRIES = 40000
CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)\Z")
EOCD = struct.Struct("<4s4H2LH")


class ProbeRefused(ValueError):
    pass


def trusted_url(url: str, *, release_only: bool = False) -> None:
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or
            p.username or p.password or p.port not in (None, 443)):
        raise ProbeRefused("Only official GitHub release asset hosts are permitted")
    if release_only and (p.hostname != "github.com" or
                         not p.path.startswith(RELEASE_PREFIX) or
                         not p.path.lower().endswith(".zip") or
                         p.query or p.fragment):
        raise ProbeRefused("Expected a direct DeckCheatz BuiltPrefixes-dev release ZIP URL")


def read_range(url: str, header: str, *, opener=urlopen) -> tuple[int, int, int, bytes]:
    req = Request(url, headers={"Range": header,
                                "Accept-Encoding": "identity",
                                "User-Agent": "GameWeld-ZIP-directory-audit"})
    with opener(req, timeout=30) as reply:
        trusted_url(reply.geturl())
        if reply.status != 206:
            raise ProbeRefused("Server ignored HTTP Range; refused full archive download")
        m = CONTENT_RANGE.fullmatch(reply.headers.get("Content-Range", ""))
        if not m:
            raise ProbeRefused("Server did not supply a valid Content-Range")
        start, end, total = map(int, m.groups())
        expected = end - start + 1
        if not (0 <= start <= end < total <= MAX_ARCHIVE_BYTES) or expected > MAX_CD_BYTES:
            raise ProbeRefused("Unsafe or unexpectedly large Range response")
        if header.startswith("bytes=-"):
            if end != total - 1 or expected != min(int(header[7:]), total):
                raise ProbeRefused("Suffix Range does not match request")
        elif header != f"bytes={start}-{end}":
            raise ProbeRefused("Server returned a different byte range")
        data = reply.read(expected + 1)
        if len(data) != expected:
            raise ProbeRefused("Incomplete or oversized Range response")
    return start, end, total, data


def inspect_directory(url: str, *, opener=urlopen) -> tuple[dict, list[str]]:
    trusted_url(url, release_only=True)
    suffix_start, _, total, tail = read_range(url, f"bytes=-{TAIL_BYTES}", opener=opener)
    # EOCD ends with a variable-length comment; reject unrelated magic in its contents.
    eocd_at = -1
    for i in range(len(tail) - EOCD.size, -1, -1):
        if tail[i:i+4] == b"PK\x05\x06":
            end = EOCD.unpack_from(tail, i)
            if i + EOCD.size + end[-1] == len(tail):
                eocd_at = i
                break
    if eocd_at < 0:
        raise ProbeRefused("Could not find ZIP end-of-directory record")
    sig, disk, start_disk, disk_entries, entries, cd_size, cd_start, comment = EOCD.unpack_from(tail, eocd_at)
    if (disk != 0 or start_disk != 0 or disk_entries != entries or
            entries >= 0xFFFF or cd_size == 0xFFFFFFFF or cd_start == 0xFFFFFFFF):
        raise ProbeRefused("Multidisk/ZIP64 archive needs separate offline inspection")
    if entries > MAX_ENTRIES or cd_size > MAX_CD_BYTES or cd_size < 46:
        raise ProbeRefused("ZIP directory exceeds bounded inspection limits")
    if cd_start + cd_size != suffix_start + eocd_at:
        raise ProbeRefused("ZIP has offset/preamble differences requiring offline inspection")
    if cd_start >= suffix_start:
        central = tail[cd_start-suffix_start:cd_start-suffix_start+cd_size]
    else:
        a, b, n, central = read_range(url, f"bytes={cd_start}-{cd_start+cd_size-1}", opener=opener)
        if (a, b, n) != (cd_start, cd_start+cd_size-1, total):
            raise ProbeRefused("Central directory response size/identity changed")
    if len(central) != cd_size:
        raise ProbeRefused("Incomplete central directory")
    # ZIP readers only need central entries and adjusted EOCD for enumeration.
    # Local file contents are deliberately unavailable.
    adjusted = bytearray(tail[eocd_at:])
    struct.pack_into("<I", adjusted, 16, 0)
    try:
        with zipfile.ZipFile(io.BytesIO(central + adjusted)) as reader:
            members = reader.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ProbeRefused("Malformed ZIP central-directory records") from exc
    if len(members) != entries:
        raise ProbeRefused("Central-directory member count differs from ZIP footer")
    seen: dict[str, tuple[str, bool]] = {}
    counts: Counter[str] = Counter()
    examples: list[str] = []
    for member in members:
        name = member.filename.rstrip("/")
        normalized = unicodedata.normalize("NFC", name).casefold()
        is_dir = member.is_dir()
        if normalized in seen:
            earlier, was_dir = seen[normalized]
            if is_dir != was_dir:
                kind = "file/directory path conflict"
            elif name == earlier:
                kind = "exact duplicate directory" if is_dir else "exact duplicate file"
            else:
                kind = "case/Unicode name collision"
            counts[kind] += 1
            if len(examples) < 4:
                # Escaped, so malformed archive names cannot inject terminal controls.
                examples.append(f"{kind}: {ascii(earlier)[:180]} versus {ascii(name)[:180]}")
        else:
            seen[normalized] = (name, is_dir)
    counts["total entries"] = len(members)
    counts["directory bytes fetched (at most)"] = TAIL_BYTES + cd_size
    return dict(counts), examples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-asset-url", required=True)
    args = parser.parse_args()
    try:
        counts, examples = inspect_directory(args.release_asset_url)
    except (ProbeRefused, OSError, TimeoutError, ValueError) as exc:
        parser.exit(2, f"Read-only ZIP directory probe unavailable: {exc}\n")
    print("GAMEWELD — REMOTE ZIP DIRECTORY PROBE (read-only, no archive download)")
    for k, v in counts.items():
        print(f"{k}: {v}")
    if examples:
        print("First collision examples (escaped archive entry names):")
        for e in examples:
            print("  " + e)
    print("No ZIP extracted, cached, trusted, or installed by this probe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
