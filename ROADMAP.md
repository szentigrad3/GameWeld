# Roadmap

## 0.7.0 — Stable

Trainer Library, session-aware Steam/Heroic/Lutris launch paths, FLiNG publisher discovery, version-label comparisons, read-only preflight, signed-catalog format, checksum-pinned staging and rollback. Field-tested against an existing library; no provider-authenticated automatic download feed is bundled.

## 0.8.0 — Download source integration (in development)

- **Dev 1:** inspect exact first-party FLiNG file links without downloading or installing files.
- Distinguish first-party page links from authenticated package releases.
- Provider-specific support for verifiable metadata and download workflows where supported.
- Approved and integrity-checked acquisition, with staging and rollback.
- Reduce reliance on legacy AppImage bases during builds.

## 0.9.0 — Update automation

- Scheduled discovery, version checks and manager-application monitoring.
- Unified review queue with explicit *candidate*, *verified* and *installed* states.
- Background preparation only when a supported provider offers sufficiently trustworthy release data.

## 1.0.0 — General availability

- Self-contained, reproducible Linux builds; stable CI/CD.
- Documentation, issue triage, application accessibility and localization readiness.
- Security, install/rollback and compatibility test gates across representative launchers.

Roadmap targets are not commitments to features unsupported by providers or restricted by licensing.
