#!/usr/bin/env bash
# Read-only integrity and packaging inspection of an EXISTING local GameWeld PC2
# AppImage. Does not rebuild, launch the GUI, start a game, or change Wine/Steam.
# A passing result is NOT a public-release, license, or portability approval.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/pc2-source/local-appimages"
REPORT="$OUT/pc2-rc1-package-audit.txt"
mkdir -p "$OUT"

if [[ $# -gt 1 ]]; then
    echo "Usage: bash scripts/pc2-rc1-package-audit.sh [existing-PC2.AppImage]" >&2
    exit 2
fi

if [[ $# -eq 1 ]]; then
    mapfile -d '' -t candidates < <(find "$OUT" -maxdepth 1 -type f \
        -name 'GameWeld-PC2-RC1-LOCAL-*-x86_64.AppImage' -print0)
    if [[ "${#candidates[@]}" -eq 0 ]]; then
        echo "No local PC2 AppImage found; pass its exact pathname." >&2
        exit 2
    fi
    IMAGE="$(ls -t -- "${candidates[@]}" | head -n 1)"
fi
[[ -f "$IMAGE" && ! -L "$IMAGE" ]] || {
    echo "Refusing missing or symlinked image: $IMAGE" >&2
    exit 2
}
IMAGE="$(realpath -- "$IMAGE")"
[[ -f "$IMAGE.sha256" ]] || {
    echo "Missing adjacent checksum: $IMAGE.sha256" >&2
    exit 2
}

TEMP="$(mktemp -d -t gameweld-pc2-package-audit-XXXXXXXX)"
trap 'rm -rf -- "$TEMP"' EXIT

{
    echo 'GAMEWELD PC2 - EXISTING APPIMAGE RC1 PACKAGE AUDIT'
    echo 'Scope: local-only integrity, contents, entrypoint, dependencies, policy'
    echo 'No game, trainer, Wine, Proton, GUI or Steam launched'
    echo "Image: $IMAGE"
    echo
    echo '=== Check supplied SHA256 ==='
    (cd "$(dirname -- "$IMAGE")" && sha256sum -c -- "$IMAGE.sha256")
    echo
    echo '=== Extract AppImage without launching its GUI ==='
    (cd "$TEMP" && "$IMAGE" --appimage-extract >/dev/null)
    APP="$TEMP/squashfs-root"
    [[ -d "$APP" ]] || { echo 'FAIL: AppImage extraction missing root' >&2; exit 3; }
    echo 'Extracted filesystem: OK'
    echo
    echo '=== Required entrypoint, backend and trainer helpers ==='
    for item in \
        AppRun \
        usr/bin/gameweld \
        usr/libexec/wand-native-backend \
        usr/libexec/gameweld-deckcheatz-direct.py \
        usr/libexec/gameweld-deckcheatz-install.py \
        usr/libexec/gameweld-deckcheatz-proton.py \
        usr/share/applications/gameweld.desktop \
        usr/share/icons/hicolor/scalable/apps/gameweld.svg \
        PC2-DEVELOPMENT-ONLY.txt; do
        [[ -f "$APP/$item" ]] || { echo "FAIL: missing $item" >&2; exit 4; }
        echo "OK: $item"
    done
    [[ -x "$APP/AppRun" && -x "$APP/usr/bin/gameweld" &&
       -x "$APP/usr/libexec/wand-native-backend" ]] || {
        echo 'FAIL: missing executable permissions' >&2
        exit 4
    }
    python3 - "$APP" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for item in ('usr/bin/gameweld', 'usr/libexec/wand-native-backend'):
    with (root / item).open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            raise SystemExit(f'FAIL: not ELF: {item}')
print('PASS: GTK and backend ELF formats')
PY
    echo
    echo '=== Reject bundled trainer/Windows binaries ==='
    if find "$APP/usr/libexec" -type f \
        \( -iname '*.exe' -o -iname '*.dll' \) -print -quit | grep -q .; then
        echo 'FAIL: Windows executable or DLL under GameWeld libexec' >&2
        exit 5
    fi
    echo 'PASS: no trainer EXE or Windows DLL in GameWeld libexec'
    if find "$APP" -type l -print0 | while IFS= read -r -d '' link; do
        dest="$(readlink "$link")"
        case "$dest" in /*) echo "$link -> $dest";; esac
    done | grep -q .; then
        echo 'WARN: absolute AppDir symlinks found; inspect portability'
    else
        echo 'PASS: no absolute AppDir symlinks detected'
    fi
    echo
    echo '=== Bundled GTK library inventory ==='
    find "$APP/usr/lib" "$APP/usr/lib64" -name 'libgtk-3.so*' \
        -print 2>/dev/null || true
    echo
    echo '=== Platform and library baselines (information only) ==='
    command -v readelf >/dev/null 2>&1 && {
        readelf -V "$APP/usr/bin/gameweld" 2>/dev/null |
            grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -n 1 || true
        readelf -V "$APP/usr/libexec/wand-native-backend" 2>/dev/null |
            grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -n 1 || true
    }
    echo
    echo '=== License and provenance notice ==='
    if [[ ! -f "$APP/usr/share/doc/gameweld/LICENSE" ]]; then
        echo 'RELEASE BLOCKER: MIT license not yet bundled in this local test image.'
    else
        echo 'GameWeld license included.'
    fi
    if [[ ! -f "$APP/usr/share/doc/gameweld/THIRD-PARTY.md" ]]; then
        echo 'RELEASE BLOCKER: third-party notices not yet bundled.'
    else
        echo 'Third-party notices included (individual bundled dependency licenses still require review).'
    fi
    echo
    echo 'Result: PASS (LOCAL PACKAGE INTEGRITY + REQUIRED STRUCTURE)'
    echo 'PUBLIC RELEASE: NOT CLEARED; cross-distro testing, library licenses and distribution audit remain.'
} 2>&1 | tee "$REPORT"

echo "Audit report: $REPORT"
