# Batch36 — actual WeMod startup blocker identified: Electron ASAR integrity mismatch

31 October 2026, Steam AppID 3008130, draft PR #18. Real user log (297 bytes):

```
[FATAL:asar_util.cc(144)] Integrity check failed for asar archive (279243030461986759df5d398d994cb2d511530001e716857663e82f732854e5 vs 3d0a49d8c45ff06b1421ecd135f8ab0b03a3205fec3072f2772f424f55118b4e)
[ERROR:crashpad_client_win.cc(868)] not connected
```

**Established:** the Windows Electron process performed an ASAR integrity check and terminated on a hash mismatch. This is a new actual application startup failure, independent of the prior confirmed Steam process discovery, existing wineserver correlation and authenticated *trainer-disabled* RPC. The Crashpad message follows the fatal error and is not separate root-cause proof.

**Not established:** whether the ASAR file is damaged, the WeMod.exe and ASAR are mismatched releases, the installation was altered by a compatibility workaround, or an official build was packaged incorrectly. Raw WeMod.exe/ASAR bytes from the user's CachyOS system have not been supplied. Exit code 3 is a symptom, not a known fix.

**Official technical reference:** Electron Windows applications can embed ASAR header SHA256 in a PE INTEGRITY / ELECTRONASAR resource. Runtime checks terminate when the adjacent archive's JSON-header digest does not match the embedded digest (https://www.electronjs.org/docs/latest/tutorial/asar-integrity). Electron Packager hashes the serialized JSON ASAR header string (https://github.com/electron/packager/blob/main/src/platform.ts).

## Batch36 full source ZIP separate from GitHub branch

New MIT `gameweld/scripts/gameweld-wand-v2-asar-audit.py` and wrapper `run-wemod-asar-audit.sh` perform **read-only local EXE/ASAR pair audit**. For each explicit candidate `--exe`, parse its Windows PE resource and compare embedded resources/app.asar hash with its adjacent ASAR Pickle JSON-header SHA256. Optional prior failure log pair comparison, but no raw logs or full local paths in JSON. Reject missing, malformed, ambiguous or symlink sources; no integrity rewrite, disablement, OS process launch, Steam edit, game or trainer signal, or Wine prefix modification.

An on-machine audit across the actual configured WeMod.exe and the two known alternative WeMod installations can distinguish **pair_integrity_mismatch** from **pair_integrity_match**. A matching pair is not proof of official publisher trust, working WeMod GUI, trainer attachment or cleanup. Preferred solution to a failed pair: complete publisher-trusted install with a matching EXE, ASAR, and unpacked assets. Never mix version files or patch integrity hashes to suppress this error.

Executed development tests: **653 Python unittests passed**, 15 new cases including synthetic PE/ASAR, corrupt archive, symlink, missing resource and privacy rules, shell and Python syntax, ZIP CRC. Clean-ZIP regression executed separately. Rust and Windows builds unnecessary: AGPL Windows observer unchanged from the user's live verified previous version.

Selected user paths from existing prior private configuration: `$HOME/.local/share/gameweld/deckcheatz/wemod_data/wemod_bin/WeMod.exe` plus `$HOME/.local/share/gameweld/wemod-compat/11.6.0/WeMod.exe` and `$HOME/.local/share/gameweld/wemod-compat/11.6.0-unverified-20261029-160512/WeMod.exe`. These are observed historical candidate locations; any missing path must be reported, not guessed.

## Action gate

User should unzip the new Batch36 source ZIP on CachyOS, run the read-only audit on the three known EXE paths and the existing 297-byte failure log, and return the generated JSON. No WeMod launch, game restart, manual Steam Launch Options change, Wine process killing or download is needed. Keep PR #18 draft and the trainer-capable production launch path disabled.