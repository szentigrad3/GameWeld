#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded output + direct-child lifecycle for the GameWeld v2 monitor bridge.

This runs only the already-selected Python upstream entrypoint. It never
starts Steam, Proton, Wine, a game, or a trainer itself. It never walks,
signals, or kills descendant processes. Trainer cleanup needs separate proof.
"""
from __future__ import annotations

import subprocess
import threading


class MonitorRunFailure(RuntimeError):
    """A stable, non-secret reason for a failed upstream process boundary."""


def run_monitor(command: list[str], env: dict[str, str], *,
                timeout_seconds: float = 86400,
                max_stdout_bytes: int = 262144) -> subprocess.CompletedProcess[str]:
    if (not command or not all(isinstance(x, str) and x for x in command)
            or not 0 < timeout_seconds <= 86400
            or not 1024 <= max_stdout_bytes <= 1024 * 1024):
        raise MonitorRunFailure("upstream_monitor_invalid_limits")
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True,
        )
    except OSError as exc:
        raise MonitorRunFailure("upstream_monitor_spawn_failed") from exc

    captured = bytearray()
    stats = [0]
    read_errors: list[BaseException] = []

    def drain():
        try:
            assert proc.stdout is not None
            while True:
                chunk = proc.stdout.read(8192)
                if not chunk:
                    return
                stats[0] += len(chunk)
                remaining = max_stdout_bytes + 1 - len(captured)
                if remaining > 0:
                    captured.extend(chunk[:remaining])
        except (OSError, ValueError) as exc:
            read_errors.append(exc)

    thread = threading.Thread(target=drain, name="gameweld-upstream-stdout",
                              daemon=True)
    thread.start()
    timed_out = False
    try:
        returncode = proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Only the exact direct Python subprocess we created is signalled.
        # Do not kill a process group, Wine server, Steam, or the game.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if proc.poll() is None:
                    proc.kill()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    raise MonitorRunFailure("upstream_monitor_direct_child_unreaped")
        returncode = proc.returncode

    thread.join(timeout=2.0)
    if thread.is_alive():
        raise MonitorRunFailure("upstream_monitor_output_pipe_not_closed")
    if proc.stdout is not None:
        proc.stdout.close()
    if timed_out:
        raise MonitorRunFailure("upstream_monitor_timeout")
    if read_errors:
        raise MonitorRunFailure("upstream_monitor_output_read_failed")
    if stats[0] > max_stdout_bytes:
        raise MonitorRunFailure("upstream_monitor_output_limit_exceeded")
    try:
        decoded = captured.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise MonitorRunFailure("upstream_monitor_output_not_utf8") from exc
    return subprocess.CompletedProcess(command, returncode, stdout=decoded)
