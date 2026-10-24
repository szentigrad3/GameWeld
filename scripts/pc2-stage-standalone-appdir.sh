#!/usr/bin/env bash
# Build a PRIVATE, relocatable PC2 development AppDir for local testing.
# Not a redistributable AppImage, not a cleared public release.
# No legacy PC1 binaries, trainer binaries or external DeckCheatz source.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${GAMEWELD_PC2_STAGE_DIR:-$ROOT/build/pc2-source/pc2-test-AppDir}"
case "$OUT" in /*) ;; *) echo 'Set GAMEWELD_PC2_STAGE_DIR to an absolute path' >&2; exit 2;; esac
case "$OUT/" in "$ROOT/"build/*) ;; *) echo 'Refusing to stage outside the GameWeld build directory' >&2; exit 2;; esac
test ! -L "$OUT" || { echo 'Refusing to replace a symlinked staging destination' >&2; exit 2; }

bash "$ROOT/scripts/pc2-rc1-preflight.sh"
BUILT="$ROOT/build/pc2-source/rc1-preflight"
TEMP="$(mktemp -d "$ROOT/build/pc2-source/.pc2-stage-XXXXXXXX")"
trap 'rm -rf -- "$TEMP"' EXIT
APP="$TEMP/AppDir"
mkdir -p "$APP/usr/bin" "$APP/usr/libexec" "$APP/usr/share/gameweld"
install -m 0755 "$BUILT/gameweld" "$APP/usr/bin/gameweld"
install -m 0755 "$BUILT/wand-native-backend" "$APP/usr/libexec/wand-native-backend"
# Keep all helpers outside the main binary, but physically included in the
# isolated AppDir. The source runner uses symlinks; this candidate uses copies.
for helper in "$ROOT"/scripts/gameweld-*.py "$ROOT"/scripts/gameweld-*.sh \
              "$ROOT"/scripts/gameforge-*.sh "$ROOT"/scripts/wand-*.sh; do
    [[ -f "$helper" ]] || continue
    case "$helper" in *.sh) perms=0755 ;; *) perms=0644 ;; esac
    install -m "$perms" "$helper" "$APP/usr/libexec/${helper##*/}"
done
for required in gameweld-deckcheatz-direct.py gameweld-deckcheatz-proton.py \
                gameweld-deckcheatz-install.py gameweld-steam-game-exe.py \
                gameweld-platform-session.py gameweld-steam-wemod-platform.py \
                gameweld-wemod-client-audit.py gameweld-wemod-prefix-readiness.py \
                gameweld-steam-wemod-runtime-audit.py \
                gameweld-steam-shortcuts.py gameweld-steam-handoff.py \
                gameweld-heroic-provider.py gameweld-heroic-launch.sh \
                gameweld-lutris-provider.py gameweld-lutris-session.sh; do
    test -s "$APP/usr/libexec/$required" || {
        printf 'Missing runtime helper: %s\n' "$required" >&2; exit 3;
    }
done

cat > "$APP/AppRun" <<'APP_RUN'
#!/usr/bin/env bash
# Local source-build AppDir entrypoint, not a distributable AppImage.
set -Eeuo pipefail
APPDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR
export WAND_NATIVE_BACKEND="$APPDIR/usr/libexec/wand-native-backend"
exec "$APPDIR/usr/bin/gameweld" "$@"
APP_RUN
chmod 0755 "$APP/AppRun"
cat > "$APP/PC2-DEVELOPMENT-ONLY.txt" <<'NOTICE'
GameWeld PC2 development source AppDir.
This is NOT a distributable AppImage or release candidate.
Host GTK3 libraries are required; no library bundling or public license audit
has been performed. Upstream DeckCheatz/WeMod and game files are NOT bundled.
Installer and launcher remain separate user-consent actions.
NOTICE

# Never fold the live repository or an already-installed GameWeld binary into
# this isolated stage. No symlinked helper may escape on another user's system.
if find "$APP" -type l -print -quit | grep -q .; then
    echo 'Refusing stage: helper symlink found' >&2; exit 4
fi
if [[ -e "$OUT" ]]; then
    echo "Staging destination already exists: $OUT" >&2
    echo 'Move it aside yourself, then rerun. Existing files were not touched.' >&2
    exit 5
fi
mv -- "$APP" "$OUT"
printf '%s\n' 'PC2 standalone development AppDir staged (not an AppImage).'
printf 'Path: %s\n' "$OUT"
printf 'Entrypoint: %s/AppRun\n' "$OUT"
printf '%s\n' 'No trainer or game launched; Steam Launch Options and Wine prefixes unchanged.'
