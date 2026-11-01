# Batch42 live user acceptance: five configured paths visible as identical filesystem objects in both Steam process views

**2026-11-01 · AppID 3008130 · PR #18 stays draft · WeMod GUI / trainer still unverified.**

## Exact user-provided report

The user uploaded `gameweld-b42-container-path-visibility.json`. Its `state` is `wemod_container_path_visibility_diagnostic_complete`. **All 10 cross-view comparisons return `same_object`**.

| Selected configured object | Linux game view | Selected wineserver view |
| --- | --- | --- |
| `game_executable` | `same_object` | `same_object` |
| `selected_proton_launcher` | `same_object` | `same_object` |
| `steam_root` | `same_object` | `same_object` |
| `wemod_executable` | `same_object` | `same_object` |
| `wine_prefix` | `same_object` | `same_object` |

The read-only script returned `path_identity_is_not_wine_socket_proof=true`, `cross_namespace_launch_authorized=false`, `launch_authorized_by_diagnostic=false`, `wine_loader_process_started=false`, `trainer_launched=false`, `win32_pid_verified=false`, `gui_visible_verified=false` and no Steam configuration or Launch Options changes.

## Interpretation

Prior Batch41 `--diagnose-container-parity` proved the game and wineserver share a mount namespace, but the GameWeld host launcher uses a different mount namespace. The new Batch42 result **narrows** that: the five selected configured paths are reachable as the *same filesystem objects* from all tested process views. Therefore selected-path invisibility or mismatch of these five files is not supported as the explanation of the older failure.

**Do not equate filesystem-object equality with Windows Wine IPC socket connectivity, exact Linux↔Win32 PID correspondence, Electron graphics-process startup, GUI rendering or process cleanup.** No socket connection was attempted. The previously repaired 11.6.0 WeMod.exe/ASAR pairing stays intact.

The separate actual Batch40 GUI-only pilot had already started its directly owned Wine loader, submitted Electron GPU fallback arguments, observed **four** same-prefix WeMod candidates and blocked at `owned_loader_game_identity_recheck`; the private Wine output contained repeated GPU subprocess error 43. That live recheck failure is not explained by the later clean 2-second prelaunch identity or path checks. The four observed candidate processes are **historical sightings**, not verified alive, dead, owned, or cleaned. No user command should signal them without independent ownership verification.

## Next gate — do not need Batch43 solely for diagnostics

The Batch42 full-source ZIP ALREADY contains Batch41's specific postspawn identity subphase reporting and the conservative `--inspect-existing` mode. First with game launched normally through Steam, rerun **read-only**:

```bash
cd ~/Downloads/deckcheatz-batch42-full-integration
bash run-wemod-gui-pilot.sh --inspect-existing \
  | tee "$HOME/Downloads/gameweld-b42-existing-after-visibility.json"
```

If any same-prefix or unattributed WeMod process is reported, **do not launch another WeMod**, kill Wine or assume cleanup. Do not edit Steam Launch Options.

Only after a clean no-existing-candidate result and independently passing `--provenance-check`, `--check`, `--diagnose-running-identity` and `--diagnose-launch-readiness`, the user may separately authorize one existing Batch42 GUI-only pilot with the three required acknowledgements, if they wish. The next real failure should report `identity_check_subphase` and `identity_failure_code` rather than mask which validation failed. A GUI launch can write to the selected Wine prefix and leave descendants; real trainer remains disabled. **There is no verified need yet for any Steam container entry or a new runtime framework.**

All executable Batch42 source remains in the delivered development ZIP; documentation-only GitHub update. PR remains DRAFT, no trainer launch, no backend changes.
