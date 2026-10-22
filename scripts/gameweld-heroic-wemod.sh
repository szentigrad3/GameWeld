#!/usr/bin/env bash
set -Eeuo pipefail

RUNNER="${1:-}"; APPID="${2:-}"; TITLE="${3:-}"; INSTALL="${4:-}"; GAME_EXE="${5:-}"; PREFIX="${6:-}"; WINE_TYPE="${7:-}"; WINE_BIN="${8:-}"; HEROIC_ROOT="${9:-}"
[[ -n "$RUNNER" && -n "$APPID" && -n "$PREFIX" && -n "$WINE_BIN" ]] || { echo 'usage: gameweld-heroic-wemod.sh RUNNER APPID TITLE INSTALL GAME_EXE PREFIX WINE_TYPE WINE_BIN HEROIC_ROOT' >&2; exit 2; }

HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
DATA="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/gameweld"
STATE="${XDG_STATE_HOME:-$HOME_DIR/.local/state}/gameweld"
PROC_ROOT="${GAMEWELD_PROC_ROOT:-/proc}"
mkdir -p "$DATA" "$STATE"
SAFE_RUNNER="$(printf '%s' "$RUNNER" | tr -c '[:alnum:]_.-' '_')"
SAFE_APPID="$(printf '%s' "$APPID" | tr -c '[:alnum:]_.-' '_')"
LOG="$STATE/heroic-wemod-${SAFE_RUNNER}-${SAFE_APPID}.log"
RESULT="$STATE/heroic-wemod-${SAFE_RUNNER}-${SAFE_APPID}.result"
LOCK="$STATE/heroic-wemod-${SAFE_RUNNER}-${SAFE_APPID}.lock"

exec 9>"$LOCK"
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || { echo 'Another GameWeld Heroic WeMod launch is already being prepared for this game.' >&2; exit 11; }
fi

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ -n "${APPDIR:-}" && -r "${APPDIR}/usr/libexec/gameweld-heroic-common.sh" ]]; then COMMON="${APPDIR}/usr/libexec/gameweld-heroic-common.sh"; else COMMON="$script_dir/gameweld-heroic-common.sh"; fi
# shellcheck disable=SC1090
source "$COMMON"
[[ -n "$HEROIC_ROOT" ]] && export GAMEWELD_HEROIC_ROOT="$HEROIC_ROOT"

canon(){ readlink -f -- "$1" 2>/dev/null || printf '%s' "$1"; }
read_env(){ [[ -r "$PROC_ROOT/$1/environ" ]] || return 1; cat "$PROC_ROOT/$1/environ" 2>/dev/null | tr '\0' '\n'; }
read_cmd(){ [[ -r "$PROC_ROOT/$1/cmdline" ]] || return 1; cat "$PROC_ROOT/$1/cmdline" 2>/dev/null | tr '\0' ' '; }
real_prefix(){ local p="$1"; if [[ -d "$p/pfx/drive_c" && ! -d "$p/drive_c" ]]; then printf '%s\n' "$p/pfx"; else printf '%s\n' "$p"; fi; }
TARGET_PFX="$(real_prefix "$PREFIX")"

write_result(){ local t="$RESULT.tmp.$$"; printf '%s\n' "$@" > "$t"; mv -f -- "$t" "$RESULT"; }
log(){ printf '[%(%F %T)T] %s\n' -1 "$*" | tee -a "$LOG" >&2; }

prefix_matches_env(){
  local envs="$1" ep want="$(canon "$TARGET_PFX")"
  while IFS= read -r ep; do
    [[ -n "$ep" ]] || continue
    [[ "$(canon "$ep")" == "$want" || "$(canon "$ep/pfx")" == "$want" ]] && return 0
  done < <(sed -n 's/^WINEPREFIX=//p;s/^STEAM_COMPAT_DATA_PATH=//p' <<<"$envs")
  return 1
}

game_live(){
  # Test 31 deliberately does NOT search the whole command line for the game
  # filename. The previous check could mistake cmd.exe/start.exe wrappers for
  # the real game because their argument list contains e.g. Control.exe.
  local p pid envs comm base="${GAME_EXE##*/}" lowbase shortbase lowcomm
  lowbase="${base,,}"; shortbase="${lowbase:0:15}"
  [[ -n "$lowbase" ]] || return 1
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    pid="${p##*/}"; envs="$(read_env "$pid" || true)"; comm="$(cat "$p/comm" 2>/dev/null || true)"; lowcomm="${comm,,}"
    # Linux comm is capped at 15 visible bytes, so accept only the exact EXE
    # basename or its kernel-truncated form. Never accept cmd/start/wine just
    # because Control.exe appears later in their argv.
    [[ "$lowcomm" == "$lowbase" || "$lowcomm" == "$shortbase" ]] || continue
    if grep -Fqx "HEROIC_APP_NAME=$APPID" <<<"$envs"; then printf '%s\n' "$pid"; return 0; fi
    prefix_matches_env "$envs" || continue
    printf '%s\n' "$pid"; return 0
  done
  return 1
}

wemod_live(){
  # Test 33 only accepts a real Windows Wand/WeMod process.  Test 32 could
  # mistake the Proton runinprefix launcher for Wand because Wand.exe appeared
  # in the launcher's argv.  comm is kernel-capped to 15 bytes, so compare the
  # executable identity itself instead of scanning wrapper command lines.
  local p pid envs comm lowcomm
  for p in "$PROC_ROOT"/[0-9]*; do
    [[ -r "$p/environ" ]] || continue
    pid="${p##*/}"; envs="$(read_env "$pid" || true)"; prefix_matches_env "$envs" || continue
    comm="$(cat "$p/comm" 2>/dev/null || true)"; lowcomm="${comm,,}"
    case "$lowcomm" in
      wand.exe|wemod.exe) printf '%s\n' "$pid"; return 0 ;;
    esac
  done
  return 1
}

