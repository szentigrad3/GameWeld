#!/usr/bin/env bash
set -Eeuo pipefail

TOOL_ID="GE-Proton-Wand-SHA256"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/wand-native"
PAYLOAD_ROOT="${WAND_PAYLOAD_ROOT:-$DATA_HOME/payload/crypt32}"
CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/wand-native/ge-proton"
PAYLOAD_MANIFEST="$PAYLOAD_ROOT/manifest.json"
BASELINE="GE-Proton11-7"
BASELINE_X64_CRYPT32_SHA256="000505b2ea8ce65c57ef1610b6f1e96d3a73fb11388ba812dd71a180b722bf29"
BASELINE_ASSET="GE-Proton11-7-x86_64.tar.gz"
BASELINE_URL="https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-7/$BASELINE_ASSET"
BASELINE_SHA_ASSET="GE-Proton11-7-x86_64.sha512sum"
BASELINE_SHA_URL="https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-7/$BASELINE_SHA_ASSET"

say() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

steam_roots() {
  {
    [[ -n "${STEAM_DIR:-}" ]] && printf '%s\n' "$STEAM_DIR"
    printf '%s\n' \
      "$HOME/.local/share/Steam" \
      "$HOME/.steam/root" \
      "$HOME/.steam/steam"
  } | while IFS= read -r root; do
    [[ -d "$root" ]] || continue
    readlink -f "$root" 2>/dev/null || printf '%s\n' "$root"
  done | awk '!seen[$0]++'
}

steam_libraries() {
  {
    steam_roots
    while IFS= read -r root; do
      for vdf in "$root/steamapps/libraryfolders.vdf" "$root/config/libraryfolders.vdf"; do
        [[ -f "$vdf" ]] || continue
        sed -nE 's/^[[:space:]]*"path"[[:space:]]+"([^"]+)".*/\1/p' "$vdf" | sed 's#\\\\#/#g'
      done
    done < <(steam_roots)
  } | while IFS= read -r path; do
    [[ -d "$path" ]] || continue
    readlink -f "$path" 2>/dev/null || printf '%s\n' "$path"
  done | awk '!seen[$0]++'
}

fetch_url() {
  local url="$1" out="$2"
  if command -v curl >/dev/null; then
    curl -fL --retry 3 --connect-timeout 20 -o "$out" "$url"
  elif command -v wget >/dev/null; then
    wget -O "$out" "$url"
  else
    die "curl or wget is required to download the tested Proton-GE baseline"
  fi
}

candidate_x64_crypt32() {
  find "$1/files" -type f -path '*/x86_64-windows/crypt32.dll' -print -quit 2>/dev/null || true
}

compatible_base() {
  local dir="$1" dll hash
  [[ -x "$dir/proton" ]] || return 1
  dll="$(candidate_x64_crypt32 "$dir")"
  [[ -n "$dll" && -f "$dll" ]] || return 1
  hash="$(sha256_file "$dll")"
  [[ "$hash" == "$BASELINE_X64_CRYPT32_SHA256" ]]
}

download_baseline() {
  command -v tar >/dev/null || die "tar is required"
  command -v sha512sum >/dev/null || die "sha512sum is required"
  mkdir -p "$CACHE_ROOT"
  local tarball="$CACHE_ROOT/$BASELINE_ASSET"
  local checksum="$CACHE_ROOT/$BASELINE_SHA_ASSET"
  local extracted="$CACHE_ROOT/$BASELINE"

  if [[ ! -s "$tarball" || ! -s "$checksum" ]]; then
    say "No installed Proton-GE matches the tested Wand baseline." >&2
    say "Downloading the official $BASELINE runtime once (~540 MiB)..." >&2
    fetch_url "$BASELINE_SHA_URL" "$checksum.part"
    mv "$checksum.part" "$checksum"
    fetch_url "$BASELINE_URL" "$tarball.part"
    mv "$tarball.part" "$tarball"
  fi

  say "Verifying official GE-Proton checksum..." >&2
  (cd "$CACHE_ROOT" && sha512sum -c "$BASELINE_SHA_ASSET") >/dev/null \
    || { rm -f "$tarball"; die "GE-Proton checksum verification failed"; }

  if [[ ! -x "$extracted/proton" ]]; then
    say "Extracting $BASELINE..." >&2
    rm -rf "$extracted"
    tar -xf "$tarball" -C "$CACHE_ROOT"
  fi
  compatible_base "$extracted" || die "Downloaded $BASELINE does not match the tested crypt32 fingerprint"
  printf '%s\n' "$extracted"
}

