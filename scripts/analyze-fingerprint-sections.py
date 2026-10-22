#!/usr/bin/env python3
"""Offline PE-section geometry analysis for Wand Native fingerprint traces.

This consumes a 0.1.36+ wand-fingerprint trace. It does not access a live
process and never reads or writes process memory.
"""
import argparse
import pathlib
import re
from collections import defaultdict

PAGE = 4096

PE_RE = re.compile(
    r"^PE (?P<name>\S+)(?: kind=(?P<kind>\S+))? "
    r"file_size=(?P<file>\d+) size_of_image=(?P<image>\d+) "
    r"entry_rva=0x(?P<entry>[0-9a-fA-F]+) image_base=0x(?P<base>[0-9a-fA-F]+) "
    r"sections=(?P<count>\d+) sha256=(?P<sha>[0-9a-fA-F]+)(?: source=.*)?$"
)
SEC_RE = re.compile(
    r"^  SECTION (?P<module>\S+)\s+(?P<section>.*?)\s*"
    r"vaddr=0x(?P<vaddr>[0-9a-fA-F]+) vsize=(?P<vsize>\d+) "
    r"(?:aligned_vsize=(?P<aligned>\d+) )?"
    r"raw_size=(?P<raw>\d+) chars=0x(?P<chars>[0-9a-fA-F]+)$"
)
MAP_RE = re.compile(
    r"^(?P<t>[0-9.]+) ANON_(?P<class>EXEC|SECTION)_(?:ADD|CHANGE) "
    r"range=0x(?P<lo>[0-9a-fA-F]+)-0x(?P<hi>[0-9a-fA-F]+) "
    r"size=(?P<size>\d+) perms=(?P<perms>\S+)"
)


def align_page(n):
    return (n + PAGE - 1) & ~(PAGE - 1)


def parse(path):
    modules = {}
    events = []
    current = None
    for raw in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = PE_RE.match(raw)
        if m:
            current = m.group("name")
            modules[current] = {
                "size_of_image": int(m.group("image")),
                "kind": m.group("kind") or "unknown",
                "sections": [],
            }
            continue
        m = SEC_RE.match(raw)
        if m and current:
            modules[current]["sections"].append({
                "name": m.group("section").strip() or "<unnamed>",
                "vaddr": int(m.group("vaddr"), 16),
                "vsize": int(m.group("vsize")),
                "raw": int(m.group("raw")),
                "chars": int(m.group("chars"), 16),
            })
            continue
        m = MAP_RE.match(raw)
        if m:
            events.append({
                "time": float(m.group("t")),
                "lo": int(m.group("lo"), 16),
                "hi": int(m.group("hi"), 16),
                "size": int(m.group("size")),
                "perms": m.group("perms"),
                "event_class": m.group("class"),
                "raw": raw,
            })
    return modules, events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--min-section", type=lambda x: int(x, 0), default=0x10000,
                    help="minimum aligned PE section size considered distinctive (default 64 KiB)")
    args = ap.parse_args()

    modules, events = parse(args.trace)
    evidence = defaultdict(dict)
    event_matches = defaultdict(list)

    for ei, ev in enumerate(events):
        for module, fp in modules.items():
            for si, sec in enumerate(fp["sections"]):
                aligned = align_page(sec["vsize"])
                if aligned != ev["size"]:
                    continue
                base = ev["lo"] - sec["vaddr"]
                rec = {
                    "event": ei,
                    "time": ev["time"],
                    "module": module,
                    "section_index": si,
                    "section": sec["name"],
                    "vaddr": sec["vaddr"],
                    "vsize": sec["vsize"],
                    "aligned": aligned,
                    "base": base,
                    "perms": ev["perms"],
                }
                event_matches[ei].append(rec)
                if aligned >= args.min_section:
                    evidence[(module, base)].setdefault(si, rec)

    ranked = []
    for (module, base), by_section in evidence.items():
        bytes_matched = sum(r["aligned"] for r in by_section.values())
        ranked.append((len(by_section), bytes_matched, module, base, by_section))
    ranked.sort(reverse=True)

    print("Wand Native PE section-geometry analysis")
    print(f"trace={args.trace}")
    exec_count = sum(1 for e in events if e.get("event_class") == "EXEC")
    section_count = sum(1 for e in events if e.get("event_class") == "SECTION")
    print(f"pe_modules={len(modules)} map_events={len(events)} exec_events={exec_count} section_sized_events={section_count}")
    print()
    print("===== multi-section common-base candidates =====")
    any_candidate = False
    for count, total, module, base, by_section in ranked:
        if count < 2:
            continue
        any_candidate = True
        names = ",".join(
            f"{r['section']}@0x{r['vaddr']:x}" for _, r in sorted(by_section.items())
        )
        times = ",".join(f"{r['time']:.3f}" for _, r in sorted(by_section.items()))
        print(
            f"MODULE_SECTION_MATCH module={module} kind={modules[module]['kind']} "
            f"base=0x{base:x} sections={count} matched_bytes={total} "
            f"times={times} detail={names}"
        )
    if not any_candidate:
        print("NONE")

    print()
    print("===== unmatched recorded mappings =====")
    unmatched = 0
    for ei, ev in enumerate(events):
        large = [m for m in event_matches[ei] if m["aligned"] >= args.min_section]
        if large:
            continue
        unmatched += 1
        print(ev["raw"])
    if not unmatched:
        print("NONE")

    print()
    print("===== notes =====")
    print("A strong candidate requires multiple distinctive PE sections to imply the same image base.")
    print("Single-size matches are intentionally not treated as proof because packed runtimes reuse common section sizes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
