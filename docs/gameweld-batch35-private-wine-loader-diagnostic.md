# GameWeld Batch35 — read-only inspection found no persistent WeMod; private loader diagnostic prepared

**31 October 2026 · Dying Light: The Beast, Steam AppID 3008130 · development only · draft PR #18**

## User's actual Batch34 result

The user executed `bash run-wemod-gui-pilot.sh --inspect-existing` with the game and selected wineserver still running. It returned `state=wemod_no_existing_candidate_visible`, **three samples over two seconds**, `same_prefix_candidate_count_last=0`, `same_prefix_stable_candidate_count=0`, `same_prefix_stable_candidate_identities=[]`, `unattributed_candidate_peak=0`, `wine_loader_process_started=false`. Linux game PID 185951 and start ticks 12945298, wineserver PID 185869 and start ticks 12945222 stayed correlated. Steam Launch Options untouched, no game, WeMod or trainer launched.

**Precise conclusion:** no WeMod process candidate was visible in that bounded read-only sample window. This is NOT proof of crash, full descendant cleanup, working GUI, or trainer functionality.

## Prior actual real-launch evidence

Batch32's explicitly opted-in real WeMod pilot started its directly owned Proton Wine loader and invoked the configured WeMod.exe. The direct Wine loader exited with code **3**, with one same-prefix WeMod process candidate in one observation and none in the later Batch34 window. Wine produced **297 bytes of output**, but the allowlisted classifier yielded `loader_diagnostic_categories=[]`; the raw bytes were not persisted and cannot be recovered from the earlier JSON. Do NOT invent a root cause. The new source exists to make the NEXT explicitly chosen retry diagnosable.

## Batch35 complete source package — separate from GitHub PR code

`GameWeld-DeckCheatz-Batch35-Complete-Source-DEV.zip`, **356114 bytes**, **157 entries**, SHA256 `e5d9abaf08f1f792563c3030095932ca425c9c6262c1b221945449c97a1104d1`.

Changes are strictly MIT-only `gameweld-wand-v2-wemod-pilot.py`, its shell wrapper, regression tests, README and guarded staging. AGPL Windows observer is unchanged, separate and not moved into MIT GameWeld.

New `--launch-with-private-log --accept-unverified-cross-namespace-mapping --accept-private-loader-logging` requires **two explicit acknowledgments**. Before any real executable is started it retains original game Linux PID/birth, actual selected Proton/wineserver provenance, exact WeMod PE identity, independent sampled Win32 game PID/FILETIME and fully trainer-disabled authenticated RPC gate. The pilot launches only configured WeMod.exe; no trainer queue, game launch or Steam config changes.

On explicit opt-in, it privately saves up to **64 KiB of raw STDOUT/STDERR from the directly owned Wine loader** to one random, exclusively created **mode 0600** file under `~/Downloads`. Nothing is uploaded. This raw file **may include private paths, credentials, tokens, email addresses, account information or sensitive arguments**; the user must review and redact it before sharing. JSON emits only the randomized basename, byte count, truncation/error and existing allowlisted categories, never raw output. Normal launch, `--check`, and `--inspect-existing` write **no raw diagnostic log**. The pilot still signals only its **directly owned Linux loader through a held pidfd**, not Windows descendants, Steam game or wineserver; full WeMod process ownership/cleanup remains unverified.

**638/638 Python tests passed twice**, including **19 new Batch35 tests**; second run from clean ZIP extraction. Python and shell syntax and ZIP CRC passed. Rust tests not run in this environment; existing Rust source unchanged. Live Batch35 WeMod retry has NOT been performed. Keep the PR draft and production trainer disabled.

## CachyOS instructions

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch35-Complete-Source-DEV.zip
cd deckcheatz-batch35-full-integration
bash run-all-tests.sh
# Only for user-approved REAL launch pilot; run Dying Light normally via Steam, preferably offline:
bash run-rpc-identity-only.sh --prepare-venv
bash run-rpc-identity-only.sh --build
bash run-rpc-identity-only.sh --provenance-check
bash run-wemod-gui-pilot.sh --inspect-existing
bash run-wemod-gui-pilot.sh --check
# User explicitly opts into WeMod.exe launch AND raw private diagnostic log:
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --launch-with-private-log --accept-unverified-cross-namespace-mapping --accept-private-loader-logging 2>&1 | tee "$HOME/Downloads/gameweld-b35-live-wemod-diagnostic.json"'
```

User should inspect the local log privately via the JSON `private_loader_log_filename` in Downloads, redact sensitive data BEFORE providing any excerpts, and report visible GUI/login/game-detection separately. Even if code 3 recurs, a real error must be evidenced from that private output, not guessed.

An optional dry-run-first `apply-gameweld-pr18-batch35.sh` safely stages **only the new MIT pilot** into the user's existing local PR checkout, provided it matches an exact Batch31–34 hash. No Git commit, push or user worktree overwrite. The full source remains in conversation ZIP; this GitHub document is NOT a claim code was pushed.

## Remaining release gates

Independent Linux↔Win32 PID linkage is still unproven, production trainer-capable monitor not authorized, WeMod GUI/login/recognition/functional attachment not demonstrated, all WeMod descendants not owned/cleaned up. PR draft; no Steam Launch Options edits or blanket `pkill wine`.
