#!/usr/bin/env bash
set -Eeuo pipefail

APPID="${1:-}"
CHEAT_ENGINE="${2:-}"
TABLE="${3:-}"

[[ "$APPID" =~ ^[0-9]+$ ]] || { echo "Usage: gameweld-cheat-table.sh APPID /path/to/CheatEngine /path/to/table.ct" >&2; exit 2; }
[[ -f "$CHEAT_ENGINE" ]] || { echo "Cheat Engine executable not found: $CHEAT_ENGINE" >&2; exit 3; }
[[ -f "$TABLE" ]] || { echo "Cheat Engine table not found: $TABLE" >&2; exit 4; }

STATE="${XDG_STATE_HOME:-$HOME/.local/state}/gameweld"
mkdir -p "$STATE"
LOG="$STATE/cheat-table-${APPID}.log"
exec >>"$LOG" 2>&1
printf '\n[%(%F %T)T] Cheat table launch: appid=%s ce=%s table=%s\n' -1 "$APPID" "$CHEAT_ENGINE" "$TABLE"

# Prevent repeated PLAY clicks from leaving multiple handoff scanners/fallbacks
# racing against one another and interleaving into the same per-game log.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$STATE/cheat-table-${APPID}.lock"
  if ! flock -n 9; then
    echo "Another Cheat Table launch for AppID $APPID is already active; ignoring duplicate request."
    exit 0
  fi
fi

is_native_ce=0
if head -c 4 "$CHEAT_ENGINE" 2>/dev/null | LC_ALL=C grep -q $'\x7fELF'; then
  is_native_ce=1
fi

is_windows_ce_payload() {
  local f="$1" magic base
  [[ -n "$f" && -f "$f" ]] || return 1
  base="${f##*/}"
  case "${base,,}" in
    *.exe) ;;
    *) return 1 ;;
  esac
  magic="$(head -c 2 -- "$f" 2>/dev/null || true)"
  [[ "$magic" == "MZ" ]] || return 1
  return 0
}

safe_cmdline() {
  local pid="$1"
  cat "/proc/$pid/cmdline" 2>/dev/null | tr '\0' ' ' || true
}

read_proc_env() {
  local pid="$1"
  cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n' || true
}

safe_cgroup() {
  local pid="$1"
  cat "/proc/$pid/cgroup" 2>/dev/null || true
}

steam_roots() {
  {
    printf '%s\n' \
      "$HOME/.local/share/Steam" \
      "$HOME/.steam/root" \
      "$HOME/.steam/steam" \
      "$HOME/.var/app/com.valvesoftware.Steam/data/Steam" \
      "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" \
      "/mnt/games/Steam"
    find /mnt /media "/run/media/${USER:-}" -maxdepth 4 -type d -name Steam -print 2>/dev/null || true
  } | while IFS= read -r p; do
    [[ -d "$p" ]] || continue
    readlink -f "$p" 2>/dev/null || printf '%s\n' "$p"
  done | awk 'NF && !seen[$0]++'
}

steam_libraries() {
  local root vdf path
  while IFS= read -r root; do
    [[ -d "$root/steamapps" ]] && printf '%s\n' "$root"
    for vdf in "$root/steamapps/libraryfolders.vdf" "$root/config/libraryfolders.vdf"; do
      [[ -r "$vdf" ]] || continue
      while IFS= read -r path; do
        [[ -n "$path" && -d "$path/steamapps" ]] && printf '%s\n' "$path"
      done < <(sed -n 's/^[[:space:]]*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$vdf" | sed 's/\\\\/\\/g')
    done
  done < <(steam_roots)
}

collect_game_candidates() {
  local lib manifest installdir install compat
  while IFS= read -r lib; do
    manifest="$lib/steamapps/appmanifest_${APPID}.acf"
    [[ -r "$manifest" ]] || continue
    installdir="$(sed -n 's/^[[:space:]]*"installdir"[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest" | head -1)"
    [[ -n "$installdir" ]] || continue
    install="$lib/steamapps/common/$installdir"
    compat="$lib/steamapps/compatdata/$APPID"
    printf '%s\t%s\t%s\n' "$lib" "$install" "$compat"
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
}

GAME_LIBS=()
GAME_INSTALLS=()
GAME_COMPATS=()
while IFS=$'\t' read -r lib install compat; do
  [[ -n "${lib:-}" ]] || continue
  GAME_LIBS+=("$lib")
  GAME_INSTALLS+=("$install")
  GAME_COMPATS+=("$compat")
done < <(collect_game_candidates)

