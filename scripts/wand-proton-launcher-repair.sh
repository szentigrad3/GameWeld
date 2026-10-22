#!/usr/bin/env bash
set -Eeuo pipefail

TOOL_ID="GE-Proton-Wand-SHA256"
QUIET=0
DRY_RUN=0
GATE_MARK="wand-native-explicit-gate-v1"

while (($#)); do
  case "$1" in
    --quiet) QUIET=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      cat <<'TXT'
Wand Native custom Proton launcher gate repair

Usage:
  wand-proton-launcher-repair.sh [--quiet] [--dry-run]

Old GE-Proton-Wand-SHA256 builds auto-started Wand on every Steam Play. This
repair keeps that proven Wand-launch wrapper behind a one-shot arm marker:
normal Steam Play executes clean Proton; PLAY WITH WAND explicitly arms the
wrapper for exactly one launch.
TXT
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say(){ ((QUIET)) || printf '%s\n' "$*"; }
warn(){ printf 'WARN: %s\n' "$*" >&2; }

contains_wand_autolaunch(){
  local p="$1"
  [[ -f "$p" ]] || return 1
  grep -Eqi 'Wand\.exe|WeMod\.exe|AppData[/\\]Local[/\\](Wand|WeMod)|WAND=.*PFX.*/drive_c/users' "$p" 2>/dev/null
}
is_gate(){ grep -Fq "$GATE_MARK" "$1" 2>/dev/null; }
resolve_dir(){ [[ -d "$1" ]] || return 1; readlink -f "$1" 2>/dev/null || printf '%s\n' "$1"; }

steam_roots(){
  {
    [[ -n "${STEAM_DIR:-}" ]] && printf '%s\n' "$STEAM_DIR"
    printf '%s\n' "$HOME/.local/share/Steam" "$HOME/.steam/root" "$HOME/.steam/steam" \
      "$HOME/.var/app/com.valvesoftware.Steam/data/Steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"
    for p in /proc/[0-9]*/cmdline; do
      [[ -r "$p" ]] || continue
      cmd="$(tr '\0' ' ' < "$p" 2>/dev/null || true)"
      case "$cmd" in *steamwebhelper*|*/steam\ *|*/steam) ;; *) continue ;; esac
      [[ "$cmd" =~ -steampath=([^[:space:]]+) ]] && printf '%s\n' "${BASH_REMATCH[1]}"
      [[ "$cmd" =~ -logdir=([^[:space:]]+)/logs ]] && printf '%s\n' "${BASH_REMATCH[1]}"
    done
    for top in /mnt /media "/run/media/${USER:-}"; do
      [[ -d "$top" ]] || continue
      find "$top" -maxdepth 4 -type d \( -name steamapps -o -name compatibilitytools.d \) -print 2>/dev/null | while IFS= read -r d; do
        case "$d" in */steamapps|*/compatibilitytools.d) dirname "$d" ;; esac
      done
    done
  } | while IFS= read -r root; do [[ -n "$root" && -d "$root" ]] && resolve_dir "$root" || true; done | awk 'NF && !seen[$0]++'
}
compat_dirs(){
  {
    while IFS= read -r root; do printf '%s\n' "$root/compatibilitytools.d"; done < <(steam_roots)
    printf '%s\n' "$HOME/.local/share/Steam/compatibilitytools.d" "$HOME/.steam/steam/compatibilitytools.d" "$HOME/.steam/root/compatibilitytools.d"
  } | while IFS= read -r d; do [[ -d "$d" ]] && resolve_dir "$d" || true; done | awk 'NF && !seen[$0]++'
}
tool_dirs(){
  while IFS= read -r compat; do [[ -d "$compat/$TOOL_ID" ]] && resolve_dir "$compat/$TOOL_ID" || true; done < <(compat_dirs) | awk 'NF && !seen[$0]++'
}
clean_base_candidates(){
  local target="$1" compat d
  compat="$(dirname "$target")"
  {
    for d in "$compat"/Proton-GE* "$compat"/GE-Proton*; do printf '%s\n' "$d"; done
    while IFS= read -r c; do for d in "$c"/Proton-GE* "$c"/GE-Proton*; do printf '%s\n' "$d"; done; done < <(compat_dirs)
  } | while IFS= read -r d; do
    [[ -d "$d" && "$d" != "$target" && "$(basename "$d")" != "$TOOL_ID" ]] || continue
    [[ "$(basename "$d")" != *backup* && "$(basename "$d")" != *Backup* ]] || continue
    [[ -f "$d/proton" ]] || continue
    contains_wand_autolaunch "$d/proton" && continue
    resolve_dir "$d" || true
  done | awk 'NF && !seen[$0]++'
}
choose_base(){ clean_base_candidates "$1" | head -1; }

