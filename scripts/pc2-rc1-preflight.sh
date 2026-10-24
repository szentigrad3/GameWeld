#!/usr/bin/env bash
# GameWeld PC2 RC1 source-only preflight.
# Does NOT start GameWeld, Steam, WeMod, a game, the updater, or Wine.
# Does NOT modify Steam configuration or Wine prefixes.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/build/pc2-source/rc1-preflight"
mkdir -p "$OUT"
REPORT="$OUT/rc1-preflight-report.txt"
AIO_REPORT="$ROOT/build/pc2-source/deckcheatz-aio-report.txt"

{
    printf '%s\n' 'GAMEWELD PC2 RC1 / OFFLINE SOURCE PREFLIGHT'
    printf '%s\n' 'Release state: RC1 CANDIDATE CHECKS ONLY (not RC1 release)'
    printf '%s\n' 'Launch Steam/game/trainer: NO'
    printf '%s\n' 'Modify game Wine prefix / Steam Launch Options: NO'
    printf '%s\n' 'Install or update DeckCheatz: NO'
    echo
    for cmd in go gcc pkg-config python3 git; do
        command -v "$cmd" >/dev/null || { printf 'FAIL: missing required build tool %s\n' "$cmd"; exit 3; }
    done
    pkg-config --exists gtk+-3.0 || { printf '%s\n' 'FAIL: GTK3 development package missing'; exit 3; }
    printf '%s\n' '=== Workspace source revision ==='
    git rev-parse --verify HEAD
    git status --short
    echo
    printf '%s\n' '=== DeckCheatz offline AIO regressions + GTK syntax ==='
    bash "$ROOT/scripts/pc2-deckcheatz-aio.sh"
    grep -Fq 'Result: PASS (OFFLINE FIXTURES + GUI SYNTAX ONLY)' "$AIO_REPORT" || {
        printf '%s\n' 'FAIL: DeckCheatz AIO did not return PASS'; exit 4;
    }
    echo
    printf '%s\n' '=== Source AppDir helper layout (no launch) ==='
    bash "$ROOT/scripts/run-pc2-source-frontend.sh" --check-layout
    for helper in gameweld-deckcheatz-direct.py gameweld-deckcheatz-proton.py \
                  gameweld-deckcheatz-install.py; do
        test -f "$ROOT/build/pc2-source/dev-AppDir/usr/libexec/$helper" || {
            printf 'FAIL: source AppDir lacks %s\n' "$helper"; exit 5;
        }
    done
    echo
    printf '%s\n' '=== Go backend test suite ==='
    (cd "$ROOT/cmd/gameweld-backend" && go test ./...)
    printf '%s\n' '=== Build Go backend ==='
    (cd "$ROOT/cmd/gameweld-backend" && go build -trimpath -o "$OUT/wand-native-backend" .)
    test -s "$OUT/wand-native-backend" || { printf '%s\n' 'FAIL: Go backend binary absent'; exit 6; }
    printf '%s\n' '=== Link complete GTK frontend (do not execute it) ==='
    gcc -O2 -pipe -pthread -DGAMEWELD_PC2_DISCOVERY_ONLY=1 \
        "$ROOT/crates/wand-ui/appimage-gtk3/gameweld-native-040.c" \
        -o "$OUT/gameweld" \
        $(pkg-config --cflags --libs gtk+-3.0)
    test -s "$OUT/gameweld" || { printf '%s\n' 'FAIL: GTK executable absent'; exit 7; }
    printf '%s\n' '=== Output artifact hashes (non-game executable build outputs) ==='
    sha256sum "$OUT/wand-native-backend" "$OUT/gameweld"
    echo
    printf '%s\n' 'Result: PASS (OFFLINE SOURCE BUILD + FIXTURES ONLY)'
    printf '%s\n' 'Still untested: runtime GUI resize, other games, fresh network install, actual updater replacement.'
} 2>&1 | tee "$REPORT"

printf 'Report: %s\n' "$REPORT"
