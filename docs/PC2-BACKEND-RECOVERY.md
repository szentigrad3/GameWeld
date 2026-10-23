# GameWeld PC2 — source backend and optional Wand-Enhancer

**Experimental feature branch:** `feature/pc2-source-backend`. This is **not** the published or field-tested PC1 AppImage and does not replace it.

## Source-only backend smoke test on CachyOS

```bash
cd /mnt/other/github/GameWeld
git fetch origin
git switch feature/pc2-source-backend
git pull --ff-only
sudo pacman -S --needed go base-devel gtk3 pkgconf
bash scripts/run-pc2-source-frontend.sh
```

This builds a small, source-controlled Go executable named `wand-native-backend` and the GTK C frontend into `build/pc2-source/` (ignored by Git). The frontend launches the backend using `WAND_NATIVE_BACKEND`. **No ZIP is needed.**

The backend is **read-only** for this phase. It implements the GTK startup handshake, `GET /api/status`, `GET /api/job`, `GET /api/verify`, `GET /api/health`, and explicit HTTP 501 failures for `POST /api/install` and `POST /api/set-game`. It discovers installed Steam games from VDF manifests. Heroic/Lutris discovery remains frontend-script-owned. It cannot install Wand, stage a provider, set Proton, repair a prefix or hand off to a trainer. Those actions must not be interpreted as tested or working simply because the GUI opens.

Do **not** merge this backend into the working `release/0.7.0-pc1` branch or distribute a PC2 AppImage until full behaviour and test parity exist.

## Wand-Enhancer: optional upstream extension

Upstream: https://github.com/k1tbyte/Wand-Enhancer  
Upstream repository license: Apache-2.0, subject to its full notices and any third-party dependencies.  
Latest upstream release reviewed: `2.1.1.0` (18 October 2026).

Wand-Enhancer is a **Windows WPF/.NET Framework 4.8 tool** that alters a user's locally installed Wand client and offers optional UX extensions. Upstream intentionally **does not publish compiled executables** in its GitHub Releases. Their documented supported build path is a Windows build toolchain or a user-owned GitHub Actions fork. GameWeld **does not bundle its code, binaries, modified client files, or brand assets**, and will not download executables from mirrors.

### Initial PC2 integration — external, opt-in launcher

`scripts/gameweld-wand-enhancer.sh` supports:

- `--status`: report whether a **user-built** `WandEnhancer.exe`, existing Wine prefix and Wine runner are configured; do not execute or modify anything.
- `--open-upstream`: open the upstream source repository in the desktop browser.
- `--launch`: **only when explicitly invoked** run the user-supplied executable under an explicitly configured, existing Wine prefix.

Example (adjust paths to your installation):

```bash
export WAND_ENHANCER_EXE="$HOME/Tools/WandEnhancer.exe"
export WAND_ENHANCER_PREFIX="$HOME/.local/share/wineprefixes/wand"
export WAND_ENHANCER_WINE=wine

bash scripts/gameweld-wand-enhancer.sh --status
bash scripts/gameweld-wand-enhancer.sh --launch
```

**Important compatibility limitations:**

- This helper is **not a native Linux port**. The WPF/.NET Framework 4.8 desktop may not run correctly under Wine/Proton. No working Wine combination is claimed here. Install/repair .NET only by the user's own explicit action; avoid altering the active Steam/WeMod prefix automatically.
- Do not silently enable the optional remote web panel. Upstream describes unpaired plain HTTP over port 3223; anyone who can reach it may control the active trainer. Enable it only on a trusted LAN/VPN, never directly expose it to the internet.
- The launcher does **not** implement account/subscription activation, client-integrity bypass, injection patches, custom JS, automatic patching, or automatic downloads. Those are not prerequisites for GameWeld's core Steam/Heroic/Lutris functionality.
- A future GameWeld GUI button/settings UI can wrap `--status` and `--launch` after live Linux compatibility testing; the current feature branch provides the source integration foundation, not an in-app button.

### Validation checklist before PC2 promotion

- [ ] Go tests/race checks pass in GitHub Actions and on CachyOS.
- [ ] Experimental GTK frontend launches from this source backend and displays real Steam game metadata accurately.
- [ ] No mutating action is presented as available; Steam/Heroic/Lutris launches stay on the validated PC1 AppImage.
- [ ] User-built Wand-Enhancer detection and explicit invocation tested in an **isolated** Wine prefix. If not working, the optional extension remains disabled without preventing GameWeld startup.
- [ ] A future independently built PC2 AppImage has its own hash, standalone tests, licensing provenance, release notes and separate tag; PC1 test results must not transfer to it.
