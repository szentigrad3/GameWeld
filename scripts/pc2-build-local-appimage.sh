#!/usr/bin/env bash
# GameWeld PC2 RC1 packaging experiment for LOCAL field testing only.
# Does not publish a release, download tools, install trainers, launch Steam,
# or modify game prefixes/Steam options. Linux host libraries may limit portability.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(uname -m)" == "x86_64" ]] || { echo 'Only x86_64 supported' >&2; exit 2; }

find_tool() {
    local variable="$1" command_name="$2" cached="$3" selected=""
    selected="${!variable:-}"
    if [[ -n "$selected" ]]; then
        [[ -x "$selected" ]] || { echo "Not executable: $selected" >&2; return 1; }
        printf '%s\n' "$selected"
        return 0
    fi
    if command -v "$command_name" >/dev/null 2>&1; then
        command -v "$command_name"
        return 0
    fi
    if [[ -x "$cached" ]]; then
        printf '%s\n' "$cached"
        return 0
    fi
    echo "Missing $command_name. Provide $variable=/absolute/path/to/tool; no automatic downloads occur." >&2
    return 1
}

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/wand-native/appimage-tools"
LINUXDEPLOY_BIN="$(find_tool LINUXDEPLOY linuxdeploy "$CACHE/linuxdeploy-x86_64.AppImage")"
APPIMAGETOOL_BIN="$(find_tool APPIMAGETOOL appimagetool "$CACHE/appimagetool-x86_64.AppImage")"
run_tool() {
    local executable="$1"
    shift
    if [[ "$executable" == *.AppImage ]]; then
        "$executable" --appimage-extract-and-run "$@"
    else
        "$executable" "$@"
    fi
}

OUT="$ROOT/build/pc2-source/local-appimages"
mkdir -p "$OUT"
WORK="$(mktemp -d "$ROOT/build/pc2-source/.pc2-local-appimage-XXXXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
APP="$WORK/PC2.AppDir"
REPORT="$OUT/pc2-local-appimage-report.txt"
if [[ "${GAMEWELD_PC2_PUBLIC_UI:-0}" == 1 ]]; then
    IMAGE="$OUT/GameWeld-PC2-RC1-CANDIDATE-$(date +%Y%m%d-%H%M%S)-x86_64.AppImage"
else
    IMAGE="$OUT/GameWeld-PC2-RC1-LOCAL-$(date +%Y%m%d-%H%M%S)-x86_64.AppImage"
fi

