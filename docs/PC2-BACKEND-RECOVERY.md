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

## PC2 Test 5 field result and Test 6 legacy compatibility handling

Maintainer's 23 October 2026 Test 5 report: **PASS**, 122 Steam manifests, one compatibility candidate with `proton` executable and valid Steam tool registration, and `metadata_state=missing` (`WAND-HYBRID.json` **absent**, not invalid). Health remains **unverified**. Do **not** replace a working Proton installation based on this bookkeeping absence.

PC2 now reports the descriptive state `legacy_metadata_missing` when the registered tool and Proton executable are present but the optional GameWeld sidecar is absent. The frontend receives the detected tool path for diagnostic display, **while all provider health/compatible flags stay false**. This is not a license to patch/install Proton or evidence of working trainer runtime.

Next AIO:

```bash
git pull --ff-only
bash scripts/pc2-test6-aio-report.sh
```

The read-only report is written to `build/pc2-source/pc2-test6-aio-report.txt`; it checks discovery and fail-closed health. No paths are printed. Passing this check does not validate live game/trainer launches; those remain PC1-only.

## PC2 Test 6 result and Test 7 runtime evidence

The maintainer's Test 6 CachyOS report (23 October 2026) passed: **122 installed Steam manifests**, one registered Proton tool with an executable, `legacy_metadata_missing` because `WAND-HYBRID.json` was absent, all trust/health flags **false**, mutation endpoints HTTP 501. This is expected for an older or independently installed tool; no reinstall is indicated.

Test 7 adds a separately invoked, **read-only** `GET /api/runtime-integrity` endpoint. It checks *only known GE-Proton file layouts* for `x86_64-windows/crypt32.dll` and `i386-windows/crypt32.dll`; when present and regular, it calculates SHA256 fingerprints of files no larger than 64 MiB. It does not execute Proton, download missing files, scan arbitrary directory trees, follow symlinked runtime paths, compare to untrusted expected hashes, or change anything. Missing DLLs in those layouts are **not proof of a broken installation**—a different runtime layout may exist. No hash is claimed to be verified against a trusted reference. Trainer health and readiness remain **unverified**.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test7-aio-report.sh
```

A text report is saved to `build/pc2-source/pc2-test7-aio-report.txt` without installation paths. It can include DLL fingerprints, which identify file contents, but not user account data. Avoid attaching raw Proton files. Keep PC1 for live game launches.

## PC2 Test 7 field result and Test 8 local payload parity

Both uploaded Test 7 reports (23 October 2026) agree: AIO **PASS**, 122 Steam games, existing `GE-Proton-Wand-SHA256` registered and executable, metadata sidecar absent, and **both** DLL files readable in known GE-Proton layouts. SHA256 fingerprints:

- `x86_64-windows/crypt32.dll`: `685d73c195b8a785799149a2ff43a405f39e96825122cd95f24603dcd5c39b67`
- `i386-windows/crypt32.dll`: `bec8949d931332ed8f82161d9eb085e56ac279aa3a1ca5b7b5bd149353f28a3a`

Neither fingerprint has yet been compared with a trusted upstream source; **this does not establish authenticity, license status, or live trainer functionality**.

Test 8 adds a **local-only parity comparison**. It looks for payloads at `WAND_PAYLOAD_ROOT` when explicitly set to an absolute directory, or under `${XDG_DATA_HOME:-$HOME/.local/share}/wand-native/payload/crypt32`, as defined in `scripts/wand-proton-manager.sh`. For each architecture it compares installed DLL SHA256 to the local payload file. Report states distinguish `matches_local_payload`, `differs_from_local_payload` and `comparison_unavailable` (including missing payload). It refuses symlinked payload boundaries and does not expose filesystem paths in the AIO report, create files, download assets or mutate the installed tool.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test8-aio-report.sh
```

Result: `build/pc2-source/pc2-test8-aio-report.txt`. A match confirms local byte equality **only**; neither result should be used to automatically repair Proton or enable trainers. The original PC1 remains the known working release; source-built PC2 stays discovery-only.

## PC2 Test 8 field result and Test 9 Steam launch preview

Maintainer-uploaded Test 8 report (23 October 2026): AIO **PASS**, **122 Steam manifests**, installed Proton tool with two readable and fingerprinted `crypt32.dll` files, but **both local reference payloads are absent** (`comparison_unavailable`). The repository payload manifest has `null` patched-DLL checksums, and no compiled payload DLLs are committed. **This is a missing comparison source, not a damaged installation.** No reinstall, downloaded patch, or metadata repair is justified by that report.

PC2 Test 9 begins functional recovery with **source-owned, GET-only Steam launch preview**. `GET /api/launch-preview?appid=<decimal Steam ID>` rejects unknown, uninstalled, malformed and nonnumeric IDs; for a Steam appmanifest it returns a `steam://rungameid/<id>` URI with `mode=preview_only` and `launch_enabled=false`. It does not execute Steam, issue a process, modify LaunchOptions, or invoke a trainer. The discovery-only GTK Library page has a `Preview Steam launch (no action)` button for the selected standard Steam game; Heroic, Lutris and shortcuts remain outside the scope.

