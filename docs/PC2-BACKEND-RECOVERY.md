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

The source launcher now builds the GTK frontend with `GAMEWELD_PC2_DISCOVERY_ONLY=1` to make the discovery-only UI visibly identifiable and intercept legacy launch/setup/configuration button clicks **before** their handlers. In this mode it also refuses `--cleanup-steam-hooks`, skips automatic legacy Steam-wrapper replacement, and does not start trainer-library scans or update-monitor background jobs. Use the previous PC1 AppImage for real game/trainer launches. These are additional UI guards, not proof that every legacy callback or external command is fully isolated.

The backend is **read-only** for this phase. It implements the GTK startup handshake, `GET /api/status`, `GET /api/job`, `GET /api/verify`, `GET /api/health`, and explicit HTTP 501 failures for `POST /api/install` and `POST /api/set-game`. It discovers installed Steam games from VDF manifests. Heroic/Lutris discovery remains frontend-script-owned. It cannot install Wand, stage a provider, set Proton, repair a prefix or hand off to a trainer. **This limitation applies to the Go backend, not every legacy GTK UI callback**: some local Settings/Trainer Library controls still operate directly on files. During a PC2 smoke test, use game discovery and UI navigation only; do not click install, patch, backup, restore or launch controls. Those actions must not be interpreted as tested or working simply because the GUI opens.

Do **not** merge this backend into the working `release/0.7.0-pc1` branch or distribute a PC2 AppImage until full behaviour and test parity exist.

## PC2 Test 3 result and Test 4 diagnostics

Maintainer-provided Test 3 report (23 October 2026): **PASS**, **122 installed Steam manifests**, **one Wand Proton candidate**, inspector state **`incomplete`**, `verified=false`, and both backend mutation endpoints return HTTP 501. This is a read-only field check, **not** proof of compatibility tool health.

To identify the incomplete candidate's exact missing indicators without exposing home-directory paths or changing compatibility files, run:

```bash
git pull --ff-only
bash scripts/pc2-test4-aio-report.sh
```

Report: `build/pc2-source/pc2-test4-aio-report.txt`. Per candidate it records whether `proton` is executable, a tool entry exists in `compatibilitytool.vdf`, and `WAND-HYBRID.json` has valid schema/tool/base metadata. It does **not** validate DLL hashes, compare installed bytes, prove game/trainer health or run a repair. **Do not reinstall** the tool simply because the inspector marks metadata incomplete. Continue using the working PC1 build for game/trainer operations.

## PC2 Test 4 field result and Test 5 diagnostics

Maintainer's uploaded Test 4 AIO report (23 October 2026): `PASS`, 122 Steam manifests, one existing tool candidate, `has_proton=true`, `has_manifest=true`, `has_metadata=false`. The result is **incomplete metadata**, not proof that Proton itself is damaged or the trainer incompatible. No automatic reinstall is authorized.

The source inspector now classifies `WAND-HYBRID.json` precisely as `missing`, `empty`, `too_large`, `unreadable`, `not_regular`, `invalid_json`, `invalid_schema`, `unexpected_tool_id`, `missing_base_proton` or `valid_metadata_only`; none of these outcomes claims verified DLL hashes or trainer functionality.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test5-aio-report.sh
```

The read-only, path-redacted result is written to `build/pc2-source/pc2-test5-aio-report.txt`. This check does not delete or repair installed files. Keep PC1 as the working game/trainer version.

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
- The existing experimental **Settings → Wand / WeMod Patcher** panel now links directly to upstream source/build instructions and accepts a self-built executable. Its **Launch External Patcher** control remains intentionally disabled pending a validated Wine runner. The standalone helper provides an explicit developer-only launch path. This is not yet a validated full in-app integration.

### Validation checklist before PC2 promotion

- [x] Go tests and GTK source frontend compilation passed on CachyOS; CI Go race/static/build checks have passed. (See workflow runs.)
- [x] Maintainer confirmed source GTK frontend startup and correct Steam, Heroic and Lutris game display on CachyOS. This is a **user-reported visual check**; no per-provider logs were collected.
- [ ] Re-test the compiled discovery-only UI guards and verify they prevent legacy actions without interfering with read-only navigation.
- [ ] No mutating action is presented as available; Steam/Heroic/Lutris launches stay on the validated PC1 AppImage.
- [ ] User-built Wand-Enhancer detection and explicit invocation tested in an **isolated** Wine prefix. If not working, the optional extension remains disabled without preventing GameWeld startup.
- [ ] A future independently built PC2 AppImage has its own hash, standalone tests, licensing provenance, release notes and separate tag; PC1 test results must not transfer to it.
