#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  diagnose-wand-rendering.sh system-wine APPID [-- extra Wand args]
  diagnose-wand-rendering.sh proton      APPID [-- extra Wand args]
  diagnose-wand-rendering.sh proton-system-dwrite APPID [-- extra Wand args]
  diagnose-wand-rendering.sh proton-no-colrv1 APPID [-- extra Wand args]
  diagnose-wand-rendering.sh proton-dwritecore APPID [-- extra Wand args]

Examples:
  ./scripts/diagnose-wand-rendering.sh system-wine 2713000
  ./scripts/diagnose-wand-rendering.sh proton 2713000
  ./scripts/diagnose-wand-rendering.sh proton-system-dwrite 2713000
  ./scripts/diagnose-wand-rendering.sh proton-no-colrv1 2713000
  ./scripts/diagnose-wand-rendering.sh proton-dwritecore 2713000
  ./scripts/diagnose-wand-rendering.sh proton 2713000 -- --disable-gpu

The game must be closed. The script enforces a clean Wine-server boundary
before and after each run so system Wine and Proton cannot contaminate each
other's test.

Diagnostics are written under:
  ~/.local/state/wand/render-diagnostics/
USAGE
}

[[ $# -ge 2 ]] || { usage >&2; exit 2; }
ENGINE="$1"
APPID="$2"
shift 2

if [[ "${1:-}" == "--" ]]; then shift; fi
EXTRA_ARGS=("$@")

case "$ENGINE" in
  system-wine|proton|proton-system-dwrite|proton-no-colrv1|proton-dwritecore) ;;
  *) echo "Unknown engine: $ENGINE" >&2; usage >&2; exit 2 ;;
esac

for cmd in wandctl jq ps find sed awk python3 fc-list; do
  command -v "$cmd" >/dev/null || {
    echo "$cmd is required for renderer diagnostics." >&2
    exit 1
  }
done

INSPECT_JSON="$(wandctl inspect "$APPID")"
STATUS_JSON="$(wandctl status)"
PREFIX="$(jq -r '.game.prefix_dir' <<<"$INSPECT_JSON")"
COMPAT="$(jq -r '.game.compatdata_dir' <<<"$INSPECT_JSON")"
INSTALL_DIR="$(jq -r '.game.install_dir' <<<"$INSPECT_JSON")"
PROTON_SCRIPT="$(jq -r '.proton.proton_script // empty' <<<"$INSPECT_JSON")"
PROTON_ROOT="$(jq -r '.proton.root // empty' <<<"$INSPECT_JSON")"
PROTON_NAME="$(jq -r '.proton.display_name // empty' <<<"$INSPECT_JSON")"
STEAM_ROOT="$(jq -r '.steam_root // empty' <<<"$STATUS_JSON")"

[[ -d "$PREFIX" ]] || { echo "Prefix not found: $PREFIX" >&2; exit 1; }

# Refuse to mix this standalone diagnostic with a live game session.
if wandctl processes "$APPID" | jq -e '.best_candidate_pid != null' >/dev/null 2>&1; then
  echo "Steam AppID $APPID is running. Close the game before renderer diagnostics." >&2
  exit 1
fi

WAND_EXE="${WAND_WEMOD_EXE:-}"
if [[ -z "$WAND_EXE" || ! -f "$WAND_EXE" ]]; then
  WAND_EXE="$(find "$PREFIX/drive_c/users" -type f \( -iname Wand.exe -o -iname WeMod.exe \) \
    -path '*/AppData/Local/*' -print 2>/dev/null | sort -V | tail -1)"
fi
[[ -n "$WAND_EXE" && -f "$WAND_EXE" ]] || {
  echo "Could not find Wand.exe/WeMod.exe inside $PREFIX" >&2
  exit 1
}

