# GameWeld Batch42 — live Steam container boundary and selected-path read-only audit

31 October 2026, Dying Light: The Beast Steam AppID 3008130. PR #18 stays **draft**, production WeMod trainer remains disabled.

## ACTUAL uploaded Batch41 JSON results

- `gameweld-b41-running-identity.json` state `wemod_running_identity_samples_stable_no_wine_started`, 3 samples/2 seconds. Selected Linux game PID **47950** / birth **1040536** and wineserver PID **47868** / birth **1040464**. Stable **during this historical window only**, not presumed alive later.
- `gameweld-b41-container-parity.json` state `wemod_container_namespace_diagnostic_complete`. Game ↔ wineserver share mount and PID namespaces. Game ↔ GameWeld launcher **do not share mount namespace**; same PID namespace. Wineserver ↔ launcher differ in mount namespace. Steam Launch Options unchanged, Wine and trainers not launched by either diagnostic.
- **Meaning:** a real mount namespace difference exists. It is NOT proof of a failed shared Wineserver connection, Electron GPU malfunction, Windows↔Linux PID mapping, or unsafe prefix. The user's earlier Batch40 `launch_owned_loader_game_identity_recheck_unavailable` was observed only during the Wine/WeMod pilot (4 same-prefix candidates, repeated GPU error 43). Static stable pre-launch identity does not explain that live post-spawn recheck.

## Batch42 MIT-only development source

Full development ZIP `GameWeld-DeckCheatz-Batch42-Complete-Source-DEV.zip`, **186 entries, 418227 bytes**, SHA-256 `63cc3ccfb6bddc9522473bde5c28c00e8a5a3a8029d792ff298c841aaf466bd8`. Available to user as complete source artifact; **new source NOT pushed into their local or remote MIT repo**. AGPL Windows observer remains separately owned and unchanged.

Added:
- `gameweld/scripts/gameweld-wand-v2-container-paths.py`: read-only `stat` comparison of exact selected five configured filesystem objects (`wine_prefix`, `wemod_executable`, `selected_proton_launcher`, `game_executable`, `steam_root`) from host, Linux game and wineserver views through owned `/proc/PID/root`.
- `bash run-wemod-gui-pilot.sh --diagnose-container-path-visibility`: repeats complete Linux game PID+birth and selected wineserver PID+birth pre/post and repeats path audit twice. Refuses changed identity/visibility; reports only `same_object`, `different_object`, `not_visible`, `unreadable` for each named object and each process view. No mount inode numbers, paths, process env, usernames or raw exception messages returned.
- `tests/test_batch42_container_paths.py`: 13 focused regression tests, including no launch, no namespace entry, report redaction, PID reuse/visibility changes, host missing, read permission, path validation, and actual self /proc stat.

**No Wine/Windows RPC**, no Steam edits or Launch Options, no `nsenter`, no sudo, no Wine socket access, no process signalling, no trainer queue and no credential inspection. `unreadable` is a valid non-authoritative result; do not ask user to disable ptrace safeguards. Filesystem inode identity does NOT prove a Wine IPC socket is connectable, and overlay/bind mounts can create different identity for equivalent file content.

Focused 13/13 tests, ZIP CRC and clean extraction PASS. **Final verified:** working-tree full regression **784/784 tests PASS** (145.502s, exit 0), and complete clean extraction of the FINAL ZIP **784/784 PASS again** (94.245s, exit 0). Python compilation, Bash syntax and ZIP CRC passed on the clean extraction. Rust/Cargo unavailable and unbuilt; no live WeMod or CachyOS path probe executed here. Rust and live CachyOS test NOT performed here.

## Next user action — read-only, no second WeMod launch

```bash
cd ~/Downloads
unzip -oq GameWeld-DeckCheatz-Batch42-Complete-Source-DEV.zip
cd deckcheatz-batch42-full-integration
bash run-all-tests.sh
# Start Dying Light normally via Steam, no changes to Launch Options:
bash run-rpc-identity-only.sh --provenance-check
bash run-wemod-gui-pilot.sh --inspect-existing
bash -o pipefail -c 'bash run-wemod-gui-pilot.sh --diagnose-container-path-visibility 2>&1 | tee "$HOME/Downloads/gameweld-b42-container-path-visibility.json"'
```

Existing/unattributed WeMod candidates (if any) must still block any new real GUI pilot. The Batch42 checker works without launching or killing them. Keep PR draft; no real GUI, game recognition, trainer attachment or complete process cleanup are yet demonstrated.
