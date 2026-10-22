#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
TARBALL="${1:-$HOME/src/wand-ge-proton/build/GE-Proton-Wand-SHA256.tar.gz}"
[[ -f "$TARBALL" ]] || { echo "Missing Proton tarball: $TARBALL" >&2; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
tar -xf "$TARBALL" -C "$TMP"
for arch in x86_64-windows i386-windows; do
  src="$(find "$TMP" -type f -path "*/$arch/crypt32.dll" -print -quit)"
  [[ -n "$src" ]] || { echo "No $arch crypt32.dll in tarball" >&2; exit 1; }
  dst="$ROOT/payload/crypt32/$arch/crypt32.dll"
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
  chmod 0644 "$dst"
  echo "$arch: $(sha256sum "$dst")"
done
cat > "$ROOT/payload/crypt32/SHA256SUMS" <<EOF2
$(cd "$ROOT/payload/crypt32" && sha256sum x86_64-windows/crypt32.dll i386-windows/crypt32.dll)
EOF2
python3 - "$ROOT/payload/crypt32/manifest.json" \
  "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" \
  "$ROOT/payload/crypt32/i386-windows/crypt32.dll" <<'PY2'
import hashlib,json,pathlib,sys
manifest,x64,i386=map(pathlib.Path,sys.argv[1:])
obj=json.loads(manifest.read_text())
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
obj['patched_x86_64_crypt32_sha256']=h(x64)
obj['patched_i386_crypt32_sha256']=h(i386)
manifest.write_text(json.dumps(obj,indent=2)+'\n')
PY2
echo "Payload populated. Run scripts/package-release.sh after building Wand Native binaries."