SYSTEM_WINESERVER="$(command -v wineserver || true)"
PROTON_WINESERVER=""
if [[ -n "$PROTON_ROOT" ]]; then
  for candidate in \
    "$PROTON_ROOT/files/bin/wineserver" \
    "$PROTON_ROOT/files/lib/wine/x86_64-unix/wineserver"
  do
    if [[ -x "$candidate" ]]; then
      PROTON_WINESERVER="$candidate"
      break
    fi
  done
fi

find_system_dwrite() {
  local candidates=(
    "/usr/lib/wine/x86_64-windows/dwrite.dll"
    "/usr/lib64/wine/x86_64-windows/dwrite.dll"
    "/usr/local/lib/wine/x86_64-windows/dwrite.dll"
  )

  local wine_bin
  wine_bin="$(command -v wine || true)"
  if [[ -n "$wine_bin" ]]; then
    local wine_real wine_prefix
    wine_real="$(readlink -f "$wine_bin" 2>/dev/null || printf '%s' "$wine_bin")"
    wine_prefix="$(dirname "$(dirname "$wine_real")")"
    candidates+=(
      "$wine_prefix/lib/wine/x86_64-windows/dwrite.dll"
      "$wine_prefix/lib64/wine/x86_64-windows/dwrite.dll"
    )
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  find /usr/lib /usr/lib64 /usr/local/lib -type f \
    -path '*/wine/x86_64-windows/dwrite.dll' -print 2>/dev/null \
    | head -1
}

SYSTEM_DWRITE="$(find_system_dwrite || true)"

matching_prefix_wine_pids() {
  python3 - "$PREFIX" <<'PY'
import os, sys
prefix = sys.argv[1]
for name in os.listdir("/proc"):
    if not name.isdigit():
        continue
    pid = int(name)
    try:
        env = open(f"/proc/{pid}/environ", "rb").read().split(b"\0")
        env = dict(
            item.split(b"=", 1) for item in env
            if b"=" in item
        )
        if env.get(b"WINEPREFIX", b"").decode(errors="ignore") != prefix:
            continue
        comm = open(f"/proc/{pid}/comm", "r", errors="replace").read().strip()
        cmdline = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
        if any(token in comm.lower() or token in cmdline.lower()
               for token in ("wine", "wineserver", "wand.exe", "wemod.exe")):
            print(pid)
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
PY
}

