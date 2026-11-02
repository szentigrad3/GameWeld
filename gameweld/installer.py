"""Optional per-user Linux desktop integration, never writes system directories.

Install only allowlisted own Python modules; do not install trainer binaries,
Wine/Proton prefixes, project tests, or personal state. No sudo required.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from . import __version__
from .core import read_file

MARKER = '.gameweld-desktop-managed'
DESKTOP_NAME = 'io.github.gameweld.Desktop.desktop'
MODULES = ('__init__.py', '__main__.py', 'core.py', 'diagnostics.py',
           'helpers.py', 'history.py', 'installer.py', 'ipc.py', 'startup.py', 'ui.py')
MAX_MODULE = 256 * 1024


def locations():
    home = Path.home()
    xdg = os.environ.get('XDG_DATA_HOME')
    data = Path(xdg) if xdg and Path(xdg).is_absolute() else home / '.local/share'
    return {'code': data / 'gameweld',
            'desktop': data / 'applications' / DESKTOP_NAME,
            'launcher': home / '.local/bin/gameweld'}


def _check_parent(path):
    """Reject an existing symlink along the selected installation path."""
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('installation_symlink_rejected')


def _safe_create_parent(path):
    _check_parent(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _check_parent(path)


def _owned_bytes(path):
    if path.is_symlink():
        raise ValueError('unmanaged_existing_symlink')
    if not path.exists():
        return None
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
        raise ValueError('unmanaged_existing_file')
    return read_file(path, 32 * 1024)


def _owned_tree(path):
    if path.is_symlink():
        raise ValueError('unmanaged_existing_directory')
    if not path.exists():
        return False
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise ValueError('unmanaged_existing_directory')
    if _owned_bytes(path / MARKER) != b'GameWeld managed desktop alpha\n':
        raise ValueError('unmanaged_existing_directory')
    return True


def _launcher_text(root):
    # Include no arbitrary user input in a command without shell quoting.
    import shlex
    value = shlex.quote(str(root))
    return ('#!/bin/sh\n# GameWeld managed desktop launcher\n'
            'exec env PYTHONPATH=' + value + ' python3 -m gameweld "$@"\n')


def _desktop_exec(path):
    # Desktop Entry Exec value quoting; reject CR/LF and double quotes.
    value = str(path)
    if any(c in value for c in ('\n', '\r', '"', '\\')):
        raise ValueError('unsupported_launcher_path')
    if any(c.isspace() for c in value):
        return '"' + value + '"'
    return value


def _desktop_text(launcher):
    return ('[Desktop Entry]\nType=Application\nName=GameWeld\n'
            'Comment=Local game library and owned Wine IPC laboratory\n'
            'Exec=' + _desktop_exec(launcher) + '\n'
            'Icon=applications-games\nTerminal=false\nCategories=Game;Utility;\n'
            'StartupNotify=true\nX-GameWeld-Managed=true\n')


def _write_atomic(path, content, mode):
    _safe_create_parent(path)
    tmp = path.parent / ('.gameweld-install-' + os.urandom(10).hex())
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, 'O_NOFOLLOW', 0), mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        _check_parent(path)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _source_module_bytes():
    source = Path(__file__).resolve().parent
    # Source modules are read without following symlinks or evaluating file content.
    return {name: read_file(source / name, MAX_MODULE) for name in MODULES}


def install(*, dry_run=False):
    loc = locations()
    for dest in loc.values():
        _check_parent(dest)
    has_code = _owned_tree(loc['code'])
    known_launcher = _owned_bytes(loc['launcher'])
    if known_launcher is not None and not known_launcher.startswith(
            b'#!/bin/sh\n# GameWeld managed desktop launcher\n'):
        raise ValueError('unmanaged_existing_launcher')
    known_entry = _owned_bytes(loc['desktop'])
    if known_entry is not None and b'X-GameWeld-Managed=true\n' not in known_entry:
        raise ValueError('unmanaged_existing_desktop_entry')
    manifest = _source_module_bytes()
    launcher = _launcher_text(loc['code']).encode()
    desktop = _desktop_text(loc['launcher']).encode()
    if not dry_run:
        _safe_create_parent(loc['code'])
        staging = Path(tempfile.mkdtemp(prefix='.gameweld-stage-', dir=loc['code'].parent))
        backup = None
        try:
            folder = staging / 'gameweld'
            folder.mkdir(mode=0o700)
            for name, content in manifest.items():
                (folder / name).write_bytes(content)
                (folder / name).chmod(0o600)
            (staging / MARKER).write_bytes(b'GameWeld managed desktop alpha\n')
            if has_code:
                backup = loc['code'].parent / ('.gameweld-backup-' + os.urandom(10).hex())
                loc['code'].rename(backup)
            try:
                staging.rename(loc['code'])
            except Exception:
                if backup is not None:
                    backup.rename(loc['code'])
                    backup = None
                raise
            _write_atomic(loc['launcher'], launcher, 0o700)
            _write_atomic(loc['desktop'], desktop, 0o600)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
            if backup is not None and backup.exists():
                shutil.rmtree(backup)
    return {'operation': 'gameweld-desktop-install', 'state': 'dry_run' if dry_run else 'installed',
            'version': __version__, 'modules_installed': len(manifest),
            'scope': 'current_user', 'third_party_executables_installed': False,
            'game_memory_accessed': False, 'steam_modified': False,
            'user_preferences_preserved': True}


def uninstall(*, dry_run=False):
    loc = locations()
    for dest in loc.values():
        _check_parent(dest)
    code_owned = _owned_tree(loc['code'])
    launcher = _owned_bytes(loc['launcher'])
    desktop = _owned_bytes(loc['desktop'])
    if launcher is not None and not launcher.startswith(b'#!/bin/sh\n# GameWeld managed desktop launcher\n'):
        raise ValueError('unmanaged_existing_launcher')
    if desktop is not None and b'X-GameWeld-Managed=true\n' not in desktop:
        raise ValueError('unmanaged_existing_desktop_entry')
    if not dry_run:
        if desktop is not None: loc['desktop'].unlink()
        if launcher is not None: loc['launcher'].unlink()
        if code_owned: shutil.rmtree(loc['code'])
    return {'operation': 'gameweld-desktop-uninstall',
            'state': 'dry_run' if dry_run else 'uninstalled',
            'user_preferences_preserved': True, 'history_preserved': True,
            'game_memory_accessed': False, 'steam_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m gameweld.installer')
    parser.add_argument('action', choices=('install', 'uninstall'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = install(dry_run=args.dry_run) if args.action == 'install' else uninstall(dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(json.dumps({'operation': 'gameweld-desktop-install', 'state': 'refused',
                          'error_category': str(exc)[:70], 'game_memory_accessed': False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
