# Desktop architecture and verification gates

## Source of truth

The new GTK4 desktop line is based on the independently developed Native Lab/Win64 IPC work (Batch44–77), with a Batch78 desktop shell in local development. **Those files have not been imported into this GitHub branch yet.** The historical `main` GTK3/AppImage source and its packaging path are separate. Do not silently mix them.

## Proposed source layout after migration

```text
app/                  GTK4 frontend, shell, views and navigation
gameweld_core/        game discovery, favourites, diagnostics, models
sidecar/              versioned Win64 fixture and explicitly gated sessions
tests/                headless core, IPC, security and integration tests
packaging/            native Linux packaging and release manifests
docs/                 architecture, migration decisions and evidence
legacy/               selectively retained old code, only after provenance review
```

This is a target layout, **not** a representation of files already present in the repository.

## Operating principles

1. Steam/Heroic/Lutris game discovery is read-only by default. Do not modify Steam launch options or Wine prefixes on browse.
2. A recorded Windows process argument or `/proc` mapping is not proof of a game process identity.
3. Treat separate system Wine, Steam Proton and the active game environment as distinct runtimes.
4. The only current executable approved for automated test launches is GameWeld's hash-pinned, original Win64 probe, with explicit user consent.
5. Never enable arbitrary executable selection, trainer auto-attachment, game-memory access or anti-cheat bypass as a side effect of desktop UI work.
6. Report observed helper disappearance separately from proof of complete Wine helper cleanup.
7. Keep paths, process identities, stderr and environment values out of shareable diagnostics unless intentionally reviewed/redacted.

## Verified milestones as of 2026-11-02

- Batch74: three real isolated system-Wine sessions, READY → STOP → STOPPED.
- Batch75: two real system-Wine runs, seven active prefix-marked helpers each; no marked helpers in post-exit scans, with incomplete visibility.
- Batch76: two real runs; each set of seven previously observed PID/start-token identities absent in two follow-up checks.
- Batch77: two real original-Win64 v2 runs successfully completed READY → PING/PONG → STATUS/OK → STOP/STOPPED.
- Batch78: GTK4 desktop shell is being built locally; **no GitHub merge or real GTK4 GUI validation is claimed here**.

These fixture results do not verify commercial trainers, actual game-memory attachment or Proton-sidecar integration.

## Release gates

- Source-complete, legally reviewed code and binary provenance.
- Python/IPC/security regression suites and clean extraction verified.
- GTK4 actual launch and interaction on CachyOS (headless core tests are not a substitute).
- Explicit release artifacts, checksums, packaging manifest and no private data.
- Read-only defaults and consent gates validated.
- Regression checks for old security-sensitive behaviour before incorporating legacy modules.