find_base_proton() {
  if [[ -n "${WAND_BASE_PROTON:-}" ]]; then
    [[ -x "$WAND_BASE_PROTON/proton" ]] || die "WAND_BASE_PROTON is not a Proton tool: $WAND_BASE_PROTON"
    if compatible_base "$WAND_BASE_PROTON" || [[ "${WAND_ALLOW_UNTESTED_PROTON:-0}" == "1" ]]; then
      printf '%s\n' "$WAND_BASE_PROTON"
      return
    fi
    die "WAND_BASE_PROTON does not match the tested $BASELINE baseline"
  fi

  local -a candidates=()
  local root dir
  while IFS= read -r root; do
    for dir in "$root"/compatibilitytools.d/Proton-GE* "$root"/compatibilitytools.d/GE-Proton*; do
      [[ -x "$dir/proton" ]] || continue
      [[ "$dir" == *"$TOOL_ID"* ]] && continue
      [[ "$dir" == *backup* ]] && continue
      candidates+=("$dir")
    done
  done < <(steam_libraries)

  for dir in "$HOME/.local/share/Steam/compatibilitytools.d"/Proton-GE* "$HOME/.local/share/Steam/compatibilitytools.d"/GE-Proton*; do
    [[ -x "$dir/proton" ]] || continue
    [[ "$dir" == *"$TOOL_ID"* ]] && continue
    [[ "$dir" == *backup* ]] && continue
    candidates+=("$dir")
  done

  local candidate
  for candidate in "${candidates[@]}"; do
    if compatible_base "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  download_baseline
}

primary_steam_root() {
  local root
  for root in "$HOME/.steam/root" "$HOME/.local/share/Steam" "$HOME/.var/app/com.valvesoftware.Steam/data/Steam"; do
    [[ -d "$root" ]] || continue
    readlink -f "$root" 2>/dev/null || printf '%s\n' "$root"
    return
  done
  steam_roots | head -1
}

payload_dll() {
  local arch="$1"
  local p="$PAYLOAD_ROOT/$arch/crypt32.dll"
  [[ -s "$p" ]] || die "Wand crypt32 payload is missing: $p. This release bundle is incomplete."
  printf '%s\n' "$p"
}

write_manifest() {
  local dest="$1"
  rm -f "$dest/compatibilitytool.vdf"
  cat > "$dest/compatibilitytool.vdf" <<EOFVDF
"compatibilitytools"
{
  "compat_tools"
  {
    "$TOOL_ID"
    {
      "install_path" "."
      "display_name" "GE Proton Wand SHA256"
      "from_oslist" "windows"
      "to_oslist" "linux"
    }
  }
}
EOFVDF
}

metadata_path() { printf '%s/WAND-HYBRID.json\n' "$1"; }

install_tool() {
  command -v rsync >/dev/null || die "rsync is required"
  command -v sha256sum >/dev/null || die "sha256sum is required"
  command -v python3 >/dev/null || die "python3 is required"

  local base base_parent dest payload64 payload32
  base="$(find_base_proton)"
  base_parent="$(dirname "$base")"
  if [[ "$base_parent" == */compatibilitytools.d ]]; then
    dest="${WAND_PROTON_DEST:-$base_parent/$TOOL_ID}"
  else
    local steam_root
    steam_root="$(primary_steam_root)"
    [[ -n "$steam_root" ]] || die "Could not locate the Steam installation root"
    dest="${WAND_PROTON_DEST:-$steam_root/compatibilitytools.d/$TOOL_ID}"
  fi
  payload64="$(payload_dll x86_64-windows)"
  payload32="$(payload_dll i386-windows)"

  say "Wand Native Proton setup"
  say "  Base Proton: $base"
  say "  Wand tool:   $dest"
  say

  if [[ -e "$dest" ]]; then
    [[ "$(basename "$dest")" == "$TOOL_ID" && "$(basename "$(dirname "$dest")")" == "compatibilitytools.d" ]] \
      || die "Refusing to replace unexpected path: $dest"
    say "Refreshing existing Wand Proton tool..."
    rm -rf -- "$dest"
  fi

  say "Cloning the working Proton-GE runtime..."
  mkdir -p "$dest"
  rsync -aL --delete "$base/" "$dest/"

  local src dst arch old_mode
  for spec in "x86_64-windows:$payload64" "i386-windows:$payload32"; do
    arch="${spec%%:*}"
    src="${spec#*:}"
    dst="$(find "$dest/files" -type f -path "*/$arch/crypt32.dll" -print -quit)"
    [[ -n "$dst" ]] || die "Base Proton has no $arch/crypt32.dll"
    old_mode="$(stat -c '%a' "$dst")"
    chmod u+w "$dst"
    cp -f "$src" "$dst"
    chmod "$old_mode" "$dst"
    cmp -s "$src" "$dst" || die "Failed to verify patched $arch crypt32.dll"
  done

  write_manifest "$dest"

  python3 - "$base" "$dest" "$payload64" "$payload32" "$(metadata_path "$dest")" <<'PY'
import json, hashlib, pathlib, sys, datetime
base, dest, p64, p32, out = map(pathlib.Path, sys.argv[1:])
def h(p):
    d=hashlib.sha256();
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): d.update(b)
    return d.hexdigest()
