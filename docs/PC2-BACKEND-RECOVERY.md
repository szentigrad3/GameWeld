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

## Test 11 CachyOS field report and Test 12 targeted process evidence

Maintainer-uploaded `pc2-test11-aio-report.txt` (23 October 2026): **PASS**, 122 Steam installed manifests, GET session API PASS, **`no_process_evidence` with zero associations**, and all mutation endpoints locked (405 / 501). Test 11 sampled the **first valid Steam manifest in the discovered library**, not necessarily the selected or previously launched game. That result is **not proof AdVenture Capitalist stopped or failed to launch**. The maintainer has separately confirmed that AdVenture Capitalist launched successfully via explicit Steam game-only opt-in.

Test 12 corrects the target-selection blind spot without broadening process rights. It explicitly inspects the standard installed Steam game **App ID `346900`** (AdVenture Capitalist) using three short, read-only observations of the existing endpoint. It does not launch a game, change Steam settings, send signals, attach a trainer, or print PID/process-name/path information in the AIO report. Exact Steam app-ID environment matches are **associations only**, never verified executable identity, prefix ownership or trainer readiness. Absence of matches is not evidence the game is stopped.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
# Start AdVenture Capitalist from Steam or the guarded PC2 opt-in UI first.
# With the game still open, use another terminal:
bash scripts/pc2-test12-aio-report.sh 346900
```

Output: `build/pc2-source/pc2-test12-aio-report.txt`. An argument for another valid Steam app ID is supported. CI environments lacking the specified Steam manifest report the target check as **SKIPPED** while validating the API and fail-closed contract. Even with matches, session/trainer parity is still not validated; maintain the PC1 baseline.

## PC2 Test 12 live field result and Test 13 process-role evidence

Maintainer's uploaded Test 12 report (23 October 2026): **PASS**, installed Steam App ID **346900** (AdVenture Capitalist) found among 122 Steam manifests, and **4 / 4 / 4** exact same-user Steam app-ID process associations across three short read-only snapshots. No process scan truncation. The result supports consistent association while the game was running, **not** the identity of the main game executable or Wine/Proton session owner. User separately confirmed a successful live Steam game-only launch. PC1 remains the working trainer release.

Test 13 adds **GET `/api/steam-process-roles?appid=<installed Steam app ID>`** and `scripts/pc2-test13-aio-report.sh` to classify associated processes as `steam_helper`, `wine_runtime`, `windows_executable_candidate`, or `other_associated`. The backend reads only same-user `/proc` environment metadata, the short `comm` name, and the executable symlink's **basename**, never the executable bytes or its full path. Its report includes whether `STEAM_COMPAT_DATA_PATH` and `WINEPREFIX` keys are present, never their values or actual directories. The number of inspected processes and returned role observations remains bounded by the existing read-only Test 11 scanner.

**Role labels are heuristics only**, not a certified game executable, verified prefix owner, attach target, or evidence of successful trainer functionality. A Windows `.exe` process name alone is insufficient for trainer handoff. No launch, signal, Steam configuration write, Proton change or trainer action is performed. `game_executable_verified`, `prefix_ownership_verified` and `trainer_handoff_enabled` always remain false. POST and unknown app IDs fail closed.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
# Leave AdVenture Capitalist running before collecting process evidence:
bash scripts/pc2-test13-aio-report.sh 346900
```

The path-redacted report is saved to `build/pc2-source/pc2-test13-aio-report.txt`. It includes process role labels but omits PIDs and full paths. CI without the target game installed validates Go fixtures and report contracts; only a real running-game field report can characterize the actual four associated processes.

## Test 13 live field result and Test 14 native Linux executable evidence

The maintainer's Test 13 CachyOS report (23 October 2026) **passed** for AdVenture Capitalist, Steam App ID `346900`. Steam process environment matches remained **4 / 4 / 4** across three observations. The four associated processes were:

- `reaper` — `steam_helper` (`STEAM_COMPAT_DATA_PATH` key present; `WINEPREFIX` absent)
- `srt-bwrap` — Steam container helper, classified `other_associated`
- `pv-adverb` — Steam runtime helper, classified `other_associated`
- `adventure-capit` — executable basename `adventure-capitalist.x86`, classified `other_associated`

