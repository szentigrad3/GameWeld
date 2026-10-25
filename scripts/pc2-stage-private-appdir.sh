#!/usr/bin/env bash
# Stage an UNPUBLISHED source-built PC2 AppDir for private packaging research.
# Not a portable AppImage: GTK/system dependencies and redistribution are not cleared.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="${GAMEWELD_PC2_STAGE:-$ROOT/build/pc2-source/private-AppDir}"
for cmd in gcc go pkg-config python3; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }; done
pkg-config --exists gtk+-3.0 || { echo "Missing GTK3 development headers" >&2; exit 1; }
if [[ -e "$OUT" ]]; then echo "Refusing to overwrite existing AppDir: $OUT" >&2; exit 2; fi
mkdir -p "$OUT/usr/bin" "$OUT/usr/libexec"
(cd cmd/gameweld-backend && go test ./... && go build -trimpath -o "$OUT/usr/bin/wand-native-backend" .)
MODE="${GAMEWELD_PC2_BUILD_MODE:-discovery}"
case "$MODE" in
  discovery) CFLAGS=(-DGAMEWELD_PC2_DISCOVERY_ONLY=1) ;;
  functional)
    [[ "${GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST:-}" == "I_UNDERSTAND_PRIVATE_TEST_ONLY" ]] || {
      echo "Functional mode requires GAMEWELD_PC2_ENABLE_FUNCTIONAL_TEST=I_UNDERSTAND_PRIVATE_TEST_ONLY" >&2
      exit 2
    }
    CFLAGS=()
    ;;
  *) echo "Invalid GAMEWELD_PC2_BUILD_MODE: $MODE" >&2; exit 2 ;;
esac
gcc -O2 -pipe -pthread "${CFLAGS[@]}" \
  crates/wand-ui/appimage-gtk3/gameweld-native-040.c \
  -o "$OUT/usr/bin/gameweld" $(pkg-config --cflags --libs gtk+-3.0)
for helper in scripts/gameweld-*.py scripts/gameweld-*.sh scripts/gameforge-*.sh scripts/wand-*.sh; do
  [[ -f "$helper" ]] || continue
  cp -- "$helper" "$OUT/usr/libexec/"
done
for required in gameweld-steam-compat-bridge.py gameweld-deckcheatz-direct.py \
                gameweld-deckcheatz-proton.py gameweld-deckcheatz-install.py; do
  test -s "$OUT/usr/libexec/$required" || { echo "Missing staged helper: $required" >&2; exit 3; }
done
cat > "$OUT/AppRun" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
APPDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR
export WAND_NATIVE_BACKEND="$APPDIR/usr/bin/wand-native-backend"
export PATH="$APPDIR/usr/libexec:${PATH:-/usr/bin:/bin}"
exec "$APPDIR/usr/bin/gameweld" "$@"
EOF
chmod 755 "$OUT/AppRun" "$OUT/usr/bin/gameweld" "$OUT/usr/bin/wand-native-backend"
printf '%s\n' 'PRIVATE SOURCE-BUILT APPDIR ONLY (NOT AN APPIMAGE / NOT APPROVED FOR DISTRIBUTION)' > "$OUT/NOT-FOR-DISTRIBUTION.txt"
printf 'Build mode: %s\n' "$MODE" >> "$OUT/NOT-FOR-DISTRIBUTION.txt"
printf 'Git revision: %s\n' "$(git rev-parse HEAD)" >> "$OUT/NOT-FOR-DISTRIBUTION.txt"
sha256sum "$OUT/usr/bin/gameweld" "$OUT/usr/bin/wand-native-backend"
echo "Created: $OUT"
echo 'Do not publish. Build is dynamically linked and third-party redistribution review is outstanding.'
