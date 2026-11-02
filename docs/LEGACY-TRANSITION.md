# Legacy transition register — do not delete history

GameWeld's public GitHub repository began with a GTK3/AppImage trainer manager (0.7.0 stable narrative and 0.8.0 Dev 1 source) and accumulated security, Steam bridge and DeckCheatz experiments. The active plan is now a GTK4 desktop shell built around independent, verified Native Lab functionality. This register preserves previous work for deliberate disposition.

## Historical issues retained for triage

| Issue | Historical topic | Initial migration disposition |
|---|---|---|
| [#4](../issues/4) | Publish 0.7.0 stable AppImage | Legacy release track; do not equate it with the new app |
| [#5](../issues/5) | Third-party redistribution and licensing | Carry forward the license-review requirement |
| [#6](../issues/6) | Source-complete reproducible AppImage | Carry forward the build/provenance requirement |
| [#7](../issues/7) | Publisher metadata and approved downloads | Defer until a trusted provider workflow exists |

## Historical open PRs retained for triage

| PR | Initial disposition |
|---|---|
| [#13](../pull/13) | Historical WeMod release-discovery workflow; do not auto-port |
| [#14](../pull/14) | Review state isolation/security before reuse |
| [#15](../pull/15) | Review unsafe CMD and Wine profile hardening before reuse |
| [#16](../pull/16) | Historical Steam bridge registration; review compatibility |
| [#17](../pull/17) | DeckCheatz v2 preflight; compare with current Native Lab |
| [#18](../pull/18) | Batch43 fixes and live Wine limitations; preserve test evidence |

No issue or PR has been closed merely by adding this document. Keeping them open does not mean they are approved for the new app.

## Proposed cleanup workflow

1. Preserve `main` and branch history. This transition branch is the proposed new direction.
2. Import source-complete Batch78 app files with a documented mapping from the independently developed Native Lab tree. Do **not** copy commercial executables, private logs, game files or unreviewed third-party assets.
3. Validate license and security-sensitive legacy pieces one by one; port tests, not assumptions.
4. Once the new app builds, split future work into `app/`, `core/`, `sidecar/`, `tests/` and packaging (final names may differ).
5. Triage each old issue and PR individually. Close or archive only after review, with explanation and references to retained commits.
6. Retire old documentation only when its replacement is merged and the new build path is verified.

## Do not merge blindly

The historical README claimed daily-use 0.7.0 and AppImage packaging requiring an existing 0.7.0 binary. That build path is not the new source-built GTK4 app. Neither codebase should overwrite the other without an explicit migration and validation step.