Developer / maintainer validation:

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test9-aio-report.sh
bash scripts/run-pc2-source-frontend.sh
```

The AIO creates `build/pc2-source/pc2-test9-aio-report.txt` and checks that malformed or unknown IDs cannot produce a launch plan, a valid installed Steam manifest generates the expected preview URI, and mutation endpoints still fail closed. CI without installed Steam uses the backend's fixture-backed unit tests. **A successful URI preview is not a live launch, trainer readiness, Proton health, or release approval.** The source frontend remains guarded, and PC1 is the live gaming baseline.

## PC2 Test 9 field result and Test 10 opt-in Steam game-only handoff

The maintainer's Test 9 AIO report (23 October 2026) **passed** against **122 Steam manifests**, including an installed-game `steam://rungameid/<id>` preview, malformed/unknown app ID rejection, and confirmations that no Steam game, trainer or configuration change was initiated. **That AIO does not prove the preview button works in the GUI**, or that a game successfully launches.

Test 10 introduces a **separate game-only opt-in** in the GTK Library inspector without unlocking inherited legacy launch or trainer buttons. By default, the new `Launch Steam game only (opt-in)` control is disabled. A shell environment value alone is insufficient for the normal source launcher. When explicitly requested at startup, the control becomes available:

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test10-aio-report.sh
# Default / safe UI:  bash scripts/run-pc2-source-frontend.sh
# Only when deliberately testing a real game:
bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch
```

Under that opt-in mode only, selecting an ordinary **installed Steam game** and clicking the game-only button requests the backend GET preview, checks provider / exact app ID / exact URI / read-only mode, then opens a **Yes/No confirmation dialog**. Only a Yes asks the local `steam -applaunch <appid>` executable to handle the selected game. Neither the backend nor the UI starts trainers, modifies Steam LaunchOptions, chooses a Proton version, or calls legacy play handlers. Steam itself may naturally update content. Heroic, Lutris and non-Steam shortcuts remain unsupported by the new opt-in path. The GUI reports only that a **handoff was requested**, not that Steam/game startup succeeded. No confirmed live launch has yet been reported.

The Test 10 AIO script performs all offline and safe gate probes **without opening the UI or starting Steam**; the test checks normal default disabled, inherited environment disabled, explicit gate enabled, and Test 9 preview regressions. Output: `build/pc2-source/pc2-test10-aio-report.txt`. If the tester wants to verify a real launch, they must deliberately supply the opt-in flag and confirm in the UI. Continue using validated PC1 for normal trainer operations.

## Test 10 Overview usability correction (CachyOS screenshot)

The 23 October 2026 CachyOS screenshot shows PC2 loading the rich inherited Overview correctly with **135 Steam entries (122 installed manifests + 13 Steam shortcuts), 2 Heroic entries, and 3 Lutris entries**. It also reveals that the inherited PC1 Overview continued to visually advertise **PLAY WITH STEAM TRAINER**, **Play Normally**, **Services ready**, and **Needs repair**, even though those legacy actions are blocked and trainer/Proton health is unverified. These were misleading descriptions, **not** proof of available trainer functionality or a defective Proton tool.

PC2's guarded source frontend now:

- Adds its **Launch Steam game only (opt-in)** button directly to the **Overview current-game panel**, using the **same confirmed, backend-validated Steam-only handler** as Library. The button remains insensitive in the default source runner and enables only for `--enable-steam-game-launch`.
- Clearly labels the Overview as **PC2 SOURCE TEST**, refers to **library discovery** instead of global service readiness, and describes legacy trainer controls as disabled.
- Displays **Unverified / Not verified** for trainer and runtime rather than asserting a repair is needed.
- Visually disables inherited action buttons and guards their sensitive state from legacy `refresh_ui()` re-enablement. Navigation uses independent nav controls and remains available.

Testing the UI remains a separate manual field gate. The **Test 10 AIO**, despite passing, did not execute a game; the launch requires deliberate opt-in, selection of an installed standard Steam game and a Yes confirmation. Keep using PC1 for trainer/session operations.

## PC2 Test 10 live Steam game launch: confirmed; Test 11 observation

Maintainer live field result (23 October 2026): **AdVenture Capitalist successfully launched** from the source-built GameWeld PC2 Overview using the explicit Steam game-only opt-in. This validates the manual Steam handoff, not the process/Proton ownership or trainer integration. No PC2 trainer action was exercised. The reliable PC1 release remains preserved.

Test 11 implements an additional **read-only, explicitly requested** Steam session observation:

- `GET /api/steam-session?appid=<id>` only accepts a valid installed standard Steam appmanifest ID. POST returns 405; unknown/uninstalled IDs return 404; install/mapping APIs remain HTTP 501.
- Scans same-user Linux `/proc` entries, bounded to 8192 PIDs and 32 returned observations, and searches NUL-separated environment variables for **exact** `SteamAppId`, `SteamGameId` or `STEAM_COMPAT_APP_ID` matches. No other users' process environment is inspected.
- Returns `associated_processes_observed`, `no_process_evidence`, or `unavailable`. The `game_running_confirmed` flag is **always false**: an associated Steam helper or wine process does **not** independently prove the game's executable identity, prefix or session ownership. No PID is signalled, launched, stopped, or changed. The AIO report omits PID/process-name details.
- The GTK Overview and Library have **Check Steam session (read-only)**, available without the game-launch opt-in flag. Results appear in Activity. It only observes; it never enables a trainer.

Validation:

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test11-aio-report.sh
# Optional UI check while the Steam game is running:
bash scripts/run-pc2-source-frontend.sh
```

The report is saved at `build/pc2-source/pc2-test11-aio-report.txt`. AIO PASS confirms the scanner/API contracts only; for game-specific process association, the selected game must be running while inspection occurs. The first real session-observation field test is still pending.

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
