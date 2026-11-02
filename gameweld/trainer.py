"""Opt-in local Windows trainer launch experiments.

GameWeld does not distribute trainers, verify their reputation, attach to a game,
modify Steam launch options, or interfere with anti-cheat. Proton mode MAY
modify the selected game's pre-existing compatibility prefix. No game-memory
access or compatibility claim is implied by a successful process launch.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from .core import installed_games, load_settings, libraries

MAX_EXE = 256 * 1024 * 1024
CHUNK = 1024 * 1024
MODES = ('isolated', 'proton')


def _regular(path, *, executable=False, allow_link=False, owner=True):
    p = Path(path).expanduser()
    if p.is_symlink() and not allow_link:
        raise ValueError('symlink_not_allowed')
    st = p.stat()
    if not stat.S_ISREG(st.st_mode) or (executable and not os.access(p, os.X_OK)):
        raise ValueError('not_usable_file')
    if owner and st.st_uid != os.getuid():
        raise ValueError('file_not_owned_by_user')
    return p.resolve(strict=True)


def inspect_trainer(path):
    """Detect PE machine type and hash exactly the opened file; NOT a malware scan."""
    p = _regular(path)
    if p.suffix.lower() != '.exe':
        raise ValueError('trainer_exe_extension_required')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        st = os.fstat(fd)
        if st.st_size < 256 or st.st_size > MAX_EXE or not stat.S_ISREG(st.st_mode):
            raise ValueError('trainer_invalid_size')
        head = os.read(fd, 4096)
        if head[:2] != b'MZ':
            raise ValueError('trainer_not_windows_pe')
        pe = int.from_bytes(head[0x3c:0x40], 'little')
        if not 64 <= pe <= 1024 or pe + 24 > len(head) or head[pe:pe + 4] != b'PE\x00\x00':
            raise ValueError('trainer_invalid_pe_header')
        machine = int.from_bytes(head[pe + 4:pe + 6], 'little')
        if machine not in (0x14c, 0x8664):
            raise ValueError('trainer_unsupported_machine')
        opt = int.from_bytes(head[pe + 24:pe + 26], 'little')
        if opt not in (0x10b, 0x20b):
            raise ValueError('trainer_unsupported_pe_format')
        digest = hashlib.sha256()
        digest.update(head)
        while True:
            block = os.read(fd, CHUNK)
            if not block:
                break
            digest.update(block)
        if os.fstat(fd).st_size != st.st_size:
            raise ValueError('trainer_changed_during_read')
        return {'operation': 'trainer-inspect', 'state': 'windows_pe_inspected',
                'sha256': digest.hexdigest(), 'size_bytes': st.st_size,
                'machine': 'x64' if machine == 0x8664 else 'x86',
                'reputation_verified': False, 'game_attachment_verified': False,
                'executed': False, 'raw_paths_disclosed': False}
    finally:
        os.close(fd)


def _find_wine():
    for name in ('wine', 'wine64'):
        found = shutil.which(name)
        if found:
            return _regular(found, executable=True, allow_link=True, owner=False)
    raise ValueError('system_wine_unavailable')


def _proton_context(game, proton):
    """Inspect an EXISTING Steam game prefix. Never initialise one implicitly."""
    path = _regular(proton, executable=True, allow_link=True, owner=False)
    if path.name != 'proton':
        raise ValueError('proton_executable_name_required')
    steamapps = Path(game['_steamapps']).expanduser().resolve(strict=True)
    appid = str(game['appid'])
    compat = steamapps / 'compatdata' / appid
    if compat.is_symlink() or not compat.is_dir():
        raise ValueError('game_proton_prefix_missing')
    if compat.resolve(strict=True) != compat or compat.stat().st_uid != os.getuid():
        raise ValueError('game_prefix_unsafe')
    prefix = compat / 'pfx'
    if prefix.is_symlink() or not prefix.is_dir() or prefix.stat().st_uid != os.getuid():
        raise ValueError('game_proton_prefix_missing')
    if not (prefix / 'drive_c').is_dir():
        raise ValueError('game_proton_prefix_uninitialised')
    # Proton expects STEAM_COMPAT_CLIENT_INSTALL_PATH to point to Steam's root.
    steam_root = steamapps.parent
    # Prefer the parent of primary steamapps for the Steam client; secondary
    # Steam library parents are NOT necessarily a Steam client installation.
    client_root = Path.home() / '.local/share/Steam'
    if not client_root.is_dir():
        client_root = steam_root
    return path, compat, client_root


def discover_proton(steamapps=None):
    """Read-only Proton executable discovery. Selection is NOT game-version proof."""
    paths = []
    for folder in libraries(steamapps or load_settings()['steamapps']):
        paths.append(Path(folder) / 'common')
    paths.extend((Path.home() / '.steam/root/compatibilitytools.d',
                  Path.home() / '.local/share/Steam/compatibilitytools.d'))
    candidates = []
    seen = set()
    for base in paths[:66]:
        if not base.is_dir():
            continue
        try:
            folders = sorted((x for x in base.iterdir() if x.is_dir()), key=lambda x: x.name.lower())[:200]
        except OSError:
            continue
        for folder in folders:
            name = folder.name.lower()
            if 'proton' not in name:
                continue
            script = folder / 'proton'
            try:
                exe = _regular(script, executable=True, allow_link=True, owner=False)
            except (OSError, ValueError):
                continue
            if exe not in seen:
                seen.add(exe)
                candidates.append({'label': folder.name[:100], 'path': str(exe)})
            if len(candidates) >= 64:
                break
        if len(candidates) >= 64:
            break
    return candidates


def _selected_game(appid, steamapps=None):
    if type(appid) is not int or not 0 < appid < 10000000000:
        raise ValueError('invalid_game_appid')
    matches = installed_games(steamapps or load_settings()['steamapps'])
    game = next((item for item in matches if item['appid'] == appid), None)
    if game is None:
        raise ValueError('game_not_in_installed_library')
    return game


def prepare_trainer(path, *, appid, mode='isolated', proton=None, steamapps=None):
    if mode not in MODES:
        raise ValueError('unsupported_trainer_mode')
    game = _selected_game(appid, steamapps)
    binary = inspect_trainer(path)
    if mode == 'proton':
        if not proton:
            raise ValueError('proton_path_required')
        _proton_context(game, proton)
    else:
        _find_wine()
    return {'operation': 'trainer-preflight', 'state': 'ready_for_explicit_consent',
            'game_appid': game['appid'], 'trainer_sha256': binary['sha256'],
            'trainer_bytes': binary['size_bytes'], 'machine': binary['machine'],
            'mode': mode, 'uses_existing_game_prefix': mode == 'proton',
            'may_modify_game_prefix': mode == 'proton',
            'trainer_reputation_verified': False, 'trainer_game_compatibility_verified': False,
            'game_process_accessed': False, 'trainer_launched': False,
            'raw_paths_disclosed': False}


def _launch_env(mode, *, root=None, compat=None, client_root=None, game=None):
    # Preserve desktop display and runtime variables needed by native Wine/
    # Proton, but never inherit another game's Steam/Proton identity or overlays.
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith(('STEAM_COMPAT_', 'PROTON_', 'PRESSURE_VESSEL_')):
            env.pop(key, None)
    env.pop('WINEPREFIX', None)
    env.pop('LD_PRELOAD', None)
    env['WINEDEBUG'] = '-all'
    if mode == 'isolated':
        env.update({'HOME': str(root / 'home'),
                    'XDG_CONFIG_HOME': str(root / 'config'),
                    'XDG_CACHE_HOME': str(root / 'cache'),
                    'XDG_DATA_HOME': str(root / 'data'),
                    'WINEPREFIX': str(root / 'prefix'), 'WINEARCH': 'win64'})
    else:
        env['STEAM_COMPAT_DATA_PATH'] = str(compat)
        env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = str(client_root)
        env['STEAM_COMPAT_APP_ID'] = str(game['appid'])
        env['SteamAppId'] = str(game['appid'])
        env['SteamGameId'] = str(game['appid'])
    return env


def _staging_base():
    """Private per-user staging tree; no trainer bytes persist after session."""
    home = Path.home()
    base = home / '.cache' / 'gameweld' / 'trainer-staging'
    for part in (home / '.cache', home / '.cache' / 'gameweld', base):
        if part.is_symlink():
            raise ValueError('staging_symlink_rejected')
        part.mkdir(mode=0o700, exist_ok=True)
        st = part.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or (part != home / '.cache' and st.st_mode & 0o077):
            raise ValueError('staging_directory_not_private')
    return base


def _stage_pinned_exe(source, target, expected_hash):
    """Stage the exact reviewed executable to close inspect/exec substitution."""
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    out = None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or not 256 <= st.st_size <= MAX_EXE:
            raise ValueError('trainer_changed_before_launch')
        out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                      getattr(os, 'O_NOFOLLOW', 0), 0o600)
        digest = hashlib.sha256()
        copied = 0
        while True:
            data = os.read(fd, CHUNK)
            if not data:
                break
            copied += len(data)
            if copied > MAX_EXE:
                raise ValueError('trainer_oversized_after_review')
            digest.update(data)
            mv = memoryview(data)
            while mv:
                n = os.write(out, mv)
                if n < 1:
                    raise OSError('trainer_staging_write_failed')
                mv = mv[n:]
        if copied != st.st_size or digest.hexdigest() != expected_hash:
            raise ValueError('trainer_changed_after_review')
        os.fsync(out)
        return target
    finally:
        os.close(fd)
        if out is not None:
            os.close(out)


def _stop_owned(proc):
    if proc.poll() is not None:
        return
    # The launcher is started in a new session; never use wineserver -k or
    # killall, which could terminate the user's game or unrelated trainers.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_trainer(path, *, appid, expected_sha256, consent=False, mode='isolated',
                proton=None, consent_game_prefix=False, steamapps=None,
                timeout=120, cancel_event=None, wine_executable=None):
    """Start a locally supplied Windows PE on request; only execution is verified.

    Testing hook wine_executable is not exposed in the CLI/UI. No trainer/game
    memory inspection or process matching is performed.
    """
    base = {'operation': 'trainer-launch', 'mode': mode, 'trainer_process_started': False,
            'trainer_functional_verified': False, 'trainer_window_verified': False,
            'all_trainer_descendants_terminated_verified': False,
            'game_process_accessed_by_gameweld': False,
            'game_attachment_verified': False, 'steam_modified': False,
            'raw_paths_disclosed': False, 'existing_game_prefix_used': mode == 'proton'}
    if not consent:
        return {**base, 'state': 'explicit_consent_required'}
    if mode == 'proton' and not consent_game_prefix:
        return {**base, 'state': 'game_prefix_consent_required'}
    if type(expected_sha256) is not str or len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256):
        return {**base, 'state': 'invalid_expected_sha256'}
    if type(timeout) is not int or not 10 <= timeout <= 1800:
        return {**base, 'state': 'invalid_timeout'}
    try:
        plan = prepare_trainer(path, appid=appid, mode=mode, proton=proton, steamapps=steamapps)
        if plan['trainer_sha256'] != expected_sha256:
            return {**base, 'state': 'trainer_changed_since_review'}
        binary = _regular(path)
        game = _selected_game(appid, steamapps)
        if mode == 'isolated':
            runtime = _regular(wine_executable, executable=True, allow_link=True, owner=False) if wine_executable else _find_wine()
        else:
            runtime, compat, client_root = _proton_context(game, proton)
    except (OSError, ValueError):
        return {**base, 'state': 'preflight_failed'}
    started = False
    cancelled = False
    timed_out = False
    elapsed = None
    returncode = None
    proc = None
    begin = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='gameweld-trainer-', dir=_staging_base()) as temp:
            root = Path(temp)
            staged = _stage_pinned_exe(binary, root / binary.name, expected_sha256)
            if mode == 'isolated':
                for name in ('home', 'config', 'cache', 'data'):
                    (root / name).mkdir(mode=0o700)
                env = _launch_env(mode, root=root)
                argv = [str(runtime), str(staged)]
            else:
                env = _launch_env(mode, compat=compat, client_root=client_root, game=game)
                argv = [str(runtime), 'run', str(staged)]
            if cancel_event is not None and cancel_event.is_set():
                return {**base, 'state': 'cancelled_before_launch'}
            proc = subprocess.Popen(argv, cwd=str(binary.parent), env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, close_fds=True,
                                    start_new_session=True)
            started = True
            while proc.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    break
                if time.monotonic() - begin >= timeout:
                    timed_out = True
                    break
                time.sleep(0.1)
            if cancelled or timed_out:
                _stop_owned(proc)
            try:
                returncode = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _stop_owned(proc)
                returncode = proc.wait(timeout=3)
            elapsed = round((time.monotonic() - begin) * 1000)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {**base, 'state': 'launcher_error', 'trainer_process_started': started,
                'elapsed_ms': elapsed}
    return {**base, 'state': ('cancelled' if cancelled else 'timeout_stopped' if timed_out
                            else 'trainer_process_exited'), 'trainer_process_started': started,
            'exit_code': returncode, 'elapsed_ms': elapsed,
            'owned_launcher_reaped': proc.poll() is not None,
            'wine_prefix_may_have_changed': mode == 'proton',
            'isolated_prefix_removed': mode == 'isolated'}