write_gate(){
  local target="$1" real="$2" wrapped="$3" proton="$target/proton" tmp="$target/.proton.wand-native-gate.tmp"
  cat > "$tmp" <<'GATE'
#!/usr/bin/env bash
# wand-native-explicit-gate-v1
set -u
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REAL="$HERE/proton.wand-real"
WRAPPED="$HERE/proton.wand-autolaunch"
APPID="${SteamAppId:-${SteamGameId:-${STEAM_COMPAT_APP_ID:-unknown}}}"
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  ARM_DIR="$XDG_RUNTIME_DIR/wand-native"
else
  ARM_DIR="/tmp/wand-native-${UID}"
fi
ARM="$ARM_DIR/arm-${APPID}"
armed=0
if [[ -f "$ARM" ]]; then
  now="$(date +%s)"; then="$(stat -c %Y "$ARM" 2>/dev/null || printf 0)"
  age=$((now-then))
  rm -f -- "$ARM"
  if (( age >= 0 && age <= 120 )); then armed=1; fi
fi
if (( armed )) && [[ -x "$WRAPPED" ]]; then
  exec "$WRAPPED" "$@"
fi
exec "$REAL" "$@"
GATE
  chmod 755 "$tmp"
  mv -f "$tmp" "$proton"
}

repair_one(){
  local target="$1" proton="$target/proton" real="$target/proton.wand-real" wrapped="$target/proton.wand-autolaunch" base backup stamp
  [[ -f "$proton" ]] || return 0
  if is_gate "$proton"; then say "Gated: $target"; return 0; fi
  contains_wand_autolaunch "$proton" || { say "Clean: $target"; return 0; }

  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="$target/proton.wand-native-autolaunch-backup-$stamp"
  say "Gating historical Wand auto-launcher: $target"
  say "  backup: $backup"
  if ((DRY_RUN)); then return 0; fi
  cp -a -- "$proton" "$backup"

  # Preserve the known-working historical Wand wrapper behind the gate.
  cp -f -- "$proton" "$wrapped"
  chmod 755 "$wrapped"

  # Old wrappers normally already have proton.wand-real. If not, recover a
  # clean launcher from another installed Proton-GE without touching files/.
  if [[ ! -f "$real" ]] || contains_wand_autolaunch "$real"; then
    base="$(choose_base "$target" || true)"
    if [[ -z "$base" || ! -f "$base/proton" ]]; then
      warn "Cannot find a clean Proton-GE launcher for $target; original left unchanged."
      cp -f -- "$backup" "$proton"
      return 1
    fi
    cp -f -- "$base/proton" "$real"
    chmod 755 "$real"
  fi
  contains_wand_autolaunch "$real" && { warn "Clean launcher verification failed for $target"; cp -f -- "$backup" "$proton"; return 1; }
  write_gate "$target" "$real" "$wrapped"
  is_gate "$proton" || { warn "Gate verification failed for $target"; cp -f -- "$backup" "$proton"; return 1; }
  say "  direct Steam Play: clean Proton only"
  say "  PLAY WITH WAND:    one-shot armed Wand wrapper"
}

found=0; failed=0
while IFS= read -r target; do [[ -n "$target" ]] || continue; found=1; repair_one "$target" || failed=1; done < <(tool_dirs)
((found)) || say "No GE-Proton-Wand-SHA256 installation found."
((failed)) && exit 1
exit 0
