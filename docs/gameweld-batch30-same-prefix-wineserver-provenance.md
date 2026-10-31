# GameWeld Batch30 — same-prefix wineserver provenance and read-only launch gate

**31 October 2026 · development only · PR #18 stays draft**

## Real baseline verified by user

Batch29 **actually passed on the user's CachyOS** for Dying Light: The Beast Steam AppID 3008130:
- `identity_only_rpc_preflight_ready_not_executed` with no monitor launched.
- `win32_identity_only_rpc_lifecycle_correlated`: authenticated Hello observed, unauthenticated Hello rejected, trainer queue Execute and Finished denied at the Windows Rust server, owned monitor exited.
- Live Linux candidate PID `185951` and process birth ticks `12945298`; Win32 observed PID `312` and creation FILETIME `134378829461334430`, stable over repeated held-HANDLE identity checks.
- No game or WeMod trainer launched; Steam Launch Options/settings unchanged.

**This does not prove independent Linux↔Windows PID mapping, production monitor authorization, functional WeMod or real trainer cleanup.**

## Batch30 source deliverable, distinct from GitHub PR code

The user-facing full source artifact is `GameWeld-DeckCheatz-Batch30-Complete-Source-DEV.zip` (276154 bytes, 135 entries; SHA256 `a708db2ea2929b41b417d0ed1d3963ea88eec0849afd4f1b9bc03f2cabebefaf`). The full source is packaged in the conversation; **not auto-committed/staged into this GitHub branch**, since the user's local PR checkout has older uncommitted MIT source updates and an AGPL Rust observer must stay separate from MIT GameWeld.

New MIT-only changes:
- `gameweld-wand-v2-server-provenance.py`: read-only Linux /proc provenance snapshot. Require one same-UID `wineserver` with selected Steam AppID, canonical exact `WINEPREFIX` + `STEAM_COMPAT_DATA_PATH`, exact expected Proton wineserver kernel executable symlink and Linux start-time birth token, with reacquisition to detect PID reuse. Reject missing, wrong, ambiguous, unreadable and switched servers.
- `gameweld-wand-v2-auth-only-aio.py`: new read-only `--provenance-check`; existing explicit identity-only `--exercise` now pins same-prefix wineserver before/after auth-only RPC, preserving Windows PID/creation time and Linux PID/birth validation. On success reports `same_prefix_wineserver_stable=true`. All trainer and production authorization flags stay false; user game's Steam process is never signalled.
- `run-rpc-identity-only.sh` exposes `--provenance-check`.
- `apply-gameweld-pr18-batch30.sh` is a guarded *dry-run-first* local stage of exactly those two MIT helpers. Accepts a known Batch29 helper SHA or identical Batch30 source; rejects user edits, symlinks, unrelated local Git changes and wrong branch. No commit/push; no AGPL files mixed into MIT repo.
- 32 new synthetic regression tests, including a full integration simulation of a stable authenticated RPC and a blocked changed-wineserver case.

**Executed here**: **507/507 Python tests passed**, also 507/507 from a clean ZIP extraction; Python compilation, shell syntax and archive CRC passed. Invalid-config + unknown mode both fail closed. **Cargo/Rust build unavailable here, no live Batch30 wineserver test executed**. Rust source is unchanged from user-tested Batch29.

## CachyOS acceptance commands

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch30-Complete-Source-DEV.zip
cd deckcheatz-batch30-full-integration
bash run-all-tests.sh
bash run-rpc-identity-only.sh --prepare-venv
bash run-rpc-identity-only.sh --build

# With Dying Light already running normally via Steam:
bash run-rpc-identity-only.sh --check
bash run-rpc-identity-only.sh --provenance-check
bash -o pipefail -c 'bash run-rpc-identity-only.sh --exercise 2>&1 | tee "$HOME/Downloads/gameweld-b30-rpc-provenance.log"'
```

The new read-only target is `same_prefix_wineserver_candidate_stable`. The explicit auth-only RPC target remains `win32_identity_only_rpc_lifecycle_correlated` with `same_prefix_wineserver_stable=true` and wineserver PID and kernel birth tick. If blocked because the live Proton environment does not export enough /proc evidence, **do not bypass by accepting a shared prefix name only**.

`--check` and `--provenance-check` perform read-only checks. `--exercise` spawns only the trainer-disabled test observer in existing Steam Wine prefix; Wine may make incidental bookkeeping writes. It never launches the game, WeMod or a trainer. No Steam Launch Options changes.

## Next gates before first WeMod launch

- Stronger independently supported Windows↔Linux process identity and Wine server connection binding: current results are candidate correlations, not cryptographic proof.
- Ownership-scoped termination/crash validation of actual monitor *and potential descendants*, not merely a single direct child exiting.
- Then explicit opt-in real WeMod GUI/login/attach test; verify functionality and cleanup without ever modifying Steam Launch Options. **Keep production toggle disabled; PR draft.**