find_exact_heroic_game_target(){
  # Heroic/UMU launchers carry the target EXE in argv.  Test 32 therefore
  # accepted /usr/bin/python3 /usr/bin/umu-run .../Control.exe as if it were
  # the Windows game.  Match the process executable identity (comm) against
  # Heroic's ranked EXE hints instead.  For names longer than Linux's 15-byte
  # comm limit, require the full hint to also appear in argv.
  local install="$1" hint_text="$2" hint hlow short p pid envs comm lowcomm cmd ilow
  local -a hints=()
  IFS='|' read -r -a hints <<< "$hint_text"
  ilow="${install,,}"
  for hint in "${hints[@]}"; do
    [[ -n "$hint" ]] || continue
    hlow="${hint,,}"; short="${hlow:0:15}"
    for p in "$PROC_ROOT"/[0-9]*; do
      [[ -r "$p/comm" ]] || continue
      pid="${p##*/}"; comm="$(cat "$p/comm" 2>/dev/null || true)"; lowcomm="${comm,,}"
      [[ "$lowcomm" == "$hlow" || "$lowcomm" == "$short" ]] || continue
      cmd="$(read_cmd "$pid" || true)"
      if (( ${#hlow} > 15 )); then
        [[ "${cmd,,}" == *"$hlow"* ]] || continue
      fi
      envs="$(read_env "$pid" || true)"
      if grep -Fqx "HEROIC_APP_NAME=$APPID" <<<"$envs" || prefix_matches_env "$envs" || [[ -n "$ilow" && "${cmd,,}" == *"$ilow"* ]]; then
        printf '%s\t%s\t%s\n' "$pid" "$hint" "$cmd"
        return 0
      fi
    done
  done
  return 1
}

wait_for_exact_heroic_game_target(){
  local install="$1" hints="$2" max_wait="${3:-120}" second target settled
  for ((second=0; second<max_wait; second++)); do
    target="$(find_exact_heroic_game_target "$install" "$hints" || true)"
    if [[ -n "$target" ]]; then
      # Give a bootstrap EXE a moment to hand off to a renderer-specific child
      # and prefer the newly-visible ranked exact process when available.
      sleep 3
      settled="$(find_exact_heroic_game_target "$install" "$hints" || true)"
      [[ -n "$settled" ]] && target="$settled"
      printf '%s\n' "$target"
      return 0
    fi
    if (( second > 0 && second % 10 == 0 )); then
      printf 'Heroic has been asked to launch the game, but no exact Windows game process is visible yet (%ss/%ss)...\n' "$second" "$max_wait" >&2
    fi
    sleep 1
  done
  return 1
}

select_target_user(){
  local users="$TARGET_PFX/drive_c/users" u name
  [[ -d "$users/steamuser" ]] && { printf '%s\n' "$users/steamuser"; return 0; }
  for u in "$users"/*; do [[ -d "$u" ]] || continue; name="${u##*/}"; case "${name,,}" in public|default|'default user'|'all users') continue;; esac; printf '%s\n' "$u"; return 0; done
  return 1
}

runtime_in_tree(){
  local root="$1" p
  [[ -d "$root" ]] || return 1
  p="$(find "$root" -maxdepth 8 -type f \( -iname 'Wand.exe' -o -iname 'WeMod.exe' \) -print 2>/dev/null | awk 'BEGIN{IGNORECASE=1} /\/Wand\.exe$/{print;exit} {fallback=$0} END{if(!NR)exit 1;if(fallback && !seen)print fallback}' | head -n1)" || true
  [[ -n "$p" && -f "$p" ]] || return 1
  printf '%s\n' "$p"
}

target_runtime(){ runtime_in_tree "$TARGET_PFX/drive_c/users"; }

steam_roots(){
  local vdf root p
  for root in "$HOME_DIR/.steam/steam" "$HOME_DIR/.local/share/Steam"; do [[ -d "$root" ]] && printf '%s\n' "$root"; done
  for vdf in "$HOME_DIR/.steam/steam/steamapps/libraryfolders.vdf" "$HOME_DIR/.local/share/Steam/steamapps/libraryfolders.vdf"; do
    [[ -r "$vdf" ]] || continue
    sed -n 's/.*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$vdf" | sed 's/\\\\/\\/g'
  done | awk 'NF&&!seen[$0]++'
}

source_runtime(){
  local p root compat user localroot
  [[ -n "${GAMEWELD_HEROIC_WEMOD_SOURCE:-}" && -f "${GAMEWELD_HEROIC_WEMOD_SOURCE:-}" ]] && { printf '%s\n' "$GAMEWELD_HEROIC_WEMOD_SOURCE"; return 0; }
  [[ -n "${WAND_WEMOD_EXE:-}" && -f "${WAND_WEMOD_EXE:-}" ]] && { printf '%s\n' "$WAND_WEMOD_EXE"; return 0; }
  p="$(runtime_in_tree "$HOME_DIR/.local/share/wand/wemod-runtime" || true)"; [[ -n "$p" ]] && { printf '%s\n' "$p"; return 0; }
  for root in "${WAND_WEMOD_SOURCE_PREFIX:-}" "$HOME_DIR/.local/share/wand/wemod-prefix" "$HOME_DIR/.local/share/wand/prefix" "$HOME_DIR/.wine"; do
    [[ -n "$root" ]] || continue; p="$(runtime_in_tree "$(real_prefix "$root")/drive_c/users" || true)"; [[ -n "$p" ]] && { printf '%s\n' "$p"; return 0; }
  done
  while IFS= read -r root; do
    [[ -d "$root/steamapps/compatdata" ]] || continue
    for compat in "$root"/steamapps/compatdata/*; do
      [[ -d "$compat" ]] || continue
      p="$(runtime_in_tree "$(real_prefix "$compat")/drive_c/users" || true)"; [[ -n "$p" ]] && { printf '%s\n' "$p"; return 0; }
    done
  done < <(steam_roots)
  return 1
}

product_root_for_exe(){
  local exe="$(canon "$1")" cur="$(dirname -- "$(canon "$1")")" name
  while [[ "$cur" != / && -n "$cur" ]]; do name="${cur##*/}"; case "${name,,}" in wand|wemod) printf '%s\t%s\n' "$cur" "$name"; return 0;; esac; cur="$(dirname -- "$cur")"; done
  # A central override can point directly at a flat application folder.
  name="$(basename -- "$exe")"; case "${name,,}" in wand.exe) printf '%s\tWand\n' "$(dirname -- "$exe")";; wemod.exe) printf '%s\tWeMod\n' "$(dirname -- "$exe")";; *) return 1;; esac
}

source_prefix_for_exe(){
  local cur="$(dirname -- "$(canon "$1")")"
  while [[ "$cur" != / && -n "$cur" ]]; do [[ -d "$cur/drive_c/users" ]] && { printf '%s\n' "$cur"; return 0; }; cur="$(dirname -- "$cur")"; done
  return 1
}

provision_runtime(){
  local target src pair srcroot product user targetlocal stage sourcepfx srcuser srcroam targetroam shared dtarget
  target="$(target_runtime || true)"; [[ -n "$target" ]] && { printf '%s\n' "$target"; return 0; }
  src="$(source_runtime || true)"; [[ -n "$src" ]] || { log 'No existing Wand.exe/WeMod.exe runtime was found. Launch WeMod once with a regular Steam game or import/install its runtime first.'; return 1; }
  pair="$(product_root_for_exe "$src" || true)"; [[ -n "$pair" ]] || { log "Could not identify the WeMod/Wand application root for $src"; return 1; }
  IFS=$'\t' read -r srcroot product <<<"$pair"
  user="$(select_target_user || true)"; [[ -n "$user" ]] || { log "Heroic prefix has no Windows user directory yet: $TARGET_PFX"; return 1; }
  targetlocal="$user/AppData/Local/$product"; mkdir -p "$(dirname -- "$targetlocal")"
  if [[ -e "$targetlocal" ]]; then
    mv -- "$targetlocal" "$targetlocal.gameweld-incomplete-$(date +%Y%m%d-%H%M%S)"
    log "Backed up an incomplete target $product runtime before importing the known-good runtime."
  fi
  stage="$targetlocal.gameweld-stage-$$"; rm -rf -- "$stage"; cp -a -- "$srcroot" "$stage"; mv -- "$stage" "$targetlocal"
  log "Imported $product runtime into the selected Heroic prefix from $srcroot"
  sourcepfx="$(source_prefix_for_exe "$src" || true)"
  if [[ -n "$sourcepfx" ]]; then
    srcuser="$(dirname -- "$(dirname -- "$(dirname -- "$(dirname -- "$srcroot")")")")" 2>/dev/null || true
    # Use the product's sibling Roaming tree when the source really came from AppData/Local.
    if [[ "$srcroot" == */AppData/Local/$product ]]; then
      srcuser="${srcroot%/AppData/Local/$product}"
      srcroam="$srcuser/AppData/Roaming/$product"; targetroam="$user/AppData/Roaming/$product"
      if [[ -d "$srcroam" && ! -e "$targetroam" ]]; then mkdir -p "$(dirname -- "$targetroam")"; cp -a -- "$srcroam" "$targetroam"; log "Imported matching $product Roaming state into the Heroic prefix."; fi
    fi
  fi
  target="$(target_runtime || true)"; [[ -n "$target" ]] || return 1
  shared="$HOME_DIR/.local/share/wand/dwritecore/2.1.0/DWriteCore.dll"; dtarget="$(dirname -- "$target")/DWriteCore.dll"
  if [[ -f "$shared" && ! -f "$dtarget" ]]; then cp -f -- "$shared" "$dtarget"; log 'Installed shared DWriteCore compatibility runtime beside the imported WeMod/Wand executable.'; fi
  printf '%s\n' "$target"
}

