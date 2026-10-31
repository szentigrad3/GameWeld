# Batch34 — Fix blocked read-only WeMod process inspection

**31 October 2026 — Development only — GameWeld PR #18 stays draft**

## Actual user's Batch33 result

The user's real Dying Light: The Beast (Steam AppID 3008130) read-only `bash run-wemod-gui-pilot.sh --inspect-existing` reported:

```json
{"appid":3008130,"game_launched":false,"reason":"windows_probe_preflight_not_ready","state":"wemod_gui_pilot_blocked","steam_launch_options_changed":false,"trainer_attachment_verified":false}
```

This state means **the intended process scan never ran**. It cannot show whether the Batch32 same-prefix WeMod process candidate persists or disappeared.

## Confirmed code defect and change

Batch33's MIT `gameweld-wand-v2-wemod-pilot.py` called `probe.probe(appid,config,monitor,perform=False)` and `probe.verify_probe_binary(monitor)` **unconditionally** in `context_from_config`. The new source extraction defaulted to a Windows monitor binary under its *new* directory, despite inspection being Linux-only and the user's previous observer having been built in an earlier directory. The GUI pilot's standard `--check` and `--launch` legitimately require this observer gate; read-only `--inspect-existing` does not.

Batch34 limits the bypass strictly to `allow_existing_for_inspection=True`. **No real-launch security checks are relaxed.** The inspector continues to load private config, require the configured Steam install, game EXE, Proton and wineserver provenance, valid configured monitor and WeMod PE, then sample `/proc` candidate PIDs and birth ticks across three observations with exact AppID/WINEPREFIX attribution, zombie exclusion, process-reuse detection and game/wineserver identity revalidation. No Wine/WeMod/monitor/game processes are started or signalled. No Steam configuration or Launch Options are modified.

The historical Batch33 staging helper now pins its own original fixture; a new guarded `apply-gameweld-pr18-batch34.sh` stages **only** the MIT pilot, accepting only exact known Batch31/32/33 file hashes or an exact current Batch34 file. Dry-run first, refuses edited/unrelated files. AGPL Rust remains separate and unchanged; the user's local PR files were not modified.

## Verification boundary

- Batch34 source archive `GameWeld-DeckCheatz-Batch34-Complete-Source-DEV.zip` contains **153 entries**, ZIP CRC passed; SHA256 `ce89d54c08cb20fb90f50e21792e42bcb9d1b91247c6b9bb8b285deb5a703433`.
- **619/619 Python tests passed TWICE** (working source and a clean extraction of the final ZIP), 16 new tests including CLI-level no-Windows-observer, guarded normal preflight, identity checks, CLI candidate/no-candidate reporting and local SHA-pinned Git staging.
- Rust/Cargo unavailable here: Rust tests **SKIPPED**, not passed. **Live CachyOS inspection not yet run** as of this documentation.
- Full source ZIP is delivered in the user conversation, **not automatically pushed into the GitHub source branch**; only this documentation is committed. The user's local uncommitted GameWeld staging remains untouched.

## CachyOS next command — NO WeMod launch

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch34-Complete-Source-DEV.zip
cd deckcheatz-batch34-full-integration
bash run-all-tests.sh
# With Dying Light already open normally through Steam:
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --inspect-existing 2>&1 | tee "$HOME/Downloads/gameweld-b34-existing-wemod-inspection.json"'
```

No `--build`, `--prepare-venv`, `--probe` or `--launch` is needed for the read-only inspector. If it reports `wemod_existing_same_prefix_candidate_stable`, inspect the desktop for the actual WeMod window before another launch attempt. `wemod_no_existing_candidate_visible` means only that no candidate appeared during the bounded sample, not that cleanup is proven. Do not use blanket `pkill wine`, `wineserver -k` or change Steam Launch Options.

**Production release blocked:** GUI not yet observed, Wine loader exit 3 unexplained, real trainer functionality/attachment absent, Linux↔Win32 PID linkage and owned-descendant cleanup unproven.