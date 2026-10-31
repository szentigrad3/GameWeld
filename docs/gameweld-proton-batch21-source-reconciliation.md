# GameWeld Batch 21 — Source-based DeckCheatz v2 integration review

**31 October 2026 · Development-only · PR #18 remains draft**

## Real source archive received

User provided the complete \`deckcheatz-rewrite-v2-gameweld-batch12_3-runtime-maps-triage.zip\` twice. Both ZIPs were byte-identical (SHA-256 \`23ce29329130a027011a0972b3fda7177791345cb57914df019781d39dbb62cd\`). The archive contains:

- MIT GameWeld v2 full Steam session driver, per-AppID configuration helper, strict runtime planner, Steam audit and diagnostic scripts.
- AGPL-3.0-only DeckCheatz Rust Windows monitor \`monitor-rust/src/main.rs\` and \`process_win.rs\`, using \`ObserveExisting\`, a read-only/query+synchronize Win32 game handle and independently owned trainer processes.
- AGPL-3.0-only Python \`upstream-overlay/src/wand_launcher/\` observer client and gRPC transport.
- The original 267 tests and packaging instructions.

The **actual upstream source exists now**. Previous "missing source" comments in this PR refer only to the GitHub checkout, which does not yet contain the complete newer source.

## Completed separately packaged Batch 21 full-source fixes

The complete updated development source artifact was created from the exact supplied ZIP and contains:

1. **Strict but layout-aware Proton runtime proof**. Accept \`/proc/PID/exe\` only from the selected Proton installation's allowlisted \`files/bin\`, \`files/lib/wine/x86_64-unix\`, \`files/lib64/wine/x86_64-unix\` and \`files/lib/wine/i386-unix\` paths. A Wine name or mapped module alone is never sufficient to authorize launching a monitor.
2. **Name-only Wine game-process corroboration**. The true Linux game PID's basename-only argv and truncated 15-character \`comm\` may be matched with an independent full-path Steam launcher argv when App ID, prefix and same-prefix wineserver are exact. Verify game PID start ticks before/after evidence collection. Refuse wrong App ID, wrong prefix, wrong Proton, missing wineserver and multiple actual game candidates.
3. **Prefer true Linux game process over Steam launch wrapper** when exactly one real process matches, while preserving ambiguous-process rejection.
4. **Repair cleanup-report interface**. The newer GameWeld bridge returns \`upstream_trainer_cleanup_reported=true\` but \`trainer_cleanup_verified=false\`. The older source driver falsely required independent cleanup \`true\`. The source driver now accepts the new *unverified* status, returns \`gameweld_v2_observed_session_finished_unverified\`, keeps Win32 PID, attachment and cleanup flags false and exits nonzero for the GTK success gate.
5. 22 additional Python regression tests (16 runtime + 6 bridge contract); 289 cumulative tests.

The Windows monitor's AGPL code, its dependencies, and the AGPL Python RPC client were preserved **unchanged** in Batch 21. No Rust cross-compilation or real-game monitor/WeMod attachment was possible in this authoring environment.

**Verification:** Source baseline: 267/267 Python tests passed. Updated full package: 289/289 tests passed, including after clean ZIP extraction. Python compilation and archive integrity checks passed. Cargo/Rust/Windows/Wine tests unavailable here and **not counted as passed**.

## State of the connected GitHub PR

PR #18 now contains successful GTK strict-status handling, guarded Linux game identity, single-instance locking, bounded monitor subprocess handling, read-only residual process audit, and CI for those modules. The experimental GTK button calls \`scripts/gameweld-wand-v2-driver.py\`. The first driver file authored in this PR is a **temporary prototype**, not the user-supplied full controller and not compatible with the older complete source's \`schema=1\` settings.

**Do not enable the GTK experimental WeMod action based on this prototype.** Stage the new MIT full driver/runtime-plan/config helper from Batch 21 before compiling or testing the experimental GUI.

### Safe source staging

The full development ZIP supplied in the conversation contains \`apply-gameweld-pr18-batch21.sh\`. It is dry-run by default and refuses Git main/dirty or unknown branches:

\`\`\`bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch21-Complete-Source-DEV.zip -d deckcheatz-batch21-full-integration
cd deckcheatz-batch21-full-integration
bash run-all-tests.sh
bash apply-gameweld-pr18-batch21.sh /mnt/other/github/GameWeld-PR18-test
bash apply-gameweld-pr18-batch21.sh /mnt/other/github/GameWeld-PR18-test --apply
\`\`\`

The third/fourth commands work only after the separately prepared PR #18 test checkout has been updated and is clean. The staging script copies **only three MIT files** into \`GameWeld-PR18-test/scripts/\`: \`gameweld-wand-v2-driver.py\`, \`gameweld-wand-v2-runtime-plan.py\`, and \`gameweld-wand-v2-configure.py\`. It preserves newer PR versions of \`session.py\`, \`live-context.py\`, \`live-anchor.py\`, \`bounded-monitor.py\`, \`residue-audit.py\`, and the CI workflow.

Do not copy \`monitor-rust/\` or \`upstream-overlay/\` into the MIT GameWeld repository; develop those independently under their AGPL-3.0-only terms. Staging changes only the local PR worktree; it does **not** push to GitHub or touch Steam.

## Outstanding release blockers

1. Compile Rust Windows monitor and disposable Wine \`ObserveExisting\` smoke test in a CachyOS environment. The included monitor builds a protected Win32 read-only process handle; this has not been validated against the user's actual game session.
2. Confirm exact currently selected Proton Wine loader, wineserver and Steam launch session. On incomplete evidence block, do not guess a runtime from module maps.
3. Demonstrate WeMod GUI/login plus actual trainer functionality in Dying Light, not simply process spawn or observer events.
4. Independently prove trainer-owned PID/birth-time cleanup on game exit and crash without signalling Steam/game/wineserver or unrelated processes.
5. Complete native GTK build + end-to-end testing; keep the PR draft and the experimental GUI toggle off by default. No manual editing of Steam Launch Options.

**The corrected code is in the supplied Batch 21 development ZIP, but the three complete MIT replacement files have not yet been pushed to PR #18.** This distinction matters: CI on PR #18 does not test the complete updated Batch 21 source until staged and committed.