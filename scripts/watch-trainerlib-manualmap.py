#!/usr/bin/env python3
import argparse
import ctypes
import ctypes.util
import os
import pathlib
import select
import struct
import sys
import time
from datetime import datetime, timezone

IN_ACCESS = 0x00000001
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_CLOSE_NOWRITE = 0x00000010
IN_OPEN = 0x00000020
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800

WATCH_MASK = (
    IN_ACCESS | IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | IN_CLOSE_NOWRITE |
    IN_OPEN | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE |
    IN_DELETE_SELF | IN_MOVE_SELF
)

EVENT_NAMES = [
    (IN_ACCESS, "ACCESS"),
    (IN_MODIFY, "MODIFY"),
    (IN_ATTRIB, "ATTRIB"),
    (IN_CLOSE_WRITE, "CLOSE_WRITE"),
    (IN_CLOSE_NOWRITE, "CLOSE_NOWRITE"),
    (IN_OPEN, "OPEN"),
    (IN_MOVED_FROM, "MOVED_FROM"),
    (IN_MOVED_TO, "MOVED_TO"),
    (IN_CREATE, "CREATE"),
    (IN_DELETE, "DELETE"),
    (IN_DELETE_SELF, "DELETE_SELF"),
    (IN_MOVE_SELF, "MOVE_SELF"),
]

def now_wall():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")

def mono():
    return time.monotonic()

def proc_cmdline(pid):
    try:
        data = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
        return data.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except Exception:
        return ""

def find_resonance_pid():
    candidates = []
    for ent in pathlib.Path("/proc").iterdir():
        if not ent.name.isdigit():
            continue
        pid = int(ent.name)
        cmd = proc_cmdline(pid)
        low = cmd.lower()
        if "resonance.exe" in low or "resonance a plague tale legacy" in low:
            try:
                stat = ent.stat()
                candidates.append((stat.st_mtime_ns, pid, cmd))
            except Exception:
                candidates.append((0, pid, cmd))
    if not candidates:
        return None, ""
    candidates.sort(reverse=True)
    _, pid, cmd = candidates[0]
    return pid, cmd

def locate_trainerlib(prefix):
    root = pathlib.Path(prefix) / "drive_c" / "users"
    matches = []
    if root.is_dir():
        for p in root.glob("*/AppData/Local/Wand/app-*/resources/app.asar.unpacked/static/unpacked/trainerlib"):
            try:
                ver = p.parts[p.parts.index("Local") + 2]
            except Exception:
                ver = ""
            matches.append((p.stat().st_mtime_ns if p.exists() else 0, ver, p))
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][2]

def parse_maps(pid):
    out = {}
    try:
        data = pathlib.Path(f"/proc/{pid}/maps").read_text(errors="replace").splitlines()
    except Exception:
        return None
    for line in data:
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        addr = parts[0]
        perms = parts[1]
        offset = parts[2]
        dev = parts[3]
        inode = parts[4]
        path = parts[5] if len(parts) > 5 else ""
        out[addr] = (perms, offset, dev, inode, path, line)
    return out

def interesting_map(rec):
    perms, _, _, _, path, _ = rec
    low = path.lower()
    return (
        "x" in perms or
        "trainerlib" in low or
        "tophat" in low or
        "wand" in low
    )