**Key architecture finding:** this specific game appears to run as a **native Linux executable inside Steam's runtime**, not a Windows `.exe` through Wine/Proton. The presence of `STEAM_COMPAT_DATA_PATH` for an associated process does *not* imply that the game runs under Proton. The Test 13 process role labels were only name heuristics; game executable and session ownership were not verified. Do not assume a Proton prefix or attempt Windows trainer handoff.

Test 14 introduces **GET `/api/steam-native-executable?appid=<installed Steam app ID>`**, an additional read-only corroboration. For same-user, exact-app-ID-associated processes, it reads `/proc/PID/exe`'s symlink, resolves the installed game directory from Steam appmanifest, checks that the canonical executable path is *within* that directory, and reads only the first five bytes of the executable for the Linux ELF signature and ELF32/ELF64 class. A result of `native_elf_inside_install_directory` is **corroborating native process evidence**, not a publisher signature, trustworthy hash, proof of game identity in all cases, or trainer attach authorization. Steam runtime mount namespaces may prevent host-side path reconciliation; a path-unavailable/outside result alone is not proof the game isn't running.

This endpoint and its AIO report never return full paths, PIDs, Steam/Wine prefixes or executable contents. They never start/stop a process, modify Steam/Proton or enable trainer handoff. Both `game_executable_verified` and `trainer_handoff_enabled` remain **false**.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
# With AdVenture Capitalist already running:
bash scripts/pc2-test14-aio-report.sh 346900
```

Output: `build/pc2-source/pc2-test14-aio-report.txt`. The CI fixture tests exercise positive native ELF32/ELF64 evidence, escaped install-directory paths, non-ELF executables, incorrect app-ID associations and safety failures. Passing CI does not replace the first CachyOS field run. Continue using PC1 for normal trainer operations; PC2's Steam game-only launch is user opt-in.

## GameWeld PC2 — integrated WeMod Enhancer GUI patch/restore

At the maintainer's request, PC2 now integrates [e-gleba/wemod_enhancer](https://github.com/e-gleba/wemod_enhancer) **directly inside GameWeld's Settings page**, rather than requiring a separate WeMod Enhancer window or using the older Windows-only k1tbyte/Wand-Enhancer GUI. The **e-gleba code is upstream MIT-licensed**; GameWeld does not copy the entire project into this branch.

**How to use it on CachyOS:**

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/run-pc2-source-frontend.sh
```

In **Settings → WeMod Enhancer — Integrated Linux Patcher**, click **Detect**. By default, the helper detects `~/wemod-launcher/wemod_data/wemod_bin`, plus some standard fallback paths. The existing read-only Wand/WeMod scanner can also populate an unambiguous detected installation. If neither finds the installation, click **Choose Folder**, selecting the folder containing `WeMod.exe` and `resources/app.asar`. Close WeMod itself before patching.