resolve_wand_provider_proton(){
  local override="${GAMEWELD_WAND_PROTON:-${WAND_PROTON:-}}" root tool proton
  if [[ -n "$override" ]]; then
    if [[ -d "$override" ]]; then tool="$override"; else proton="$override"; tool="$(dirname -- "$proton")"; fi
    [[ -x "${proton:-$tool/proton}" ]] || { log "Configured Wand compatibility provider is not executable: $override"; return 1; }
    if [[ -z "$proton" ]]; then
      if [[ -x "$tool/proton.wand-real" ]]; then proton="$tool/proton.wand-real"; else proton="$tool/proton"; fi
    fi
    printf '%s\n' "$proton"; return 0
  fi
  while IFS= read -r root; do
    tool="$root/compatibilitytools.d/GE-Proton-Wand-SHA256"
    [[ -d "$tool" ]] || continue
    if [[ -x "$tool/proton.wand-real" ]]; then printf '%s\n' "$tool/proton.wand-real"; return 0; fi
    [[ -x "$tool/proton" ]] && { printf '%s\n' "$tool/proton"; return 0; }
  done < <(steam_roots)
  for tool in \
    "$HOME_DIR/.steam/root/compatibilitytools.d/GE-Proton-Wand-SHA256" \
    "$HOME_DIR/.local/share/Steam/compatibilitytools.d/GE-Proton-Wand-SHA256"; do
    [[ -d "$tool" ]] || continue
    if [[ -x "$tool/proton.wand-real" ]]; then printf '%s\n' "$tool/proton.wand-real"; return 0; fi
    [[ -x "$tool/proton" ]] && { printf '%s\n' "$tool/proton"; return 0; }
  done
  return 1
}

provider_tool_dir(){ dirname -- "$1"; }


validate_wand_provider(){
  local proton="$1" tool
  [[ -x "$proton" ]] || return 1
  tool="$(provider_tool_dir "$proton")"
  [[ "$(basename -- "$tool")" == "GE-Proton-Wand-SHA256" || -n "${GAMEWELD_WAND_PROTON:-${WAND_PROTON:-}}" ]] || return 1
  [[ -d "$tool/files" ]] || return 1
  return 0
}

heroic_preflight_exact(){
  local out
  out="$(python3 "$HEROIC_PROVIDER" preflight "$APPID" 2>&1)" || { log "Heroic compatibility preflight failed: $out"; return 1; }
  printf '%s\n' "$out" >> "$LOG"
  python3 - "$out" "$HEROIC_ROOT" "$PREFIX" <<'PYCHK'
import json, os, sys
j=json.loads(sys.argv[1]); expected_root=os.path.realpath(os.path.expanduser(sys.argv[2])) if sys.argv[2] else ''
actual_root=os.path.realpath(os.path.expanduser(str(j.get('heroic_root') or ''))) if j.get('heroic_root') else ''
if expected_root and actual_root and expected_root != actual_root:
    print(f'Heroic root mismatch: selected={expected_root} resolved={actual_root}', file=sys.stderr); raise SystemExit(1)
selected_prefix=os.path.realpath(os.path.expanduser(sys.argv[3])) if sys.argv[3] else ''
resolved_prefix=str(j.get('prefix') or '')
resolved_prefix=os.path.realpath(os.path.expanduser(resolved_prefix)) if resolved_prefix else ''
if selected_prefix and resolved_prefix and selected_prefix != resolved_prefix:
    print(f'Heroic prefix mismatch: selected={selected_prefix} resolved={resolved_prefix}', file=sys.stderr); raise SystemExit(1)
PYCHK
}