def thread_count(pid):
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("Threads:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "?"

def main():
    ap = argparse.ArgumentParser(
        description="Observe Resonance trainerlib file access and executable/permission map changes without ptrace."
    )
    ap.add_argument("--appid", default="2713000")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--wait", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=0.02)
    ap.add_argument("--steam-root", default=os.environ.get("WAND_STEAM_ROOT", "/mnt/games/Steam"))
    args = ap.parse_args()

    compat = os.environ.get(
        "WAND_COMPAT_DATA_PATH",
        os.path.join(args.steam_root, "steamapps", "compatdata", args.appid),
    )
    prefix = os.path.join(compat, "pfx")
    trainerlib = locate_trainerlib(prefix)
    if trainerlib is None:
        print(f"Could not find Wand trainerlib under {prefix}", file=sys.stderr)
        return 2

    outdir = pathlib.Path.home() / "Desktop"
    if not outdir.is_dir():
        outdir = pathlib.Path.home()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = outdir / f"wand-manualmap-{args.appid}-{stamp}.txt"

    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        print("Could not locate libc for inotify.", file=sys.stderr)
        return 3
    libc = ctypes.CDLL(libc_name, use_errno=True)

    inotify_init1 = libc.inotify_init1
    inotify_init1.argtypes = [ctypes.c_int]
    inotify_init1.restype = ctypes.c_int
    fd = inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd < 0:
        err = ctypes.get_errno()
        print(f"inotify_init1 failed: errno={err}", file=sys.stderr)
        return 4

    inotify_add_watch = libc.inotify_add_watch
    inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    inotify_add_watch.restype = ctypes.c_int
    wd = inotify_add_watch(fd, os.fsencode(trainerlib), WATCH_MASK)
    if wd < 0:
        err = ctypes.get_errno()
        print(f"inotify_add_watch failed for {trainerlib}: errno={err}", file=sys.stderr)
        os.close(fd)
        return 5

    start_wait = mono()
    pid, cmd = find_resonance_pid()
    while pid is None and mono() - start_wait < args.wait:
        time.sleep(0.10)
        pid, cmd = find_resonance_pid()

    if pid is None:
        print(f"Timed out waiting for Resonance after {args.wait:.0f}s.", file=sys.stderr)
        os.close(fd)
        return 6

    baseline = parse_maps(pid)
    if baseline is None:
        print(f"Could not read /proc/{pid}/maps.", file=sys.stderr)
        os.close(fd)
        return 7

    t0 = mono()
    prev = baseline
    last_threads = thread_count(pid)

    with out.open("w", encoding="utf-8", buffering=1) as log:
        log.write("Wand Native manual-map observer\n")
        log.write(f"wall_start={now_wall()}\n")
        log.write(f"appid={args.appid}\n")
        log.write(f"linux_pid={pid}\n")
        log.write(f"cmdline={cmd}\n")
        log.write(f"trainerlib={trainerlib}\n")
        log.write(f"duration_seconds={args.seconds}\n")
        log.write(f"sample_interval_seconds={args.interval}\n")
        log.write(f"initial_threads={last_threads}\n")
        log.write("\n===== baseline interesting mappings =====\n")
        for addr, rec in sorted(prev.items()):
            if interesting_map(rec):
                log.write(f"MAP_BASE {rec[5]}\n")
        log.write("\n===== live events =====\n")

        while mono() - t0 < args.seconds:
            elapsed = mono() - t0

            # Drain inotify events.
            try:
                while True:
                    data = os.read(fd, 65536)
                    if not data:
                        break
                    off = 0
                    while off + 16 <= len(data):
                        wd_i, mask, cookie, name_len = struct.unpack_from("iIII", data, off)
                        off += 16
                        raw_name = data[off:off + name_len]
                        off += name_len
                        name = raw_name.split(b"\0", 1)[0].decode("utf-8", "replace")
                        names = [label for bit, label in EVENT_NAMES if mask & bit]
                        label = "|".join(names) if names else hex(mask)
                        log.write(
                            f"{elapsed:09.3f} INOTIFY {label} cookie={cookie} name={name}\n"
                        )
            except BlockingIOError:
                pass
            except OSError as exc:
                log.write(f"{elapsed:09.3f} INOTIFY_ERROR {exc}\n")

            cur = parse_maps(pid)
            if cur is None:
                log.write(f"{elapsed:09.3f} PROCESS_GONE pid={pid}\n")
                break

            # New mappings and permission/path changes at the same address range.
            for addr, rec in cur.items():
                old = prev.get(addr)
                if old is None:
                    if interesting_map(rec):
                        log.write(f"{elapsed:09.3f} MAP_ADD {rec[5]}\n")
                elif old != rec:
                    if interesting_map(old) or interesting_map(rec):
                        log.write(f"{elapsed:09.3f} MAP_CHANGE OLD {old[5]}\n")
                        log.write(f"{elapsed:09.3f} MAP_CHANGE NEW {rec[5]}\n")

            for addr, old in prev.items():
                if addr not in cur and interesting_map(old):
                    log.write(f"{elapsed:09.3f} MAP_REMOVE {old[5]}\n")

            threads = thread_count(pid)
            if threads != last_threads:
                log.write(f"{elapsed:09.3f} THREADS {last_threads} -> {threads}\n")
                last_threads = threads

            prev = cur
            time.sleep(max(args.interval, 0.005))

        log.write("\n===== final =====\n")
        log.write(f"wall_end={now_wall()}\n")
        log.write(f"process_alive={pathlib.Path(f'/proc/{pid}').exists()}\n")
        log.write(f"final_threads={thread_count(pid)}\n")

    os.close(fd)
    print(out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