Click **Patch WeMod**; a confirmation dialog describes exactly what will happen. This one action downloads the pinned upstream Linux release **v1.0.7** if needed, verifies GitHub's published **SHA256** digest against a project-pinned value, extracts its `bin/wemod_enhancer.py` and `bin/version.dll` to the user's **XDG data directory** (never to the game's Proton installation), then executes the upstream `python3 wemod_enhancer.py patch --install-dir <selected>` command. The upstream patcher modifies WeMod's ASAR, updates client-side subscription display, integrity and update behavior, installs a Windows DLL proxy and maintains an original-file backup. This is a modification of a third-party application that may cease working with future WeMod updates; it is **not** the same as acquiring a legitimate paid subscription.

**Restore Original** calls the upstream restore operation for that same selected WeMod folder; missing backups fail closed. **Install** downloads the helper separately, without touching WeMod. **Detect** is fully read-only. All operations use subprocess argument arrays, bounded output, and the GameWeld Activity log. No shell commands or game/Steam/Proton configuration writes are performed by GameWeld's adapter. The optional `GAMEWELD_WEMOD_ENHANCER_DIR` environment setting accepts an already-extracted upstream CLI under `bin/`, bypassing the managed download.

The upstream Linux release requires **Python 3.11+** and its packaged Windows `version.dll`. GameWeld does not yet integrate the game/WeMod session launch from this patcher: use the established Linux WeMod launcher for Windows games and a supported Wine/Proton environment. Native Linux games (including AdVenture Capitalist) do not automatically become compatible with Windows-only trainers.

Unit tests in `scripts/test_gameweld_wemod_enhancer.py` exercise these actions using **disposable mock WeMod files and a fake upstream patcher**; they never patch the developer's real WeMod. GitHub CI compiles PC2 GTK and runs those tests. Real field validation requires clicking Patch on a local WeMod installation and inspecting the Activity result. PC1 stable remains untouched.

## PC2 integrated WeMod Enhancer — single-panel cleanup and existing Wand installs

A 23 October 2026 CachyOS Settings screenshot exposed a confusing duplicate: the new **WeMod Enhancer — Integrated Linux Patcher** sat above the old **Wand / WeMod Patcher (experimental)**, which referred to the obsolete k1tbyte Windows WPF helper. The screenshot also showed **Multiple Wand/WeMod installs found** in the old scanner but **WeMod installation: NOT FOUND** in the new adapter.

Resolved on `feature/pc2-source-backend`:

- Removed the old patcher **panel and retired GUI handlers**, keeping only the integrated upstream e-gleba patch/restore workflow.
- Reused the established GameWeld read-only Wand/WeMod scanner in the integrated panel. It lists existing client installations in Steam, Heroic, Lutris and Wine prefixes. If multiple versions exist, the user **must select the correct app-version**; no arbitrary installation is patched. Manual folder choice remains supported.
- The upstream bridge recognizes `Wand.exe`, `WeMod.exe` or a discovered `app-N.N.N` Electron client directory with a real `resources/app.asar`. It does **not** confuse the `GE-Proton-Wand-SHA256` compatibility runtime with a standalone Wand/WeMod application.
- Clarified the distinction between **installing the Wand/WeMod client**, **installing a Wand-compatible Proton provider**, and **installing the e-gleba WeMod Enhancer patcher**. The PC1 UI/backend handled Wand/WeMod setup in earlier versions, and the previous PC1 release remains untouched. The source-only PC2 backend still intentionally returns HTTP 501 to install/setup requests and does not install or replace existing Proton tools. A missing optional `WAND-HYBRID.json` file is not reason to reinstall a working provider.

To inspect the updated GUI:

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/run-pc2-source-frontend.sh
```

Under **Settings → WeMod Enhancer — Patch / Restore**, select the desired client in **Existing Wand / WeMod client installations**, then use **Patch WeMod**. If no installation is recognized, choose the actual installed client version directory containing `resources/app.asar` (not the GE-Proton tool directory). Upstream Patch/Restore still requires confirmation and closes no processes; **close the Wand/WeMod client yourself** beforehand. CI fixture checks cover both Wand and WeMod forms and ambiguous discovery; a real local patch still needs field validation.

## PC2 — Test patched Wand for the selected game

Following the maintainer's successful GameWeld-integrated e-gleba WeMod Enhancer patch on a real **Wand app-12.55.0** installation, PC2 now exposes direct checks rather than expecting a successful patch command to imply in-game trainer compatibility.

**GUI:** Select the game you intend to play in **Overview** or **Library**. In Overview, click **Test Wand for Selected Game**, or in **Settings → WeMod Enhancer — Patch / Restore**, click **Verify Wand Patch + Game**. These checks are **read-only**. The bridge compares the active `resources/app.asar` to the preserved original `resources/app.asar.backup`, and compares the installed client `version.dll` SHA256 to the trusted, pinned upstream Enhancer DLL installed in GameWeld's per-user tools directory. A pass is **patch-file evidence**, not proof the client launched, the DLL loaded in Wine, the user's account obtained a subscription, the selected game's trainer exists, or that it attached correctly. No automatic patch or Proton repair occurs during checking.

For standard Steam games, PC2 also queries the existing read-only source-backend session endpoints to distinguish **native Linux ELF actually observed**, **Windows process-name association only**, or **runtime unknown**. It reports the selected app ID, installed-game directory, detected prefix match or mismatch when resolvable, and whether a Windows Wand trainer is ruled out for a native Linux executable. **AdVenture Capitalist, Steam 346900, was observed as a native Linux game; its native build is not a Windows Proton trainer target.** For any Windows game, no claim of ready in-game trainer support is made until client/game runtime handoff and functionality are verified.

For a separate client-only launch test, use **Settings → Launch Patched Wand (Smoke Test)**. Confirm Yes. This requires the selected Wand app to have patch files verified, an **existing scanned Wine prefix**, a local `Wand.exe` / `WeMod.exe`, and `wine` on PATH. It starts only that client via Wine in the selected prefix, supplying the upstream-required `WINEDLLOVERRIDES=version=n,b` for native-first DLL loading. The command does **not** start a game, run a trainer, share a Steam Proton prefix by assumption, write Steam launch options, install compatibility tools, or verify the runtime DLL was actually loaded. If the selected `app-N.N.N` folder lacks a directly launchable EXE, it fails closed and asks the user to start Wand via its existing launcher.

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/run-pc2-source-frontend.sh
```

The source adapter supports read-only CLI `verify --install-dir <selected client>` and `game-test --install-dir <selected client> --game-provider steam --appid <id> --game-name <name> ...`; the GUI supplies arguments from the selected installed game, so no manual command is necessary. `launch-test` requires `--confirm --wine-prefix <existing prefix>`. CI tests are fully disposable fixtures; a successful GitHub build does not establish a real-game Wand session. PC1 remains untouched.

## Astrometica screenshot: Test Wand selection reset fix

Maintainer's 23 October 2026 PC2 Overview screenshot showed **Astrometica (Steam App ID 2353250)** selected, but Activity reported `WeMod Enhancer [game-test] FAILED: Choose exactly one existing Wand/WeMod app-version folder`. The game's selection was correct; the earlier selected **Wand app-12.55.0** installation in the regular Wine prefix had not been retained after reopening GameWeld, and GameWeld's scanner reported multiple existing Wand/WeMod clients. The failure was **before any game-specific trainer readiness check**, not evidence that the game or patched Wand was broken.

Two non-mutating selection fixes:

- The separate upstream bridge's read-only `verify` and `game-test` commands may now automatically use an **unambiguously patched** client if multiple clients exist. It requires one and only one app-version with an original ASAR backup, an ASAR different from its backup, and an installed Enhancer `version.dll` byte-identical to the pinned upstream reference. It fails closed if zero/multiple clients meet the standard. Automatic inference is **never** applied to the modifying `patch` or `restore` commands.
- The GTK **existing Wand installation** picker persists an explicitly selected exact Wine-prefix/app-version path pair in `${XDG_CONFIG_HOME:-~/.config}/gameweld/wand-selected-client.tsv`. On subsequent startups, a fresh read-only scan restores the choice only if the same exact prefix and install folder still exist; it otherwise asks for another selection. This file contains local paths only, never login data, and is independent from PC1 compatibility settings. The existing Steam/Proton environment and Wand client files are unchanged.

To test: `git pull --ff-only`, start PC2 through `scripts/run-pc2-source-frontend.sh`, select Astrometica, click **Test Wand for Selected Game**. If multiple fully patched versions exist, go to Settings and explicitly select the desired Wand app; this explicit choice will be remembered. A clean game-test can attest to patch-file evidence and observed game runtime only. It does not yet validate a live Wand trainer attached to Astrometica. **PC2's old trainer launch controls remain disabled** and the Windows game launch is separately opt-in.

## Astrometica: Steam handoff requested but no game started (Test 15)

Maintainer's 23 October 2026 screenshot shows **Astrometica**, Steam App ID **2353250**, with the integrated Wand **app-12.55.0** ASAR backup, changed active ASAR and proxy DLL all passing the upstream patch-file check. The Steam installed directory was found, while the game runtime remained unknown because it had not started. The Activity panel logged **only** `PC2 Steam game-only handoff requested`. The maintainer confirmed **the game did not launch**.

This exposes a genuine source-PC2 observability bug: the GTK handler called `spawn_detached("steam","-applaunch",appid)` and **immediately logged a handoff request** without checking whether the Steam executable was found, the command failed, Steam was starting, or an associated game process appeared. The App ID is not the problem: Astrometica's official Steam app ID is 2353250.

**Test 15** replaces the fire-and-forget call with an asynchronous, checked, argument-only `gameweld-steam-handoff.py` helper. It preserves explicit `--enable-steam-game-launch` startup opt-in, a per-game Yes/No confirmation, the source backend's installed-app/URI validation, and fully blocked trainer/compatibility mutations. The helper looks up `steam` in the inherited PATH, invokes `steam -applaunch 2353250` (for the selected ID, not hard-coded), reads the command's exit status where available and samples only same-user Linux `/proc` for exact app-ID environment association. It reports **FAILED**, **STEAM_ASSOCIATION_OBSERVED**, or **UNCONFIRMED**. A successful Steam command exit **does not** certify game start. A process association does **not** authenticate the actual executable or trainer. If Steam stays open, the helper does not kill the live Steam command; it reports an unconfirmed result. Its bounded background worker logs results to Activity without freezing the GUI.

Reproduce and diagnose:

```bash
cd /mnt/other/github/GameWeld
git pull --ff-only
bash scripts/pc2-test15-aio-report.sh 2353250    # Safe: no real game launch
bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch
```

In Overview, select Astrometica and confirm the **Launch Steam game only (opt-in)** action. Activity now provides a status instead of a misleading unconditional handoff message. If the command is reported as unconfirmed, distinguish a GameWeld-only issue from a Steam/Proton or game problem by closing GameWeld and testing **`steam -applaunch 2353250`** in a terminal, keeping Steam compatibility settings unchanged. If it fails outside GameWeld too, inspect Steam's game status or Proton logs instead of assuming the Wand patch has damaged anything. A real successful Astrometica startup, Wand runtime DLL loading, or attached in-game trainer has **not** yet been confirmed. PC1 remains the stable release.

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


## PC2 Test 15 follow-up — distinguish Wand patch inspection from Steam startup

After the 23 October 2026 Astrometica report showed `WeMod Enhancer [game-test] OK` but no game launched, the GTK labels were corrected to remove an ambiguous promise. **Check Wand Patch (no game launch)** on Overview and **Verify Wand Patch + Game (no launch)** in Settings only inspect files and read-only runtime evidence; they do **not** start Steam, Astrometica, Wand or a trainer. The Activity log now explicitly says so when a patch check starts.

The actual launch action remains **Launch Steam game only (opt-in)**. Run the branch's source launcher with the explicit startup flag, select **Astrometica (Steam 2353250)**, click the game-only launch button, and answer Yes. Test 15's asynchronous Steam helper checks the command and same-user app-ID process evidence, then reports **FAILED**, **STEAM_ASSOCIATION_OBSERVED** or **UNCONFIRMED** in Activity. Run the patch check again once the game is actually open to inspect current runtime evidence. None of these statuses proves a WeMod trainer has attached.

```bash
cd /mnt/other/github/GameWeld
git switch feature/pc2-source-backend
git pull --ff-only
bash scripts/pc2-test15-aio-report.sh 2353250  # non-launching contract test
bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch
```

If Steam launch remains FAILED or UNCONFIRMED, test the same Steam app through its native CLI (`steam -applaunch 2353250`) outside GameWeld. If both routes fail, collect Steam/Proton startup diagnostics first; do not repatch WeMod or change the game's compatibility settings merely because the patch-file check passed.


## PC2 Test 16 — optional live Wand handoff for an already running Steam Windows game

The maintainer confirmed that Astrometica's startup crash came from an incorrect Steam command line on their system and was corrected. **Do not change the working Steam launch options** or repatch Wand just to test live integration.

Test 16 adds **Launch Wand in Running Steam Game (opt-in)** to the Overview and integrated WeMod Settings. This differs from Test 15's **Launch Steam game only** and Test 15's **Check Wand Patch (no game launch)**. The Test 16 button is a real *Wand client launch attempt*, not a read-only inspection or a complete trainer attachment implementation.

After per-action Yes confirmation, the helper:

- requires one explicitly selected existing Wand client app-version folder and matching verified patch files, including the ASAR backup and pinned DLL proxy
- requires a valid installed standard Steam game ID, an existing game installation directory, and a same-user **live Windows .exe process candidate** with exact Steam app-ID environment association
- requires exactly one live existing Steam Proton prefix and Proton executable, recovered from that running session's \`STEAM_COMPAT_DATA_PATH\` and \`STEAM_COMPAT_TOOL_PATHS\`; a conflicting/missing runtime **blocks** the handoff
- starts the selected client EXE through the observed live Proton's \`runinprefix\` with \`WINEDLLOVERRIDES=version=n,b\`, passing the active Steam compatibility environment into that child **only**
- never changes Steam launch options, installs/repairs Proton, changes another Wand installation, or silently launches a game

This is an experimental same-prefix process launch. It **may change state inside the game's existing Proton/Wine prefix** as any Windows application startup can. It does not certify a visible Wand window, successful DLL load, WeMod login, presence of an Astrometica trainer, or successful in-game attachment. The frontend logs the separate command result. A Windows \`.exe\` process role is heuristic evidence, not a verified signed process identity. No multiplayer/anti-cheat bypass is attempted.

Test:

\`\`\`bash
cd /mnt/other/github/GameWeld
git switch feature/pc2-source-backend
git pull --ff-only
bash scripts/pc2-test16-aio-report.sh    # runs only disposable fake Steam/Proton/Wand fixtures
bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch
\`\`\`

In Settings, pick the existing patched **Wand app-12.55.0** installation. Launch **Astrometica** normally in Steam, leave its game process running, then in GameWeld select Astrometica and click **Launch Wand in Running Steam Game (opt-in)** and confirm Yes. Inspect Activity for **Live Wand Proton runinprefix request: SENT** or a specific fail-closed reason. A missing direct Wand.exe in the chosen app-version, missing live Proton path or only Steam helpers is an explicit block, not evidence the trainer is broken. Report: \`build/pc2-source/pc2-test16-aio-report.txt\`.

This is not yet complete trainer functionality; the first real CachyOS field result must establish whether the client opens and whether its trainer can interact with the running game.

### Test 16 follow-up — three detected Wand clients with no live launch

Maintainer Activity on 24 October 2026 reported **three installations across 157 Wine prefixes**, then `WeMod Enhancer [live-launch] FAILED: No unique Wand/WeMod client selected`. The failure happened **before** any live Proton handoff. Test 16's `game-test` could already identify the single patched app-12.55.0 by its original ASAR backup, changed active ASAR and pinned `version.dll` match, but the new `live-launch` action retained the older strict single-install guard.

Corrected on the PC2 source branch: an explicitly confirmed `live-launch` may reuse `resolve_read_only_client`'s **exactly one verified patched client** decision. Multiple patched clients still fail closed; the user must choose the exact app-version in Settings. Explicit `--install-dir` choices are honored, including deliberate blocking if the chosen client is unpatched. Patch/Restore actions still **never** auto-pick among multiple installations. The GTK Activity message also now differentiates real `live-launch` attempts from read-only `game-test`. Fixture regression checks ensure the three-client case works without starting a real game, Wine, Proton or Wand.

Re-run `bash scripts/pc2-test16-aio-report.sh`, start the source GUI with `--enable-steam-game-launch`, and with Astrometica already open click **Launch Wand in Running Steam Game (opt-in)**. The next message should either identify the selected uniquely patched client, then show a precise live Proton or EXE issue, or record `Live Wand Proton runinprefix request: SENT`. A successful request still does not demonstrate visible Wand, actual DLL loading or trainer attachment. Do **not** alter the previously corrected Steam launch command line.


## PC2 Test 17 — blank Wand window after live Proton handoff

On 24 October 2026 the maintainer tested Astrometica (Steam 2353250) and uniquely patched Wand app-12.55.0. The original live launch reported Proton runinprefix request SENT and a top-level Wand window appeared, but its Electron contents were entirely white. The handoff does not demonstrate initialized UI or functional trainer attachment.

Test 17 adds **Retry Wand (GPU Off, opt-in)** to Overview and integrated Settings. Close the existing white Wand window normally before retrying and leave the selected game running. The per-action confirmation uses the exact validated live Proton executable and game prefix; only the child Wand invocation gains `--disable-gpu`, `--disable-gpu-compositing` and `--enable-logging=stderr`. No Steam launch options, Proton installation, patches, registry, caches, Chromium sandbox or game settings are changed. A single-instance Wand process may intercept a retry, so avoid leaving an old instance active.

The helper saves Proton/Wand stdout and stderr in `${XDG_STATE_HOME:-$HOME/.local/state}/gameweld/wand-live-2353250.log`. This private file is created with mode 0600, truncated on a confirmed re-launch, and may contain local paths or account/session information. Review and redact such details before sharing. GameWeld's handoff state is never promoted to an assertion that Electron rendered successfully.

Commands:

```bash
cd /mnt/other/github/GameWeld
git switch feature/pc2-source-backend
git pull --ff-only
bash scripts/pc2-test17-aio-report.sh
bash scripts/run-pc2-source-frontend.sh --enable-steam-game-launch
# With Astrometica running and the blank Wand window closed:
# use GUI: Retry Wand (GPU Off, opt-in)
tail -n 100 "${XDG_STATE_HOME:-$HOME/.local/state}/gameweld/wand-live-2353250.log"
```

If the window remains white, diagnose logged Chromium renderer, GPU, dependency, authentication or ASAR errors; do not delete the existing compatibility prefix or Wand profile without explicit backup and separate troubleshooting. Test 17 AIO uses fake Proton and GTK compilation checks, not real rendering.
