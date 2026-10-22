#!/usr/bin/env python3
import argparse
import ctypes
import ctypes.util
import hashlib
import os
import pathlib
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime

IN_ACCESS = 0x00000001
IN_CLOSE_NOWRITE = 0x00000010
IN_OPEN = 0x00000020
WATCH_MASK = IN_ACCESS | IN_CLOSE_NOWRITE | IN_OPEN
PAGE = 4096
MIN_DISTINCTIVE_SECTION = 0x10000

TRAINER_DLLS = [
    "tophat_service_x64.dll",
    "TrainerLib_x64.dll",
    "TrainerLibPlugin_x64.dll",
    "CELib_x64.dll",
    "ContractRuntimePlugin_x64.dll",
    "LuaExecutorPlugin_x64.dll",
    "InputCapturePlugin_x64.dll",
]

SIGS = {
    b"MZ": "MZ",
    b"PE\x00\x00": "PE",
    b"BSJB": "CLR_BSJB",
    b".wemod": "WEMOD_SECTION",
    b"TrainerLib": "TRAINERLIB_STRING",
    b"CLRCreateInstance": "CLR_CREATE_INSTANCE",
    b"mscoree": "MSCOREE_STRING",
    b"tophat": "TOPHAT_STRING",
}


class IOVec(ctypes.Structure):
    _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]


def wall():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def align_page(n):
    return (n + PAGE - 1) & ~(PAGE - 1)


def cmdline(pid):
    try:
        data = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
        return data.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except Exception:
        return ""


def find_game():
    hits = []
    for p in pathlib.Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        pid = int(p.name)
        c = cmdline(pid)
        low = c.lower()
        if "resonance.exe" in low or "resonance a plague tale legacy" in low:
            hits.append((pid, c))
    if not hits:
        return None, ""
    hits.sort(reverse=True)
    return hits[0]


def locate_trainerlib(prefix):
    root = pathlib.Path(prefix) / "drive_c" / "users"
    hits = []
    if root.is_dir():
        for p in root.glob("*/AppData/Local/Wand/app-*/resources/app.asar.unpacked/static/unpacked/trainerlib"):
            try:
                hits.append((p.stat().st_mtime_ns, p))
            except OSError:
                pass
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def dependency_pe_paths(prefix):
    """Return a small set of known Wine PE dependencies used as controls.

    The 0.1.36 Resonance capture showed ICU .text mappings that looked like
    anonymous trainer candidates until compared with an earlier Wine loader
    trace. Fingerprinting the prefix copies makes those ordinary PE mappings
    identifiable in future captures without enabling broad loader tracing.
    """
    system32 = pathlib.Path(prefix) / "drive_c" / "windows" / "system32"
    if not system32.is_dir():
        return []
    found = []
    seen = set()
    for pattern in ("icu.dll", "icuin*.dll", "icuuc*.dll", "icudt*.dll"):
        for path in sorted(system32.glob(pattern)):
            key = path.name.lower()
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            found.append(path)
    return found