def find(root, arch):
    xs=list((root/'files').glob(f'**/{arch}/crypt32.dll'))
    return xs[0] if xs else None
obj={
  'schema': 1,
  'tool_id': 'GE-Proton-Wand-SHA256',
  'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'base_proton': str(base),
  'base_x86_64_crypt32_sha256': h(find(base,'x86_64-windows')),
  'base_i386_crypt32_sha256': h(find(base,'i386-windows')),
  'patched_x86_64_crypt32_sha256': h(p64),
  'patched_i386_crypt32_sha256': h(p32),
  'destination': str(dest),
}
out.write_text(json.dumps(obj,indent=2)+'\n')
PY

  say
  say "Installed successfully."
  say "Restart Steam, then for each game you want to use with Wand:"
  say "  Properties -> Compatibility -> Force compatibility tool -> GE Proton Wand SHA256"
  say
  say "Wand itself can remain on your normal Proton-GE setup."
}

locate_install() {
  local root d
  if [[ -n "${WAND_PROTON_DEST:-}" && -d "$WAND_PROTON_DEST" ]]; then
    printf '%s\n' "$WAND_PROTON_DEST"; return
  fi
  while IFS= read -r root; do
    d="$root/compatibilitytools.d/$TOOL_ID"
    [[ -d "$d" ]] && { printf '%s\n' "$d"; return; }
  done < <(steam_libraries)
  d="$HOME/.local/share/Steam/compatibilitytools.d/$TOOL_ID"
  [[ -d "$d" ]] && { printf '%s\n' "$d"; return; }
  return 1
}

verify_tool() {
  local dest p64 p32 d64 d32 failed=0
  dest="$(locate_install)" || die "Wand Proton is not installed"
  p64="$(payload_dll x86_64-windows)"; p32="$(payload_dll i386-windows)"
  d64="$(find "$dest/files" -type f -path '*/x86_64-windows/crypt32.dll' -print -quit)"
  d32="$(find "$dest/files" -type f -path '*/i386-windows/crypt32.dll' -print -quit)"

  say "Wand Proton verification"
  say "  Tool: $dest"
  for spec in "x86_64:$p64:$d64" "i386:$p32:$d32"; do
    local label rest src dst
    label="${spec%%:*}"; rest="${spec#*:}"; src="${rest%%:*}"; dst="${rest#*:}"
    if [[ -n "$dst" && -f "$dst" ]] && cmp -s "$src" "$dst"; then
      say "  $label crypt32: OK ($(sha256_file "$dst"))"
    else
      say "  $label crypt32: FAILED"
      failed=1
    fi
  done
  [[ -f "$dest/compatibilitytool.vdf" ]] && say "  Steam manifest: OK" || { say "  Steam manifest: FAILED"; failed=1; }
  [[ -f "$(metadata_path "$dest")" ]] && say "  Wand metadata: OK" || { say "  Wand metadata: FAILED"; failed=1; }

  ((failed == 0)) || exit 2
  say "Result: healthy"
}

remove_tool() {
  local dest
  if ! dest="$(locate_install)"; then
    say "Wand Proton is not installed"
    return 0
  fi
  [[ "$(basename "$dest")" == "$TOOL_ID" && "$(basename "$(dirname "$dest")")" == "compatibilitytools.d" ]] \
    || die "Refusing to remove unexpected path: $dest"
  rm -rf -- "$dest"
  say "Removed Wand Proton from Steam compatibility tools."
  say "Restart Steam to refresh the compatibility-tool list."
}

status_tool() {
  local dest
  if ! dest="$(locate_install)"; then
    say "Wand Proton: not installed"
    say "Run: wandctl setup"
    return 1
  fi
  say "Wand Proton: installed"
  say "Path: $dest"
  if [[ -f "$(metadata_path "$dest")" ]]; then
    python3 - "$(metadata_path "$dest")" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
print('Base Proton:',x.get('base_proton','unknown'))
print('Created:',x.get('created_at','unknown'))
PY
  fi
  verify_tool
}

case "${1:-}" in
  install|setup) install_tool ;;
  verify) verify_tool ;;
  status) status_tool ;;
  remove) remove_tool ;;
  *)
    cat <<EOFUSAGE
Usage: wand-proton-manager {install|status|verify|remove}

Normal setup:
  wandctl setup

Advanced:
  wandctl proton install
  wandctl proton status
  wandctl proton verify
  wandctl proton remove
EOFUSAGE
    exit 2
    ;;
esac
