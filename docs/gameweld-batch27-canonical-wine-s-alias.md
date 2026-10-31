# GameWeld / DeckCheatz — Batch 27: strict canonical Wine `S:` drive alias retry

**31 October 2026 · Development only · PR #18 remains draft**

## Ground truth: real Batch26 Windows lookup

User ran a query-only Rust Windows observer in the existing Dying Light: The Beast Steam AppID 3008130 Proton session. Linux-side Proton identity remained stable. The observer reported:

```json
{
  "state":"win32_probe_blocked",
  "reason":"win32_process_lookup_failed",
  "observer_reason":"win32_game_image_path_mismatch",
  "observed_target_image":"S:\\steamapps\\common\\Dying Light The Beast\\ph_ft\\work\\bin\\x64\\DyingLightGame_TheBeast_x64_rwdi.exe",
  "win32_basename_candidates":1,
  "win32_readable_image_count":1,
  "win32_image_query_failures":0,
  "win32_pid_verified":false
}
```

This establishes that Wine's Win32 process enumeration sees **one process named for the expected executable**, and its full Windows image is readable, but the actual Windows path is `S:` rather than the probe's expected `Z:` rooted Linux path. **The drive mapping itself has not been verified on the user's machine.**

## Complete Batch27 source package (separate from this PR)

The downloadable complete development ZIP `GameWeld-DeckCheatz-Batch27-Complete-Source-DEV.zip` is 231,685 bytes, 119 entries, SHA256 `417b329cdef33419c27413ccfec6922920b5fc80c806951c92e1aa9600cb133f`.

Modified **only MIT** `gameweld/scripts/gameweld-wand-v2-win32-probe.py`:

1. Preserve the original strict `Z:` Win32 full-image-path query.
2. On its failed query, accept the existing bounded Rust diagnostic **only if** there is one basename candidate, one readable target image, and no query failures.
3. Parse the full observed Windows path defensively; resolve `S:` (or another observed non-Z drive) via **that game's existing prefix** `pfx/dosdevices/s:` symlink; require the resolved path be the **same canonical Linux file** as the previously verified selected game EXE. Never use basename matching, similar file bytes/hashes, or a guessed drive root as success evidence.
4. Verify unchanged Linux PID/birth and unchanged DOS mapping around the retry, then do at most **one additional bounded 15-second/4096-byte query-only Rust observer call** with the reported Windows path.
5. Return only `win32_existing_game_handle_correlated` candidate evidence if the second strict Windows full-image-path query succeeds. Preserve `win32_pid_verified=false`, `exact_runtime_verified=false`, `monitor_session_authenticated=false`, `monitor_launch_authorized=false`, `trainer_attachment_verified=false` and `trainer_cleanup_verified=false`. **Never launch WeMod or a trainer.**
6. Block explicitly on unverified DOS alias, changed PID/birth, changed mapping, second query failure, invalid reports, duplicate processes, and timeouts.

A new guarded `apply-gameweld-pr18-batch27.sh` can optionally stage **only the MIT probe** into the user's existing local PR test checkout, dry-run first; it neither commits nor pushes source and leaves existing local edits alone. AGPL Rust monitor and Python RPC sources are unchanged from Batch26 and stay in separate source tree.

## Verification

**428/428 Python tests passed**, 31 new tests (24 for alias/probe; seven isolated Git staging tests, including a bundled Batch26 source fixture). Python compilation and Bash syntax checks passed. ZIP integrity check passed, and 428 tests passed from a clean extraction. No modified Rust code in this batch; nevertheless no new Windows build or real Win32 retry was run in this authoring environment.

## CachyOS instructions

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch27-Complete-Source-DEV.zip
cd deckcheatz-batch27-full-integration
bash run-all-tests.sh
# Read-only: verify whether S: targets the chosen Steam library
readlink -f '/mnt/games/Steam/steamapps/compatdata/3008130/pfx/dosdevices/s:'
# New extracted source does not include a Windows EXE:
bash run-win32-identity-probe.sh --build
```

With Dying Light already launched normally through Steam:

```bash
bash run-win32-identity-probe.sh --check
bash -o pipefail -c 'bash run-win32-identity-probe.sh --probe 2>&1 | tee "$HOME/Downloads/gameweld-b27-win32-probe.log"'
```

The explicit probe starts query-only Wine processes and **may cause incidental Wine prefix writes**. There is no manual Steam Launch Options change, game relaunch, trainer process or gRPC monitor session.

**Release remains blocked** until independently authenticated Linux/Win32 process mapping, same-Proton monitor session, real WeMod GUI and trainer attachment, and owned-process crash/exit cleanup have been proven. Do not infer these from a candidate PID. Keep PR #18 draft.
