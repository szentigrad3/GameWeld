#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
fail=0
for s in "$ROOT/install.sh" "$ROOT/uninstall.sh" "$ROOT/MAKE-APPIMAGE.sh" "$ROOT/scripts/wand-proton-manager.sh" "$ROOT/scripts/wand-trainer-health.sh" "$ROOT/scripts/wand-cheat-table.sh" "$ROOT/scripts/wand-cheat-engine-manager.sh" "$ROOT/scripts/wand-local-trainer.sh" "$ROOT/scripts/wand-appimage-setup.sh" "$ROOT/scripts/extract-wand-proton-payload.sh" "$ROOT/scripts/package-release.sh" "$ROOT/scripts/package-appimage.sh" "$ROOT/scripts/wand-setup" "$ROOT/packaging/appimage/AppRun"; do
  if bash -n "$s"; then echo "shell: OK  ${s#$ROOT/}"; else fail=1; fi
done
for f in "$ROOT/payload/crypt32/x86_64-windows/crypt32.dll" "$ROOT/payload/crypt32/i386-windows/crypt32.dll"; do
  if [[ -s "$f" ]]; then echo "payload: OK ${f#$ROOT/}"; else echo "payload: MISSING ${f#$ROOT/}"; fail=1; fi
done
if command -v cargo >/dev/null; then
  (cd "$ROOT" && cargo fmt --all -- --check && cargo check --workspace && cargo test --workspace)
else
  echo "rust: SKIPPED (cargo is not installed on this machine)"
fi
((fail == 0)) || exit 2
echo "Release checks passed."
