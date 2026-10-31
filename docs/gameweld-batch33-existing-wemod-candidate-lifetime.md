# GameWeld Batch33 — inspect post-loader WeMod process before relaunching

31 October 2026 · Development only · draft PR #18

## ACTUAL user Batch32 GUI pilot observation

Read-only selected Steam/Proton/wineserver checks and authenticated trainer-disabled Windows RPC passed for Dying Light: The Beast Steam AppID 3008130. Real opt-in WeMod startup was requested. The direct Wine loader **exited with status 3**, resulting in `wemod_gui_pilot_launch_failed`, `reason=wine_loader_nonzero_exit`. Unlike Batch31, this time the pilot observed **one same-prefix WeMod candidate** and zero unattributed WeMod candidates. It captured **297 bytes** of Wine output, but `loader_diagnostic_categories=[]`. Batch32 deliberately discarded raw output rather than printing private paths; there is no evidence-backed root cause from that JSON. GUI visibility, login, game detection, actual trainer attachment and cleanup remain unverified.

**Important:** loader exit 3 can coexist with a child/secondary WeMod process. It is not by itself proof that the application GUI could not start. Conversely a single same-prefix process snapshot is not proof of a persistent healthy WeMod GUI, nor of process ownership.

## Batch33 complete source development ZIP (separate from remote GitHub source)

Conversation artifact `GameWeld-DeckCheatz-Batch33-Complete-Source-DEV.zip`: **323021 bytes**, **149 archive entries**, SHA256 `ded19201785b427f4e69ef07f433fd5d6345ba99bd870268fe73fdeea3b0879c`.

Adds MIT read-only mode `bash run-wemod-gui-pilot.sh --inspect-existing`. It is *not* a trainer or Wine launcher. It reads existing /proc metadata, obtains exact Linux PID/start-time tokens of candidate WeMod processes, correlates configured `WINEPREFIX` and Steam AppID from readable process environment, rejects zombies and re-used PID, and samples **three observations one second apart** while independently revalidating the selected Steam game and same-prefix wineserver PID/birth before/after each sample. Output is bounded to at most eight PID/birth candidate tuples; no raw cmdline, environment or private path is serialized. Ambiguous/unattributed processes are counted but not claimed as owned. No game, WeMod, wineserver or other process is signalled.

New explicit states: `wemod_existing_same_prefix_candidate_stable`, `wemod_existing_candidate_transient`, `wemod_existing_unattributed_candidate`, `wemod_no_existing_candidate_visible`; or `wemod_gui_pilot_blocked`. Even a persistent candidate does not verify GUI visibility, game detection, trainer attachment or cleanup.

Previous `--check` and explicit `--launch` behaviour is unchanged, including the nonzero Wine loader failure status and refusal to launch while existing candidates are visible. A SHA-guarded, dry-run-first local stage `apply-gameweld-pr18-batch33.sh` updates only the MIT WeMod pilot if it is missing or an exact known Batch31/32 file (otherwise blocks). AGPL Rust source stays separate; this GitHub commit contains only documentation, not the local source ZIP.

## Verification here

603/603 Python tests passed in source and 603/603 from a clean ZIP extraction (29 new regression tests), Python syntax, Bash syntax and ZIP CRC passed. **Rust native and Windows cross-build skipped** because Cargo unavailable; Rust was unchanged. No live Batch33 /proc inspection was performed against the user's CachyOS runtime.

## Exact next step for user (do not relaunch WeMod)

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch33-Complete-Source-DEV.zip
cd deckcheatz-batch33-full-integration
bash run-all-tests.sh
# Keep Dying Light running normally through Steam.
bash run-wemod-gui-pilot.sh --inspect-existing | tee "$HOME/Downloads/gameweld-b33-existing-wemod-inspection.json"
```

If the candidate is stable, manually inspect the desktop for an already-open WeMod window and close only using its own GUI as appropriate; do not launch another instance. If no candidate remains, this is **not** proof of complete cleanup—only absence during the bounded sampled window. Never run blanket `pkill wine`, `wineserver -k`, or change Steam Launch Options. Keep PR #18 draft and production integration disabled.