{
    echo '=== Build local PC2 AppImage candidate ==='
    if [[ "${GAMEWELD_PC2_PUBLIC_UI:-0}" == 1 ]]; then
        echo 'Status: CLEAN RC1 CANDIDATE; NOT APPROVED FOR PUBLIC DISTRIBUTION'
    else
        echo 'Status: PRIVATE FIELD TEST ONLY; no redistribution or RC1 approval'
    fi
    echo 'Source commit:'
    git rev-parse HEAD
    echo 'Changed local files (source runner is not overwritten):'
    git status --short
    echo
    echo '=== Offline tests, Go/GTK compile, isolated AppDir ==='
    GAMEWELD_PC2_STAGE_DIR="$APP" bash "$ROOT/scripts/pc2-stage-standalone-appdir.sh"
    if [[ "${GAMEWELD_PC2_PUBLIC_UI:-0}" == 1 ]]; then
        rm -f -- "$APP/PC2-DEVELOPMENT-ONLY.txt"
        cat > "$APP/PC2-RC1-CANDIDATE.txt" <<'NOTICE'
GameWeld RC1 candidate - prerelease field validation.
Not yet approved for public distribution. GameWeld performs game-specific
runtime checks and requests user consent before external trainer launches.
Testing on multiple Linux distributions and dependency/license audit is pending.
NOTICE
    fi

    mkdir -p "$APP/usr/share/applications" "$APP/usr/share/icons/hicolor/scalable/apps"
    cat > "$APP/gameweld.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=GameWeld
Comment=Linux game and trainer manager
Exec=gameweld
Icon=gameweld
Terminal=false
Categories=Game;Utility;
DESKTOP
    cp "$APP/gameweld.desktop" "$APP/usr/share/applications/gameweld.desktop"
    cat > "$APP/gameweld.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<rect x="4" y="4" width="120" height="120" rx="25" fill="#172735"/>
<path d="M26 66c0-20 13-34 33-34h41v15H59c-11 0-18 8-18 19 0 12 8 19 18 19h12V68h18v32H59c-20 0-33-14-33-34z" fill="#70d7ab"/>
</svg>
SVG
    cp "$APP/gameweld.svg" "$APP/usr/share/icons/hicolor/scalable/apps/gameweld.svg"
    cp "$APP/gameweld.svg" "$APP/.DirIcon"

    # Ship GameWeld's primary notice even in private test packages. This does
    # not establish rights to redistribute every bundled third-party library.
    mkdir -p "$APP/usr/share/doc/gameweld"
    install -m 0644 "$ROOT/LICENSE" "$APP/usr/share/doc/gameweld/LICENSE"
    install -m 0644 "$ROOT/THIRD-PARTY.md" "$APP/usr/share/doc/gameweld/THIRD-PARTY.md"

    echo '=== Bundle host ELF dependencies with linuxdeploy ==='
    run_tool "$LINUXDEPLOY_BIN" \
        --appdir "$APP" \
        --executable "$APP/usr/bin/gameweld" \
        --executable "$APP/usr/libexec/wand-native-backend" \
        --desktop-file "$APP/gameweld.desktop" \
        --icon-file "$APP/gameweld.svg"

    # linuxdeploy may replace AppRun; restore a predictable GameWeld entrypoint.
    cat > "$APP/AppRun" <<'APPRUN'
#!/usr/bin/env bash
set -Eeuo pipefail
APPDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR
export WAND_NATIVE_BACKEND="$APPDIR/usr/libexec/wand-native-backend"
export PATH="$APPDIR/usr/bin:${PATH:-/usr/bin:/bin}"
export XDG_DATA_DIRS="$APPDIR/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
for libdir in "$APPDIR/usr/lib" "$APPDIR/usr/lib64" "$APPDIR/usr/lib/x86_64-linux-gnu"; do
    if [[ -d "$libdir" ]]; then
        export LD_LIBRARY_PATH="$libdir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    fi
done
exec "$APPDIR/usr/bin/gameweld" "$@"
APPRUN
    chmod 0755 "$APP/AppRun"
    test -x "$APP/usr/bin/gameweld"
    test -s "$APP/usr/libexec/wand-native-backend"
    for helper in gameweld-deckcheatz-install.py gameweld-deckcheatz-direct.py \
                  gameweld-deckcheatz-proton.py gameweld-steam-game-exe.py \
                  gameweld-platform-session.py gameweld-steam-wemod-platform.py \
                  gameweld-steam-handoff.py \
                  gameweld-heroic-launch.sh gameweld-lutris-session.sh; do
        test -s "$APP/usr/libexec/$helper" || { echo "Missing helper $helper" >&2; exit 5; }
    done
    if find "$APP/usr/libexec" -type f \( -iname '*.exe' -o -iname '*.dll' \) -print -quit | grep -q .; then
        echo 'Refusing package: a Windows executable/DLL appeared in libexec' >&2
        exit 5
    fi
    echo '=== Package local AppImage ==='
    [[ ! -e "$IMAGE" ]] || { echo "Refusing to overwrite $IMAGE" >&2; exit 6; }
    ARCH=x86_64 VERSION=pc2-rc1-local run_tool "$APPIMAGETOOL_BIN" "$APP" "$IMAGE"
    chmod 0755 "$IMAGE"
    echo '=== Non-GUI AppImage smoke test ==='
    local_status="$("$IMAGE" --appimage-extract-and-run --pc2-launch-gate-status)"
    printf '%s\n' "$local_status"
    # Development builds keep the game-only gate off. In the public-facing
    # candidate, an explicit Play Game click is the opt-in. No trainer starts.
    if [[ "${GAMEWELD_PC2_PUBLIC_UI:-0}" == 1 ]]; then
        expected_gate='PC2 Steam game-only launch: enabled'
    else
        expected_gate='PC2 Steam game-only launch: disabled'
    fi
    [[ "$local_status" == "$expected_gate" ]] || {
        echo "FAIL: packaged game-only safety gate mismatch; wanted: $expected_gate" >&2
        exit 7
    }
    sha256sum "$IMAGE" > "$IMAGE.sha256"
    echo '=== Read-only extracted package audit ==='
    bash "$ROOT/scripts/pc2-rc1-package-audit.sh" "$IMAGE"
    echo "Image: $IMAGE"
    echo "SHA256: $IMAGE.sha256"
    echo 'Result: PASS (LOCAL PACKAGING + NON-GUI SMOKE ONLY)'
    if [[ "${GAMEWELD_PC2_PUBLIC_UI:-0}" == 1 ]]; then
        echo 'RC1 candidate: clean user-facing UI; cross-distro, functionality, and licensing validation are still required.'
    else
        echo 'Still required: launch the AppImage, verify 4K resize/reset/reopen, inspect GTK portability and license obligations.'
    fi
} 2>&1 | tee "$REPORT"
printf 'Build report: %s\n' "$REPORT"