shutdown_prefix_wineserver() {
  local phase="$1"

  # Use both implementations. Only the one matching the active server protocol
  # can actually communicate with it; failures are deliberately ignored here.
  if [[ -n "$SYSTEM_WINESERVER" ]]; then
    WINEPREFIX="$PREFIX" "$SYSTEM_WINESERVER" -k >/dev/null 2>&1 || true
  fi
  if [[ -n "$PROTON_WINESERVER" ]]; then
    WINEPREFIX="$PREFIX" "$PROTON_WINESERVER" -k >/dev/null 2>&1 || true
  fi

  for _ in $(seq 1 30); do
    mapfile -t remaining < <(matching_prefix_wine_pids)
    if (( ${#remaining[@]} == 0 )); then
      return 0
    fi
    sleep 0.2
  done

  mapfile -t remaining < <(matching_prefix_wine_pids)
  if (( ${#remaining[@]} > 0 )); then
    echo "Prefix still has Wine processes during $phase:" >&2
    ps -o pid,ppid,stat,comm,args -p "$(IFS=,; echo "${remaining[*]}")" >&2 || true
    echo "Close those processes before rerunning the renderer diagnostic." >&2
    return 1
  fi
}


scan_unsupported_colrv1_fonts() {
  local output="$1"
  local font_list="$2"

  # Do not pipe into Python while also feeding the Python program through a
  # here-document: the heredoc owns stdin and would leave the fc-list pipe
  # unread, causing pipefail to terminate the diagnostic.
  fc-list -f '%{file}\n' | sort -u > "$font_list"

  python3 - "$output" "$font_list" <<'PY'
import os, struct, sys

out = sys.argv[1]
font_list = sys.argv[2]

def u16be(data, off):
    if off + 2 > len(data):
        raise ValueError
    return struct.unpack_from(">H", data, off)[0]

def u32be(data, off):
    if off + 4 > len(data):
        raise ValueError
    return struct.unpack_from(">I", data, off)[0]

def face_offsets(data):
    if data[:4] == b"ttcf":
        count = u32be(data, 8)
        if count > 65535:
            raise ValueError("implausible TTC face count")
        return [u32be(data, 12 + i * 4) for i in range(count)]
    return [0]

def colr_info(data, face):
    if face + 12 > len(data):
        return None
    num_tables = u16be(data, face + 4)
    table_dir = face + 12
    for i in range(num_tables):
        rec = table_dir + i * 16
        if rec + 16 > len(data):
            return None
        tag = data[rec:rec+4]
        if tag != b"COLR":
            continue
        # SFNT/TTC table offsets are file-relative.
        offset = u32be(data, rec + 8)
        length = u32be(data, rec + 12)
        if offset + 4 > len(data) or length < 4:
            return None
        version = u16be(data, offset)
        num_baseglyph_records = u16be(data, offset + 2)
        return version, num_baseglyph_records
    return None

bad = []
seen = set()

with open(font_list, "r", encoding="utf-8", errors="replace") as source:
    for line in source:
        path = line.rstrip("\n")
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            with open(path, "rb") as f:
                data = f.read()
            matches = []
            for idx, face in enumerate(face_offsets(data)):
                info = colr_info(data, face)
                if info:
                    version, legacy_count = info
                    # Match Wine commit 742dd377: COLR version != 0 with no
                    # legacy base-glyph records is unsupported by older dwrite.
                    if version != 0 and legacy_count == 0:
                        matches.append((idx, version, legacy_count))
            if matches:
                bad.append((path, matches))
        except Exception:
            pass

with open(out, "w", encoding="utf-8") as f:
    for path, matches in bad:
        faces = ",".join(
            f"face={idx}:COLR-v{version}:legacy-baseglyphs={count}"
            for idx, version, count in matches
        )
        f.write(f"{path}\t{faces}\n")

print(len(bad))
PY
}

xml_escape() {
  python3 -c 'import html,sys; print(html.escape(sys.stdin.read().rstrip("\n"), quote=True))'
}

build_no_colrv1_fontconfig() {
  local list="$1"
  local config="$2"

  {
    echo '<?xml version="1.0"?>'
    echo '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
    echo '<fontconfig>'
    echo '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>'
    echo '  <selectfont>'
    echo '    <rejectfont>'
    while IFS=$'\t' read -r font_file detail; do
      [[ -n "$font_file" ]] || continue
      escaped="$(printf '%s' "$font_file" | xml_escape)"
      printf '      <glob>%s</glob>\n' "$escaped"
    done < "$list"
    echo '    </rejectfont>'
    echo '  </selectfont>'
    echo '</fontconfig>'
  } > "$config"
}

echo "Ensuring AppID $APPID prefix has no leftover Wine server..."
shutdown_prefix_wineserver "pre-launch cleanup"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_BASE="${XDG_STATE_HOME:-$HOME/.local/state}/wand/render-diagnostics"
OUT="$OUT_BASE/${STAMP}-${ENGINE}-appid${APPID}"
mkdir -p "$OUT"

printf '%s\n' "$INSPECT_JSON" > "$OUT/inspect.json"
printf '%s\n' "$STATUS_JSON" > "$OUT/status.json"
env | sort > "$OUT/host-environment.txt"

COLRV1_LIST="$OUT/unsupported-colrv1-fonts.txt"
COLRV1_SOURCE_LIST="$OUT/fontconfig-source-files.txt"
COLRV1_CONFIG="$OUT/fontconfig-no-colrv1.conf"
COLRV1_COUNT=0

if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
  echo "Scanning installed fonts for unsupported COLRv1-only faces..."
  COLRV1_COUNT="$(scan_unsupported_colrv1_fonts "$COLRV1_LIST" "$COLRV1_SOURCE_LIST")"
  echo "Found $COLRV1_COUNT unsupported COLRv1-only font file(s)."
  build_no_colrv1_fontconfig "$COLRV1_LIST" "$COLRV1_CONFIG"

  {
    echo "font_source_file_count=$(wc -l < "$COLRV1_SOURCE_LIST")"
    echo "unsupported_colrv1_font_count=$COLRV1_COUNT"
    echo "fontconfig_file=$COLRV1_CONFIG"
  } > "$OUT/colrv1-scan-summary.txt"

  # Prove the generated policy actually filters the discovered files.
  FONTCONFIG_FILE="$COLRV1_CONFIG" fc-list -f '%{file}\n' | sort -u \
    > "$OUT/fontconfig-visible-files.txt"
  : > "$OUT/fontconfig-filter-verification.txt"
  while IFS=$'\t' read -r font_file detail; do
    [[ -n "$font_file" ]] || continue
    if grep -Fxq "$font_file" "$OUT/fontconfig-visible-files.txt"; then
      printf 'FAIL\t%s\t%s\n' "$font_file" "$detail" \
        >> "$OUT/fontconfig-filter-verification.txt"
    else
      printf 'PASS\t%s\t%s\n' "$font_file" "$detail" \
        >> "$OUT/fontconfig-filter-verification.txt"
    fi
  done < "$COLRV1_LIST"
fi

{
  echo "engine=$ENGINE"
  echo "appid=$APPID"
  echo "prefix=$PREFIX"
  echo "compatdata=$COMPAT"
  echo "install_dir=$INSTALL_DIR"
  echo "wand_exe=$WAND_EXE"
  echo "steam_root=$STEAM_ROOT"
  echo "proton_name=$PROTON_NAME"
  echo "proton_root=$PROTON_ROOT"
  echo "proton_script=$PROTON_SCRIPT"
  echo "system_wine=$(command -v wine || true)"
  echo "system_wine_version=$(wine --version 2>/dev/null || true)"
  echo "system_wineserver=$SYSTEM_WINESERVER"
  echo "proton_wineserver=$PROTON_WINESERVER"
  echo "system_dwrite=$SYSTEM_DWRITE"
  if [[ -f "$PROTON_ROOT/version" ]]; then
    printf 'proton_version_file='; tr '\n' ' ' < "$PROTON_ROOT/version"; echo
  fi
  echo "desktop_DISPLAY=${DISPLAY:-}"
  echo "desktop_WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
  echo "desktop_XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-}"
  printf 'extra_args='; printf '%q ' "${EXTRA_ARGS[@]}"; echo
  if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
    echo "unsupported_colrv1_font_count=$COLRV1_COUNT"
    echo "fontconfig_file=$COLRV1_CONFIG"
  fi
  if [[ "$ENGINE" == "proton-dwritecore" ]]; then
    echo "dwritecore_path=$(dirname "$WAND_EXE")/DWriteCore.dll"
  fi
} > "$OUT/summary.txt"

# Snapshot potentially relevant registry state without launching Wine.
# Important: invoking `wine reg query` here would recreate a system-Wine
# wineserver after the pre-launch cleanup and contaminate a Proton A/B test.
USER_REG="$PREFIX/user.reg"
{
  echo "# Source: $USER_REG"
  echo "# Extracted without starting wine/wineserver"
  if [[ -f "$USER_REG" ]]; then
    awk '
      BEGIN { capture=0 }
      /^\[Software\\\\Wine\\\\Drivers\]/ { capture=1 }
      capture {
        if ($0 ~ /^\[/ && $0 !~ /^\[Software\\\\Wine\\\\Drivers\]/ && seen) exit
        print
        seen=1
      }
    ' "$USER_REG"
  else
    echo "user.reg not found"
  fi
} > "$OUT/wine-drivers-registry.txt"

if [[ "$ENGINE" == "proton-dwritecore" ]]; then
  echo "Installing official Microsoft DWriteCore beside Wand/WeMod for this test..."
  "$(dirname "$0")/install-dwritecore.sh" --target-exe "$WAND_EXE"
  DWRITECORE_PATH="$(dirname "$WAND_EXE")/DWriteCore.dll"
  [[ -s "$DWRITECORE_PATH" ]] || {
    echo "DWriteCore installation failed: $DWRITECORE_PATH" >&2
    exit 1
  }
  {
    echo "dwritecore_path=$DWRITECORE_PATH"
    stat -c 'dwritecore_size=%s' "$DWRITECORE_PATH"
    sha256sum "$DWRITECORE_PATH"
  } > "$OUT/dwritecore.txt"
fi

# Sanity boundary: no diagnostic inspection command is allowed to leave a
# wineserver alive before the actual engine launch.
shutdown_prefix_wineserver "final pre-launch cleanup"

# Process sampler. This is intentionally broad enough to catch Electron renderer,
# GPU, utility, Wine and Wand subprocesses without requiring OCR/UI inspection.
(
  for i in $(seq 1 40); do
    echo "===== sample $i $(date --iso-8601=seconds) ====="
    ps -eo pid,ppid,stat,comm,args --sort=pid \
      | grep -Ei 'Wand|WeMod|electron|renderer|gpu-process|utility|crashpad|wine|wineserver' \
      | grep -v -E 'grep -Ei|diagnose-wand-rendering' || true
    sleep 1
  done
) > "$OUT/processes.txt" 2>&1 &
SAMPLER_PID=$!

cleanup() {
  kill "$SAMPLER_PID" 2>/dev/null || true
}
trap cleanup EXIT

COMMON_ELECTRON_ARGS=(
  --enable-logging=stderr
  --v=1
)

# Keep Wine logging useful but bounded. Override if a deeper channel is needed.
export WINEDEBUG="${WAND_DIAG_WINEDEBUG:--all,err+all,warn+all}"
export ELECTRON_ENABLE_LOGGING=1
export ELECTRON_ENABLE_STACK_DUMPING=1

{
  echo "=== pre-engine wineserver snapshot ==="
  ps -eo pid,ppid,stat,comm,args --sort=pid \
    | grep -Ei '(^|[[:space:]])wineserver([[:space:]]|$)' \
    | grep -v -E 'grep -Ei|diagnose-wand-rendering' || true
} > "$OUT/pre-engine-wineservers.txt"

OVERLAY_ACTIVE=0
WAND_DIR="$(dirname "$WAND_EXE")"
WAND_DWRITE="$WAND_DIR/dwrite.dll"
WAND_DWRITE_BACKUP="$OUT/original-dwrite.dll"

restore_dwrite_overlay() {
  if [[ "$OVERLAY_ACTIVE" == "1" ]]; then
    rm -f "$WAND_DWRITE"
    if [[ -f "$WAND_DWRITE_BACKUP" ]]; then
      cp -a "$WAND_DWRITE_BACKUP" "$WAND_DWRITE"
    fi
  fi
}

if [[ "$ENGINE" == "proton-system-dwrite" ]]; then
  [[ -n "$SYSTEM_DWRITE" && -f "$SYSTEM_DWRITE" ]] || {
    echo "Could not locate system Wine x86_64 dwrite.dll." >&2
    exit 1
  }

  if [[ -e "$WAND_DWRITE" ]]; then
    cp -a "$WAND_DWRITE" "$WAND_DWRITE_BACKUP"
  fi

  cp -a "$SYSTEM_DWRITE" "$WAND_DWRITE"
  OVERLAY_ACTIVE=1
  trap 'restore_dwrite_overlay; cleanup' EXIT
fi

set +e
if [[ "$ENGINE" == "system-wine" ]]; then
  WINE_BIN="${WAND_WINE_BIN:-$(command -v wine || true)}"
  [[ -n "$WINE_BIN" ]] || { echo "System Wine not found." >&2; exit 1; }

  {
    echo "WINEPREFIX=$PREFIX"
    echo "WINEDEBUG=$WINEDEBUG"
    echo "ELECTRON_ENABLE_LOGGING=1"
    echo "ELECTRON_ENABLE_STACK_DUMPING=1"
  } > "$OUT/effective-environment.txt"

  echo "Launching Wand with system Wine. Close the Wand window when you are done observing it."
  echo "Diagnostics: $OUT"
  WINEPREFIX="$PREFIX" \
    "$WINE_BIN" "$WAND_EXE" \
    "${COMMON_ELECTRON_ARGS[@]}" "${EXTRA_ARGS[@]}" \
    >"$OUT/stdout.log" 2>"$OUT/stderr.log"
  RC=$?
else
  [[ -n "$PROTON_SCRIPT" && -x "$PROTON_SCRIPT" ]] || {
    echo "Resolved Proton script is missing/not executable: $PROTON_SCRIPT" >&2
    exit 1
  }
  [[ -n "$STEAM_ROOT" ]] || { echo "Could not resolve Steam root from wandctl status." >&2; exit 1; }

  export STEAM_COMPAT_DATA_PATH="$COMPAT"
  export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
  export STEAM_COMPAT_APP_ID="$APPID"
  export SteamAppId="$APPID"
  export SteamGameId="$APPID"
  export PROTON_LOG=1
  export PROTON_LOG_DIR="$OUT"

  if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
    export FONTCONFIG_FILE="$COLRV1_CONFIG"
  fi

  if [[ "$ENGINE" == "proton-system-dwrite" ]]; then
    export WINEDLLOVERRIDES="dwrite=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
  fi

  {
    echo "STEAM_COMPAT_DATA_PATH=$STEAM_COMPAT_DATA_PATH"
    echo "STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_COMPAT_CLIENT_INSTALL_PATH"
    echo "STEAM_COMPAT_APP_ID=$STEAM_COMPAT_APP_ID"
    echo "SteamAppId=$SteamAppId"
    echo "SteamGameId=$SteamGameId"
    echo "PROTON_LOG=$PROTON_LOG"
    echo "PROTON_LOG_DIR=$PROTON_LOG_DIR"
    echo "WINEDLLOVERRIDES=${WINEDLLOVERRIDES:-}"
    echo "FONTCONFIG_FILE=${FONTCONFIG_FILE:-}"
    if [[ "$ENGINE" == "proton-dwritecore" ]]; then
      echo "DWriteCore.dll=$(dirname "$WAND_EXE")/DWriteCore.dll"
      cat "$OUT/dwritecore.txt" 2>/dev/null || true
    fi
    if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
      echo "unsupported_colrv1_font_count=$COLRV1_COUNT"
      cat "$OUT/colrv1-scan-summary.txt" 2>/dev/null || true
    fi
    if [[ "$ENGINE" == "proton-system-dwrite" ]]; then
      echo "wand_local_dwrite=$WAND_DWRITE"
      echo "system_dwrite_source=$SYSTEM_DWRITE"
      sha256sum "$SYSTEM_DWRITE" "$WAND_DWRITE" 2>/dev/null || true
    fi
    echo "WINEDEBUG=$WINEDEBUG"
    echo "ELECTRON_ENABLE_LOGGING=1"
    echo "ELECTRON_ENABLE_STACK_DUMPING=1"
  } > "$OUT/effective-environment.txt"

  echo "Launching Wand with $PROTON_NAME. Close the Wand window when you are done observing it."
  echo "Diagnostics: $OUT"
  "$PROTON_SCRIPT" run "$WAND_EXE" \
    "${COMMON_ELECTRON_ARGS[@]}" "${EXTRA_ARGS[@]}" \
    >"$OUT/stdout.log" 2>"$OUT/stderr.log"
  RC=$?
fi
set -e

restore_dwrite_overlay
OVERLAY_ACTIVE=0
cleanup
trap - EXIT

# A closed Electron window does not guarantee wineserver exited. Shut down the
# diagnostic's prefix server now so the next A/B run cannot inherit a different
# Wine protocol generation.
shutdown_prefix_wineserver "post-launch cleanup" || true

{
  echo "exit_code=$RC"
  echo "finished=$(date --iso-8601=seconds)"
} >> "$OUT/summary.txt"

# Produce a compact triage view so the user does not need to sift through logs.
{
  echo "=== errors/warnings from stderr ==="
  grep -Ei 'error|fatal|fail|exception|crash|gpu|renderer|sandbox|egl|glx|vulkan|dxvk|cef|electron' \
    "$OUT/stderr.log" | tail -200 || true
  echo
  echo "=== pre-engine wineserver snapshot ==="
  cat "$OUT/pre-engine-wineservers.txt" 2>/dev/null || true
  echo
  echo "=== Wine protocol / wineserver highlights ==="
  grep -EHi 'version mismatch|wrong wineserver|wineserver|wine client error'     "$OUT/stderr.log" | tail -100 || true
  for log in "$OUT"/steam-*.log; do
    [[ -f "$log" ]] || continue
    grep -EHi 'version mismatch|wrong wineserver|wineserver|wine client error'       "$log" | tail -100 || true
  done
  echo
  if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
    echo "=== COLRv1 filter verification ==="
    cat "$OUT/colrv1-scan-summary.txt" 2>/dev/null || true
    cat "$OUT/fontconfig-filter-verification.txt" 2>/dev/null || true
    echo
  fi
  if [[ "$ENGINE" == "proton-dwritecore" ]]; then
    echo "=== DWriteCore compatibility ==="
    cat "$OUT/dwritecore.txt" 2>/dev/null || true
    for log in "$OUT"/steam-*.log; do
      [[ -f "$log" ]] || continue
      grep -EHi 'DWriteCore\.dll|DWriteCoreCreateFactory|Loaded .*DWriteCore|DWrite\.dll' \
        "$log" | tail -160 || true
    done
    echo
  fi
  echo "=== DirectWrite / renderer crash highlights ==="
  for log in "$OUT"/steam-*.log; do
    [[ -f "$log" ]] || continue
    grep -EHi 'DWrite\.dll|dwritefont|CrRendererMain|c0000005|EXCEPTION_ACCESS_VIOLATION'       "$log" | tail -220 || true
  done
  echo
  echo "=== Proton log highlights ==="
  for log in "$OUT"/steam-*.log; do
    [[ -f "$log" ]] || continue
    grep -Ei 'error|fatal|fail|exception|crash|gpu|renderer|sandbox|egl|glx|vulkan|dxvk|wayland|x11' \
      "$log" | tail -250 || true
  done
} > "$OUT/highlights.txt"

cat <<RESULT

Renderer diagnostic complete.
Engine:      $ENGINE
Exit code:   $RC
Directory:   $OUT

Useful files:
  $OUT/summary.txt
  $OUT/highlights.txt
  $OUT/stderr.log
  $OUT/processes.txt
RESULT

if [[ "$ENGINE" == "proton-no-colrv1" ]]; then
  echo "  $OUT/unsupported-colrv1-fonts.txt"
  echo "  $OUT/fontconfig-filter-verification.txt"
fi

if [[ "$ENGINE" == "proton-dwritecore" ]]; then
  echo "  $OUT/dwritecore.txt"
fi

if compgen -G "$OUT/steam-*.log" >/dev/null; then
  echo "  $OUT/steam-*.log"
fi

exit "$RC"