def parse_pe(path):
    data = path.read_bytes()
    if len(data) < 0x100 or data[:2] != b"MZ":
        return None
    peoff = struct.unpack_from("<I", data, 0x3C)[0]
    if peoff + 0x108 > len(data) or data[peoff:peoff + 4] != b"PE\0\0":
        return None
    machine, nsects = struct.unpack_from("<HH", data, peoff + 4)
    optoff = peoff + 24
    magic = struct.unpack_from("<H", data, optoff)[0]
    if magic == 0x20B:
        entry = struct.unpack_from("<I", data, optoff + 16)[0]
        image_base = struct.unpack_from("<Q", data, optoff + 24)[0]
    elif magic == 0x10B:
        entry = struct.unpack_from("<I", data, optoff + 16)[0]
        image_base = struct.unpack_from("<I", data, optoff + 28)[0]
    else:
        return None
    section_align = struct.unpack_from("<I", data, optoff + 32)[0]
    size_image = struct.unpack_from("<I", data, optoff + 56)[0]
    size_headers = struct.unpack_from("<I", data, optoff + 60)[0]
    opt_size = struct.unpack_from("<H", data, peoff + 20)[0]
    sec_off = optoff + opt_size
    sections = []
    for i in range(nsects):
        off = sec_off + i * 40
        if off + 40 > len(data):
            break
        name = data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        vsize, vaddr, raw_size, raw_off = struct.unpack_from("<IIII", data, off + 8)
        chars = struct.unpack_from("<I", data, off + 36)[0]
        sections.append({
            "index": i,
            "name": name or "<unnamed>",
            "vsize": vsize,
            "aligned_vsize": align_page(vsize),
            "vaddr": vaddr,
            "raw_size": raw_size,
            "raw_off": raw_off,
            "chars": chars,
        })
    return {
        "file_size": len(data),
        "machine": machine,
        "sections": nsects,
        "entry_rva": entry,
        "image_base": image_base,
        "section_alignment": section_align,
        "size_of_image": size_image,
        "size_of_headers": size_headers,
        "section_list": sections,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def maps(pid):
    try:
        lines = pathlib.Path(f"/proc/{pid}/maps").read_text(errors="replace").splitlines()
    except Exception:
        return None
    out = {}
    for line in lines:
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        addr, perms, offset, dev, inode = parts[:5]
        path = parts[5] if len(parts) > 5 else ""
        lo_s, hi_s = addr.split("-", 1)
        lo, hi = int(lo_s, 16), int(hi_s, 16)
        out[(lo, hi)] = {
            "lo": lo, "hi": hi, "size": hi - lo,
            "perms": perms, "offset": offset, "dev": dev,
            "inode": inode, "path": path, "line": line,
        }
    return out


def anonymous(rec):
    # Empty-path mappings are the useful PE/manual-map signal. Named kernel
    # regions such as [heap] and [stack] are intentionally excluded.
    return not rec["path"]


def anon_exec(rec):
    return anonymous(rec) and "x" in rec["perms"]


def thread_count(pid):
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text(errors="replace").splitlines():
            if line.startswith("Threads:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        return None
    return None


def process_state(pid):
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text(errors="replace").splitlines():
            if line.startswith("State:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def task_ids(pid):
    try:
        return {int(ent.name) for ent in pathlib.Path(f"/proc/{pid}/task").iterdir() if ent.name.isdigit()}
    except Exception:
        return set()


def task_info(pid, tid):
    ent = pathlib.Path(f"/proc/{pid}/task/{tid}")
    comm = "?"
    state = "?"
    wchan = "?"
    try:
        comm = (ent / "comm").read_text(errors="replace").strip()
    except Exception:
        pass
    try:
        for line in (ent / "status").read_text(errors="replace").splitlines():
            if line.startswith("State:"):
                state = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    try:
        wchan = (ent / "wchan").read_text(errors="replace").strip() or "0"
    except Exception:
        pass
    return {"comm": comm, "state": state, "wchan": wchan}


def task_snapshot(pid):
    return {tid: task_info(pid, tid) for tid in sorted(task_ids(pid))}


def process_metrics(pid):
    wanted = {"Threads", "VmSize", "VmRSS", "RssAnon", "RssFile", "VmData", "VmExe"}
    out = {}
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text(errors="replace").splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k in wanted:
                out[k] = " ".join(v.strip().split())
    except Exception:
        pass
    return out


def trainer_fd_snapshot(pid, trainerlib):
    hits = {}
    fdroot = pathlib.Path(f"/proc/{pid}/fd")
    try:
        fds = list(fdroot.iterdir())
    except Exception:
        return hits
    trainer_root = str(trainerlib)
    for fdent in fds:
        try:
            target = os.readlink(fdent)
        except OSError:
            continue
        low = target.lower()
        if trainer_root.lower() in low or "/wand/" in low or "trainerlib" in low:
            hits[fdent.name] = target
    return hits


def interesting_map(rec):
    low = rec["path"].lower()
    if anon_exec(rec):
        return True
    needles = ("wand", "trainer", "tophat", "clr", "mscoree", "dotnet", "mono", "icu")
    return any(x in low for x in needles)


def metrics_text(metrics):
    return " ".join(f"{k}={metrics[k]}" for k in sorted(metrics))


def map_line_escaped(line):
    return line.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def yama_scope():
    try:
        return pathlib.Path("/proc/sys/kernel/yama/ptrace_scope").read_text().strip()
    except Exception:
        return "unknown"


def read_mem(pid, addr, length, libc):
    process_vm_readv = getattr(libc, "process_vm_readv", None)
    if process_vm_readv is None:
        return None, "process_vm_readv unavailable"
    process_vm_readv.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(IOVec), ctypes.c_ulong,
        ctypes.POINTER(IOVec), ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    process_vm_readv.restype = ctypes.c_ssize_t
    buf = ctypes.create_string_buffer(length)
    local = IOVec(ctypes.cast(buf, ctypes.c_void_p), length)
    remote = IOVec(ctypes.c_void_p(addr), length)
    ctypes.set_errno(0)
    n = process_vm_readv(pid, ctypes.byref(local), 1, ctypes.byref(remote), 1, 0)
    if n < 0:
        return None, f"errno={ctypes.get_errno()}"
    return bytes(buf.raw[:n]), None


def signatures(blob):
    if not blob:
        return []
    found = []
    for needle, label in SIGS.items():
        pos = blob.find(needle)
        if pos >= 0:
            found.append(f"{label}@0x{pos:x}")
    return found


def image_matches(size, fingerprints):
    exact = []
    near = []
    for name, fp in fingerprints.items():
        img = fp["size_of_image"]
        delta = size - img
        if delta == 0:
            exact.append(name)
        elif abs(delta) <= 0x10000:
            near.append(f"{name}(delta={delta:+d})")
    return exact, near


def section_matches(rec, fingerprints, min_size=MIN_DISTINCTIVE_SECTION):
    out = []
    for module, fp in fingerprints.items():
        for sec in fp["section_list"]:
            if sec["aligned_vsize"] != rec["size"]:
                continue
            if sec["aligned_vsize"] < min_size:
                continue
            out.append({
                "module": module,
                "section_index": sec["index"],
                "section": sec["name"],
                "vaddr": sec["vaddr"],
                "vsize": sec["vsize"],
                "aligned": sec["aligned_vsize"],
                "chars": sec["chars"],
                "base": rec["lo"] - sec["vaddr"],
            })
    return out


def overlap_lines(cur, lo, hi):
    rows = []
    for rec in cur.values():
        if rec["hi"] <= lo or rec["lo"] >= hi:
            continue
        rows.append(rec["line"])
    return sorted(rows, key=lambda x: int(x.split("-", 1)[0], 16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appid", default="2713000")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--wait", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=0.005)
    ap.add_argument("--sample-bytes", type=int, default=131072)
    ap.add_argument("--burst-window", type=float, default=2.5,
                    help="seconds after first trainerlib access to record full map/task deltas")
    ap.add_argument("--burst-recovery-grace", type=float, default=0.75,
                    help="extra seconds after thread count returns to baseline")
    ap.add_argument("--steam-root", default=os.environ.get("WAND_STEAM_ROOT", "/mnt/games/Steam"))
    args = ap.parse_args()

    compat = os.environ.get(
        "WAND_COMPAT_DATA_PATH",
        os.path.join(args.steam_root, "steamapps", "compatdata", args.appid),
    )
    prefix = os.path.join(compat, "pfx")
    trainerlib = locate_trainerlib(prefix)
    if trainerlib is None:
        print(f"Could not find trainerlib under {prefix}", file=sys.stderr)
        return 2

    fingerprints = {}
    fingerprint_kind = {}
    fingerprint_path = {}
    for name in TRAINER_DLLS:
        p = trainerlib / name
        if not p.is_file():
            continue
        try:
            fp = parse_pe(p)
        except Exception:
            fp = None
        if fp:
            fingerprints[name] = fp
            fingerprint_kind[name] = "trainer"
            fingerprint_path[name] = p

    # Known Wine/Proton dependencies are negative controls: if their section
    # geometry explains an anonymous mapping, it should not be treated as
    # evidence that a downstream Wand trainer DLL was manually mapped.
    for p in dependency_pe_paths(prefix):
        name = p.name
        if name in fingerprints:
            continue
        try:
            fp = parse_pe(p)
        except Exception:
            fp = None
        if fp:
            fingerprints[name] = fp
            fingerprint_kind[name] = "dependency-control"
            fingerprint_path[name] = p

    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        print("libc not found", file=sys.stderr)
        return 3
    libc = ctypes.CDLL(libc_name, use_errno=True)

    inotify_init1 = libc.inotify_init1
    inotify_init1.argtypes = [ctypes.c_int]
    inotify_init1.restype = ctypes.c_int
    fd = inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd < 0:
        print(f"inotify_init1 errno={ctypes.get_errno()}", file=sys.stderr)
        return 4
    inotify_add_watch = libc.inotify_add_watch
    inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    inotify_add_watch.restype = ctypes.c_int
    if inotify_add_watch(fd, os.fsencode(trainerlib), WATCH_MASK) < 0:
        print(f"inotify_add_watch errno={ctypes.get_errno()}", file=sys.stderr)
        return 5

    wait_start = time.monotonic()
    pid, game_cmd = find_game()
    while pid is None and time.monotonic() - wait_start < args.wait:
        time.sleep(0.1)
        pid, game_cmd = find_game()
    if pid is None:
        print("Timed out waiting for Resonance.", file=sys.stderr)
        return 6

    prev = maps(pid)
    if prev is None:
        print(f"Could not read /proc/{pid}/maps", file=sys.stderr)
        return 7

    outdir = pathlib.Path.home() / "Desktop"
    if not outdir.is_dir():
        outdir = pathlib.Path.home()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = outdir / f"wand-fingerprint-{args.appid}-{stamp}.txt"

    t0 = time.monotonic()
    trainer_epoch = None
    mem_read_status_logged = False
    sampled_regions = set()
    section_evidence = defaultdict(dict)
    announced_counts = {}
    candidate_snapshots = set()
    last_threads = thread_count(pid)
    last_state = process_state(pid)
    baseline_threads = last_threads
    peak_threads = last_threads or 0
    peak_time = None
    recovery_time = None
    task_prev_ids = task_ids(pid)
    task_info_cache = {tid: task_info(pid, tid) for tid in sorted(task_prev_ids)}
    task_first_seen = {tid: 0.0 for tid in task_prev_ids}
    trainer_fds_prev = {}
    burst_map_events = 0
    burst_task_adds = 0
    burst_task_removes = 0
    burst_baseline_maps = None
    burst_baseline_tasks = None
    burst_snapshot_reasons = set()

    with out.open("w", encoding="utf-8", buffering=1) as log:
        log.write("Wand Native PE section-map fingerprint observer\n")
        log.write(f"wall_start={wall()}\n")
        log.write(f"appid={args.appid}\n")
        log.write(f"linux_pid={pid}\n")
        log.write(f"cmdline={game_cmd}\n")
        log.write(f"trainerlib={trainerlib}\n")
        log.write(f"interval_seconds={args.interval}\n")
        log.write(f"sample_bytes={args.sample_bytes}\n")
        log.write(f"burst_window_seconds={args.burst_window}\n")
        log.write(f"burst_recovery_grace_seconds={args.burst_recovery_grace}\n")
        log.write(f"yama_ptrace_scope={yama_scope()}\n")
        log.write(f"initial_threads={last_threads if last_threads is not None else 'unknown'}\n")
        log.write(f"initial_state={last_state or 'unknown'}\n\n")

        log.write("===== PE fingerprints =====\n")
        for name, fp in fingerprints.items():
            log.write(
                f"PE {name} kind={fingerprint_kind.get(name, 'unknown')} "
                f"file_size={fp['file_size']} size_of_image={fp['size_of_image']} "
                f"entry_rva=0x{fp['entry_rva']:x} image_base=0x{fp['image_base']:x} "
                f"sections={fp['sections']} sha256={fp['sha256']} "
                f"source={fingerprint_path.get(name, '')}\n"
            )
            for s in fp["section_list"]:
                log.write(
                    f"  SECTION {name} {s['name']} vaddr=0x{s['vaddr']:x} "
                    f"vsize={s['vsize']} aligned_vsize={s['aligned_vsize']} "
                    f"raw_size={s['raw_size']} chars=0x{s['chars']:08x}\n"
                )

        log.write("\n===== live events =====\n")
        while time.monotonic() - t0 < args.seconds:
            elapsed = time.monotonic() - t0

            try:
                while True:
                    data = os.read(fd, 65536)
                    if not data:
                        break
                    off = 0
                    while off + 16 <= len(data):
                        _, mask, cookie, nlen = struct.unpack_from("iIII", data, off)
                        off += 16
                        raw = data[off:off + nlen]
                        off += nlen
                        name = raw.split(b"\0", 1)[0].decode("utf-8", "replace")
                        if not name or name not in TRAINER_DLLS:
                            continue
                        labels = []
                        if mask & IN_OPEN:
                            labels.append("OPEN")
                        if mask & IN_ACCESS:
                            labels.append("ACCESS")
                        if mask & IN_CLOSE_NOWRITE:
                            labels.append("CLOSE_NOWRITE")
                        if trainer_epoch is None:
                            trainer_epoch = elapsed
                            burst_baseline_maps = dict(prev)
                            burst_baseline_tasks = set(task_prev_ids)
                            baseline_threads = len(task_prev_ids) if task_prev_ids else last_threads
                            peak_threads = baseline_threads or 0
                            log.write(f"{elapsed:09.3f} TRAINER_EPOCH first={name} baseline_threads={baseline_threads if baseline_threads is not None else '?'}\n")
                            log.write(f"{elapsed:09.3f} BURST_METRICS reason=epoch {metrics_text(process_metrics(pid))}\n")
                            for rec0 in sorted(prev.values(), key=lambda r: r['lo']):
                                if interesting_map(rec0):
                                    log.write(f"{elapsed:09.3f} BURST_MAP_SNAPSHOT reason=epoch {map_line_escaped(rec0['line'])}\n")
                        log.write(f"{elapsed:09.3f} FILE {'|'.join(labels)} name={name}\n")
            except BlockingIOError:
                pass
            except OSError as exc:
                log.write(f"{elapsed:09.3f} INOTIFY_ERROR {exc}\n")

            cur = maps(pid)
            if cur is None:
                log.write(f"{elapsed:09.3f} PROCESS_GONE\n")
                break

            burst_active = (
                trainer_epoch is not None and
                elapsed <= trainer_epoch + args.burst_window + args.burst_recovery_grace
            )

            task_cur_ids = task_ids(pid)
            if trainer_epoch is not None:
                added_tids = sorted(task_cur_ids - task_prev_ids)
                removed_tids = sorted(task_prev_ids - task_cur_ids)
                for tid in added_tids:
                    info = task_info(pid, tid)
                    task_info_cache[tid] = info
                    task_first_seen[tid] = elapsed
                    burst_task_adds += 1
                    log.write(
                        f"{elapsed:09.3f} THREAD_ADD tid={tid} comm={info['comm']!r} "
                        f"state={info['state']!r} wchan={info['wchan']!r}\n"
                    )
                for tid in removed_tids:
                    info = task_info_cache.get(tid, {"comm": "?", "state": "?", "wchan": "?"})
                    born = task_first_seen.get(tid)
                    life = "unknown" if born is None else f"{max(0.0, elapsed-born):.3f}"
                    burst_task_removes += 1
                    log.write(
                        f"{elapsed:09.3f} THREAD_REMOVE tid={tid} comm={info['comm']!r} "
                        f"last_state={info['state']!r} lifetime={life}\n"
                    )

                trainer_fds = trainer_fd_snapshot(pid, trainerlib)
                for fdno, target in sorted(trainer_fds.items()):
                    if trainer_fds_prev.get(fdno) != target:
                        log.write(f"{elapsed:09.3f} TRAINER_FD_OPEN fd={fdno} target={target}\n")
                for fdno, target in sorted(trainer_fds_prev.items()):
                    if fdno not in trainer_fds:
                        log.write(f"{elapsed:09.3f} TRAINER_FD_CLOSE fd={fdno} target={target}\n")
                trainer_fds_prev = trainer_fds

                if burst_active:
                    # Record every VMA delta during the short trainer-init window.
                    # This deliberately includes file-backed mappings and anonymous
                    # non-executable staging regions that 0.1.37 omitted.
                    for key2, rec2 in sorted(cur.items(), key=lambda kv: kv[1]['lo']):
                        old2 = prev.get(key2)
                        if old2 is None:
                            burst_map_events += 1
                            log.write(f"{elapsed:09.3f} BURST_MAP_ADD {map_line_escaped(rec2['line'])}\n")
                        elif old2['perms'] != rec2['perms'] or old2['path'] != rec2['path']:
                            burst_map_events += 1
                            log.write(
                                f"{elapsed:09.3f} BURST_MAP_CHANGE old_perms={old2['perms']} "
                                f"old_path={old2['path']!r} new={map_line_escaped(rec2['line'])}\n"
                            )
                    for key2, rec2 in sorted(prev.items(), key=lambda kv: kv[1]['lo']):
                        if key2 not in cur:
                            burst_map_events += 1
                            log.write(f"{elapsed:09.3f} BURST_MAP_REMOVE {map_line_escaped(rec2['line'])}\n")

            threads = len(task_cur_ids) if task_cur_ids else thread_count(pid)
            if threads is not None and threads > peak_threads:
                peak_threads = threads
                peak_time = elapsed
                if trainer_epoch is not None:
                    log.write(f"{elapsed:09.3f} BURST_PEAK threads={threads} delta={threads-(baseline_threads or 0)}\n")
                    log.write(f"{elapsed:09.3f} BURST_METRICS reason=peak {metrics_text(process_metrics(pid))}\n")
                    # Only emit interesting mappings at each new peak to bound output.
                    for rec0 in sorted(cur.values(), key=lambda r: r['lo']):
                        if interesting_map(rec0):
                            log.write(f"{elapsed:09.3f} BURST_MAP_SNAPSHOT reason=peak {map_line_escaped(rec0['line'])}\n")

            if (trainer_epoch is not None and recovery_time is None and
                    baseline_threads is not None and peak_threads > baseline_threads and
                    threads is not None and threads <= baseline_threads and
                    elapsed > trainer_epoch):
                recovery_time = elapsed
                log.write(
                    f"{elapsed:09.3f} BURST_RECOVERED threads={threads} "
                    f"peak={peak_threads} duration={elapsed-trainer_epoch:.3f}\n"
                )
                log.write(f"{elapsed:09.3f} BURST_METRICS reason=recovered {metrics_text(process_metrics(pid))}\n")
                for rec0 in sorted(cur.values(), key=lambda r: r['lo']):
                    if interesting_map(rec0):
                        log.write(f"{elapsed:09.3f} BURST_MAP_SNAPSHOT reason=recovered {map_line_escaped(rec0['line'])}\n")

            threads = thread_count(pid)
            if threads != last_threads:
                log.write(
                    f"{elapsed:09.3f} THREADS "
                    f"{last_threads if last_threads is not None else '?'}->"
                    f"{threads if threads is not None else '?'}\n"
                )
                last_threads = threads
            state = process_state(pid)
            if state != last_state:
                log.write(f"{elapsed:09.3f} STATE {last_state or '?'}->{state or '?'}\n")
                last_state = state

            for key, rec in cur.items():
                old = prev.get(key)
                changed = old is None or old["perms"] != rec["perms"] or old["path"] != rec["path"]
                if not changed or not anonymous(rec):
                    continue

                exact_img, near_img = image_matches(rec["size"], fingerprints)
                sec_matches = section_matches(rec, fingerprints)
                match_text = ""
                if exact_img:
                    match_text += " exact_image=" + ",".join(exact_img)
                if near_img:
                    match_text += " near_image=" + ",".join(near_img)

                if anon_exec(rec):
                    event_kind = "ANON_EXEC_ADD" if old is None else "ANON_EXEC_CHANGE"
                    old_text = "" if old is None else f" old_perms={old['perms']}"
                    log.write(
                        f"{elapsed:09.3f} {event_kind} range=0x{rec['lo']:x}-0x{rec['hi']:x} "
                        f"size={rec['size']} perms={rec['perms']}{old_text}{match_text}\n"
                    )
                elif sec_matches:
                    event_kind = "ANON_SECTION_ADD" if old is None else "ANON_SECTION_CHANGE"
                    old_text = "" if old is None else f" old_perms={old['perms']}"
                    log.write(
                        f"{elapsed:09.3f} {event_kind} range=0x{rec['lo']:x}-0x{rec['hi']:x} "
                        f"size={rec['size']} perms={rec['perms']}{old_text}\n"
                    )

                for sm in sec_matches:
                    key2 = (sm["module"], sm["base"])
                    evidence_key = sm["section_index"]
                    section_evidence[key2].setdefault(evidence_key, {
                        **sm, "time": elapsed, "perms": rec["perms"],
                        "range": (rec["lo"], rec["hi"]),
                    })
                    log.write(
                        f"{elapsed:09.3f} SECTION_MATCH module={sm['module']} kind={fingerprint_kind.get(sm['module'], 'unknown')} "
                        f"section={sm['section']} index={sm['section_index']} "
                        f"vaddr=0x{sm['vaddr']:x} base=0x{sm['base']:x} "
                        f"map_size={rec['size']} perms={rec['perms']}\n"
                    )

                    count = len(section_evidence[key2])
                    previous_count = announced_counts.get(key2, 0)
                    if count >= 2 and count > previous_count:
                        announced_counts[key2] = count
                        entries = section_evidence[key2]
                        total = sum(x["aligned"] for x in entries.values())
                        detail = ",".join(
                            f"{x['section']}@0x{x['vaddr']:x}"
                            for _, x in sorted(entries.items())
                        )
                        log.write(
                            f"{elapsed:09.3f} MODULE_SECTION_MATCH module={sm['module']} kind={fingerprint_kind.get(sm['module'], 'unknown')} "
                            f"base=0x{sm['base']:x} sections={count} "
                            f"matched_bytes={total} detail={detail}\n"
                        )

                        snap_key = (sm["module"], sm["base"], count)
                        if snap_key not in candidate_snapshots:
                            candidate_snapshots.add(snap_key)
                            fp = fingerprints[sm["module"]]
                            image_lo = sm["base"]
                            image_hi = sm["base"] + fp["size_of_image"]
                            log.write(
                                f"{elapsed:09.3f} MODULE_MAP_BEGIN module={sm['module']} "
                                f"base=0x{image_lo:x} end=0x{image_hi:x}\n"
                            )
                            for row in overlap_lines(cur, image_lo, image_hi):
                                log.write(f"{elapsed:09.3f} MODULE_MAP {row}\n")
                            log.write(
                                f"{elapsed:09.3f} MODULE_MAP_END module={sm['module']}\n"
                            )

                if anon_exec(rec):
                    regkey = (rec["lo"], rec["hi"], rec["perms"])
                    if regkey not in sampled_regions:
                        sampled_regions.add(regkey)
                        length = min(args.sample_bytes, rec["size"])
                        blob, err = read_mem(pid, rec["lo"], length, libc)
                        if blob is None:
                            if not mem_read_status_logged:
                                log.write(
                                    f"{elapsed:09.3f} MEM_SAMPLE_UNAVAILABLE {err} "
                                    f"yama_ptrace_scope={yama_scope()}\n"
                                )
                                mem_read_status_logged = True
                        else:
                            sig = signatures(blob)
                            digest = hashlib.sha256(blob).hexdigest()
                            log.write(
                                f"{elapsed:09.3f} MEM_SAMPLE range=0x{rec['lo']:x}-0x{rec['hi']:x} "
                                f"bytes={len(blob)} sha256={digest} "
                                f"signatures={','.join(sig) if sig else 'none'}\n"
                            )

                if old is not None and old["perms"] != rec["perms"]:
                    if (("w" in old["perms"] and "x" in rec["perms"]) or
                            ("x" in old["perms"] and "w" in rec["perms"])):
                        log.write(
                            f"{elapsed:09.3f} EXEC_PERM_CHANGE range=0x{rec['lo']:x}-0x{rec['hi']:x} "
                            f"size={rec['size']} {old['perms']}->{rec['perms']}\n"
                        )

            prev = cur
            task_prev_ids = task_cur_ids
            time.sleep(max(args.interval, 0.001))

        log.write("\n===== trainer-init burst summary =====\n")
        log.write(f"baseline_threads={baseline_threads if baseline_threads is not None else 'unknown'}\n")
        log.write(f"peak_threads={peak_threads}\n")
        log.write(f"peak_time={peak_time if peak_time is not None else 'not-seen'}\n")
        log.write(f"recovery_time={recovery_time if recovery_time is not None else 'not-seen'}\n")
        log.write(f"thread_add_events={burst_task_adds}\n")
        log.write(f"thread_remove_events={burst_task_removes}\n")
        log.write(f"burst_map_events={burst_map_events}\n")

        log.write("\n===== section-match summary =====\n")
        ranked = []
        for (module, base), entries in section_evidence.items():
            if len(entries) < 2:
                continue
            ranked.append((len(entries), sum(x["aligned"] for x in entries.values()), module, base, entries))
        ranked.sort(reverse=True)
        if not ranked:
            log.write("NONE\n")
        for count, total, module, base, entries in ranked:
            detail = ",".join(
                f"{x['section']}@0x{x['vaddr']:x}" for _, x in sorted(entries.items())
            )
            log.write(
                f"MODULE_SECTION_MATCH module={module} kind={fingerprint_kind.get(module, 'unknown')} base=0x{base:x} "
                f"sections={count} matched_bytes={total} detail={detail}\n"
            )

        log.write("\n===== final =====\n")
        log.write(f"wall_end={wall()}\n")
        log.write(f"trainer_epoch={trainer_epoch if trainer_epoch is not None else 'not-seen'}\n")
        log.write(f"process_alive={pathlib.Path(f'/proc/{pid}').exists()}\n")
        log.write(f"final_threads={thread_count(pid) if pathlib.Path(f'/proc/{pid}').exists() else 'gone'}\n")
        log.write(f"final_state={process_state(pid) if pathlib.Path(f'/proc/{pid}').exists() else 'gone'}\n")

    os.close(fd)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