if ((${#GAME_LIBS[@]})); then
  echo "Steam metadata candidates for AppID $APPID:"
  for i in "${!GAME_LIBS[@]}"; do
    printf '  [%d] library=%s\n      install=%s (%s)\n      compat=%s (%s)\n' \
      "$i" "${GAME_LIBS[$i]}" \
      "${GAME_INSTALLS[$i]}" "$([[ -d "${GAME_INSTALLS[$i]}" ]] && echo present || echo missing)" \
      "${GAME_COMPATS[$i]}" "$([[ -d "${GAME_COMPATS[$i]}/pfx" ]] && echo present || echo missing)"
  done
else
  echo "No Steam appmanifest candidate found for AppID $APPID."
fi

PRIMARY_LIB=""
PRIMARY_INSTALL=""
PRIMARY_COMPAT=""
# Prefer a candidate that has both the game and an initialized prefix.
for i in "${!GAME_LIBS[@]}"; do
  if [[ -d "${GAME_INSTALLS[$i]}" && -d "${GAME_COMPATS[$i]}/pfx" ]]; then
    PRIMARY_LIB="${GAME_LIBS[$i]}"
    PRIMARY_INSTALL="${GAME_INSTALLS[$i]}"
    PRIMARY_COMPAT="${GAME_COMPATS[$i]}"
    break
  fi
done
# Next prefer an initialized prefix, then any manifest candidate.
if [[ -z "$PRIMARY_COMPAT" ]]; then
  for i in "${!GAME_LIBS[@]}"; do
    if [[ -d "${GAME_COMPATS[$i]}/pfx" ]]; then
      PRIMARY_LIB="${GAME_LIBS[$i]}"
      PRIMARY_INSTALL="${GAME_INSTALLS[$i]}"
      PRIMARY_COMPAT="${GAME_COMPATS[$i]}"
      break
    fi
  done
fi
if [[ -z "$PRIMARY_LIB" && ${#GAME_LIBS[@]} -gt 0 ]]; then
  PRIMARY_LIB="${GAME_LIBS[0]}"
  PRIMARY_INSTALL="${GAME_INSTALLS[0]}"
  PRIMARY_COMPAT="${GAME_COMPATS[0]}"
fi
[[ -n "$PRIMARY_LIB" ]] && echo "Primary Steam candidate: $PRIMARY_LIB"

GAME_TITLE=""
if [[ -n "$PRIMARY_LIB" ]]; then
  manifest="$PRIMARY_LIB/steamapps/appmanifest_${APPID}.acf"
  if [[ -r "$manifest" ]]; then
    GAME_TITLE="$(sed -n 's/^[[:space:]]*"name"[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest" | head -1)"
  fi
fi
[[ -n "$GAME_TITLE" ]] && echo "Steam game title: $GAME_TITLE"

game_exe_hints() {
  local install
  for install in "${GAME_INSTALLS[@]}"; do
    [[ -d "$install" ]] || continue
    find "$install" -maxdepth 8 -type f -iname '*.exe' -printf '%s\t%f\n' 2>/dev/null || true
  done | sort -t$'\t' -k1,1nr | awk -F'\t' '
    BEGIN{IGNORECASE=1}
    {
      name=$2
      low=tolower(name)
      if (low ~ /^(unins|uninstall)/) next
      if (low ~ /(vcredist|dxsetup|ue4prereq|vc_redist|crashreportclient|crashpad_handler|easyanticheat|eac_launcher|beservice|battleye)/) next
      if (!seen[low]++) print name
      if (++n>=48) exit
    }' | paste -sd'|' -
}

GAME_EXE_HINTS="$(game_exe_hints || true)"
if [[ -n "$GAME_EXE_HINTS" ]]; then
  echo "Windows CE auto-attach executable hints: $GAME_EXE_HINTS"
else
  echo "No executable-name hints could be derived from the Steam install; CE will use title/window fallback matching."
fi

# Steam marks a title as "Running" as soon as its launch pipeline is alive.
# That is not proof that the Windows game executable exists yet.  Do not start
# Windows CE until an actual game .exe from this Steam install is visible in
# /proc; launching CE earlier can create/join an idle wineserver and leave it
# unable to see the later game process.
find_live_game_target() {
  local hint hlow p pid cmd comm low install ilow
  local -a hints=()
  IFS='|' read -r -a hints <<< "$GAME_EXE_HINTS"

  # First pass: exact Steam-derived executable basenames, in size-priority
  # order.  The hint list is already filtered to exclude common redistributable,
  # anti-cheat and crash-handler helpers.
  for hint in "${hints[@]}"; do
    [[ -n "$hint" ]] || continue
    hlow="${hint,,}"
    for p in /proc/[0-9]*; do
      [[ -d "$p" ]] || continue
      pid="${p##*/}"
      cmd="$(safe_cmdline "$pid")"
      [[ -n "$cmd" ]] || continue
      comm="$(cat "$p/comm" 2>/dev/null || true)"
      low="${cmd,,} ${comm,,}"
      if [[ "$low" == *"$hlow"* ]]; then
        printf '%s\t%s\t%s\n' "$pid" "$hint" "$cmd"
        return 0
      fi
    done
  done

  # Conservative fallback: a Windows executable whose command line contains
  # this game's actual Steam install directory.
  for p in /proc/[0-9]*; do
    [[ -d "$p" ]] || continue
    pid="${p##*/}"
    cmd="$(safe_cmdline "$pid")"
    [[ -n "$cmd" ]] || continue
    low="${cmd,,}"
    [[ "$low" == *'.exe'* ]] || continue
    case "$low" in
      *cheatengine*|*wineboot*|*wineserver*|*steamwebhelper*|*crashpad*|*crashreport*|*easyanticheat*|*battleye*) continue ;;
    esac
    for install in "${GAME_INSTALLS[@]}"; do
      [[ -n "$install" ]] || continue
      ilow="${install,,}"
      if [[ "$low" == *"$ilow"* ]]; then
        printf '%s\t%s\t%s\n' "$pid" "$(basename -- "${cmd%% *}")" "$cmd"
        return 0
      fi
    done
  done
  return 1
}

wait_for_live_game_target() {
  local max_wait="${1:-120}" second target
  for ((second=0; second<max_wait; second++)); do
    target="$(find_live_game_target || true)"
    if [[ -n "$target" ]]; then
      printf '%s\n' "$target"
      return 0
    fi
    if (( second > 0 && second % 10 == 0 )); then
      echo "Steam reports launch activity, but the actual game executable is not visible yet (${second}s/${max_wait}s)..." >&2
    fi
    sleep 1
  done
  return 1
}

LIVE_GAME_PID=""
LIVE_GAME_EXE_HINT=""

install_wand_ce_autoattach_helper() {
  local ce_dir="$1" autorun helper
  [[ -n "$ce_dir" && -d "$ce_dir" ]] || return 1
  autorun="$ce_dir/autorun"
  mkdir -p "$autorun"
  helper="$autorun/gameweld-autoattach.lua"
  cat > "$helper" <<'LUA'
-- GameWeld automatic Cheat Engine process attachment.
-- Inert for ordinary/manual CE launches; Wand enables it with environment vars.
if os.getenv('WAND_CE_AUTOATTACH') ~= '1' then return end

local appid = os.getenv('WAND_CE_ATTACH_APPID') or ''
local title = os.getenv('WAND_CE_ATTACH_TITLE') or ''
local hintText = os.getenv('WAND_CE_ATTACH_HINTS') or ''
local primaryHint = os.getenv('WAND_CE_ATTACH_PRIMARY') or ''
local hints = {}
if primaryHint ~= '' then table.insert(hints, primaryHint) end
for h in string.gmatch(hintText, '([^|]+)') do
  local duplicate = false
  for _, existing in ipairs(hints) do
    if string.lower(existing) == string.lower(h) then duplicate = true break end
  end
  if not duplicate then table.insert(hints, h) end
end

local function lower(s) return string.lower(tostring(s or '')) end
local function basename(s)
  s = tostring(s or '')
  return s:match('([^\\/]+)$') or s
end
local function norm(s) return lower(s):gsub('[^%w]', '') end
local function opened() return (getOpenedProcessID and getOpenedProcessID() or 0) ~= 0 end

local blocked = {
  ['cheatengine.exe']=true, ['cheatengine-x86_64.exe']=true,
  ['cheatengine-x86_64-sse4-avx2.exe']=true, ['cheat engine.exe']=true,
  ['explorer.exe']=true, ['services.exe']=true, ['svchost.exe']=true,
  ['steam.exe']=true, ['steamwebhelper.exe']=true, ['winedevice.exe']=true,
  ['rpcss.exe']=true, ['plugplay.exe']=true, ['conhost.exe']=true,
  ['start.exe']=true, ['cmd.exe']=true, ['reg.exe']=true, ['wineboot.exe']=true,
}

local function attach(pid, name, why)
  if opened() then return true end
  local n = tonumber(pid)
  if not n then return false end
  local ok, err = pcall(function() openProcess(n) end)
  if ok and opened() then
    print(string.format('[GameWeld] auto-attached AppID %s to %s (PID %s) via %s', appid, tostring(name), tostring(pid), why))
    return true
  end
  if not ok then print('[GameWeld] auto-attach openProcess failed: '..tostring(err)) end
  return false
end

local function snapshot()
  local ok, p = pcall(getProcesslist)
  if not ok or type(p) ~= 'table' then return {} end
  return p
end

local function tryExactHints(p)
  for _, hint in ipairs(hints) do
    local want = lower(basename(hint))
    for pid, name in pairs(p) do
      if lower(basename(name)) == want and attach(pid, name, 'Steam executable hint') then return true end
    end
  end
  return false
end

local function tryWindowTitle()
  if title == '' or not getWindowlist then return false end
  local want = norm(title)
  if #want < 4 then return false end
  local ok, wins = pcall(getWindowlist)
  if not ok or type(wins) ~= 'table' then return false end
  for pid, entry in pairs(wins) do
    local caption = ''
    if type(entry) == 'table' then caption = tostring(entry[2] or entry.caption or entry.Caption or '')
    else caption = tostring(entry or '') end
    local c = norm(caption)
    if c ~= '' and (c:find(want, 1, true) or want:find(c, 1, true)) then
      if attach(pid, caption, 'window title') then return true end
    end
  end
  return false
end

local function tryTitleProcess(p)
  if title == '' then return false end
  local tokens = {}
  for token in string.gmatch(lower(title), '[%w]+') do
    if #token >= 4 and token ~= 'game' then table.insert(tokens, token) end
  end
  local bestPid, bestName, bestScore = nil, nil, 0
  for pid, name in pairs(p) do
    local b = lower(basename(name))
    if not blocked[b] then
      local n = norm(b)
      local score = 0
      for _, token in ipairs(tokens) do
        if n:find(norm(token), 1, true) then score = score + 1 end
      end
      if score > bestScore then bestPid, bestName, bestScore = pid, name, score end
    end
  end
  if bestPid and bestScore >= 2 then return attach(bestPid, bestName, 'game-title process match') end
  return false
end

local function tryAttach()
  if opened() then return true end
  local p = snapshot()
  if tryExactHints(p) then return true end
  if tryWindowTitle() then return true end
  if tryTitleProcess(p) then return true end
  return false
end

-- CE initializes autorun scripts before it loads the .CT command-line argument.
-- This first attempt can therefore attach an already-running game before the
-- table is processed; the timer covers games that are still finishing startup.
if tryAttach() then return end

local attempts = 0
local timer = createTimer(nil, false)
timer.Interval = 500
timer.OnTimer = function(t)
  attempts = attempts + 1
  if tryAttach() or attempts >= 120 then
    t.Enabled = false
    if not opened() then
      print(string.format('[GameWeld] auto-attach timed out for AppID %s; CE remains open for manual process selection', appid))
      local visible = {}
      for pid, name in pairs(snapshot()) do
        if #visible < 64 then table.insert(visible, string.format('%s=%s', tostring(pid), tostring(name))) end
      end
      table.sort(visible)
      print('[GameWeld] CE-visible processes at timeout: '..table.concat(visible, ' | '))
    end
    pcall(function() t.destroy() end)
  end
end
timer.Enabled = true
LUA
  echo "Wand CE auto-attach helper ready: $helper"
}

path_is_under() {
  local path="$1" root="$2"
  [[ -n "$path" && -n "$root" ]] || return 1
  [[ "$path" == "$root" || "$path" == "$root"/* ]]
}

compat_is_candidate() {
  local value="$1" c
  [[ -n "$value" ]] || return 1
  for c in "${GAME_COMPATS[@]}"; do
    [[ "$value" == "$c" || "$value" == "$c/pfx" ]] && return 0
  done
  [[ "$value" == */compatdata/"$APPID" || "$value" == */compatdata/"$APPID"/pfx ]]
}

install_matches_text() {
  local text="$1" d
  [[ -n "$text" ]] || return 1
  for d in "${GAME_INSTALLS[@]}"; do
    [[ -n "$d" && "$text" == *"$d"* ]] && return 0
  done
  return 1
}

find_proton_from_process() {
  local pid="$1" q parent exe arg root hit
  q="$pid"
  for _ in {1..28}; do
    [[ -e "/proc/$q" ]] || break
    while IFS= read -r -d '' arg; do
      if [[ "$(basename -- "$arg" 2>/dev/null || true)" == "proton" && -x "$arg" ]]; then
        printf '%s\n' "$arg"
        return 0
      fi
    done < <(cat "/proc/$q/cmdline" 2>/dev/null || true)

    exe="$(readlink -f "/proc/$q/exe" 2>/dev/null || true)"
    case "$exe" in
      */files/bin/wine*|*/files/lib*/wine/*|*/dist/bin/wine*|*/dist/lib*/wine/*)
        root="${exe%%/files/*}"
        [[ "$root" != "$exe" && -x "$root/proton" ]] && { printf '%s\n' "$root/proton"; return 0; }
        root="${exe%%/dist/*}"
        [[ "$root" != "$exe" && -x "$root/proton" ]] && { printf '%s\n' "$root/proton"; return 0; }
        ;;
    esac

    parent="$(awk '{print $4}' "/proc/$q/stat" 2>/dev/null || true)"
    [[ "$parent" =~ ^[0-9]+$ && "$parent" -gt 1 ]] || break
    q="$parent"
  done

  if [[ -r "/proc/$pid/maps" ]]; then
    hit="$(sed -n 's#^.* \(/[^ ]*/\(files\|dist\)/[^ ]*wine[^ ]*\)$#\1#p' "/proc/$pid/maps" 2>/dev/null | head -1 || true)"
    if [[ -n "$hit" ]]; then
      root="${hit%%/files/*}"
      [[ "$root" != "$hit" && -x "$root/proton" ]] && { printf '%s\n' "$root/proton"; return 0; }
      root="${hit%%/dist/*}"
      [[ "$root" != "$hit" && -x "$root/proton" ]] && { printf '%s\n' "$root/proton"; return 0; }
    fi
  fi
  return 1
}

find_proton_from_config_info() {
  local compat="$1" cfg line candidate parent marker
  [[ -n "$compat" ]] || return 1
  cfg="$compat/config_info"
  [[ -r "$cfg" ]] || return 1

  # Proton's config_info contains paths from the exact compatibility tool that
  # initialized/updated this prefix (fonts/lib/default_pfx on Valve Proton;
  # downstream builds may use a different nesting). Walk upward from every
  # absolute path instead of assuming one fixed /files or /dist layout.
  while IFS= read -r line; do
    line="${line%$'\r'}"
    [[ -n "$line" ]] || continue
    if [[ "$line" == */proton && -x "$line" ]]; then
      printf '%s\n' "$line"
      return 0
    fi
    [[ "$line" == /* ]] || continue
    candidate="$line"
    [[ -d "$candidate" ]] || candidate="$(dirname -- "$candidate")"
    for _ in {1..12}; do
      [[ -n "$candidate" && "$candidate" != "/" && "$candidate" != "." ]] || break
      if [[ -x "$candidate/proton" ]]; then
        printf '%s\n' "$candidate/proton"
        return 0
      fi
      parent="$(dirname -- "$candidate")"
      [[ "$parent" != "$candidate" ]] || break
      candidate="$parent"
    done
  done < <(strings -a "$cfg" 2>/dev/null || tr '\0' '\n' < "$cfg" 2>/dev/null || true)

  # Compatibility fallback for older config_info layouts where one long line
  # contains a Proton subtree path.
  while IFS= read -r line; do
    for marker in /files/ /dist/; do
      case "$line" in
        *"$marker"*)
          candidate="${line%%$marker*}"
          [[ -x "$candidate/proton" ]] && { printf '%s\n' "$candidate/proton"; return 0; }
          ;;
      esac
    done
  done < <(strings -a "$cfg" 2>/dev/null || true)
  return 1
}

find_steam_client_root() {
  local r
  while IFS= read -r r; do
    [[ -d "$r" ]] || continue
    if [[ -x "$r/ubuntu12_32/steam" || -x "$r/steam.sh" || -d "$r/config" ]]; then
      printf '%s\n' "$r"
      return 0
    fi
  done < <(steam_roots)
  return 1
}

find_session() {
  local p pid env compat wineprefix tools proton item steamroot config wow64 cwd cmdline cgroup maps associated c
  for p in /proc/[0-9]*; do
    pid="${p##*/}"
    [[ -e "$p" ]] || continue
    env="$(read_proc_env "$pid")"
    wineprefix="$(printf '%s\n' "$env" | sed -n 's/^WINEPREFIX=//p' | head -1)"
    compat="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_DATA_PATH=//p' | head -1)"
    cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
    cmdline="$(safe_cmdline "$pid")"
    cgroup="$(safe_cgroup "$pid")"
    associated=0

    if [[ "$env" == *"SteamAppId=$APPID"* || "$env" == *"SteamGameId=$APPID"* || "$env" == *"STEAM_COMPAT_APP_ID=$APPID"* ]]; then
      associated=1
    fi
    if compat_is_candidate "$compat" || compat_is_candidate "$wineprefix"; then
      associated=1
    fi
    if [[ "$cgroup" == *"$APPID"* && "$cgroup" == *steam* ]]; then
      associated=1
    fi
    if (( ! associated )); then
      for c in "${GAME_INSTALLS[@]}"; do
        if path_is_under "$cwd" "$c" || [[ -n "$c" && "$cmdline" == *"$c"* ]]; then
          associated=1
          break
        fi
      done
    fi
    # PE mappings are a reliable last identity for pressure-vessel processes
    # whose cwd/cmdline/env were normalized by the container runtime.
    if (( ! associated )) && [[ -r "/proc/$pid/maps" ]]; then
      maps="$(cat "/proc/$pid/maps" 2>/dev/null || true)"
      if install_matches_text "$maps"; then
        associated=1
      fi
    fi
    (( associated )) || continue

    if [[ -z "$compat" && "$wineprefix" == */pfx ]]; then
      compat="${wineprefix%/pfx}"
    fi
    if [[ -z "$compat" ]]; then
      for c in "${GAME_COMPATS[@]}"; do
        [[ -d "$c/pfx" ]] && { compat="$c"; break; }
      done
    fi
    [[ -n "$compat" && -d "$compat/pfx" ]] || continue
    if [[ "$compat" == */compatdata/* && "$compat" != */compatdata/"$APPID" ]]; then
      continue
    fi

    tools="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_TOOL_PATHS=//p' | head -1)"
    steamroot="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_CLIENT_INSTALL_PATH=//p' | head -1)"
    config="$(printf '%s\n' "$env" | sed -n 's/^STEAM_COMPAT_CONFIG=//p' | head -1)"
    wow64="$(printf '%s\n' "$env" | sed -n 's/^PROTON_USE_WOW64=//p' | head -1)"
    proton=""

    IFS=':' read -r -a parts <<< "$tools"
    for item in "${parts[@]}"; do
      [[ -x "$item/proton" ]] && { proton="$item/proton"; break; }
    done
    [[ -n "$proton" ]] || proton="$(find_proton_from_process "$pid" || true)"
    [[ -n "$proton" && -x "$proton" ]] || continue

    if [[ -z "$steamroot" ]]; then
      while IFS= read -r c; do
        [[ -d "$c" ]] && { steamroot="$c"; break; }
      done < <(steam_roots)
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$pid" "$compat" "$proton" "$steamroot" "$config" "$wow64"
    return 0
  done
  return 1
}

find_windows_ce_in_prefix() {
  local compat="$1" saved pfx f
  [[ -n "$compat" ]] || return 1
  saved="$STATE/managed-cheat-engine-${APPID}.txt"
  if [[ -r "$saved" ]]; then
    IFS= read -r f < "$saved" || true
    if [[ -n "${f:-}" ]] && is_windows_ce_payload "$f"; then
      printf '%s\n' "$f"
      return 0
    fi
    if [[ -n "${f:-}" && -f "$f" ]]; then
      echo "Ignoring stale Windows CE state for AppID $APPID because it is not a PE .exe: $f" >&2
    fi
    rm -f -- "$saved" 2>/dev/null || true
  fi

  pfx="$compat/pfx"
  [[ -d "$pfx/drive_c" ]] || return 1
  for f in \
    "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/cheatengine-x86_64.exe \
    "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/cheatengine-x86_64-SSE4-AVX2.exe \
    "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/Cheat\ Engine.exe \
    "$pfx"/drive_c/Program\ Files\ \(x86\)/Cheat\ Engine*/cheatengine-x86_64.exe \
    "$pfx"/drive_c/Program\ Files\ \(x86\)/Cheat\ Engine*/Cheat\ Engine.exe; do
    is_windows_ce_payload "$f" && { printf '%s\n' "$f"; return 0; }
  done
  f="$(find "$pfx/drive_c" -maxdepth 7 -type f \
    \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) \
    ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
  [[ -n "$f" ]] && is_windows_ce_payload "$f" || return 1
  printf '%s\n' "$f"
}

find_windows_ce_companion() {
  local native="$1" resolved d root wb f base
  resolved="$(readlink -f -- "$native" 2>/dev/null || printf '%s' "$native")"

  # Check both the literal executable location and its resolved target. The
  # official Linux build's protonlauncher.lua expects a populated windowsbin
  # tree, and symlinked installs must not lose the literal sibling path.
  for d in "$(dirname -- "$native")" "$(dirname -- "$resolved")"; do
    [[ -d "$d" ]] || continue
    for root in "$d" "$(dirname -- "$d")"; do
      for wb in "$root/windowsbin" "$root/autorun/windowsbin"; do
        [[ -d "$wb" ]] || continue
        for f in \
          "$wb/cheatengine-x86_64.exe" \
          "$wb/cheatengine-x86_64-SSE4-AVX2.exe" \
          "$wb/Cheat Engine.exe" \
          "$wb/cheatengine.exe"; do
          is_windows_ce_payload "$f" && { printf '%s\n' "$f"; return 0; }
        done
        f="$(find "$wb" -maxdepth 6 -type f \
          \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) \
          ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
        [[ -n "$f" ]] && is_windows_ce_payload "$f" && { printf '%s\n' "$f"; return 0; }
      done

      # Be tolerant of release layouts where windowsbin was nested one level
      # differently than expected.
      f="$(find "$root" -maxdepth 8 -type f \
        \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) \
        ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | grep -i '/windowsbin/' | sort -V | tail -1 || true)"
      [[ -n "$f" && -f "$f" ]] && { printf '%s\n' "$f"; return 0; }
    done
  done
  return 1
}

find_windows_ce_from_any_managed_prefix() {
  local saved f lib root pfx d
  # First reuse any Windows CE path Wand already learned for another game.
  for saved in "$STATE"/managed-cheat-engine-*.txt; do
    [[ -r "$saved" ]] || continue
    IFS= read -r f < "$saved" || true
    if [[ -n "${f:-}" ]] && is_windows_ce_payload "$f"; then
      printf '%s\n' "$f"
      return 0
    fi
  done

  # The native CE Proton launcher may have been pointed at an extracted Windows
  # CE folder rather than an installation inside a Steam prefix. Search the
  # usual user-owned locations without crawling the entire home directory.
  for d in \
    "$HOME/.local/share/gameweld" \
    "$HOME/.local/share/Cheat Engine" \
    "$HOME/.config/Cheat Engine" \
    "$HOME/Applications" \
    "$HOME/Downloads" \
    "$HOME/Desktop"; do
    [[ -d "$d" ]] || continue
    f="$(find "$d" -maxdepth 8 -type f \
      \( -iname 'cheatengine-x86_64.exe' -o -iname 'cheatengine-x86_64-SSE4-AVX2.exe' -o -iname 'cheat engine.exe' -o -iname 'cheatengine.exe' \) \
      ! -iname '*tutorial*' ! -iname '*ceserver*' 2>/dev/null | sort -V | tail -1 || true)"
    [[ -n "$f" && -f "$f" ]] && { printf '%s\n' "$f"; return 0; }
  done

  # Then inspect all Steam prefixes. This lets one existing Windows CE install
  # become the shared payload Wand can launch inside another game's prefix.
  while IFS= read -r lib; do
    root="$lib/steamapps/compatdata"
    [[ -d "$root" ]] || continue
    for pfx in "$root"/*/pfx; do
      [[ -d "$pfx/drive_c" ]] || continue
      for f in \
        "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/cheatengine-x86_64.exe \
        "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/cheatengine-x86_64-SSE4-AVX2.exe \
        "$pfx"/drive_c/Program\ Files/Cheat\ Engine*/Cheat\ Engine.exe \
        "$pfx"/drive_c/Program\ Files\ \(x86\)/Cheat\ Engine*/cheatengine-x86_64.exe \
        "$pfx"/drive_c/Program\ Files\ \(x86\)/Cheat\ Engine*/Cheat\ Engine.exe; do
        is_windows_ce_payload "$f" && { printf '%s\n' "$f"; return 0; }
      done
    done
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
  return 1
}

WINDOWS_CE=""
if (( is_native_ce )); then
  WINDOWS_CE="$(find_windows_ce_companion "$CHEAT_ENGINE" || true)"
  if [[ -z "$WINDOWS_CE" ]]; then
    for c in "${GAME_COMPATS[@]}"; do
      WINDOWS_CE="$(find_windows_ce_in_prefix "$c" || true)"
      [[ -n "$WINDOWS_CE" ]] && break
    done
  fi
  if [[ -z "$WINDOWS_CE" ]]; then
    WINDOWS_CE="$(find_windows_ce_from_any_managed_prefix || true)"
    [[ -z "$WINDOWS_CE" ]] || echo "Reusing existing Windows CE payload discovered outside this game's prefix."
  fi
else
  if is_windows_ce_payload "$CHEAT_ENGINE"; then
    WINDOWS_CE="$CHEAT_ENGINE"
  else
    echo "Configured external Cheat Engine is not a Windows PE .exe; it cannot be used as a Proton Windows CE payload: $CHEAT_ENGINE"
  fi
fi

if [[ -n "$WINDOWS_CE" ]]; then
  echo "Windows CE handoff target: $WINDOWS_CE"
else
  echo "No valid Windows CE companion found. The managed Linux CE bridge is installed, but its windowsbin payload is missing."
  echo "Automatic Proton handoff requires the Windows Cheat Engine install files in the Linux CE windowsbin directory (or another real MZ/PE Cheat Engine .exe)."
fi

find_runtime_clients() {
  local c lib
  if c="$(command -v steam-runtime-launch-client 2>/dev/null || true)"; then
    [[ -x "$c" ]] && printf '%s\n' "$c"
  fi
  while IFS= read -r lib; do
    find "$lib/steamapps/common" -maxdepth 4 -type f -path '*/SteamLinuxRuntime*/pressure-vessel/bin/steam-runtime-launch-client' -perm -u+x -print 2>/dev/null || true
  done < <(steam_libraries | awk 'NF && !seen[$0]++')
  find "$HOME/.local/share/umu" "$HOME/.cache/protontricks" -maxdepth 6 -type f -path '*/pressure-vessel/bin/steam-runtime-launch-client' -perm -u+x -print 2>/dev/null || true
}

runtime_bus_names() {
  local default="com.steampowered.App${APPID}"
  if command -v busctl >/dev/null 2>&1; then
    busctl --user --list --no-legend 2>/dev/null | awk -v id="$APPID" '$1 ~ ("^com\\.steampowered\\.App" id "($|\\.)") {print $1}'
  fi
  printf '%s\n' "$default"
}

runtime_bus_present() {
  local bus="$1"
  if command -v busctl >/dev/null 2>&1; then
    busctl --user status "$bus" >/dev/null 2>&1 && return 0
  fi
  if command -v gdbus >/dev/null 2>&1; then
    gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
      --method org.freedesktop.DBus.NameHasOwner "$bus" 2>/dev/null | grep -q 'true' && return 0
  fi
  # If neither D-Bus inspection utility exists, allow a direct launch-client
  # probe to decide whether the well-known Steam app bus exists.
  ! command -v busctl >/dev/null 2>&1 && ! command -v gdbus >/dev/null 2>&1
}

host_path_to_wine_z() {
  local p
  p="$(readlink -f -- "$1" 2>/dev/null || printf '%s' "$1")"
  p="${p//\\/\\\\}"
  p="${p//\//\\}"
  printf 'Z:%s\n' "$p"
}

launch_windows_ce_via_runtime() {
  local win_ce="$1" client bus win_dir win_table out rc cpid
  [[ -n "$win_ce" && -f "$win_ce" ]] || return 1
  win_dir="$(cd -- "$(dirname -- "$win_ce")" && pwd)"
  install_wand_ce_autoattach_helper "$win_dir" || echo "Warning: could not install CE auto-attach helper into $win_dir"

  while IFS= read -r bus; do
    [[ -n "$bus" ]] || continue
    runtime_bus_present "$bus" || continue
    while IFS= read -r client; do
      [[ -x "$client" ]] || continue
      echo "Trying Steam Runtime handoff: bus=$bus client=$client"

      # Ask winepath *inside the already-running game container*. This avoids
      # assuming a particular Z: mapping and proves the client can reach the
      # app's live command-launcher service before CE is started.
      out="$({
        env -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
          -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
          "$client" --bus-name="$bus" --share-pids --directory "$win_dir" -- \
          winepath -w "$TABLE"
      } 2>>"$LOG" | tr -d '\r' | tail -1 || true)"
      if [[ ! "$out" =~ ^[A-Za-z]:\\ ]]; then
        echo "Runtime winepath probe failed for $client (output=${out:-<none>})."
        continue
      fi
      win_table="$out"
      echo "Runtime bus reached; table path inside game container: $win_table"
      echo "Launching Windows Cheat Engine through the game's existing pressure-vessel session."

      (
        cd -- "$win_dir"
        exec env \
          -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
          -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
          -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH \
          -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH \
          -u GIO_EXTRA_MODULES -u PYTHONHOME -u PYTHONPATH \
          WAND_CE_AUTOATTACH=1 \
          WAND_CE_ATTACH_APPID="$APPID" \
          WAND_CE_ATTACH_TITLE="$GAME_TITLE" \
          WAND_CE_ATTACH_PRIMARY="$LIVE_GAME_EXE_HINT" \
          WAND_CE_ATTACH_HINTS="$GAME_EXE_HINTS" \
          "$client" --bus-name="$bus" --share-pids --directory "$win_dir" -- \
          wine "$win_ce" "$win_table"
      ) >>"$LOG" 2>&1 &
      cpid=$!
      echo "$cpid" > "$STATE/cheat-engine-runtime-${APPID}.pid"
      sleep 2
      if kill -0 "$cpid" 2>/dev/null; then
        echo "Steam Runtime CE handoff is active (host launcher PID $cpid)."
        return 0
      fi
      rc=0
      wait "$cpid" || rc=$?
      if (( rc == 0 )); then
        echo "Steam Runtime launch client returned success; CE was handed to the game container."
        return 0
      fi
      echo "Steam Runtime CE handoff failed with status $rc; trying another client/strategy."
    done < <(find_runtime_clients | awk 'NF && !seen[$0]++')
  done < <(runtime_bus_names | awk 'NF && !seen[$0]++')
  return 1
}

prepare_table_for_prefix() {
  local compat="$1" table_name table_dir
  [[ -n "$compat" && -d "$compat/pfx" ]] || return 1
  table_name="$(basename -- "$TABLE")"
  table_name="${table_name//[^A-Za-z0-9._-]/_}"
  table_dir="$compat/pfx/drive_c/users/Public/Documents/WandNativeTables"
  mkdir -p "$table_dir"
  cp -f -- "$TABLE" "$table_dir/$table_name"
  printf 'C:\\users\\Public\\Documents\\WandNativeTables\\%s\n' "$table_name"
}

launch_windows_ce_via_proton() {
  local win_ce="$1" pid="$2" compat="$3" proton="$4" steamroot="$5" config="$6" wow64="$7"
  local win_dir win_name win_table cpid rc=0
  win_dir="$(cd -- "$(dirname -- "$win_ce")" && pwd)"
  win_name="$(basename -- "$win_ce")"
  install_wand_ce_autoattach_helper "$win_dir" || echo "Warning: could not install CE auto-attach helper into $win_dir"
  win_table="$(prepare_table_for_prefix "$compat")" || return 1

  echo "Launching Windows Cheat Engine via detected active Proton session: $win_ce"
  echo "Detected game PID: $pid"
  echo "Compatdata: $compat"
  echo "Proton: $proton"
  echo "Table: $win_table"

  env_args=("STEAM_COMPAT_DATA_PATH=$compat")
  [[ -n "$steamroot" ]] && env_args+=("STEAM_COMPAT_CLIENT_INSTALL_PATH=$steamroot")
  [[ -n "$config" ]] && env_args+=("STEAM_COMPAT_CONFIG=$config")
  [[ -n "$wow64" ]] && env_args+=("PROTON_USE_WOW64=$wow64")

  (
    cd -- "$win_dir"
    exec env \
      -u LD_LIBRARY_PATH -u ORIG_LD_LIBRARY_PATH \
      -u APPDIR -u APPIMAGE -u APPIMAGE_SILENT_INSTALL \
      -u WAND_NATIVE_ROOT -u WAND_PAYLOAD_ROOT -u WAND_SOCKET_PATH \
      -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR -u GTK_PATH \
      -u GIO_EXTRA_MODULES -u PYTHONHOME -u PYTHONPATH \
      "${env_args[@]}" \
      SteamAppId="$APPID" SteamGameId="$APPID" STEAM_COMPAT_APP_ID="$APPID" \
      WAND_CE_AUTOATTACH=1 \
      WAND_CE_ATTACH_APPID="$APPID" \
      WAND_CE_ATTACH_TITLE="$GAME_TITLE" \
      WAND_CE_ATTACH_PRIMARY="$LIVE_GAME_EXE_HINT" \
      WAND_CE_ATTACH_HINTS="$GAME_EXE_HINTS" \
      WINEDEBUG=-all \
      "$proton" runinprefix "./$win_name" "$win_table"
  ) >>"$LOG" 2>&1 &
  cpid=$!
  echo "$cpid" > "$STATE/cheat-engine-proton-${APPID}.pid"
  sleep 2
  if kill -0 "$cpid" 2>/dev/null; then
    echo "Direct Proton CE handoff is active (host PID $cpid)."
    return 0
  fi
  wait "$cpid" || rc=$?
  if (( rc == 0 )); then
    echo "Direct Proton launcher returned success."
    return 0
  fi
  echo "Direct Proton CE handoff failed with status $rc."
  return 1
}

launch_windows_ce_via_config_info() {
  local win_ce="$1" compat="$2" detected_pid="${3:-config-info}" proton steamroot config wow64
  [[ -n "$compat" && -d "$compat/pfx" ]] || return 1
  proton="$(find_proton_from_config_info "$compat" || true)"
  [[ -n "$proton" && -x "$proton" ]] || return 1
  steamroot="$(find_steam_client_root || true)"
  config=""
  wow64=""
  echo "Resolved Proton directly from compatdata config_info: $proton"
  launch_windows_ce_via_proton "$win_ce" "$detected_pid" "$compat" "$proton" "$steamroot" "$config" "$wow64"
}

launch_native_ce_fallback() {
  local ce_dir
  (( is_native_ce )) || return 1
  ce_dir="$(cd -- "$(dirname -- "$CHEAT_ENGINE")" && pwd)"
  echo "Launching native Linux Cheat Engine fallback: $CHEAT_ENGINE"
  echo "Table: $TABLE"
  (
    cd "$ce_dir"
    nohup env LD_LIBRARY_PATH="$ce_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$CHEAT_ENGINE" "$TABLE" >>"$LOG" 2>&1 &
    echo $! > "$STATE/cheat-engine-native-${APPID}.pid"
  )
  echo "Native CE fallback launched. If CE detects the Proton target, its Launch Windows Version action remains available."
  return 0
}

# Test 11 makes game-process readiness the launch gate.  Steam's UI may report
# "Running" while Proton/pressure-vessel is still bootstrapping; compatdata or a
# Steam status flag alone is therefore not sufficient to start Windows CE.

# If the actual Windows game process already exists, do not relaunch the title.
existing_target="$(find_live_game_target || true)"
if [[ -n "$existing_target" && -n "$WINDOWS_CE" ]]; then
  IFS=$'\t' read -r LIVE_GAME_PID LIVE_GAME_EXE_HINT LIVE_GAME_CMD <<< "$existing_target"
  echo "Actual game process already running: PID=$LIVE_GAME_PID exe=$LIVE_GAME_EXE_HINT"
  echo "Game command line: $LIVE_GAME_CMD"

  # Prefer the exact prefix/proton mapping recorded for this game.  With the
  # target already alive, runinprefix joins the live wineserver instead of
  # creating an early idle CE session.
  for c in "${GAME_COMPATS[@]}"; do
    [[ -d "$c/pfx" ]] || continue
    if launch_windows_ce_via_config_info "$WINDOWS_CE" "$c" "$LIVE_GAME_PID"; then
      echo "Windows CE handoff complete after verified live-game detection."
      exit 0
    fi
  done

  if launch_windows_ce_via_runtime "$WINDOWS_CE"; then
    echo "Windows CE handoff complete through verified live Steam Runtime session."
    exit 0
  fi
fi

echo "Starting game normally through Steam..."
env -u DESKTOP_STARTUP_ID -u XDG_ACTIVATION_TOKEN -u GIO_LAUNCHED_DESKTOP_FILE -u GIO_LAUNCHED_DESKTOP_FILE_PID \
  steam -applaunch "$APPID" >/dev/null 2>&1 &
echo "Steam launch request sent. Waiting for the actual Windows game executable; Steam 'Running' status is not treated as ready."

if [[ -z "$WINDOWS_CE" ]]; then
  echo "Windows CE payload is not currently installed/discoverable; skipping Proton handoff."
  echo "Use Wand Settings -> Managed Cheat Engine Provider -> Choose CE Package with an official Windows CE installer, then Install Selected Package once to populate windowsbin."
  sleep 4
  if launch_native_ce_fallback; then
    echo "Native CE launched so its Proton Target dialog remains available."
    exit 0
  fi
  echo "No Windows CE payload and no native CE fallback are available."
  exit 5
fi

# This is the key Test 11 gate.  Do not launch Windows CE merely because the
# prefix exists or Steam says the title is running.
target="$(wait_for_live_game_target 120 || true)"
if [[ -z "$target" ]]; then
  echo "Timed out waiting 120 seconds for the actual Windows game executable for AppID $APPID."
  echo "Windows CE was intentionally NOT launched early."
  if launch_native_ce_fallback; then
    echo "Fell back to native CE after game-process readiness timeout."
    exit 0
  fi
  exit 5
fi

IFS=$'\t' read -r LIVE_GAME_PID LIVE_GAME_EXE_HINT LIVE_GAME_CMD <<< "$target"
echo "Actual game process detected: PID=$LIVE_GAME_PID exe=$LIVE_GAME_EXE_HINT"
echo "Game command line: $LIVE_GAME_CMD"
# Give the game's wineserver/window initialization a small stability margin so
# CE joins the already-live session rather than racing its first process.
sleep 2

# Direct config_info resolution is the proven path on the current Dying Light
# setup.  It is now safe because a real game process has been verified first.
for c in "${GAME_COMPATS[@]}"; do
  [[ -d "$c/pfx" ]] || continue
  if launch_windows_ce_via_config_info "$WINDOWS_CE" "$c" "$LIVE_GAME_PID"; then
    echo "Windows CE handoff complete after verified game readiness."
    exit 0
  fi
done

# Secondary path for titles whose Steam Runtime command-launcher is exposed.
if launch_windows_ce_via_runtime "$WINDOWS_CE"; then
  echo "Windows CE handoff complete through Steam Runtime after verified game readiness."
  exit 0
fi

# Last-resort live session metadata path.
session="$(find_session || true)"
if [[ -n "$session" ]]; then
  IFS=$'\t' read -r GAMEPID COMPAT PROTON STEAMROOT COMPAT_CONFIG PROTON_WOW64 <<< "$session"
  if launch_windows_ce_via_proton "$WINDOWS_CE" "$GAMEPID" "$COMPAT" "$PROTON" "$STEAMROOT" "$COMPAT_CONFIG" "$PROTON_WOW64"; then
    echo "Windows CE handoff complete through final live-session fallback."
    exit 0
  fi
fi

echo "Automatic Windows CE handoff failed even though the game executable was detected."
if launch_native_ce_fallback; then
  echo "Fell back to native CE instead of failing silently."
  exit 0
fi
exit 5
