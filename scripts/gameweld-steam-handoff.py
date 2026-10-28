#!/usr/bin/env python3
"""PC2 Steam game-only launch handoff with truthful, read-only result reporting.

GameWeld validates the installed game with its own source backend and asks for
explicit user confirmation BEFORE invoking this helper. No trainer, compatibility
patch, launch options, or Wine prefix are ever modified here.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import stat
import shutil
import subprocess
import sys
import threading
import tempfile
import time

KEYS = ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")
MAX_PROC = 8192
MAX_ENV = 128 * 1024
OBSERVE_SECONDS = 12



# Steam's own client logs can reveal whether it began a launch, even when a
# game process exits too quickly to be seen in a /proc polling interval.
# Never print raw Steam log lines: they may include user paths or launch tokens.
LOG_NAMES = ("gameprocess_log.txt", "console_log.txt", "console-linux.txt")
LOG_READ_CAP = 256 * 1024
LOG_MATCH_CAP = 1000


def steam_log_dir(steam_root: pathlib.Path | None = None) -> pathlib.Path | None:
    choices = []
    if steam_root is not None:
        choices.append(steam_root)
    home = pathlib.Path.home()
    choices.extend((
        home / ".steam/steam",
        home / ".steam/root",
        home / ".local/share/Steam",
    ))
    visited = set()
    for choice in choices:
        try:
            canonical = choice.resolve(strict=True)
            if str(canonical) in visited:
                continue
            visited.add(str(canonical))
            logs = canonical / "logs"
            if logs.is_dir() and not logs.is_symlink():
                return logs
        except OSError:
            continue
    return None


def _log_identity(path: pathlib.Path) -> tuple[int, int, int] | None:
    try:
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_size < 0:
            return None
        return (meta.st_dev, meta.st_ino, meta.st_size)
    except OSError:
        return None


def _steam_event_kind(line: str, appid: str) -> str | None:
    # Exact AppID token, rather than matching another application's ID as
    # a substring; do not echo any part of an untrusted log line.
    id_pattern = rf"(?:\bAppID\s*[=: ]\s*|\bApp ID\s*[=: ]\s*|\bappid\s*[=: ]\s*){re.escape(appid)}(?!\d)"
    url_pattern = rf"\b(?:rungameid|launch)/{re.escape(appid)}(?!\d)"
    if not (re.search(id_pattern, line, re.IGNORECASE) or
            re.search(url_pattern, line, re.IGNORECASE)):
        return None
    lower = line.lower()
    if "game process added" in lower:
        return "process_added"
    if "game process removed" in lower:
        return "process_removed"
    if "game process updated" in lower:
        return "process_updated"
    if "already running" in lower or "already active" in lower:
        return "already_running"
    if "failed" in lower or "error" in lower:
        return "possible_error"
    if "gameaction" in lower or "launchapp" in lower:
        return "launch_action"
    if "rungameid/" in lower or "executesteamurl" in lower:
        return "url_request"
    return "other"


class SteamLogProbe:
    """Read-only summary of newly appended Steam client log events.

    Opening the log does not modify Steam settings, trigger a game, or read
    any user credential store. Any rotation, truncation, inaccessible file, or
    change of inode remains inconclusive.
    """

    def __init__(self, steam_root: pathlib.Path | None = None):
        self.directory = steam_log_dir(steam_root)
        self.before = {
            name: _log_identity(self.directory / name) if self.directory else None
            for name in LOG_NAMES
        }

    def summary(self, appid: str, *, historical: bool = False) -> list[str]:
        if self.directory is None:
            return ["Steam client logs: not located (status --steam-root may help)."]
        output = []
        available = 0
        matched = 0
        for name in LOG_NAMES:
            path = self.directory / name
            identity = _log_identity(path)
            if identity is None:
                continue
            available += 1
            previous = self.before.get(name)
            if not historical and (previous is None or identity[:2] != previous[:2]
                                   or identity[2] < previous[2]):
                output.append(f"Steam log {name}: changed/rotated; inconclusive.")
                continue
            start = max(0, identity[2] - LOG_READ_CAP) if historical else previous[2]
            # If the append exceeds the bounded window, we cannot claim to
            # have observed every event.
            if identity[2] - start > LOG_READ_CAP:
                start = identity[2] - LOG_READ_CAP
                output.append(f"Steam log {name}: appended data exceeded safety window.")
            try:
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(path, flags)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        continue
                    stream.seek(start - 1 if start else 0)
                    previous_byte = stream.read(1) if start else b"\n"
                    stream.seek(start)
                    data = stream.read(LOG_READ_CAP)
            except OSError:
                output.append(f"Steam log {name}: unreadable; inconclusive.")
                continue
            if start and previous_byte != b"\n":
                first_break = data.find(b"\n")
                data = data[first_break + 1:] if first_break >= 0 else b""
            kinds = {}
            for raw in data.splitlines()[-LOG_MATCH_CAP:]:
                kind = _steam_event_kind(raw.decode("utf-8", "replace"), appid)
                if kind:
                    kinds[kind] = kinds.get(kind, 0) + 1
            if kinds:
                matched += sum(kinds.values())
                labels = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
                output.append(f"Steam log {name} AppID events: {labels}.")
        if available == 0:
            return ["Steam client logs: no supported log files readable."]
        if matched == 0:
            output.append(
                "Steam log AppID activity: none observed in the inspected window "
                "(NOT proof Steam ignored the request)."
            )
        output.append("Steam logs are diagnostic only; no game process or trainer is verified.")
        return output


def valid_appid(text: str) -> bool:
    return (
        text.isascii() and text.isdecimal() and not text.startswith("0")
        and len(text) <= 10 and 0 < int(text) < 2**32
    )



def _verified_game_dir(appid: str, requested: pathlib.Path | None) -> pathlib.Path | None:
    """Accept only a manifest-backed installed Steam title, not arbitrary paths."""
    if requested is None or not requested.is_absolute() or requested.is_symlink():
        return None
    try:
        game_dir = requested.resolve(strict=True)
        apps = game_dir.parent.parent
        if (game_dir.parent.name != "common" or apps.name != "steamapps"
                or not game_dir.is_dir()):
            return None
        manifest = apps / f"appmanifest_{appid}.acf"
        if not manifest.is_file() or manifest.is_symlink():
            return None
        return game_dir
    except (OSError, ValueError):
        return None


def game_session_lifecycle(appid: str, install_dir: pathlib.Path | None,
                           *, root: str = "/proc") -> dict[str, object]:
    """Read-only assessment of game/WeMod processes at a single instant.

    A lingering WeMod process must not be interpreted as an active game.
    Absence of on-disk game evidence is inconclusive, not proof of exit.
    Nothing is killed, reaped, or modified by this inspector.
    """
    game = observed_game_executable_pids(appid, install_dir, root=root)
    blockers, client_count = associated_non_client_processes(appid, root=root)
    associated = associated_processes(appid, root=root)
    return {
        "steam_appid": appid,
        "game_executable_candidates": len(game),
        "wemod_only_wine_clients": client_count,
        "other_appid_associated_processes": len(blockers),
        "total_appid_associated_processes": len(associated),
        "game_closed_verified": False,
        "game_process_detection_conclusive": False,
    }


def print_game_lifecycle(report: dict[str, object]) -> None:
    print("Read-only game executable candidates in selected Steam install: "
          + str(report["game_executable_candidates"]), flush=True)
    print("WeMod-only Wine clients associated with AppID: "
          + str(report["wemod_only_wine_clients"]), flush=True)
    print("Other AppID-associated processes: "
          + str(report["other_appid_associated_processes"]), flush=True)
    if (report["game_executable_candidates"] == 0 and
            report["wemod_only_wine_clients"]):
        print("Lifecycle assessment: WeMod is present but game EXE was not "
              "verified. This can remain after closing the game.", flush=True)
    elif report["game_executable_candidates"]:
        print("Lifecycle assessment: a selected-game EXE was observed; do not "
              "terminate its Wine session.", flush=True)
    else:
        print("Lifecycle assessment: no selected-game EXE verified; "
              "game closure remains UNCONFIRMED.", flush=True)
    print("No process was terminated or modified.", flush=True)


def _process_game_target(tokens: list[bytes], cwd: pathlib.Path | None,
                         install_dir: pathlib.Path) -> bool:
    """Verify a concrete on-disk Windows EXE in the selected game directory.

    Do not guess from AppID environment tokens, short Windows executable names
    or arbitrary extra arguments. A Wine process may share the AppID with WeMod.
    """
    if len(tokens) < 2:
        return False
    for raw in tokens[:3]:
        if not raw or len(raw) > 2048:
            continue
        name = raw.decode("utf-8", "replace").strip(" \t\"'")
        if not name.lower().endswith(".exe") or "\x00" in name:
            continue
        base = pathlib.PureWindowsPath(name).name.lower()
        if base in ("wemod.exe", "services.exe", "explorer.exe",
                    "conhost.exe", "winedevice.exe", "rpcss.exe",
                    "plugplay.exe", "cmd.exe", "rundll32.exe"):
            continue
        candidate = None
        if name.startswith("/"):
            candidate = pathlib.Path(name)
        elif len(name) >= 3 and name[:3].lower() == "z:\\":
            candidate = pathlib.Path("/" + name[3:].replace("\\", "/"))
        elif "\\" not in name and "/" not in name and cwd is not None:
            candidate = cwd / name
        if candidate is None:
            continue
        try:
            actual = candidate.resolve(strict=True)
            if (actual.is_file() and actual != install_dir and
                    install_dir in actual.parents):
                return True
        except (OSError, ValueError):
            continue
    return False


def observed_game_executable_pids(appid: str, install_dir: pathlib.Path | None,
                                  root: str = "/proc") -> set[int]:
    """Same-UID on-disk Steam game EXE evidence; no process contents reported."""
    selected = _verified_game_dir(appid, install_dir)
    if selected is None:
        return set()
    found = set()
    try:
        entries = os.scandir(root)
    except OSError:
        return set()
    count = 0
    with entries:
        for item in entries:
            if not item.name.isascii() or not item.name.isdecimal():
                continue
            count += 1
            if count > MAX_PROC:
                break
            process = pathlib.Path(item.path)
            try:
                if process.stat().st_uid != os.getuid():
                    continue
                with (process / "cmdline").open("rb") as stream:
                    data = stream.read(8193)
                if not data or len(data) > 8192 or not data.endswith(b"\0"):
                    continue
                cwd = None
                try:
                    cwd = (process / "cwd").resolve(strict=True)
                except OSError:
                    pass
                if _process_game_target(data.split(b"\0"), cwd, selected):
                    found.add(int(item.name))
            except (OSError, ValueError):
                continue
    return found

def associated_processes(appid: str, root: str = "/proc") -> list[pathlib.Path]:
    """Return same-user PIDs with exact AppID environment tokens; no guessing.

    Never expose a process's full environment or command line. The result is
    only an association, not proof that the game executable is running.
    """
    if not valid_appid(appid):
        return []
    found = []
    examined = 0
    expected = {(key + "=" + appid).encode() for key in KEYS}
    try:
        entries = os.scandir(root)
    except OSError:
        return []
    with entries:
        for item in entries:
            if not item.name.isascii() or not item.name.isdecimal():
                continue
            examined += 1
            if examined > MAX_PROC:
                break
            path = pathlib.Path(item.path)
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                with (path / "environ").open("rb") as stream:
                    env = stream.read(MAX_ENV + 1)
                if len(env) > MAX_ENV:
                    continue
                if expected.intersection(env.split(b"\0")):
                    found.append(path)
            except OSError:
                # Missing/exiting/unreadable process: cannot infer identity.
                continue
    return found


def associated_process_count(appid: str, root: str = "/proc") -> int:
    return len(associated_processes(appid, root))


def _safe_process_basename(text: str, *, path: bool = False) -> str:
    name = text.strip().removesuffix(" (deleted)")
    if path:
        name = os.path.basename(name)
    if not name or len(name) > 80:
        return "unavailable"
    if all(ch.isascii() and (ch.isalnum() or ch in "._+-") for ch in name):
        return name
    return "redacted"


def associated_process_details(appid: str, root: str = "/proc") -> list[tuple[int, str, str, str]]:
    """Read-only, redacted process roles; classification is NOT game proof."""
    records = []
    for directory in associated_processes(appid, root):
        try:
            pid = int(directory.name)
            comm = _safe_process_basename((directory / "comm").read_text()[:128])
        except (OSError, ValueError):
            comm = "unavailable"
            try:
                pid = int(directory.name)
            except ValueError:
                continue
        try:
            executable = _safe_process_basename(os.readlink(directory / "exe"), path=True)
        except OSError:
            executable = "unavailable"
        names = (comm + " " + executable).lower()
        if any(part in names for part in (
                "steamwebhelper", "steam-runtime", "steamservice",
                "pressure-vessel", "reaper")):
            role = "steam_helper"
        elif comm.lower().endswith(".exe") and not any(
                name in names for name in (
                    "services.exe", "explorer.exe", "conhost.exe",
                    "winedevice.exe", "rpcss.exe", "plugplay.exe")):
            role = "windows_executable_candidate"
        elif any(part in names for part in (
                "wineserver", "services.exe", "explorer.exe", "conhost.exe",
                "winedevice.exe", "rpcss.exe", "plugplay.exe")):
            role = "wine_runtime"
        elif "wine64" in names or "wine-preloader" in names:
            # A wine64-preloader can HOST a game executable. Its own
            # executable name cannot distinguish game from runtime.
            role = "wine_loader_ambiguous"
        else:
            role = "other_associated"
        records.append((pid, comm, executable, role))
    return sorted(records)


def associated_process_context(appid: str, pid: int, root: str = "/proc") -> tuple[str, str, str]:
    """Return only PPID, one-letter state and a safe Windows EXE basename hint.

    Read access is restricted to the exact-AppID, same-UID process set.
    This remains untrusted diagnostic evidence, NOT a permission to launch.
    """
    if pid <= 0 or pid not in {
            int(directory.name) for directory in associated_processes(appid, root)}:
        return ("unavailable", "?", "unavailable")
    directory = pathlib.Path(root) / str(pid)
    parent = "unavailable"
    state = "?"
    try:
        with (directory / "status").open("rb") as stream:
            raw = stream.read(8193)
        if len(raw) <= 8192:
            for line in raw.splitlines():
                if line.startswith(b"PPid:"):
                    candidate = line.partition(b":")[2].strip()
                    if candidate.isascii() and candidate.isdigit():
                        parent = candidate.decode("ascii")
                elif line.startswith(b"State:"):
                    candidate = line.partition(b":")[2].strip()[:1]
                    if candidate in (b"R", b"S", b"D", b"T", b"t",
                                     b"Z", b"X", b"I"):
                        state = candidate.decode("ascii")
    except OSError:
        pass

    hint = "unavailable"
    try:
        with (directory / "cmdline").open("rb") as stream:
            raw = stream.read(8193)
        if len(raw) <= 8192:
            for token in raw.split(b"\0")[:48]:
                if not token or len(token) > 1024:
                    continue
                # Windows paths can use backslashes; never print the path
                # or any other argument, even when it resembles an EXE.
                value = token.decode("utf-8", "replace").strip(' "\'')
                name = pathlib.PureWindowsPath(value).name
                if not name.lower().endswith(".exe"):
                    continue
                safe = _safe_process_basename(name)
                if safe in ("redacted", "unavailable"):
                    continue
                if safe.lower() in (
                        "services.exe", "explorer.exe", "conhost.exe",
                        "winedevice.exe", "rpcss.exe", "plugplay.exe"):
                    continue
                hint = safe
                break
    except OSError:
        pass
    return (parent, state, hint)


def recognizable_wemod_client_only(directory: pathlib.Path) -> bool:
    """Conservatively recognize a Wine loader running ONLY WeMod.exe.

    This permits a *Steam game-only* request in the presence of an already
    running client; it does not verify WeMod attachment or allow direct Proton
    or prefix changes. Fail closed on missing, truncated or ambiguous data.
    """
    try:
        comm = (directory / "comm").read_bytes()
        if len(comm) > 128 or comm.strip().lower() not in (
                b"wine64", b"wine64-preloader", b"wemod.exe"):
            return False
        exe = os.path.basename(os.readlink(directory / "exe")).lower()
        if exe not in ("wine64", "wine64-preloader"):
            return False
        with (directory / "cmdline").open("rb") as stream:
            raw = stream.read(8193)
        if not raw or len(raw) > 8192 or not raw.endswith(b"\0"):
            return False
        executable_names = []
        for token in raw.split(b"\0"):
            if not token:
                continue
            if len(token) > 1024:
                return False
            decoded = token.decode("utf-8", "replace").strip(' "\'')
            name = pathlib.PureWindowsPath(decoded).name.lower()
            if name.endswith(".exe"):
                if _safe_process_basename(name) in ("redacted", "unavailable"):
                    return False
                executable_names.append(name)
        return executable_names == ["wemod.exe"]
    except (OSError, UnicodeError):
        return False


def associated_non_client_processes(
        appid: str, root: str = "/proc") -> tuple[list[pathlib.Path], int]:
    """An exact AppID Wine/WeMod client alone does not make a game active.

    All uncertain processes remain blockers. A client exemption is explicitly
    limited to Steam-managed game-only launches with the idle-before-launch gate.
    """
    blocking = []
    client_count = 0
    for directory in associated_processes(appid, root):
        if recognizable_wemod_client_only(directory):
            client_count += 1
        else:
            blocking.append(directory)
    return blocking, client_count


def run_launch(appid: str, *, steam: str | None = None,
               duration: float = OBSERVE_SECONDS,
               require_idle_before_launch: bool = False,
               transport: str = "applaunch",
               steam_root: pathlib.Path | None = None,
               install_dir: pathlib.Path | None = None) -> int:
    if transport not in ("applaunch", "steam-uri"):
        print("Launch result: FAILED (unsupported Steam transport).", flush=True)
        return 3
    executable = steam or shutil.which("xdg-open" if transport == "steam-uri" else "steam")
    if not executable:
        print("Steam executable: NOT FOUND on GameWeld's PATH.", flush=True)
        print("Launch result: FAILED (Steam command unavailable).", flush=True)
        return 3
    print("Steam executable: FOUND", flush=True)
    print("Steam launch transport: " + transport, flush=True)
    log_probe = SteamLogProbe(steam_root)
    previous = associated_process_count(appid)
    game_before = observed_game_executable_pids(appid, install_dir)
    if game_before and require_idle_before_launch:
        print("Launch result: FAILED (selected Steam game's executable is already present).", flush=True)
        print("Existing on-disk game executable evidence: found; not launching a duplicate.", flush=True)
        return 3
    if previous:
        print(f"Steam app-ID associated processes BEFORE launch: {previous}", flush=True)
    if require_idle_before_launch and previous:
        blockers, clients = associated_non_client_processes(appid)
        if clients:
            print(f"Recognized existing WeMod-only Wine client(s): {clients}. "
                  "This is NOT proof of trainer attachment.", flush=True)
        if blockers:
            blocking_pids = {int(directory.name) for directory in blockers}
            for pid, comm, executable, role in associated_process_details(appid):
                if pid not in blocking_pids:
                    continue
                parent, state, target = associated_process_context(appid, pid)
                print(f"Blocking AppID association: PID={pid} role={role} "
                      f"comm={comm} executable={executable} PPID={parent} "
                      f"state={state} windows_target_hint={target}", flush=True)
            print("Launch result: FAILED (unverified non-WeMod process associated "
                  "with this Steam AppID).", flush=True)
            print("The game may already be running. No duplicate request sent.", flush=True)
            return 3
        if clients == 0:
            # A process exited or changed during inspection. Never assert an
            # idle game based on a vanished or unreadable association.
            print("Launch result: FAILED (AppID association changed during "
                  "preflight; retry after checking Steam status).", flush=True)
            return 3
        # Rescan immediately before the Steam command. An uncertain newcomer
        # must not be ignored because the first observation saw WeMod only.
        blockers_again, clients_again = associated_non_client_processes(appid)
        if blockers_again or clients_again != clients:
            print("Launch result: FAILED (AppID process evidence changed "
                  "during preflight; no Steam request sent).", flush=True)
            return 3
    # The running Steam client may accept IPC and return immediately; stdout
    # therefore goes to an ephemeral file, not a pipe that keeps GameWeld
    # waiting forever because a game inherited the file descriptor.
    try:
        with tempfile.TemporaryFile(mode="w+b") as output:
            # A Steam URI is a separate, manually selected retry path, never
            # an automatic second launch after an unconfirmed first request.
            argv = ([executable, "steam://rungameid/" + appid]
                    if transport == "steam-uri" else
                    [executable, "-applaunch", appid])
            # Do not pass GameWeld's temporary source-AppDir and test flags
            # into Steam. Keep DISPLAY, WAYLAND_DISPLAY, DBUS and normal
            # desktop environment so Steam IPC/URL handlers still work.
            child_env = {key: value for key, value in os.environ.items()
                         if key not in ("APPDIR", "WAND_NATIVE_BACKEND")
                         and not key.startswith("GAMEWELD_PC2_")
                         and not key.startswith("GAMEWELD_NATIVE_")}
            child = subprocess.Popen(
                argv, env=child_env,
                stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            try:
                print("Steam " + transport + " command: STARTED", flush=True)
                deadline = time.monotonic() + max(0, duration)
                associated_only_observed = False
                while True:
                    status = child.poll()
                    if status is not None and status != 0:
                        print(f"Steam command exit status: {status}", flush=True)
                        print("Launch result: FAILED (Steam command returned an error).", flush=True)
                        for note in log_probe.summary(appid):
                            print(note, flush=True)
                        return 3
                    observed = associated_process_count(appid)
                    game_after = observed_game_executable_pids(appid, install_dir)
                    if game_after - game_before:
                        print("Steam game executable: OBSERVED in selected installation.", flush=True)
                        print("Launch result: GAME_EXECUTABLE_OBSERVED", flush=True)
                        print("Game window and trainer attachment: NOT VERIFIED.", flush=True)
                        for note in log_probe.summary(appid):
                            print(note, flush=True)
                        return 0
                    if observed and (not previous or observed > previous):
                        # Steam may mark a wrapper, reaper or Proton bootstrap as
                        # Running long before the game EXE exists. Never equate
                        # process association with confirmed game startup.
                        associated_only_observed = True
                    if time.monotonic() >= deadline:
                        if status is None:
                            print("Steam command: STILL RUNNING (left untouched).", flush=True)
                        else:
                            print(f"Steam command exit status: {status}", flush=True)
                        if observed:
                            print(f"Existing app-ID associated processes: {observed}", flush=True)
                        if associated_only_observed:
                            print("Launch result: STEAM_ASSOCIATION_ONLY (launcher process observed; game EXE not verified).", flush=True)
                            print("Steam may show Running while DeckCheatz/Proton is still preparing or stalled.", flush=True)
                        else:
                            print("Launch result: UNCONFIRMED (no new game-associated process evidence).", flush=True)
                            print("Steam may still be starting the game; check Steam or its game logs.", flush=True)
                        print("No game window or WeMod/trainer startup was verified.", flush=True)
                        for note in log_probe.summary(appid):
                            print(note, flush=True)
                        return 2
                    time.sleep(0.5)
            finally:
                # Do not kill or block on Steam: the client can keep this
                # command alive after GameWeld finishes its observation.
                # A daemon waiter retains/reaps Popen without ResourceWarning.
                if child.poll() is None:
                    threading.Thread(
                        target=child.wait,
                        name="gameweld-steam-handoff-reaper",
                        daemon=True,
                    ).start()
    except OSError as exc:
        print(f"Steam command: COULD NOT EXECUTE ({type(exc).__name__}).", flush=True)
        print("Launch result: FAILED (Steam command could not be executed).", flush=True)
        return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "launch"))
    parser.add_argument("--appid", required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--install-dir", type=pathlib.Path,
                        help="Manifest-backed Steam install directory for read-only game EXE detection")
    parser.add_argument("--steam-root", type=pathlib.Path,
                        help="Steam client root to inspect read-only logs")
    parser.add_argument("--lifecycle", action="store_true",
                        help="Summarize game EXE versus residual WeMod/Wine processes without killing them")
    parser.add_argument("--steam-log-summary", action="store_true",
                        help="Report sanitized, AppID-scoped Steam log event counts")
    parser.add_argument("--details", action="store_true",
                        help="Read-only redacted process names for AppID associations")
    parser.add_argument("--transport", choices=("applaunch", "steam-uri"),
                        default="applaunch", help="Explicit Steam handoff transport")
    parser.add_argument("--require-idle-before-launch", action="store_true",
                        help="Fail before launching if the exact AppID has an existing process")
    args = parser.parse_args()
    if not valid_appid(args.appid):
        parser.error("Invalid decimal Steam App ID")
    print("PC2 game-only Steam handoff: App ID " + args.appid, flush=True)
    if args.action == "status":
        print("Steam executable: " + (
            "FOUND" if shutil.which("steam") else "NOT FOUND"
        ), flush=True)
        print("Read-only app-ID associated process count: " +
              str(associated_process_count(args.appid)), flush=True)
        if args.details:
            details = associated_process_details(args.appid)
            if not details:
                print("Process details: none visible", flush=True)
            for pid, comm, executable, role in details:
                parent, state, target = associated_process_context(args.appid, pid)
                print(f"AppID association: PID={pid} role={role} "
                      f"comm={comm} executable={executable} PPID={parent} "
                      f"state={state} windows_target_hint={target}", flush=True)
            print("Process roles and Windows target hints are heuristic; no game executable verified.", flush=True)
        if args.lifecycle:
            print_game_lifecycle(game_session_lifecycle(args.appid, args.install_dir))
        if args.steam_log_summary:
            for note in SteamLogProbe(args.steam_root).summary(args.appid, historical=True):
                print(note, flush=True)
        print("No Steam command or trainer was launched.", flush=True)
        return 0
    if not args.confirm:
        parser.error("Steam launch requires an explicit --confirm from GameWeld's user dialog")
    return run_launch(args.appid,
                      require_idle_before_launch=args.require_idle_before_launch,
                      transport=args.transport,
                      steam_root=args.steam_root,
                      install_dir=args.install_dir)


if __name__ == "__main__":
    sys.exit(main())
