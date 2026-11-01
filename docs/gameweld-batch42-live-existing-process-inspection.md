# Batch42 live post-path-visibility WeMod inspection: NO candidates visible

2026-11-01 · GameWeld development / draft PR #18 · Dying Light: The Beast Steam AppID 3008130.

The user uploaded `gameweld-b42-existing-after-visibility.json` after the completed Batch42 filesystem-object comparison. The real CachyOS pilot reported:

- `state=wemod_no_existing_candidate_visible`
- `samples_completed=3`, `sampling_seconds=2`
- `same_prefix_candidate_count_last=0`, `same_prefix_stable_candidate_count=0`, `unattributed_candidate_peak=0`, `same_prefix_stable_candidate_identities=[]`
- Historical game Linux PID **821144**, birth ticks **8807375**; selected wineserver PID **821061**, birth ticks **8807300**.
- No Wine loader/WeMod/game/trainer launched by this inspection. No Steam configuration or Launch Options modifications. No GUI/game detection/Win32 PID mapping/trainer attachment or process cleanup verified.

The four same-prefix WeMod candidates observed earlier in the Batch40 GUI pilot were **not visible in this later finite scan**, but this is not proof of their cleanup, no future candidate, or that a new launch is automatically authorized. PID values changed since earlier Batch41 evidence and MUST be revalidated at every actual launch.

The existing Batch42 full source ZIP already provides `--provenance-check`, `--inspect-existing`, `--check`, `--diagnose-running-identity`, `--diagnose-launch-readiness`, and the three-acknowledgement `--gpu-fallback-with-private-log` 25-second bounded GUI pilot. It also contains Batch41 finer-grained `identity_check_subphase` and `identity_failure_code` reporting for the outstanding postspawn `owned_loader_game_identity_recheck` failure. No new ZIP/source patch is justified solely by this clean inspection.

**Next gated user choice:** With game already started via Steam, repeat provenance, existing-candidate scan, check, running identity and runtime readiness. Stop if any disagree or if a WeMod candidate appears. Only after successful checks and user's explicit opt-in run ONE experimental GUI-only pilot, capture its JSON and optionally user-reviewed owner-private loader log. GPU arguments are experimental, may not solve the Electron `error_code=43` and never prove a GUI, trainer attachment or descendant cleanup. A real pilot can write to the Wine prefix and leave child processes; do not broadly kill Wine, Steam or wineserver. Trainer-capable production integration remains disabled and GitHub PR remains DRAFT.

This file is a documentation-only GitHub update. The user's local GameWeld worktree, executable source, Steam settings and Wine prefix were not touched.