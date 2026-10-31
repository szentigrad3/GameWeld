# Batch37 live WeMod EXE/ASAR installation repair PASSED

31 October 2026. Dying Light: The Beast Steam AppID 3008130. PR #18 remains DRAFT and production trainer disabled.

## User-executed repair

Read-only recovery plan: state `wemod_pair_recovery_plan_ready`; source candidate 2 171 files / 382321163 bytes, pair_integrity_match, selected candidate 1 pair_integrity_mismatch, no modifications.

User then explicitly executed local recovery `--apply --acknowledge-local-source-not-publisher-verified --acknowledge-wemod-closed`.

Reported: state `wemod_pair_recovery_applied`; `repair_performed=true`; source candidate 2, 171 files and 382321163 bytes; selected pair integrity became `pair_integrity_match`; previous broken installation backed up under `wemod_bin.backup-b37-036e9491cf43d250`; `integrity_bypass_performed=false`, `game_prefix_modified=false`, `wine_started=false`, `steam_configuration_written=false`, `steam_launch_options_changed=false`, `trainer_launched=false`.

Independent post-repair read-only ASAR audit shows BOTH the newly selected installation and candidate 2 have the same EXE file SHA-256 `2598ca2fba0f24b9f2e955d8dd1a2644be04b648f350adc92e7c266182412bfd` and embedded expected and adjacent observed ASAR header SHA-256 `279243030461986759df5d398d994cb2d511530001e716857663e82f732854e5`. Both status `pair_integrity_match`. The previously fatal actual adjacent header `3d0a49d8...` is not the repaired pair.

### What is and is not proved

The exact file-pair integrity mismatch matching the earlier fatal Electron `asar_util.cc(144)` log has been corrected in the GameWeld-selected local WeMod installation, without disabling Electron integrity. This does not independently verify publisher authenticity of candidate 2, prove the next Electron startup will succeed, or prove GUI/login, game detection, real trainer attachment or cleanup. Do not claim WeMod is functional yet.

### Next accepted live gate: GUI only

The existing Batch37 full development source ZIP already includes `run-rpc-identity-only.sh`, `run-wemod-gui-pilot.sh` and the previously tested trainer-disabled RPC observer. From the user's already extracted `~/Downloads/deckcheatz-batch37-full-integration`, prepare the isolated venv and rebuild the Windows monitor if not present in this extracted tree. Start Dying Light normally via Steam (preferably offline/single player), then check `--provenance-check`, `--inspect-existing`, `--check`. If clean, explicitly authorize ONE bounded GUI-only attempt:

```bash
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --launch-with-private-log --accept-unverified-cross-namespace-mapping --accept-private-loader-logging 2>&1 | tee "$HOME/Downloads/gameweld-b37-post-repair-gui-pilot.json"'
```

The mode may write to the existing Wine prefix, produces a local private raw loader log (review/redact before sharing), and may leave WeMod child processes; no trainer queued or claimed. User must report actual GUI visibility separately; a successful launcher process observation is NOT proof of GUI. Never kill Steam/game/wineserver, change manual Steam Launch Options or merge the PR until real trainer test + cleanup independently succeed.

Note: the Batch37 runnable source is in the full ZIP and does not automatically update the remote MIT GitHub PR. This is a documentation-only GitHub commit.