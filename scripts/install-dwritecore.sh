#!/usr/bin/env bash
set -euo pipefail

VERSION="${WAND_DWRITECORE_VERSION:-2.1.0}"
PACKAGE="microsoft.windowsappsdk.dwrite"
MEMBER="runtimes-framework/win-x64/native/DWriteCore.dll"
ROOT="${WAND_DWRITECORE_ROOT:-$HOME/.local/share/wand/dwritecore/$VERSION}"
TARGET_EXE=""
QUIET=0

usage() {
  cat <<'EOF'
Usage:
  install-dwritecore.sh [--target-exe /path/to/Wand.exe|WeMod.exe] [--quiet]

Downloads Microsoft's official Microsoft.WindowsAppSDK.DWrite NuGet package,
extracts the x64 DWriteCore.dll, stores it under ~/.local/share/wand/, and
optionally places a copy beside the supplied Wand/WeMod executable.

No Microsoft DLL is bundled in Wand Native itself.
EOF
}

while (($#)); do
  case "$1" in
    --target-exe)
      TARGET_EXE="${2:-}"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v python3 >/dev/null || {
  echo "python3 is required to retrieve DWriteCore." >&2
  exit 1
}

mkdir -p "$ROOT"
SHARED="$ROOT/DWriteCore.dll"
META="$ROOT/source.json"

if [[ ! -s "$SHARED" || "${WAND_DWRITECORE_FORCE:-0}" == "1" ]]; then
  (( QUIET )) || echo "==> Downloading official Microsoft DWriteCore $VERSION from NuGet"
  python3 - "$VERSION" "$PACKAGE" "$MEMBER" "$SHARED" "$META" <<'PY'
import hashlib
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile

version, package, member, target, meta = sys.argv[1:]
url = (
    f"https://api.nuget.org/v3-flatcontainer/{package}/"
    f"{version}/{package}.{version}.nupkg"
)

req = urllib.request.Request(
    url,
    headers={"User-Agent": "Wand-Native-DWriteCore/0.1.42"},
)
with urllib.request.urlopen(req, timeout=60) as response:
    payload = response.read()

with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    data = archive.read(member)

if len(data) < 1024 * 1024 or data[:2] != b"MZ":
    raise SystemExit("Downloaded DWriteCore.dll failed PE/size validation")

os.makedirs(os.path.dirname(target), exist_ok=True)
fd, partial = tempfile.mkstemp(prefix="DWriteCore.", suffix=".part", dir=os.path.dirname(target))
try:
    with os.fdopen(fd, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(partial, target)
finally:
    if os.path.exists(partial):
        os.unlink(partial)

info = {
    "package": package,
    "version": version,
    "member": member,
    "url": url,
    "size": len(data),
    "sha256": hashlib.sha256(data).hexdigest(),
}
with open(meta, "w", encoding="utf-8") as out:
    json.dump(info, out, indent=2)
    out.write("\n")

print(f"Installed shared DWriteCore.dll: {target}")
print(f"SHA-256: {info['sha256']}")
PY
fi

if [[ -n "$TARGET_EXE" ]]; then
  [[ -f "$TARGET_EXE" ]] || {
    echo "Target executable not found: $TARGET_EXE" >&2
    exit 1
  }
  TARGET_DIR="$(dirname "$TARGET_EXE")"
  TARGET="$TARGET_DIR/DWriteCore.dll"
  install -Dm644 "$SHARED" "$TARGET"
  (( QUIET )) || echo "==> Installed DWriteCore.dll beside $(basename "$TARGET_EXE")"
  (( QUIET )) || echo "    $TARGET"
fi

(( QUIET )) || echo "DWriteCore ready: $SHARED"
