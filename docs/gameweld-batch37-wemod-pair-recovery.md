# Batch37 — exact ASAR mismatch confirmed; guarded full-install recovery option

**31 October 2026 · Development-only · PR #18 remains draft**

## Actual user-supplied Batch36 ASAR audit

The user provided `gameweld-b36-asar-audit.json`, produced on CachyOS with the existing read-only scanner. `finding=mismatched_installed_exe_asar_pair`. All three candidate WeMod.exe files have exact SHA-256 `2598ca2fba0f24b9f2e955d8dd1a2644be04b648f350adc92e7c266182412bfd` and the same embedded ASAR header SHA-256 `279243030461986759df5d398d994cb2d511530001e716857663e82f732854e5`.

- Candidate 1 (selected GameWeld `~/.local/share/gameweld/deckcheatz/wemod_data/wemod_bin/WeMod.exe`): observed adjacent header `3d0a49d8c45ff06b1421ecd135f8ab0b03a3205fec3072f2772f424f55118b4e`, **mismatch**. `log_hashes_match_pair=true`; this exactly recreates the previous real Electron integrity crash.
- Candidate 2 (`~/.local/share/gameweld/wemod-compat/11.6.0/WeMod.exe`): observed adjacent header matches embedded `279243...`, **pair_integrity_match**.
- Candidate 3 (`.../11.6.0-unverified-20261029-160512/WeMod.exe`): also internally matching, but its directory is explicitly labelled unverified and is NOT selected for recovery.

**No publisher authenticity has been established for candidate 2 or 3.** Matching Electron EXE/ASAR resource hashes demonstrate internal consistency, not a trusted original official installer. Do not repair by simply rewriting the Electron embedded hash or disabling the integrity fuse.

## Batch37 full source package

`GameWeld-DeckCheatz-Batch37-Complete-Source-DEV.zip`: 373991 bytes, 166 entries, SHA-256 `c9c981322dd6d3df1aa3ae29b4b2772e4e12085862aa3263934609f1381c3435`. This is provided in the user conversation and is **not** pushed as executable source to the GitHub PR; the user's prior uncommitted MIT checkout changes remain untouched.

New MIT `gameweld-wand-v2-pair-recovery.py` and wrapper `run-wemod-pair-recovery.sh`:

1. **Read-only default**: revalidates candidate 2 complete matched pair and selected candidate 1 exact previously observed hash mismatch. Refuses changed EXE/ASAR, unexpected installation or unsafe directory layout. Calculates bounded full-tree source manifest; no files modified.
2. **Optional explicit `--apply` only after TWO clear acknowledgments** that the candidate 2 source has not been independently publisher-verified and that WeMod has been closed. Validates again; stages complete candidate 2 installation in a sibling directory; hashes every file and compares staged vs source; requires matching staged Electron integrity and unchanged mismatched target; retains original folder as a unique backup, promotes staged tree; attempts rollback on promotion/post-check failure.
3. No WeMod/Wine/Steam processes are started or signalled. No Steam game or Wine prefix, game launch options, trainer queue or Electron integrity configuration is modified. No automatic source downloads or file mixing across versions.
4. Backup is retained, never auto-deleted. Match is NOT proof of WeMod GUI, login, game detection, trainer attachment or real cleanup.

**Tests:** 665/665 Python unit tests passed in authoring source and 665/665 again from a clean extraction, including 12 new Batch37 tests. Python syntax/Bash syntax and ZIP CRC passed; Rust unchanged and not rebuilt. No filesystem repair or actual WeMod relaunch has been run on user's CachyOS machine.

## Next user workflow

Extract the full ZIP in `~/Downloads`, enter `deckcheatz-batch37-full-integration`, run `bash run-all-tests.sh` then `bash run-wemod-pair-recovery.sh` with **no flags**. Only after personally trusting the local candidate 2 complete distribution and closing WeMod, optionally run `bash run-wemod-pair-recovery.sh --apply --acknowledge-local-source-not-publisher-verified --acknowledge-wemod-closed`. Verify both EXE/ASAR pairs with the existing read-only `run-wemod-asar-audit.sh` before any future opt-in GUI pilot.

**Release gate:** production WeMod button disabled; PR stays draft; Linux↔Windows PID mapping, GUI and trainer attachment and all owned-descendant cleanup still unproven. No manual Steam Launch Options edits.