refresh_heroic_runtime_from_config(){
  local out
  out="$(python3 "$HEROIC_PROVIDER" preflight "$APPID" 2>&1)" || { log "Could not refresh Heroic runtime from disk: $out"; return 1; }
  local -a fields=()
  mapfile -t fields < <(python3 - "$out" <<'PYREFRESH'
import json,sys
j=json.loads(sys.argv[1])
for k in ('wine_type','wine_bin','wine_name','prefix','heroic_root'):
    print(str(j.get(k) or ''))
PYREFRESH
)
  (( ${#fields[@]} >= 5 )) || return 1
  local new_type="${fields[0]}" new_bin="${fields[1]}" new_name="${fields[2]}" new_prefix="${fields[3]}"
  [[ -n "$new_bin" ]] || { log 'Heroic runtime refresh returned an empty wine/proton executable.'; return 1; }
  if [[ -n "$PREFIX" && -n "$new_prefix" && "$(canon "$PREFIX")" != "$(canon "$new_prefix")" ]]; then
    log "Refusing Heroic runtime refresh because prefix changed: selected=$PREFIX resolved=$new_prefix"
    return 1
  fi
  WINE_TYPE="$new_type"; WINE_BIN="$new_bin"; PREFIX="${new_prefix:-$PREFIX}"; TARGET_PFX="$(real_prefix "$PREFIX")"
  log "Heroic runtime refreshed from disk: name=${new_name:-unknown} type=${WINE_TYPE:-unknown} bin=$WINE_BIN"
  return 0
}

recover_stale_gameweld_runner(){
  local out rc
  set +e
  out="$(python3 "$HEROIC_PROVIDER" recover-stale-wand-runner "$APPID" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$out" >> "$LOG"
  if (( rc != 0 )); then
    log "Stale GameWeld Heroic runner recovery failed: $out"
    return "$rc"
  fi
  refresh_heroic_runtime_from_config
}

# Test 25: Heroic WeMod uses the same one-Proton-session architecture that
# previously rendered Wand 12.x correctly in the Steam provider.  Do not start
# the game in one Proton invocation and then join Wand through runinprefix: the
# Electron GPU subprocess fails in that split-session arrangement.  Instead an
# ephemeral Windows batch dispatches Wand and the real game from one
# waitforexitandrun invocation, with DWriteCore installed beside Wand.

windows_path(){
  local p base rel
  p="$(canon "$1")"; base="$(canon "$TARGET_PFX")"
  if [[ "$p" == "$base/drive_c/"* ]]; then
    rel="${p#"$base/drive_c/"}"
    rel="${rel//\//\\}"
    printf 'C:\\%s\n' "$rel"
  else
    p="${p//\//\\}"
    printf 'Z:%s\n' "$p"
  fi
}

batch_escape(){
  local v="$1"
  v="${v//%/%%}"
  printf '%s' "$v"
}

resolve_game_exe(){
  local candidate base
  if [[ -n "$GAME_EXE" ]]; then
    [[ -f "$GAME_EXE" ]] && { canon "$GAME_EXE"; return 0; }
    [[ -f "$INSTALL/$GAME_EXE" ]] && { canon "$INSTALL/$GAME_EXE"; return 0; }
    base="${GAME_EXE##*/}"
    candidate="$(find "$INSTALL" -maxdepth 5 -type f -iname "$base" -print -quit 2>/dev/null || true)"
    [[ -n "$candidate" ]] && { canon "$candidate"; return 0; }
  fi
  candidate="$(find "$INSTALL" -maxdepth 5 -type f -iname '*.exe' \
    ! -iname '*unins*' ! -iname '*uninstall*' ! -iname '*crash*' \
    ! -iname '*redist*' ! -iname '*dxsetup*' ! -iname '*easyanticheat*' \
    -printf '%s\t%p\n' 2>/dev/null | sort -nr | head -1 | cut -f2-)"
  [[ -n "$candidate" && -f "$candidate" ]] || return 1
  canon "$candidate"
}

valid_dwritecore(){
  local f="$1" size
  [[ -s "$f" ]] || return 1
  size="$(stat -c %s "$f" 2>/dev/null || printf 0)"
  (( size >= 1048576 )) || return 1
  [[ "$(dd if="$f" bs=2 count=1 status=none 2>/dev/null || true)" == MZ ]]
}

ensure_dwritecore(){
  local exe="$1" target shared installer
  target="$(dirname -- "$exe")/DWriteCore.dll"
  if valid_dwritecore "$target"; then
    log "DWriteCore compatibility runtime already present beside Wand: $target"
    printf '%s\n' "$target"; return 0
  fi
  shared="$HOME_DIR/.local/share/wand/dwritecore/2.1.0/DWriteCore.dll"
  if valid_dwritecore "$shared"; then
    cp -f -- "$shared" "$target"
    log "Installed shared DWriteCore compatibility runtime beside Wand: $target"
    printf '%s\n' "$target"; return 0
  fi
  if [[ -n "${APPDIR:-}" && -x "${APPDIR}/usr/libexec/install-dwritecore.sh" ]]; then
    installer="${APPDIR}/usr/libexec/install-dwritecore.sh"
  else
    installer="$script_dir/install-dwritecore.sh"
  fi
  if [[ -x "$installer" ]]; then
    log 'DWriteCore is missing; retrieving Microsoft.WindowsAppSDK.DWrite 2.1.0 from the official NuGet feed for Wand rendering compatibility.'
    if "$installer" --target-exe "$exe" --quiet >>"$LOG" 2>&1 && valid_dwritecore "$target"; then
      log "DWriteCore compatibility runtime installed beside Wand: $target"
      printf '%s\n' "$target"; return 0
    fi
  fi
  log 'DWriteCore compatibility runtime is unavailable. Wand 12.x is known to render incorrectly under Proton without the managed DWriteCore layer.'
  return 1
}

build_one_session_batch(){
  local game="$1" wand="$2" state_dir batch stage game_win game_dir_win wand_win wand_dir_win stage_win user
  state_dir="$STATE/heroic-wemod-one-session"; mkdir -p "$state_dir"
  batch="$state_dir/${SAFE_RUNNER}-${SAFE_APPID}-launch.bat"
  stage="$state_dir/${SAFE_RUNNER}-${SAFE_APPID}-stage.txt"
  game_win="$(windows_path "$game")"; game_dir_win="$(windows_path "$(dirname -- "$game")")"
  wand_win="$(windows_path "$wand")"; wand_dir_win="$(windows_path "$(dirname -- "$wand")")"
  stage_win="$(windows_path "$stage")"
  user="${wand#"$TARGET_PFX/drive_c/users/"}"; user="${user%%/*}"
  [[ -n "$user" && "$user" != "$wand" ]] || user=steamuser
  game_win="$(batch_escape "$game_win")"; game_dir_win="$(batch_escape "$game_dir_win")"
  wand_win="$(batch_escape "$wand_win")"; wand_dir_win="$(batch_escape "$wand_dir_win")"
  stage_win="$(batch_escape "$stage_win")"
  cat > "$batch" <<BAT
@echo off
@title GameWeld Heroic WeMod One Proton Session
> "$stage_win" echo batch-entered
set "SteamAppId=$APPID"
set "SteamGameId=$APPID"
set "SteamOverlayGameId=$APPID"
set "STEAM_COMPAT_APP_ID=$APPID"
set "WAND_SAVED_USERPROFILE=%USERPROFILE%"
set "WAND_SAVED_APPDATA=%APPDATA%"
set "WAND_SAVED_LOCALAPPDATA=%LOCALAPPDATA%"
set "WAND_SAVED_HOMEDRIVE=%HOMEDRIVE%"
set "WAND_SAVED_HOMEPATH=%HOMEPATH%"
set "USERPROFILE=C:\\users\\$user"
set "APPDATA=C:\\users\\$user\\AppData\\Roaming"
set "LOCALAPPDATA=C:\\users\\$user\\AppData\\Local"
set "HOMEDRIVE=C:"
set "HOMEPATH=\\users\\$user"
start "" /D "$wand_dir_win" "$wand_win"
>> "$stage_win" echo wand-dispatched
for /L %%I in (1,1,30) do (
  tasklist /FI "IMAGENAME eq Wand.exe" /NH 2>nul | find /I "Wand.exe" >nul 2>nul && goto :wand_ready
  ping 127.0.0.1 -n 2 >nul
)
>> "$stage_win" echo wand-timeout
exit /b 41
:wand_ready
>> "$stage_win" echo wand-ready
set "USERPROFILE=%WAND_SAVED_USERPROFILE%"
set "APPDATA=%WAND_SAVED_APPDATA%"
set "LOCALAPPDATA=%WAND_SAVED_LOCALAPPDATA%"
set "HOMEDRIVE=%WAND_SAVED_HOMEDRIVE%"
set "HOMEPATH=%WAND_SAVED_HOMEPATH%"
>> "$stage_win" echo game-dispatch
pushd "$game_dir_win"
"$game_win"
set "GAMEWELD_GAME_EXIT=%ERRORLEVEL%"
popd
>> "$stage_win" echo game-exited-%GAMEWELD_GAME_EXIT%
exit /b %GAMEWELD_GAME_EXIT%
BAT
  printf 'batch=%s\nstage=%s\ngame_windows=%s\nwand_windows=%s\nstage_windows=%s\n' "$batch" "$stage" "$game_win" "$wand_win" "$stage_win" >> "$LOG"
  printf '%s\n' "$batch"
}

build_wand_render_batch(){
  # Reuse the exact Windows shell/profile/working-directory launch shape that
  # rendered Wand correctly in Test 31, but keep this batch Wand-only so Heroic
  # can still own the game launch.  The batch stays alive while Wand.exe lives,
  # preserving the provider session instead of exiting immediately.
  local wand="$1" state_dir batch stage wand_win wand_dir_win stage_win user
  state_dir="$STATE/heroic-wemod-wand-session"; mkdir -p "$state_dir"
  batch="$state_dir/${SAFE_RUNNER}-${SAFE_APPID}-wand.bat"
  stage="$state_dir/${SAFE_RUNNER}-${SAFE_APPID}-wand-stage.txt"
  wand_win="$(windows_path "$wand")"; wand_dir_win="$(windows_path "$(dirname -- "$wand")")"
  stage_win="$(windows_path "$stage")"
  user="${wand#"$TARGET_PFX/drive_c/users/"}"; user="${user%%/*}"
  [[ -n "$user" && "$user" != "$wand" ]] || user=steamuser
  wand_win="$(batch_escape "$wand_win")"; wand_dir_win="$(batch_escape "$wand_dir_win")"; stage_win="$(batch_escape "$stage_win")"
  cat > "$batch" <<BAT
@echo off
@title GameWeld Heroic Wand Render Session
> "$stage_win" echo batch-entered
set "SteamAppId=$APPID"
set "SteamGameId=$APPID"
set "SteamOverlayGameId=$APPID"
set "STEAM_COMPAT_APP_ID=$APPID"
set "USERPROFILE=C:\users\$user"
set "APPDATA=C:\users\$user\AppData\Roaming"
set "LOCALAPPDATA=C:\users\$user\AppData\Local"
set "HOMEDRIVE=C:"
set "HOMEPATH=\users\$user"
start "" /D "$wand_dir_win" "$wand_win"
>> "$stage_win" echo wand-dispatched
for /L %%I in (1,1,45) do (
  tasklist /FI "IMAGENAME eq Wand.exe" /NH 2>nul | find /I "Wand.exe" >nul 2>nul && goto :wand_ready
  tasklist /FI "IMAGENAME eq WeMod.exe" /NH 2>nul | find /I "WeMod.exe" >nul 2>nul && goto :wand_ready
  ping 127.0.0.1 -n 2 >nul
)
>> "$stage_win" echo wand-timeout
exit /b 41
:wand_ready
>> "$stage_win" echo wand-ready
:wand_hold
tasklist /FI "IMAGENAME eq Wand.exe" /NH 2>nul | find /I "Wand.exe" >nul 2>nul && goto :wand_sleep
tasklist /FI "IMAGENAME eq WeMod.exe" /NH 2>nul | find /I "WeMod.exe" >nul 2>nul && goto :wand_sleep
>> "$stage_win" echo wand-exited
exit /b 0
:wand_sleep
ping 127.0.0.1 -n 3 >nul
goto :wand_hold
BAT
  printf 'wand_batch=%s\nwand_stage=%s\nwand_windows=%s\n' "$batch" "$stage" "$wand_win" >> "$LOG"
  printf '%s\n' "$batch"
}

launch_wand_render_session(){
  local proton="$1" install="$2" batch="$3" steamroot tool batch_win
  steamroot="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-}"
  if [[ -z "$steamroot" ]]; then
    for candidate in "$HOME_DIR/.steam/steam" "$HOME_DIR/.local/share/Steam"; do
      [[ -d "$candidate" ]] && { steamroot="$candidate"; break; }
    done
  fi
  tool="$(provider_tool_dir "$proton")"; batch_win="$(windows_path "$batch")"
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
    -u WAYLAND_DISPLAY -u PROTON_ENABLE_WAYLAND -u WINE_WAYLAND_CONFIG
    "WINEPREFIX=$TARGET_PFX"
    "STEAM_COMPAT_DATA_PATH=$TARGET_PFX"
    "STEAM_COMPAT_INSTALL_PATH=$install"
    "STEAM_COMPAT_TOOL_PATHS=$tool"
    "STEAM_COMPAT_APP_ID=$APPID"
    "SteamAppId=$APPID"
    "SteamGameId=$APPID"
    "SteamOverlayGameId=$APPID"
  )
  [[ -n "$steamroot" ]] && cmd+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$steamroot")
  cmd+=("$proton" waitforexitandrun start "$batch_win")
  printf 'wand_render_command=%q waitforexitandrun start %q\n' "$proton" "$batch_win" >&2
  "${cmd[@]}"
}

wemod_runtime_helper(){
  if [[ -n "${APPDIR:-}" && -x "${APPDIR}/usr/libexec/gameweld-heroic-trainer-runtime.sh" ]]; then
    printf '%s\n' "${APPDIR}/usr/libexec/gameweld-heroic-trainer-runtime.sh"
  elif [[ -x "$script_dir/gameweld-heroic-trainer-runtime.sh" ]]; then
    printf '%s\n' "$script_dir/gameweld-heroic-trainer-runtime.sh"
  fi
}

ensure_wemod_dotnet48(){
  [[ "${GAMEWELD_HEROIC_WEMOD_SKIP_DOTNET48:-0}" == 1 ]] && { log 'Skipping .NET Framework 4.8 preparation by explicit test override.'; return 0; }
  local helper rc
  helper="$(wemod_runtime_helper)"
  if [[ -z "$helper" || ! -x "$helper" ]]; then
    log 'The Heroic runtime helper needed to prepare .NET Framework 4.8 is missing.'
    return 27
  fi
  write_result     'state=preparing-runtime'     "game=$TITLE"     "runtime=$WAND_PROTON"     "provider=$WAND_TOOL"     "prefix=$TARGET_PFX"     "wemod_exe=$TARGET_EXE"     "log=$LOG"     'summary=Preparing .NET Framework 4.8 for Wand/WeMod. GameWeld will normalize Proton-created Windows symlinks/registry state if needed, without changing Heroic game settings.'
  log 'Checking .NET Framework 4.8 in the selected Heroic prefix before Wand starts.'
  set +e
  "$helper" ensure-wemod "$RUNNER" "$APPID" "$TITLE" "$PREFIX" "$WINE_TYPE" "$WINE_BIN" "$TARGET_EXE"
  rc=$?
  set -e
  if (( rc != 0 )); then
    log "Automatic .NET Framework 4.8 preparation failed with status $rc."
    return "$rc"
  fi
  log '.NET Framework 4.8 is ready for Wand/WeMod in the selected Heroic prefix.'
  return 0
}

launch_one_proton_session(){
  local proton="$1" install="$2" batch="$3" steamroot tool batch_win
  steamroot="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-}"
  if [[ -z "$steamroot" ]]; then
    for candidate in "$HOME_DIR/.steam/steam" "$HOME_DIR/.local/share/Steam"; do
      [[ -d "$candidate" ]] && { steamroot="$candidate"; break; }
    done
  fi
  tool="$(provider_tool_dir "$proton")"
  batch_win="$(windows_path "$batch")"
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
    -u WAYLAND_DISPLAY -u PROTON_ENABLE_WAYLAND -u WINE_WAYLAND_CONFIG
    "WINEPREFIX=$TARGET_PFX"
    "STEAM_COMPAT_DATA_PATH=$TARGET_PFX"
    "STEAM_COMPAT_INSTALL_PATH=$install"
    "STEAM_COMPAT_TOOL_PATHS=$tool"
    "STEAM_COMPAT_APP_ID=$APPID"
    "SteamAppId=$APPID"
    "SteamGameId=$APPID"
    "SteamOverlayGameId=$APPID"
  )
  [[ -n "$steamroot" ]] && cmd+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$steamroot")
  cmd+=("$proton" waitforexitandrun start "$batch_win")
  printf 'one_session_command=%q waitforexitandrun start %q\n' "$proton" "$batch_win" >&2
  "${cmd[@]}"
}

resolve_heroic_live_wine(){
  # Test 35 deliberately joins Wand to the Wine server/runtime Heroic already
  # uses for the game instead of changing the game to the special Wand Proton.
  # For Proton tools Heroic supplies the top-level proton script, while the
  # live server is owned by that tool's files/bin/wine.
  local configured="${GAMEWELD_HEROIC_LIVE_WINE:-}" tool candidate
  if [[ -n "$configured" && -x "$configured" ]]; then printf '%s\n' "$configured"; return 0; fi
  if [[ -x "$WINE_BIN" ]]; then
    case "$(basename -- "$WINE_BIN")" in
      wine|wine64) printf '%s\n' "$WINE_BIN"; return 0 ;;
    esac
    tool="$(dirname -- "$WINE_BIN")"
    for candidate in "$tool/files/bin/wine" "$tool/dist/bin/wine"; do
      [[ -x "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
    done
  fi
  return 1
}

launch_wand_live_heroic_wine(){
  # Run the proven Test 33 Windows-shell/profile batch with the exact Wine
  # binary belonging to Heroic's selected runner. WINEPREFIX is the already
  # live Heroic prefix, so Wand joins the same wineserver instead of creating a
  # second Proton compatibility session.
  local wine="$1" batch="$2" batch_win command
  batch_win="$(windows_path "$batch")"
  command="call \"$batch_win\""
  local -a cmd=(
    env
    -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL
    -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH
    -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH
    -u GIO_EXTRA_MODULES -u GI_TYPELIB_PATH -u PYTHONHOME -u PYTHONPATH
    -u QML2_IMPORT_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH
    -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH
    -u WAYLAND_DISPLAY -u PROTON_ENABLE_WAYLAND -u WINE_WAYLAND_CONFIG
    "WINEPREFIX=$TARGET_PFX"
    "SteamAppId=$APPID"
    "SteamGameId=$APPID"
    "SteamOverlayGameId=$APPID"
    "STEAM_COMPAT_APP_ID=$APPID"
    "$wine" cmd.exe /d /c "$command"
  )
  printf 'wand_live_wine_command=%q cmd.exe /d /c %q\n' "$wine" "$command" >&2
  "${cmd[@]}"
}

wait_for_stable_exact_heroic_game_target(){
  # A configured launcher EXE may legitimately hand off to a same-family
  # renderer/game EXE (Control.exe -> Control_DX*.exe is the motivating field
  # case). Test 34 treated the launcher's exit as a crash. Test 35 keeps
  # scanning the ranked exact executable hints, adopts a replacement PID, and
  # only returns after one exact target has survived the requested window.
  local install="$1" hints="$2" max_wait="${3:-120}" stable_required="${4:-8}" handoff_grace="${5:-12}"
  local second row pid match cmd current_pid='' current_match='' current_cmd='' stable=0 seen=0 missing=0 handoffs=0
  [[ "$stable_required" =~ ^[0-9]+$ ]] || stable_required=8
  [[ "$handoff_grace" =~ ^[0-9]+$ ]] || handoff_grace=12
  (( stable_required < 1 )) && stable_required=1
  (( handoff_grace < 1 )) && handoff_grace=1
  for ((second=0; second<max_wait; second++)); do
    row="$(find_exact_heroic_game_target "$install" "$hints" || true)"
    if [[ -n "$row" ]]; then
      pid="${row%%$'\t'*}"
      match="${row#*$'\t'}"; match="${match%%$'\t'*}"
      cmd="${row#*$'\t'}"; cmd="${cmd#*$'\t'}"
      if [[ "$pid" != "$current_pid" ]]; then
        if (( seen )); then
          ((handoffs+=1))
          log "Exact Heroic game handoff detected: old PID=${current_pid:-none} -> PID=$pid match=$match command=$cmd"
        else
          log "Exact Heroic game candidate detected: PID=$pid match=$match command=$cmd"
        fi
        current_pid="$pid"; current_match="$match"; current_cmd="$cmd"; stable=0; seen=1
      fi
      missing=0
      ((stable+=1))
      if (( stable >= stable_required )); then
        printf '%s\t%s\t%s\t%s\n' "$current_pid" "$current_match" "$current_cmd" "$handoffs"
        return 0
      fi
    else
      stable=0
      if (( seen )); then
        ((missing+=1))
        if (( missing >= handoff_grace )); then
          log "No exact Heroic game successor appeared within the ${handoff_grace}s handoff grace window."
          return 1
        fi
      elif (( second > 0 && second % 10 == 0 )); then
        printf 'Heroic has been asked to launch the game, but no exact Windows game process is visible yet (%ss/%ss)...\n' "$second" "$max_wait" >&2
      fi
    fi
    sleep 1
  done
  return 1
}

refresh_exact_game_row(){
  local install="$1" hints="$2" row
  row="$(find_exact_heroic_game_target "$install" "$hints" || true)"
  [[ -n "$row" ]] || return 1
  printf '%s\n' "$row"
}

exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] action=heroic-wemod-heroic-native-attach game=%s runner=%s appid=%s\n' -1 "$TITLE" "$RUNNER" "$APPID"
printf 'prefix=%s\nui_selected_runtime=%s\nui_wine_type=%s\n' "$TARGET_PFX" "$WINE_BIN" "$WINE_TYPE"

# Test 36 repairs only stale GameWeld-owned Heroic runner residue. Tests 32-34
# could restore GamesConfig while Heroic still held the temporary provider in
# memory; Heroic could later persist GE-Proton-Wand-SHA256 back to disk. Re-read
# the runtime from disk after recovery so cached UI metadata cannot reintroduce it.
if ! recover_stale_gameweld_runner; then
  write_result 'state=stale-runner-recovery-failed' "game=$TITLE" "prefix=$TARGET_PFX" "log=$LOG" 'summary=Heroic is still configured to use a stale GameWeld temporary Wand runner and the original game runtime could not be recovered safely.'
  exit 17
fi

if wemod_live >/dev/null 2>&1; then
  write_result 'state=already-running' "game=$TITLE" "game_key=heroic:$RUNNER:$APPID" "prefix=$TARGET_PFX" "log=$LOG" 'summary=WeMod/Wand is already active in the selected Heroic game prefix.'
  log "WeMod/Wand is already active for $TITLE in the selected Heroic prefix."
  exit 0
fi

HEROIC_RUNTIME="$WINE_BIN"
HEROIC_TOOL="$(dirname -- "$WINE_BIN")"
HEROIC_WINE="$(resolve_heroic_live_wine || true)"
if [[ -z "$HEROIC_WINE" || ! -x "$HEROIC_WINE" ]]; then
  write_result 'state=heroic-wine-missing' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "prefix=$TARGET_PFX" "log=$LOG" 'summary=GameWeld could not resolve the live Wine binary belonging to Heroic\x27s selected game runner.'
  log "Could not resolve a live Wine binary from Heroic runtime: $HEROIC_RUNTIME"
  exit 15
fi
# The .NET helper still uses these inherited variable names in diagnostics.
WAND_PROTON="$HEROIC_RUNTIME"
WAND_TOOL="$HEROIC_TOOL"
log "Heroic selected game runtime remains unchanged: $HEROIC_RUNTIME"
log "Wand will join the live Heroic prefix with runner Wine: $HEROIC_WINE"
log 'Test 36 repairs any stale GameWeld GE-Proton-Wand Heroic runner residue, refreshes the true runtime from disk, follows exact launcher-to-game PID handoffs, then attaches Wand through the same live Wine runtime.'

TARGET_EXE="$(provision_runtime || true)"
if [[ -z "$TARGET_EXE" ]]; then
  log 'Heroic prefix is not initialized enough to hold the Wand runtime yet; initializing it once with the selected Heroic runner before provisioning.'
  if [[ "$WINE_TYPE" == proton && -x "$HEROIC_RUNTIME" ]]; then
    heroic_proton_runinprefix "$PREFIX" "$HEROIC_RUNTIME" "$INSTALL" cmd.exe /c exit >/dev/null 2>&1 || true
  else
    WINEPREFIX="$TARGET_PFX" "$HEROIC_WINE" cmd.exe /c exit >/dev/null 2>&1 || true
  fi
  TARGET_EXE="$(provision_runtime || true)"
fi
if [[ -z "$TARGET_EXE" || ! -f "$TARGET_EXE" ]]; then
  write_result 'state=runtime-missing' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "prefix=$TARGET_PFX" "log=$LOG" 'summary=GameWeld could not provision the existing user-owned Wand/WeMod runtime into the Heroic prefix.'
  exit 24
fi

GAME_TARGET="$(resolve_game_exe || true)"
if [[ -z "$GAME_TARGET" || ! -f "$GAME_TARGET" ]]; then
  write_result 'state=game-exe-missing' "game=$TITLE" "install=$INSTALL" "runtime=$HEROIC_RUNTIME" "prefix=$TARGET_PFX" "log=$LOG" 'summary=GameWeld could not resolve a Heroic Windows game executable for readiness matching.'
  log "Could not resolve a Windows game executable below $INSTALL"
  exit 25
fi
GAME_EXE="$GAME_TARGET"
log "Resolved Heroic game executable hint: $GAME_EXE"
log "Resolved Wand executable: $TARGET_EXE"

if [[ "${GAMEWELD_HEROIC_WEMOD_DRY_RUN:-0}" == 1 ]]; then
  write_result 'state=dry-run-ready' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "attach_wine=$HEROIC_WINE" "prefix=$TARGET_PFX" "game_exe=$GAME_EXE" "wemod_exe=$TARGET_EXE" "log=$LOG" 'summary=Heroic native-runner launch/attach plan resolved; dry-run skipped process launch and DWriteCore retrieval.'
  log 'Dry-run: Heroic native runner + live-Wine Wand attach plan resolved successfully.'
  exit 0
fi

require_no_runtime_repair "$RUNNER" "$APPID" || exit 12
heroic_preflight_exact || { write_result 'state=preflight-failed' "game=$TITLE" "log=$LOG" 'summary=Heroic prefix/config preflight failed; nothing was launched.'; exit 18; }

set +e
ensure_wemod_dotnet48
dotnet_rc=$?
set -e
if (( dotnet_rc != 0 )); then
  write_result 'state=dotnet48-prep-failed' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "prefix=$TARGET_PFX" "wemod_exe=$TARGET_EXE" "log=$LOG" "summary=GameWeld could not prepare verified .NET Framework 4.8 for Wand/WeMod (status $dotnet_rc)."
  exit "$dotnet_rc"
fi

HINTS="$(build_game_exe_hints "$INSTALL" "$GAME_EXE" || true)"
log "Ranked exact game executable hints: $HINTS"
EXISTING="$(find_exact_heroic_game_target "$INSTALL" "$HINTS" || true)"
if [[ -n "$EXISTING" ]]; then
  write_result 'state=game-already-running' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "prefix=$TARGET_PFX" "log=$LOG" 'summary=The game is already running. Close it once, then launch WeMod again so GameWeld can establish a clean native Heroic session.'
  log 'The selected Heroic game is already running. Refusing to create a second game session.'
  exit 16
fi

DWRITECORE="$(ensure_dwritecore "$TARGET_EXE" || true)"
if [[ -z "$DWRITECORE" ]]; then
  write_result 'state=dwritecore-missing' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "prefix=$TARGET_PFX" "wemod_exe=$TARGET_EXE" "log=$LOG" 'summary=The Microsoft DWriteCore compatibility runtime could not be installed beside Wand; the game was not launched.'
  exit 26
fi

# Test 36 does not rewrite a healthy Heroic game runner. It only repairs
# stale GameWeld-owned temporary provider residue before launch; the game then
# starts exactly with the recovered/current Heroic runtime.
log "Launching $TITLE normally THROUGH Heroic with its unchanged selected runtime. Wand will attach only after a ranked exact Windows game target survives launcher handoffs and becomes stable."
heroic_launch_game_visible "$RUNNER" "$APPID" || {
  write_result 'state=heroic-game-dispatch-failed' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "prefix=$TARGET_PFX" "log=$LOG" 'summary=Heroic could not accept the normal game launch URI; Wand was not started.'
  exit 35
}

pre_stable="${GAMEWELD_GAME_PREWAND_STABLE_SECONDS:-8}"; [[ "$pre_stable" =~ ^[0-9]+$ ]] || pre_stable=8
handoff_grace="${GAMEWELD_GAME_HANDOFF_GRACE_SECONDS:-12}"; [[ "$handoff_grace" =~ ^[0-9]+$ ]] || handoff_grace=12
GAME_ROW="$(wait_for_stable_exact_heroic_game_target "$INSTALL" "$HINTS" "${GAMEWELD_HEROIC_GAME_TIMEOUT:-120}" "$pre_stable" "$handoff_grace" || true)"
if [[ -z "$GAME_ROW" ]]; then
  write_result 'state=game-launch-failed' "game=$TITLE" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "prefix=$TARGET_PFX" "game_exe_hint=$GAME_EXE" "handoff_grace_seconds=$handoff_grace" "log=$LOG" 'summary=Heroic did not expose a stable exact Windows game process on its normal selected runner; Wand was not started.'
  log 'Heroic accepted the normal launch request, but no ranked exact Windows game process survived launcher handoff/stability checks.'
  exit 31
fi
LIVE_GAME="${GAME_ROW%%$'\t'*}"
rest="${GAME_ROW#*$'\t'}"; GAME_MATCH="${rest%%$'\t'*}"
rest="${rest#*$'\t'}"; GAME_CMD="${rest%%$'\t'*}"
GAME_HANDOFFS="${GAME_ROW##*$'\t'}"
log "Heroic-owned game is stable on the normal selected runtime: PID=$LIVE_GAME match=$GAME_MATCH handoffs=$GAME_HANDOFFS command=$GAME_CMD stable=${pre_stable}s"

WAND_BATCH="$(build_wand_render_batch "$TARGET_EXE")"
set +e
launch_wand_live_heroic_wine "$HEROIC_WINE" "$WAND_BATCH" & WAND_CHILD=$!
set -e
log "Wand live-Heroic-Wine render-session launcher PID=$WAND_CHILD"

wand_wait="${GAMEWELD_WEMOD_READY_TIMEOUT:-60}"; [[ "$wand_wait" =~ ^[0-9]+$ ]] || wand_wait=60
LIVE_PID=''; game_missing=0
for ((i=0;i<wand_wait;i++)); do
  CURRENT_ROW="$(refresh_exact_game_row "$INSTALL" "$HINTS" || true)"
  if [[ -n "$CURRENT_ROW" ]]; then
    CURRENT_PID="${CURRENT_ROW%%$'\t'*}"
    if [[ "$CURRENT_PID" != "$LIVE_GAME" ]]; then
      ((GAME_HANDOFFS+=1))
      LIVE_GAME="$CURRENT_PID"
      rest="${CURRENT_ROW#*$'\t'}"; GAME_MATCH="${rest%%$'\t'*}"
      rest="${rest#*$'\t'}"; GAME_CMD="${rest%%$'\t'*}"
      log "Exact game PID changed while Wand was attaching; adopted PID=$LIVE_GAME match=$GAME_MATCH command=$GAME_CMD"
    fi
    game_missing=0
  else
    ((game_missing+=1))
    if (( game_missing >= handoff_grace )); then
      write_result 'state=game-exited-before-wand' "game=$TITLE" "game_pid=$LIVE_GAME" "launcher_pid=$WAND_CHILD" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "attach_wine=$HEROIC_WINE" "prefix=$TARGET_PFX" "game_match=$GAME_MATCH" "wand_batch=$WAND_BATCH" "log=$LOG" 'summary=The normal Heroic game session disappeared and no ranked exact successor appeared while GameWeld was waiting for Wand.'
      log 'Normal Heroic game session disappeared while waiting for Wand and no exact successor appeared.'
      exit 31
    fi
  fi
  LIVE_PID="$(wemod_live || true)"
  [[ -n "$LIVE_PID" ]] && break
  kill -0 "$WAND_CHILD" 2>/dev/null || break
  sleep 1
done
if [[ -z "$LIVE_PID" ]]; then
  write_result 'state=wand-launch-failed' "game=$TITLE" "game_pid=$LIVE_GAME" "launcher_pid=$WAND_CHILD" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "attach_wine=$HEROIC_WINE" "prefix=$TARGET_PFX" "game_match=$GAME_MATCH" "wemod_exe=$TARGET_EXE" "wand_batch=$WAND_BATCH" "log=$LOG" 'summary=The game is live on Heroic\x27s normal runtime, but the live-Wine Wand render session did not expose a real Wand.exe/WeMod.exe process.'
  log 'Game remained live on Heroic native runtime, but Wand did not become live as an exact Windows executable.'
  exit 34
fi
log "Real Wand/WeMod process attached through Heroic's live Wine session: PID=$LIVE_PID game_PID=$LIVE_GAME"

stable_seconds="${GAMEWELD_GAME_STABLE_SECONDS:-6}"; [[ "$stable_seconds" =~ ^[0-9]+$ ]] || stable_seconds=6
(( stable_seconds < 1 )) && stable_seconds=1
stable_ok=1; failure=''; game_missing=0
for ((i=0;i<stable_seconds;i++)); do
  sleep 1
  CURRENT_ROW="$(refresh_exact_game_row "$INSTALL" "$HINTS" || true)"
  if [[ -n "$CURRENT_ROW" ]]; then
    CURRENT_PID="${CURRENT_ROW%%$'\t'*}"
    if [[ "$CURRENT_PID" != "$LIVE_GAME" ]]; then
      ((GAME_HANDOFFS+=1)); LIVE_GAME="$CURRENT_PID"
      rest="${CURRENT_ROW#*$'\t'}"; GAME_MATCH="${rest%%$'\t'*}"
      rest="${rest#*$'\t'}"; GAME_CMD="${rest%%$'\t'*}"
      log "Exact game handoff during joint stability: PID=$LIVE_GAME match=$GAME_MATCH command=$GAME_CMD"
    fi
    game_missing=0
  else
    ((game_missing+=1))
    if (( game_missing >= handoff_grace )); then stable_ok=0; failure='game-exited'; break; fi
  fi
  LIVE_PID="$(wemod_live || true)"
  if [[ -z "$LIVE_PID" ]]; then stable_ok=0; failure='wand-exited'; break; fi
done
if (( stable_ok != 1 )); then
  write_result 'state=session-stability-failed' "failure=$failure" "game=$TITLE" "game_pid=$LIVE_GAME" "wemod_pid=${LIVE_PID:-}" "launcher_pid=$WAND_CHILD" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "attach_wine=$HEROIC_WINE" "prefix=$TARGET_PFX" "game_match=$GAME_MATCH" "game_handoffs=$GAME_HANDOFFS" "wand_batch=$WAND_BATCH" "log=$LOG" 'summary=Heroic used its normal selected game runtime and Wand attached through the same live Wine prefix, but one exact process exited during final stability.'
  log "Native Heroic/Wand joint stability window failed: $failure"
  exit 31
fi

write_result 'state=running' "game=$TITLE" "game_key=heroic:$RUNNER:$APPID" "game_pid=$LIVE_GAME" "wemod_pid=$LIVE_PID" "launcher_pid=$WAND_CHILD" "runtime=$HEROIC_RUNTIME" "provider=$HEROIC_TOOL" "attach_wine=$HEROIC_WINE" "prefix=$TARGET_PFX" "game_exe_hint=$GAME_EXE" "game_match=$GAME_MATCH" "game_handoffs=$GAME_HANDOFFS" "wemod_exe=$TARGET_EXE" "dwritecore=$DWRITECORE" 'launch_mode=heroic-native-game-first-live-wine-wand-attach-stale-runner-recovery' "prewand_stable_seconds=$pre_stable" "handoff_grace_seconds=$handoff_grace" "stable_seconds=$stable_seconds" 'game_identity=exact-comm' 'wand_identity=exact-comm' "wand_batch=$WAND_BATCH" "log=$LOG" 'summary=GameWeld repaired any stale temporary Wand runner residue, refreshed Heroic\x27s true game runtime from disk, followed exact game handoffs until stable, then attached Wand through that same live Wine prefix and both exact processes remained stable.'
log "Native Heroic session is live and stable with exact identities: game PID=$LIVE_GAME Wand PID=$LIVE_PID handoffs=$GAME_HANDOFFS prewand=${pre_stable}s joint=${stable_seconds}s"
exit 0
