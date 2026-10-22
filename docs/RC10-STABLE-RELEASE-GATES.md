# GameWeld 0.7.0 — RC10 field gates before stable

RC10's offline tests cannot establish success on real Steam, Heroic, Lutris or Proton sessions.

## Upgrade preservation

1. Copy existing GameWeld configuration and state directories as a precaution.
2. Launch RC10 on CachyOS, open Trainer Library → Advanced, choose **Run upgrade preflight and export report**.
3. Inspect `~/.local/state/gameweld/stability-preflight.md` (or `$XDG_STATE_HOME/gameweld/stability-preflight.md`). A report with READY_FOR_FIELD_TEST does **not** mean live launches have passed.
4. Confirm manual assignments, ignored entries, monitor budget and cached discovery survive without resetting.

## Session / launch gates

- Steam game with assigned standalone trainer: same game and trainer process/prefix, no unrelated game launch.
- Steam non-Steam shortcut with Proton: exact compatdata ownership and no premature trainer startup.
- Heroic managed trainer: stays inside configured Wine runner/prefix.
- Lutris classic Wine and UMU/GE-Proton: trainer joins the game's already-running session; incomplete runtime resolution fails closed.
- Select CONTROL Resonant → 7 Days to Die → CONTROL Resonant while update checks are in progress: old results must not re-enable staging.

## Update / backup gates

- No release source should claim authentication without independently verified signing-key provenance.
- Checksum catalog import remains explicit. No automatic assignment, execution or replacement is allowed.
- Inspect staged copies and check rollback with a disposable test trainer before trusting it with an active trainer.
- In all failure cases the previous manual game assignment remains unchanged.

## Release decision

**Do not label 0.7.0 stable** until the user confirms the applicable launch/session gates on actual installed games. Missing provider-authenticated feeds remain documented and are not a blocker to a stable *manual* trainer manager, but unattended downloads must not be advertised.
