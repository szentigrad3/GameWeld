#!/usr/bin/env python3
"""Read-only inventory and distribution policy check for an extracted AppDir.

Passing means only that the candidate meets a narrow packaging policy. It does
NOT establish licensing rights, trust, source reproducibility, or runtime safety.
"""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = {
    'usr/bin/gameweld': b'\x7fELF',
    'usr/libexec/wand-native-backend': b'\x7fELF',
    'usr/libexec/gameweld-elevate.exe': b'MZ',
}
ALLOWED_PE = {'usr/libexec/gameweld-elevate.exe'}
BAD_FILENAMES = {
    'resonance-native-trainer.exe',
    'resonance-hero-reference.png',
    'resonance-cover-reference.png',
    'resonance-hero-appimage.jpg',
    'wand-logo-reference.png',
}


def audit(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError(f'Not an extracted AppDir: {root}')
    objects = []
    issues = []
    for obj in sorted(root.rglob('*')):
        rel = obj.relative_to(root).as_posix()
        if obj.is_symlink():
            # AppImages may legitimately contain symlinks. Record them instead
            # of following them during a privileged audit.
            objects.append({'path': rel, 'kind': 'symlink'})
            continue
        if not obj.is_file():
            continue
        data = obj.read_bytes()
        kind = 'ELF' if data.startswith(b'\x7fELF') else ('PE' if data.startswith(b'MZ') else 'other')
        objects.append({'path': rel, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'kind': kind})
        low = rel.lower()
        if obj.name.lower() in BAD_FILENAMES or '/assets/games/2713000' in '/' + low:
            issues.append(f'Excluded third-party reference content reappeared: {rel}')
        if kind == 'PE' and rel not in ALLOWED_PE:
            issues.append(f'Unexpected Windows executable: {rel}')
        if low.endswith('.dll'):
            issues.append(f'Bundled DLL needs separate provenance approval: {rel}')
    lookup = {o['path']: o for o in objects}
    for rel, magic in REQUIRED.items():
        if rel not in lookup:
            issues.append(f'Missing required component: {rel}')
        elif lookup[rel]['kind'] != ('PE' if magic == b'MZ' else 'ELF'):
            issues.append(f'Unexpected executable format: {rel}')
    return {
        'status': 'PACKAGING_PASS_ONLY' if not issues else 'PACKAGING_FAIL',
        'files': len([o for o in objects if o['kind'] != 'symlink']),
        'symlinks': len([o for o in objects if o['kind'] == 'symlink']),
        'native_executables': [o for o in objects if o['kind'] in ('ELF', 'PE')],
        'issues': issues,
        'notice': 'Packaging-only check; licensing, authorship and source reproducibility require independent review.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('appdir', type=Path, help='Already-extracted AppImage filesystem root')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable report')
    args = parser.parse_args()
    result = audit(args.appdir)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['status']}: {result['files']} files, {result['symlinks']} symlinks, {len(result['native_executables'])} executable files")
        for item in result['native_executables']:
            print(f"  {item['kind']:3} {item['sha256']} {item['path']}")
        for issue in result['issues']:
            print('  BLOCK: ' + issue)
        print(result['notice'])
    return 0 if not result['issues'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
